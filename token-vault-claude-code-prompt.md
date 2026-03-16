# Token Vault - Python Character Token Inventory Manager

## Project Overview

Build a local web application using Python that manages an inventory of character token PNG images. The tool should allow users to browse, tag, filter, and organize their token collection with tags stored directly in PNG metadata.

## Core Requirements

### 1. Tech Stack
- **Backend:** Python with Flask or FastAPI
- **Frontend:** HTML/CSS/JavaScript (single-page app served by Python)
- **Database:** SQLite for inventory index (with PNG metadata as source of truth)
- **PNG Metadata:** Use `piexif` or `Pillow` with `PngImagePlugin` to read/write custom metadata chunks

### 2. Features

#### File Management
- Scan a designated folder (and subfolders) for PNG files
- Watch for new files added to the folder
- Support drag-and-drop upload through the web interface
- Move/copy files into the managed folder structure

#### Tagging System
Store these tags in PNG metadata (using tEXt or iTXt chunks):
- **Species** (e.g., Human, Elf, Dwarf, Orc, Tiefling)
- **Class** (e.g., Fighter, Wizard, Rogue, Cleric)
- **Source** (e.g., Hero Forge, Custom, PHB, Purchased)
- **Campaign** (e.g., Curse of Strahd, Homebrew, One-shots)

Additional metadata to track:
- Custom display name (separate from filename)
- Date added to inventory
- User notes/description

#### Web Interface
- Visual gallery view (grid of token thumbnails)
- List view option
- Search by name
- Filter dropdowns for each tag type
- Multi-select for bulk operations
- Sort by name, date added, or any tag
- Click to view full-size image
- Edit panel for modifying tags

#### Bulk Operations
- Select multiple tokens
- Apply tags to all selected
- Remove tags from all selected
- Delete selected tokens
- Export selected as ZIP

#### Import/Export
- Export inventory metadata as JSON
- Import metadata from JSON (match by filename)
- Export selected tokens as ZIP with metadata preserved
- Backup entire inventory

### 3. PNG Metadata Implementation

Use PNG tEXt chunks with these keys:
```
TokenVault:Name
TokenVault:Species
TokenVault:Class
TokenVault:Source
TokenVault:Campaign
TokenVault:Notes
TokenVault:DateAdded
```

Example Python code for reading/writing:
```python
from PIL import Image
from PIL.PngImagePlugin import PngInfo

def write_token_metadata(filepath, metadata):
    img = Image.open(filepath)
    pnginfo = PngInfo()
    
    # Preserve existing chunks
    if hasattr(img, 'text'):
        for key, value in img.text.items():
            if not key.startswith('TokenVault:'):
                pnginfo.add_text(key, value)
    
    # Add our metadata
    for key, value in metadata.items():
        pnginfo.add_text(f'TokenVault:{key}', str(value))
    
    img.save(filepath, pnginfo=pnginfo)

def read_token_metadata(filepath):
    img = Image.open(filepath)
    metadata = {}
    if hasattr(img, 'text'):
        for key, value in img.text.items():
            if key.startswith('TokenVault:'):
                field = key.replace('TokenVault:', '')
                metadata[field] = value
    return metadata
```

### 4. Project Structure

```
token-vault/
├── app.py                 # Main Flask/FastAPI application
├── database.py            # SQLite operations
├── metadata.py            # PNG metadata read/write
├── scanner.py             # Folder scanning and watching
├── static/
│   ├── css/
│   │   └── style.css      # Dark fantasy theme
│   └── js/
│       └── app.js         # Frontend logic
├── templates/
│   └── index.html         # Main page template
├── tokens/                # Default token storage folder
├── thumbnails/            # Generated thumbnails cache
└── config.json            # User configuration
```

### 5. API Endpoints

```
GET  /api/tokens              - List all tokens (with filters)
GET  /api/tokens/<id>         - Get single token details
PUT  /api/tokens/<id>         - Update token metadata
DELETE /api/tokens/<id>       - Delete token

POST /api/tokens/upload       - Upload new token(s)
POST /api/tokens/bulk-update  - Update multiple tokens
POST /api/tokens/bulk-delete  - Delete multiple tokens

GET  /api/tags/<type>         - Get all values for a tag type
POST /api/scan                - Rescan token folder
GET  /api/export              - Export inventory as JSON
POST /api/import              - Import inventory from JSON

GET  /api/thumbnail/<id>      - Get token thumbnail
GET  /api/image/<id>          - Get full-size image
```

### 6. UI Design

Dark fantasy aesthetic with:
- Deep dark background (#0a0908)
- Gold accents (#c9a227)
- Serif fonts for headers (Cinzel)
- Card-based token display
- Glowing borders on hover
- Color-coded tag pills:
  - Species: Green (#4a7c59)
  - Class: Purple (#7c4a6a)
  - Source: Blue (#5a6a7c)
  - Campaign: Amber (#7c6a4a)

### 7. Configuration

`config.json` should support:
```json
{
  "token_folder": "./tokens",
  "thumbnail_size": [150, 150],
  "watch_folder": true,
  "port": 5000,
  "host": "127.0.0.1"
}
```

### 8. Startup Behavior

1. Load configuration
2. Initialize SQLite database if not exists
3. Scan token folder for new/modified files
4. Sync database with PNG metadata (PNG is source of truth)
5. Generate missing thumbnails
6. Start web server
7. Open browser to interface (optional)

## Implementation Notes

### Database Schema

```sql
CREATE TABLE tokens (
    id INTEGER PRIMARY KEY,
    filepath TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    name TEXT,
    species TEXT,
    class TEXT,
    source TEXT,
    campaign TEXT,
    notes TEXT,
    date_added TEXT,
    file_modified TEXT,
    thumbnail_path TEXT
);

CREATE INDEX idx_species ON tokens(species);
CREATE INDEX idx_class ON tokens(class);
CREATE INDEX idx_source ON tokens(source);
CREATE INDEX idx_campaign ON tokens(campaign);
```

### Sync Strategy

When syncing database with files:
1. For each PNG in folder:
   - If not in DB: read metadata from PNG, add to DB
   - If in DB but file modified: re-read metadata from PNG
2. For each DB entry:
   - If file doesn't exist: remove from DB
3. PNG metadata is always the source of truth

### Thumbnail Generation

- Generate on first access or during scan
- Store in thumbnails folder with hashed filename
- Regenerate if source file is newer than thumbnail
- Use 150x150 max size, maintaining aspect ratio

## Example Usage

```bash
# Install dependencies
pip install flask pillow watchdog

# Run the application
python3 app.py

# Or with custom config
python3 app.py --config /path/to/config.json --port 8080
```

## Stretch Goals (Optional)

- Folder organization (move tokens into subfolders by campaign)
- Duplicate detection (by image hash)
- Token preview on hover
- Keyboard shortcuts (arrow keys to navigate, Enter to edit)
- Dark/light theme toggle
- Token sets/collections
- Print-ready token sheet generator
- Integration with VTT platforms (Foundry, Roll20 export)

## Getting Started

Start by creating the basic Flask app with the metadata.py module for PNG read/write. Then add the database layer and API endpoints. Finally, build out the frontend interface.

Test with a small set of PNG tokens first before scaling up to larger collections.
