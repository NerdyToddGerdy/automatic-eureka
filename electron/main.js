const { app, BrowserWindow, dialog, shell, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');
const Store = require('electron-store');
const OAuthHandler = require('./oauth-handler');

// Read port from config.json (fallback to 5000 if unreadable)
let appPort = 5000;
try {
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'config.json'), 'utf8'));
  appPort = config.port || 5000;
} catch (e) {
  console.log('Could not read config.json, using default port 5000');
}

// Handle EPIPE errors gracefully (occurs when writing to closed pipes)
process.stdout.on('error', (err) => {
  if (err.code === 'EPIPE') return;
  throw err;
});
process.stderr.on('error', (err) => {
  if (err.code === 'EPIPE') return;
  throw err;
});

let mainWindow;
let flaskProcess;
let oauthHandler;
let store;

// IPC handler for showing file in Finder/Explorer
ipcMain.handle('show-item-in-folder', async (event, filepath) => {
  try {
    // shell.showItemInFolder() reveals the file in Finder/Explorer
    shell.showItemInFolder(filepath);
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false  // Required for webUtils
    }
  });

  mainWindow.loadURL(`http://127.0.0.1:${appPort}`);

  // Open DevTools only in development or when explicitly requested
  if (process.env.NODE_ENV === 'development' || process.env.DEBUG_DEVTOOLS) {
    mainWindow.webContents.openDevTools();
  }
}

function startFlaskServer(tokens) {
  const pythonPath = 'python3';
  const scriptPath = path.join(__dirname, '..', 'app.py');

  // Pass OAuth tokens to Flask via environment variable
  const env = Object.assign({}, process.env);
  if (tokens) {
    env.GOOGLE_OAUTH_TOKENS = JSON.stringify(tokens);
  }

  flaskProcess = spawn(pythonPath, [scriptPath, '--port', appPort], {
    cwd: path.join(__dirname, '..'),
    env: env
  });

  flaskProcess.on('error', (error) => {
    dialog.showErrorBox('Flask Error', `Failed to start Flask server: ${error.message}`);
  });

  flaskProcess.on('exit', (code, signal) => {
    if (code !== 0 && code !== null) {
      dialog.showErrorBox('Flask Exited', `Flask server exited with code ${code}`);
    }
  });

  flaskProcess.stdout.on('data', (data) => {
    // Log Flask output (EPIPE errors handled at process level)
    console.log(`Flask: ${data}`);
  });

  flaskProcess.stderr.on('data', (data) => {
    // Log Flask errors (EPIPE errors handled at process level)
    console.error(`Flask Error: ${data}`);
  });
}

async function ensureAuthentication() {
  try {
    // Initialize store and OAuth handler
    store = new Store();
    oauthHandler = new OAuthHandler(store);

    // Try to load stored tokens
    const storedTokens = oauthHandler.loadStoredTokens();

    if (storedTokens && oauthHandler.hasValidTokens()) {
      console.log('Using stored authentication tokens');

      // Refresh if needed
      const tokens = await oauthHandler.getTokens();
      return oauthHandler.getTokensForPython();
    } else {
      console.log('No valid tokens found, starting authentication flow...');

      // Show dialog to inform user
      dialog.showMessageBoxSync({
        type: 'info',
        title: 'Google Drive Authentication',
        message: 'Image Vault needs to connect to your Google Drive',
        detail: 'Your browser will open to authenticate with Google. Please grant the requested permissions.',
        buttons: ['OK']
      });

      // Run OAuth flow
      await oauthHandler.authenticate();
      return oauthHandler.getTokensForPython();
    }
  } catch (error) {
    console.error('Authentication error:', error);

    // Show error dialog with option to skip
    const result = dialog.showMessageBoxSync({
      type: 'error',
      title: 'Authentication Failed',
      message: 'Failed to authenticate with Google Drive',
      detail: error.message + '\n\nYou can skip Google Drive and use the app without cloud sync.',
      buttons: ['Retry', 'Skip Google Drive', 'Exit']
    });

    if (result === 0) {
      // Retry
      return await ensureAuthentication();
    } else if (result === 1) {
      // Skip - return null to indicate no tokens
      console.log('Skipping Google Drive authentication');
      return null;
    } else {
      // Exit
      app.quit();
      return null;
    }
  }
}

// Poll Flask until it responds, up to maxAttempts * intervalMs ms
async function waitForFlask(port, maxAttempts = 30, intervalMs = 200) {
  for (let i = 0; i < maxAttempts; i++) {
    const alive = await new Promise((resolve) => {
      const req = http.get(`http://127.0.0.1:${port}/api/version`, (res) => {
        resolve(res.statusCode === 200);
      });
      req.on('error', () => resolve(false));
      req.setTimeout(500, () => { req.destroy(); resolve(false); });
    });
    if (alive) return true;
    await new Promise(r => setTimeout(r, intervalMs));
  }
  return false;
}

app.whenReady().then(async () => {
  // Google Drive disabled - run in local-only mode
  const tokens = null;
  startFlaskServer(tokens);

  const ready = await waitForFlask(appPort);
  if (ready) {
    createWindow();
  } else {
    dialog.showErrorBox('Startup Failed', 'Could not connect to the backend after 6 seconds.\nTry restarting the app.');
    app.quit();
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

let isQuitting = false;

app.on('before-quit', (event) => {
  if (flaskProcess && !flaskProcess.killed && !isQuitting) {
    event.preventDefault();
    isQuitting = true;

    // Give Flask up to 3s to exit cleanly before force-killing
    const forceKillTimer = setTimeout(() => {
      if (!flaskProcess.killed) {
        flaskProcess.kill('SIGKILL');
      }
      app.quit();
    }, 3000);

    flaskProcess.once('exit', () => {
      clearTimeout(forceKillTimer);
      app.quit();
    });

    flaskProcess.kill('SIGTERM');
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
