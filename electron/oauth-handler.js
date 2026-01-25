/**
 * Google OAuth Handler for Electron
 * Handles OAuth 2.0 flow with local callback server and secure token storage
 */

const { shell, safeStorage } = require('electron');
const http = require('http');
const url = require('url');
const fs = require('fs');
const path = require('path');

// OAuth configuration
const CALLBACK_PORT = 8888;
const REDIRECT_URI = `http://localhost:${CALLBACK_PORT}/oauth/callback`;
const SCOPES = ['https://www.googleapis.com/auth/drive'];

class OAuthHandler {
    constructor(store) {
        this.store = store;  // Electron-store for persisting encrypted tokens
        this.credentials = null;  // OAuth client credentials from credentials.json
        this.tokens = null;  // Access and refresh tokens
        this.callbackServer = null;
    }

    /**
     * Load OAuth client credentials from credentials.json
     */
    loadCredentials() {
        const credPath = path.join(__dirname, '..', 'credentials.json');

        if (!fs.existsSync(credPath)) {
            throw new Error(
                'credentials.json not found! Please:\n' +
                '1. Create a Google Cloud project\n' +
                '2. Enable Google Drive API\n' +
                '3. Create OAuth 2.0 credentials (Desktop app)\n' +
                '4. Download credentials.json to project root\n' +
                'See plan file for detailed instructions.'
            );
        }

        const credData = JSON.parse(fs.readFileSync(credPath, 'utf8'));
        this.credentials = credData.installed || credData.web;

        if (!this.credentials) {
            throw new Error('Invalid credentials.json format');
        }

        return this.credentials;
    }

    /**
     * Load stored tokens from encrypted storage
     */
    loadStoredTokens() {
        try {
            const encryptedTokens = this.store.get('oauth_tokens');

            if (!encryptedTokens) {
                return null;
            }

            // Decrypt tokens using OS keychain
            const buffer = Buffer.from(encryptedTokens, 'base64');
            const decryptedString = safeStorage.decryptString(buffer);
            this.tokens = JSON.parse(decryptedString);

            return this.tokens;
        } catch (error) {
            try {
                console.error('Error loading stored tokens:', error);
            } catch (e) {
                // Ignore EPIPE errors in Electron
            }
            return null;
        }
    }

    /**
     * Store tokens securely using OS keychain encryption
     */
    storeTokens(tokens) {
        try {
            this.tokens = tokens;

            // Encrypt tokens using OS keychain
            const encrypted = safeStorage.encryptString(JSON.stringify(tokens));
            const base64Encrypted = encrypted.toString('base64');

            this.store.set('oauth_tokens', base64Encrypted);
            return true;
        } catch (error) {
            try {
                console.error('Error storing tokens:', error);
            } catch (e) {
                // Ignore EPIPE errors in Electron
            }
            return false;
        }
    }

    /**
     * Clear stored tokens (for logout)
     */
    clearTokens() {
        this.tokens = null;
        this.store.delete('oauth_tokens');
    }

    /**
     * Check if we have valid tokens
     */
    hasValidTokens() {
        if (!this.tokens || !this.tokens.access_token) {
            return false;
        }

        // Check if access token is expired (simplified check)
        if (this.tokens.expiry_date && Date.now() >= this.tokens.expiry_date) {
            // Token expired - will need to refresh
            return this.tokens.refresh_token != null;
        }

        return true;
    }

    /**
     * Get the OAuth authorization URL
     */
    getAuthUrl() {
        if (!this.credentials) {
            this.loadCredentials();
        }

        const authUrl = new URL('https://accounts.google.com/o/oauth2/v2/auth');
        authUrl.searchParams.append('client_id', this.credentials.client_id);
        authUrl.searchParams.append('redirect_uri', REDIRECT_URI);
        authUrl.searchParams.append('response_type', 'code');
        authUrl.searchParams.append('scope', SCOPES.join(' '));
        authUrl.searchParams.append('access_type', 'offline');  // Get refresh token
        authUrl.searchParams.append('prompt', 'consent');  // Force consent to get refresh token

        return authUrl.toString();
    }

    /**
     * Start local HTTP server to receive OAuth callback
     */
    startCallbackServer() {
        return new Promise((resolve, reject) => {
            // Create HTTP server
            this.callbackServer = http.createServer(async (req, res) => {
                const parsedUrl = url.parse(req.url, true);

                if (parsedUrl.pathname === '/oauth/callback') {
                    const code = parsedUrl.query.code;
                    const error = parsedUrl.query.error;

                    if (error) {
                        res.writeHead(400, { 'Content-Type': 'text/html' });
                        res.end('<h1>Authentication failed</h1><p>You can close this window.</p>');
                        reject(new Error(`OAuth error: ${error}`));
                        this.stopCallbackServer();
                        return;
                    }

                    if (code) {
                        // Exchange code for tokens
                        try {
                            const tokens = await this.exchangeCodeForTokens(code);
                            this.storeTokens(tokens);

                            res.writeHead(200, { 'Content-Type': 'text/html' });
                            res.end(`
                                <h1>Authentication successful!</h1>
                                <p>You can close this window and return to Image Vault.</p>
                                <script>window.close();</script>
                            `);

                            resolve(tokens);
                        } catch (exchangeError) {
                            res.writeHead(500, { 'Content-Type': 'text/html' });
                            res.end('<h1>Token exchange failed</h1><p>Please try again.</p>');
                            reject(exchangeError);
                        }

                        this.stopCallbackServer();
                    }
                } else {
                    res.writeHead(404);
                    res.end('Not found');
                }
            });

            // Start server
            this.callbackServer.listen(CALLBACK_PORT, () => {
                try {
                    console.log(`OAuth callback server listening on port ${CALLBACK_PORT}`);
                } catch (e) {
                    // Ignore EPIPE errors in Electron
                }
            });

            // Handle server errors
            this.callbackServer.on('error', (err) => {
                if (err.code === 'EADDRINUSE') {
                    reject(new Error(`Port ${CALLBACK_PORT} is already in use`));
                } else {
                    reject(err);
                }
            });
        });
    }

