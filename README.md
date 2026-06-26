# Image Vault

> A local-first asset organizer for tabletop RPG players that stores metadata directly in your image files—so your tags go wherever your images go.

A desktop application for managing your collection of RPG assets: character tokens, maps, handouts, portraits, scene art, items, music, sound effects, and rulebook PDFs. Perfect for D&D, Pathfinder, and other tabletop RPG players and DMs.

<!-- Add a screenshot: ![Image Vault Screenshot](docs/screenshot.png) -->

## Features

- **Reference Mode**: Files stay exactly where they already live on disk — nothing is copied or moved. Point the app at your existing folders and it indexes them in place.
- **Three Content Types**: Tokens/Images (PNG, JPG), Audio (MP3, WAV, OGG, M4A, FLAC), and PDFs, each with their own gallery tab.
- **Metadata Stored in the File Itself**: For PNG and JPEG images, tags are written directly into the image file (PNG text chunks / JPEG EXIF) — no external database dependency. Audio and PDF tags are stored in the local index only (their file formats aren't used as a metadata carrier).
- **Multiple Image Types**: Token, Map, Handout, Portrait, Scene, Item — each with its own type-specific tag fields.
- **Visual Gallery**: Browse images in grid or list view; audio and PDFs get their own list views.
- **Advanced Tagging**: Dynamic tag schemas per content type, plus global Source/Campaign tags shared across everything.
- **Search & Filter**: Quickly find assets with powerful per-field filtering.
- **Bulk Operations**: Update or delete multiple items at once.
- **Tag Manager**: Rename or merge a tag value across every item that uses it, in one operation.
- **Duplicate Detection**: Smart handling with rename/skip/overwrite options.
- **Auto-Scan**: Detects new files in your watched folders automatically (or trigger a manual rescan).
- **Dark Fantasy Theme**: Dark UI with gold accents, accessible focus states, and reduced-motion support.

## Installation

**Prerequisites**: Python 3.10+ (a single runtime — no Node.js needed)

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the desktop app:
```bash
python3 desktop.py
```

A native desktop window opens with Flask running in the background (in the same process — no subprocess to manage). You'll see a green "📌 Reference Mode" indicator confirming files are referenced in place, not copied.

> **Why a desktop window, not just a browser?** Image Vault only supports Reference Mode — there's no "copy files into a vault folder" mode. Adding files by path requires real absolute file-system paths, which the desktop app's native file dialog (via [pywebview](https://pywebview.flowrl.com/)) provides; a plain browser can't, and the legacy browser-upload API routes are intentionally disabled. Running `python3 app.py` directly (without the desktop window) still works for development and for browsing/editing whatever is already indexed, but you can't add new files through the UI that way.

## Usage

### Adding Content

- **Add Files** (header button) — pick individual images, audio files, or PDFs by path.
- **Import Folder** — point at a folder (optionally recursive) and the scanner indexes every supported file inside it, prompting for tags per type/subfolder along the way.
- **Drag and drop** — drop files or a folder directly onto the gallery.
- **Rescan** — re-index your watched folders manually at any time; this also catches files that moved or were deleted outside the app.

### Organizing

- Click any item to view details and edit its metadata.
- Use the filter bar to narrow down by type, tag value, source, or campaign.
- Select multiple items (checkbox on each card) for bulk tag edits or deletes.
- Use **Manage Tags** to rename or merge a tag value everywhere it's used — e.g. fixing a typo'd Campaign name across 40 tokens in one go.

### Metadata Fields

Image types each have their own tag schema, plus shared **Source** and **Campaign** fields:

| Image Type | Type-specific fields |
|---|---|
| Token | Species, Class |
| Map | Scale, Theme |
| Handout | Type |
| Portrait | Subject, Style |
| Scene | Location, Mood |
| Item | Rarity, Category, Attunement |

Audio types follow the same pattern:

| Audio Type | Type-specific fields |
|---|---|
| Music | Genre, Mood |
| SoundEffect | Intensity, Location |
| Ambience | Mood, Intensity, Location |
| Dialogue | Character |

PDFs currently support **Source** and **Campaign** only (no type-specific schema).

Every item also has a **Display Name** (independent of filename) and free-text **Notes**.

## Configuration

Edit `config.json` to customize:

```json
{
  "thumbnail_size": [150, 150],
  "watch_folder": true,
  "port": 5000,
  "host": "127.0.0.1"
}
```

There's no fixed "token folder" setting — Reference Mode tracks each item's own original file path individually, so your assets can live anywhere on disk, across as many folders as you like.

## Command Line Options

```bash
# Run on a different port
python3 app.py --port 8080

# Use a custom config file
python3 app.py --config /path/to/config.json

# Bind to a different host
python3 app.py --host 0.0.0.0
```

## Packaging Desktop App

The app is frozen into a standalone artifact with [PyInstaller](https://pyinstaller.org/) (no Python needed on the target machine):

```bash
pyinstaller image-vault.spec
```

The packaged app lands in the `dist/` folder (`Image Vault.app` on macOS; Windows/Linux are stretch goals). Optionally, `uv build` produces a wheel first — `uv` is the maintainer's build tool and isn't something end users run.

## Project Structure

```
image-vault/
├── app.py                 # Main Flask application & API routes
├── database.py            # SQLite operations (tokens, audio_files, pdf_files tables)
├── metadata.py            # PNG/JPEG metadata read/write (source of truth for images)
├── scanner.py             # Folder scanning, file-type detection, and watching
├── cache.py                # In-memory thumbnail cache
├── file_utils.py          # File hashing, timeout-bounded file I/O, duplicate detection
├── desktop.py             # pywebview desktop entry point (Flask + native window + JS bridge)
├── image-vault.spec       # PyInstaller spec for the standalone app
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Package metadata & build config (PEP 621 + hatchling)
├── static/
│   ├── css/style.css       # Dark fantasy theme
│   ├── js/app.js           # Frontend logic (single-page app, no framework)
│   └── img/                # Static image assets
├── templates/
│   └── index.html          # Main page template
├── tests/                  # Unit tests + Playwright E2E tests (tests/chrome/)
├── tokens/                 # Legacy folder, unused in Reference Mode (gitignored)
├── thumbnails/             # Generated thumbnail cache (gitignored)
└── tokens.db                # SQLite index database (gitignored)
```

## API Endpoints

**Tokens/Images**
- `GET /api/tokens` — List with filters (search, image_type, species, class, source, campaign, sort)
- `GET /api/tokens/<id>` / `PUT /api/tokens/<id>` / `DELETE /api/tokens/<id>`
- `POST /api/tokens/add-reference` — Add a single file by path
- `POST /api/tokens/add-references-batch` — Add multiple files by path
- `POST /api/tokens/scan-folder` — Scan a folder (with subfolder support) for files to add
- `POST /api/tokens/bulk-update` / `POST /api/tokens/bulk-delete`
- `GET /api/thumbnail/<id>` / `GET /api/image/<id>`

**Audio**
- `GET /api/audio` — List with filters
- `GET /api/audio/<id>` / `PUT /api/audio/<id>` / `DELETE /api/audio/<id>`
- `POST /api/audio/add-reference`
- `GET /api/audio/stream/<id>` — Stream audio for playback

**PDFs**
- `GET /api/pdfs` — List with filters
- `GET /api/pdfs/<id>` / `PUT /api/pdfs/<id>` / `DELETE /api/pdfs/<id>`
- `POST /api/pdfs/add-reference`
- `GET /api/pdf/<id>` — Serve the raw PDF
- `GET /api/pdf-thumbnail/<id>` — Cover thumbnail rendered from page 1

**Shared**
- `GET /api/tags/<type>` — Get distinct values for a tag field
- `GET /api/tags/<field>/manage` / `PUT /api/tags/<field>/rename` — Tag Manager (merge/rename)
- `POST /api/scan` — Manually rescan watched folders
- `GET /api/stats` — Database statistics

## How It Works

### Images: File as Source of Truth

For PNG and JPEG tokens, metadata is stored directly in the image file — PNG text chunks for PNGs, EXIF UserComment (as JSON) for JPEGs. The SQLite database is only an index for faster searching; the image files are the source of truth. Audio and PDF formats aren't used this way — their tags live in the database only.

PNG metadata keys used (prefixed `ImageVault:`, with backward-compatible support for the older `TokenVault:` prefix):
- `ImageVault:Name`, `ImageVault:ImageType`, `ImageVault:Species`, `ImageVault:Class`, `ImageVault:Source`, `ImageVault:Campaign`, `ImageVault:Notes`, `ImageVault:DateAdded` (plus the other type-specific fields listed above)

### Sync Strategy

When the app starts or when you click "Rescan":
1. Watched folders are scanned for supported files.
2. For images, metadata is read from each file and used to update the database.
3. Files that moved or were deleted are detected and flagged or removed.
4. Missing thumbnails are generated.

## Tips

- **Backup**: For images, your metadata travels with the PNG/JPEG file, so backing up your image folders covers that data. Audio/PDF tags and all Display Names/Notes only exist in `tokens.db` — back that up too if you want a complete backup.
- **Sharing**: Send a PNG/JPEG to someone else and its tags go with it automatically.
- **Organization**: Use Campaign to separate different game sessions; Source to track where an asset came from (a marketplace, a sourcebook, your own art).
- **Bulk Tagging**: Import a folder, select everything, then bulk-tag with whatever's common across the batch.

## Troubleshooting

**Items not showing up?**
- Click "Rescan" to manually trigger a folder scan.
- Confirm the file extension is supported: images are `.png`/`.jpg`/`.jpeg`, audio is `.mp3`/`.wav`/`.ogg`/`.m4a`/`.flac`, PDFs are `.pdf`.
- If a file's underlying path changed, check for a "file not found" warning on its card and use the repair flow to point it at the new location.

**Thumbnails not loading?**
- Thumbnails are generated on-demand and cached; check file permissions on the `thumbnails` folder.

**Folder watcher not working?**
- Set `"watch_folder": false` in `config.json` and use manual rescan instead.

## License

MIT License — see [LICENSE](LICENSE) for details.

---

Built for tabletop RPG enthusiasts who want to organize their ever-growing collection of tokens, maps, music, and rulebooks.
