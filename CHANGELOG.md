# Changelog

All notable changes to Image Vault will be documented in this file.

## [2.0.0] - 2024-12-16

### Added - Electron Desktop Application
- **Desktop App Support**: Image Vault can now run as an Electron desktop application
- **Reference-in-Place Mode**: When running as desktop app, files are referenced at their original location instead of being copied
- **Mode Indicator**: Visual indicator shows whether you're in "Reference Mode" (Electron) or "Copy Mode" (browser)
- **Dual Mode Support**: Same codebase works as both web app and desktop app
- **Auto File Path Detection**: Electron automatically extracts file paths from drag-drop and file browser

### Technical Details
- Added Electron main process (`electron/main.js`) that manages Flask subprocess
- Added preload script (`electron/preload.js`) with secure contextBridge API
- Enhanced frontend to detect Electron environment and use reference APIs
- New helper functions for reference-mode file operations
- Backend endpoints already supported both copy and reference modes

### Running Options
- **Desktop App**: `npm start` - References files in place, doesn't copy them
- **Web App**: `python3 app.py` + browser - Copies files to vault (traditional mode)

### Packaging Support
- macOS: `npm run package-mac` → Creates .dmg installer
- Windows: `npm run package-win` → Creates .exe installer
- Linux: `npm run package-linux` → Creates AppImage

### Benefits
- No duplicate files when using desktop app
- Organize images in your own folder structure
- Database tracks original file locations
- Existing file scanning workflows still work
- "Import Folder" feature now consistent with Browse/Drag-Drop in desktop mode

## [1.0.0] - Previous Release

### Initial Features
- PNG metadata storage
- Visual gallery with grid/list views
- Tagging system (Species, Class, Source, Campaign)
- Search and filtering
- Bulk operations
- Auto-scan and folder watching
- Multiple image types (Token, Map, Handout, Portrait, Scene, Item)
- Duplicate detection with rename/skip/overwrite options
- Dark fantasy themed UI