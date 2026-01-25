# Image Vault - Character Image Manager

A hybrid web/desktop application for managing your collection of RPG character images. Perfect for D&D, Pathfinder, and other tabletop RPG players and DMs.

## 🎯 Two Ways to Run

**🖥️ Desktop App (NEW v2.0)** - Recommended
- Files stay in their original location (no copying)
- Run as native desktop application
- Perfect for large collections organized in custom folders

**🌐 Web App** - Traditional
- Files copied to vault folder
- Run in web browser
- Great for centralized collections

## Features

- **Desktop & Web Modes**: Run as Electron app (reference files) or web app (copy files)
- **PNG Metadata Storage**: Tags are stored directly in PNG files (no external database dependency)
- **Multiple Image Types**: Token, Map, Handout, Portrait, Scene, Item with type-specific tags
- **Visual Gallery**: Browse images in grid or list view
- **Advanced Tagging**: Dynamic tag schemas per image type, global Source/Campaign tags
- **Search & Filter**: Quickly find images with powerful filtering
- **Bulk Operations**: Update or delete multiple images at once
- **Duplicate Detection**: Smart handling with rename/skip/overwrite options
- **Auto-Scan**: Automatically detects new files in your folder
- **Dark Fantasy Theme**: Beautiful dark UI with gold accents

## Installation

### For Desktop App (Recommended)

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Node.js dependencies:
```bash
npm install
```

3. Run as desktop app:
```bash
npm start
```

The Electron app will launch with Flask running in the background. You'll see a green "📌 Reference Mode" indicator showing files will be referenced in place.

### For Web App (Traditional)

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the Flask server:
```bash
python app.py
```

3. Open your browser to: http://127.0.0.1:5000

You'll see a yellow "📁 Copy Mode" indicator showing files will be copied to the vault.

## Usage

### Mode Differences

**Desktop App (Reference Mode):**
- Browse/Drag-Drop files → Referenced at original location
- No files copied, no storage duplication
- Organize images in your own folder structure
- Database tracks original file paths

**Web App (Copy Mode):**
- Browse/Drag-Drop files → Copied to `tokens` folder
- Traditional centralized storage
- All files in one location

**Both Modes:**
- Import Folder feature works the same way
- Metadata written to original PNG files
- Same filtering, tagging, and search features

### First Time Setup

1. The app will create a `tokens` folder in the project directory
2. Add your PNG token images to this folder
3. The app will automatically scan and index them

### Adding Tokens

- **Upload**: Click "Upload Tokens" button and select PNG files
- **Drop Files**: Copy PNG files directly into the `tokens` folder

### Organizing Tokens

- Click on any token to view details and edit metadata
- Use filters to narrow down your collection
- Select multiple tokens for bulk operations
- All metadata is saved directly in the PNG files

### Metadata Fields

- **Display Name**: Custom name (separate from filename)
- **Species**: Human, Elf, Dwarf, Orc, etc.
- **Class**: Fighter, Wizard, Rogue, etc.
- **Source**: Hero Forge, Custom, PHB, etc.
- **Campaign**: Curse of Strahd, Homebrew, etc.
- **Notes**: Custom description

## Configuration

Edit `config.json` to customize:

```json
{
  "token_folder": "./tokens",
  "thumbnail_size": [150, 150],
  "watch_folder": true,
  "port": 5000,
  "host": "127.0.0.1"
}
```

## Command Line Options

```bash
# Run on a different port
python app.py --port 8080

# Use a custom config file
python app.py --config /path/to/config.json

# Bind to different host
python app.py --host 0.0.0.0
```

## Packaging Desktop App

To create distributable installers for the desktop app:

```bash
# macOS - Creates .dmg installer
npm run package-mac

# Windows - Creates .exe installer
npm run package-win

# Linux - Creates AppImage
npm run package-linux
```

The packaged apps will be in the `dist/` folder. These are standalone applications that include Python, Flask, and all dependencies.

## Project Structure

```
image-vault/
├── app.py                 # Main Flask application
├── database.py            # SQLite operations
├── metadata.py            # PNG metadata read/write
├── scanner.py             # Folder scanning and watching
├── config.json            # Configuration
├── requirements.txt       # Python dependencies
├── package.json           # Node/Electron config
├── electron/              # Electron app files
│   ├── main.js            # Electron main process
│   └── preload.js         # Secure bridge script
├── static/
│   ├── css/
│   │   └── style.css      # Dark fantasy theme
│   └── js/
│       └── app.js         # Frontend logic
├── templates/
│   └── index.html         # Main page template
├── tokens/                # Token storage folder
├── thumbnails/            # Generated thumbnails cache
└── tokens.db              # SQLite index database
```

## API Endpoints

- `GET /api/tokens` - List all tokens (with filters)
- `GET /api/tokens/<id>` - Get single token
- `PUT /api/tokens/<id>` - Update token metadata
- `DELETE /api/tokens/<id>` - Delete token
- `POST /api/tokens/upload` - Upload new tokens
- `POST /api/tokens/bulk-update` - Update multiple tokens
- `POST /api/tokens/bulk-delete` - Delete multiple tokens
- `GET /api/tags/<type>` - Get all values for a tag type
- `POST /api/scan` - Manually rescan token folder
- `GET /api/stats` - Get database statistics
- `GET /api/thumbnail/<id>` - Get token thumbnail
- `GET /api/image/<id>` - Get full-size image

## How It Works

### PNG as Source of Truth

Image Vault stores all metadata directly in PNG files using standard PNG text chunks. The SQLite database is only an index for faster searching - the PNG files are the source of truth.

Metadata keys used:
- `ImageVault:Name`
- `ImageVault:Species`
- `ImageVault:Class`
- `ImageVault:Source`
- `ImageVault:Campaign`
- `ImageVault:Notes`
- `ImageVault:DateAdded`

### Sync Strategy

When the app starts or when you click "Rescan":
1. All PNG files in the token folder are scanned
2. Metadata is read from each PNG file
3. Database is updated to match PNG metadata
4. Files not in the folder are removed from the database
5. Missing thumbnails are generated

## Tips

- **Backup**: Your metadata is in the PNG files, so backing up the `tokens` folder is all you need
- **Sharing**: Send PNG files to others - the metadata travels with the image
- **Organization**: Use campaigns to separate different game sessions
- **Bulk Tagging**: Upload a bunch of tokens, select them all, then bulk-tag with common attributes

## Troubleshooting

**Tokens not showing up?**
- Click the "Rescan" button to manually trigger a folder scan
- Check that files are PNG format (JPG/WEBP not supported)
- Verify the token_folder path in config.json

**Thumbnails not loading?**
- Thumbnails are generated on-demand
- Check file permissions on the `thumbnails` folder

**Folder watcher not working?**
- Set `watch_folder: false` in config.json and use manual rescan instead

## License

This project is open source and available for personal use.

## Acknowledgments

Built for tabletop RPG enthusiasts who want to organize their ever-growing collection of character tokens!
