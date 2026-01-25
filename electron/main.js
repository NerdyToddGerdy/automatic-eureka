const { app, BrowserWindow, dialog, shell, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const Store = require('electron-store');
const OAuthHandler = require('./oauth-handler');

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

  mainWindow.loadURL('http://127.0.0.1:5000');

  // Optional: Open DevTools in development
  mainWindow.webContents.openDevTools();
}

function startFlaskServer(tokens) {
  const pythonPath = 'python3';
  const scriptPath = path.join(__dirname, '..', 'app.py');

  // Pass OAuth tokens to Flask via environment variable
  const env = Object.assign({}, process.env);
  if (tokens) {
    env.GOOGLE_OAUTH_TOKENS = JSON.stringify(tokens);
  }

  flaskProcess = spawn(pythonPath, [scriptPath], {
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
    try {
      console.log(`Flask: ${data}`);
    } catch (e) {
      // Ignore EPIPE errors in Electron
    }
  });

  flaskProcess.stderr.on('data', (data) => {
    try {
      console.error(`Flask Error: ${data}`);
    } catch (e) {
      // Ignore EPIPE errors in Electron
    }
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
      try {
        console.log('Using stored authentication tokens');
      } catch (e) {
        // Ignore EPIPE errors in Electron
      }

      // Refresh if needed
      const tokens = await oauthHandler.getTokens();
      return oauthHandler.getTokensForPython();
    } else {
      try {
        console.log('No valid tokens found, starting authentication flow...');
      } catch (e) {
        // Ignore EPIPE errors in Electron
      }

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
    try {
      console.error('Authentication error:', error);
    } catch (e) {
      // Ignore EPIPE errors in Electron
    }

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

app.whenReady().then(async () => {
  // Try to authenticate (optional - can skip)
  const tokens = await ensureAuthentication();

  // Start Flask with or without OAuth tokens
  // null tokens means user skipped Google Drive
  startFlaskServer(tokens);

  // Wait for Flask to start
  setTimeout(createWindow, 2000);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (flaskProcess) {
    flaskProcess.kill();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