    /**
     * Stop the callback server
     */
    stopCallbackServer() {
        if (this.callbackServer) {
            this.callbackServer.close();
            this.callbackServer = null;
        }
    }

    /**
     * Exchange authorization code for access and refresh tokens
     */
    async exchangeCodeForTokens(code) {
        if (!this.credentials) {
            this.loadCredentials();
        }

        const tokenUrl = 'https://oauth2.googleapis.com/token';
        const params = new URLSearchParams({
            code: code,
            client_id: this.credentials.client_id,
            client_secret: this.credentials.client_secret,
            redirect_uri: REDIRECT_URI,
            grant_type: 'authorization_code'
        });

        const response = await fetch(tokenUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: params.toString()
        });

        if (!response.ok) {
            const error = await response.text();
            throw new Error(`Token exchange failed: ${error}`);
        }

        const tokens = await response.json();

        // Add expiry timestamp
        tokens.expiry_date = Date.now() + (tokens.expires_in * 1000);

        return tokens;
    }

    /**
     * Refresh the access token using refresh token
     */
    async refreshAccessToken() {
        if (!this.tokens || !this.tokens.refresh_token) {
            throw new Error('No refresh token available');
        }

        if (!this.credentials) {
            this.loadCredentials();
        }

        const tokenUrl = 'https://oauth2.googleapis.com/token';
        const params = new URLSearchParams({
            client_id: this.credentials.client_id,
            client_secret: this.credentials.client_secret,
            refresh_token: this.tokens.refresh_token,
            grant_type: 'refresh_token'
        });

        const response = await fetch(tokenUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: params.toString()
        });

        if (!response.ok) {
            const error = await response.text();
            throw new Error(`Token refresh failed: ${error}`);
        }

        const newTokens = await response.json();

        // Preserve refresh token (not always returned in refresh response)
        newTokens.refresh_token = newTokens.refresh_token || this.tokens.refresh_token;
        newTokens.expiry_date = Date.now() + (newTokens.expires_in * 1000);

        this.storeTokens(newTokens);
        return newTokens;
    }

    /**
     * Complete OAuth flow: open browser, wait for callback, get tokens
     */
    async authenticate() {
        try {
            // Start callback server
            const serverPromise = this.startCallbackServer();

            // Open browser to auth URL
            const authUrl = this.getAuthUrl();
            await shell.openExternal(authUrl);

            try {
                console.log('Opened browser for authentication...');
            } catch (e) {
                // Ignore EPIPE errors in Electron
            }

            // Wait for callback with timeout
            const timeoutPromise = new Promise((_, reject) =>
                setTimeout(() => reject(new Error('Authentication timeout')), 300000) // 5 min timeout
            );

            const tokens = await Promise.race([serverPromise, timeoutPromise]);

            try {
                console.log('Authentication successful!');
            } catch (e) {
                // Ignore EPIPE errors in Electron
            }
            return tokens;

        } catch (error) {
            this.stopCallbackServer();
            throw error;
        }
    }

    /**
     * Get current tokens (refresh if needed)
     */
    async getTokens() {
        // If no tokens, need to authenticate
        if (!this.tokens) {
            const stored = this.loadStoredTokens();
            if (!stored) {
                throw new Error('No authentication. Please log in.');
            }
        }

        // If access token expired, refresh it
        if (this.tokens.expiry_date && Date.now() >= this.tokens.expiry_date) {
            if (this.tokens.refresh_token) {
                try {
                    console.log('Access token expired, refreshing...');
                } catch (e) {
                    // Ignore EPIPE errors in Electron
                }
                await this.refreshAccessToken();
            } else {
                throw new Error('Access token expired and no refresh token available');
            }
        }

        return this.tokens;
    }

    /**
     * Get tokens formatted for Python google-auth library
     */
    getTokensForPython() {
        if (!this.tokens) {
            return null;
        }

        // Load credentials if not already loaded
        if (!this.credentials) {
            try {
                this.loadCredentials();
            } catch (error) {
                return null;
            }
        }

        return {
            token: this.tokens.access_token,
            refresh_token: this.tokens.refresh_token,
            token_uri: 'https://oauth2.googleapis.com/token',
            client_id: this.credentials.client_id,
            client_secret: this.credentials.client_secret,
            scopes: SCOPES
        };
    }
}

module.exports = OAuthHandler;
