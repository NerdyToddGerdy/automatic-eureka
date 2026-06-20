const { contextBridge, ipcRenderer } = require('electron');
const { webUtils } = require('electron');

// Expose secure API to renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  /**
   * Get absolute file path from File object
   * Only works in Electron with webUtils
   */
  getFileAbsolutePath: (file) => {
    try {
      return webUtils.getPathForFile(file);
    } catch (error) {
      console.error('Error getting file path:', error);
      return null;
    }
  },

  /**
   * Show file in Finder (macOS) or Explorer (Windows)
   * @param {string} filepath - Absolute path to the file
   * @returns {Promise<{success: boolean, error?: string}>}
   */
  showItemInFolder: (filepath) => ipcRenderer.invoke('show-item-in-folder', filepath),

  /**
   * Open a file with the system default application (e.g. PDFs in Preview/Acrobat)
   * @param {string} filepath - Absolute path to the file
   * @returns {Promise<{success: boolean, error?: string}>}
   */
  openFile: (filepath) => ipcRenderer.invoke('open-file', filepath),

  /**
   * Flag indicating we're running in Electron
   */
  isElectron: true
});
