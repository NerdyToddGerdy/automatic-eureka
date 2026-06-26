# CLAUDE.md
## ImageTagger (Image Vault) - Project-Specific Guide

> This file contains ImageTagger-specific architecture, patterns, and conventions.
> For universal conventions, see CLAUDE-shared.md

---

## Project Overview

**ImageTagger** (branded as "Image Vault") is a hybrid desktop/web application for managing tabletop RPG character images (tokens, maps, portraits, etc.). Designed for D&D, Pathfinder, and similar RPG players and DMs.

**Key Innovation**: Metadata stored directly in PNG files (source of truth) with SQLite index for performance.

---

## Common Commands

### Start Application
```bash
# Start Flask server (web mode)
python3 app.py

# Start with specific port
python3 app.py --port 5000

# Development mode with debug
FLASK_ENV=development python3 app.py

# Start the desktop app (pywebview window wrapping the Flask backend)
python3 desktop.py

# Desktop app with DevTools
DEBUG_DEVTOOLS=1 python3 desktop.py
```

### Testing
```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/ --ignore=tests/chrome/

# Run only Chrome E2E tests
pytest tests/chrome/ -v

# Run Chrome tests with visible browser
HEADLESS=0 pytest tests/chrome/ -v

# Run with coverage
pytest --cov --cov-report=html
```

### Build & Package
```bash
# Build a wheel (uv is the maintainer's dev/build tool; end users never run it)
uv build

# Freeze the desktop app into a standalone artifact (dist/Image Vault.app on macOS)
pyinstaller image-vault.spec
```

### Database Operations
```bash
# The app auto-creates tokens.db on first run
# No manual migrations needed for SQLite

# To reset database, delete and restart
rm tokens.db
python3 app.py
```

---

## Architecture Overview

### High-Level Structure
```
ImageTagger/
├── app.py                 # Flask application & API endpoints
├── database.py            # SQLite operations & schema
├── metadata.py            # PNG metadata read/write (source of truth)
├── scanner.py             # Folder scanning & file watching
├── cache.py               # Thumbnail caching layer
├── file_utils.py          # File operation utilities
├── desktop.py             # pywebview desktop entry point (Flask + native window)
├── image-vault.spec       # PyInstaller spec for the standalone app
├── config.json            # Application configuration (in user data dir at runtime)
├── templates/
│   └── index.html         # Single-page application UI
├── static/
│   ├── js/app.js          # Frontend logic & state management
│   └── css/style.css      # Dark fantasy theme styling
└── tests/
    ├── test_*.py          # Unit tests
    └── chrome/            # E2E tests (Page Object Model)
```

### Key Architectural Decisions

#### 1. Reference Mode (only mode)
Files stay in their original on-disk locations; the app indexes them in
place and stores absolute paths in the database. Nothing is copied or moved.
Adding files needs real absolute filesystem paths, which the pywebview
native file dialog (`window.pywebview.api.open_file_dialog()`) provides.

The legacy Copy Mode (copying files into `./tokens/`) and the browser-based
upload flow have been removed — the `/api/*/upload` endpoints now return 400.

#### 2. Metadata Storage Strategy
- **PNG Files = Source of Truth**: Metadata stored in PNG text chunks (`ImageVault:` prefix)
- **SQLite = Performance Index**: Fast filtering and querying
- **Synchronization**: PNG files can be shared; database rebuilt by scanning
- **Backwards Compatible**: Supports old `TokenVault:` prefix

#### 3. Image Type System
Six configurable image types with type-specific tag schemas:
- **Token**: Species, Class, Source, Campaign
- **Map**: Scale, Theme, Source, Campaign
- **Handout**: Type, Source, Campaign
- **Portrait**: Subject, Style, Source, Campaign
- **Scene**: Location, Mood, Source, Campaign
- **Item**: Rarity, Category, Attunement, Source, Campaign

---

## Tech Stack

### Backend
- **Python 3.10+**
- **Flask 3.0.0** - Web server and REST API
- **SQLite3** - Fast indexing (built-in)
- **Pillow 10.1.0** - Image processing & PNG metadata
- **Watchdog 3.0.0** - Folder monitoring
- **PyMuPDF** - PDF cover-thumbnail rendering
- **tinytag** - Audio metadata/duration
- **platformdirs** - Cross-platform user data dir for config.json/tokens.db

### Frontend
- **Vanilla JavaScript** (ES6+) - No frameworks
- **HTML5/CSS3** - Responsive design
- **pywebview 5+** - Native desktop window wrapping the Flask backend (replaced Electron)

### Packaging
- **uv** - Maintainer's build tool (`uv build` → wheel)
- **PyInstaller** - Freezes the desktop app into a standalone artifact (`image-vault.spec`)

### Testing
- **Pytest 7.4.3** - Test framework
- **Selenium 4.15.2** - Browser automation
- **ChromeDriver** - E2E tests

---

## Code Style Guidelines

### Python Modules

#### app.py - Flask Application
```python
# API endpoint pattern
@app.route('/api/endpoint', methods=['GET', 'POST'])
def endpoint_name():
    """Brief description of what this endpoint does."""
    try:
        # Validate input
        # Process request
        # Return JSON response
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        app.logger.error(f"Error in endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500
```

**Conventions**:
- All API routes start with `/api/`
- Return JSON for all API endpoints
- Use consistent error handling pattern
- Log errors with context

#### database.py - Database Operations
```python
# Always use context managers for connections
def get_token(self, token_id):
    """Retrieve a single token by ID."""
    with self.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tokens WHERE id = ?", (token_id,))
        return cursor.fetchone()
```

**Conventions**:
- Use context managers (`with`) for all DB operations
- Use parameterized queries (never string concatenation)
- Return `dict`-like objects (sqlite3.Row)
- Handle None results gracefully

#### metadata.py - PNG Metadata
```python
# Metadata keys use PascalCase for PNG compatibility
METADATA_KEYS = ['Name', 'ImageType', 'Species', 'Class', ...]

# Always preserve existing metadata when updating
@staticmethod
def write_token_metadata(filepath, metadata):
    """Write metadata to PNG file."""
    # Read existing image
    # Update only specified fields
    # Preserve other PNG chunks
    # Save with compression
```

**Conventions**:
- PNG metadata keys use PascalCase (PNG text chunk convention)
- Database keys use snake_case (Python convention)
- Always preserve existing PNG chunks
- Handle JPEG files (no metadata support)

### JavaScript Frontend (app.js)

```javascript
// Global state at top of file
let tokens = [];
let filteredTokens = [];
let currentFilters = {...};

// Use const for schemas and configurations
const tagSchemas = {
    'Token': ['Species', 'Class', 'Source', 'Campaign'],
    // ...
};

// Functions organized by feature
// 1. Initialization
// 2. API calls
// 3. UI rendering
// 4. Event handlers
// 5. Utility functions

// Use descriptive function names
function renderTokenGallery() { ... }
function handleUploadButtonClick() { ... }
function applyFiltersAndRender() { ... }
```

**Conventions**:
- Global state variables at top
- Use `const` for configuration objects
- Group related functions together
- Add comments for complex UI logic
- Use template literals for HTML generation

---

## Domain-Specific Conventions

### Image Processing
```python
# Always specify PNG compression
img.save(filepath, 'PNG', optimize=True, compress_level=6)

# Generate thumbnails consistently
thumbnail_size = (150, 150)  # Fixed size from config
img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)

# Check file types
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
```

### File Path Handling
```python
# Reference Mode (the only mode): store absolute paths so files are found
# wherever they already live on disk.
token_data['filepath'] = os.path.abspath(filepath)
```

### Tag Management
- Tags are free-form text inputs (not predefined lists)
- Autocomplete populated from existing database values
- Case-sensitive storage, case-insensitive search
- Multi-value fields (Map Theme) use comma separation

---

## Common Mistakes to Avoid

### ❌ Breaking the Metadata Contract
```python
# DON'T: Skip writing metadata to PNG
db.add_token(token_data)  # Only in database!

# DO: Always write to PNG first, then database
metadata.write_token_metadata(filepath, token_data)
db.add_token(token_data)
```

### ❌ Ignoring Dual-Mode Differences
```python
# DON'T: Assume files are always in tokens/ folder
filepath = f"tokens/{filename}"

# DO: Check mode and construct paths appropriately
if config.get('reference_mode'):
    filepath = original_path
else:
    filepath = os.path.join(tokens_folder, filename)
```

### ❌ Hardcoding Image Types
```python
# DON'T: Hardcode type-specific logic everywhere
if image_type == 'Token':
    return ['Species', 'Class']

# DO: Use the tagSchemas configuration
return tagSchemas.get(image_type, [])
```

### ❌ Not Handling Missing Files
```python
# DON'T: Assume files always exist
img = Image.open(filepath)

# DO: Check existence and handle errors
if not os.path.exists(filepath):
    db.mark_missing(token_id, True)
    return None
```

### ❌ Forgetting the pywebview Bridge
```javascript
// DON'T: Assume a <input type=file> File object carries a real path
const path = file.path;  // Always undefined in a browser/webview sandbox

// DO: Feature-detect pywebview and use its native dialog, which returns
//     real absolute paths straight from Python
if (window.pywebview) {
    const paths = await window.pywebview.api.open_file_dialog();
}
```

---

## Testing Guidelines

### Unit Tests (tests/)
- Test database operations (CRUD, filtering, sorting)
- Test metadata read/write
- Test file utilities
- Use temporary files/databases

```python
def test_add_token(test_db, sample_token_data):
    """Unit test pattern."""
    # Arrange
    token_id = test_db.add_token(sample_token_data)

    # Act
    token = test_db.get_token(token_id)

    # Assert
    assert token['filename'] == sample_token_data['filename']
```

### E2E Tests (tests/chrome/)
- Use Page Object Model pattern
- Test complete user workflows
- Verify UI, API, and database simultaneously
- Run headless in CI, headed for debugging

```python
def test_upload_single_png(chrome_driver, base_url, sample_png_path, test_db):
    """E2E test pattern with multi-level verification."""
    main_page = MainPage(chrome_driver, base_url)
    main_page.open()

    # Interact with UI
    main_page.click_upload_button()
    upload_modal.upload_with_type(sample_png_path, 'Token')

    # Verify UI updated
    assert "1 token" in main_page.get_token_count()

    # Verify database
    tokens = test_db.get_all_tokens()
    assert len(tokens) == 1
```

### Test Fixtures (conftest.py)
- `test_db`: Fresh SQLite database
- `temp_dir`: Temporary directory for files
- `sample_png_path`: Test PNG file
- `populated_test_db`: Database with sample tokens
- `chrome_driver`: Selenium WebDriver instance
- `test_server`: Flask server on port 5001

---

## Integration Points

### Desktop Shell (pywebview)
- `desktop.py` starts Flask in a daemon thread, polls `/api/version`, then
  opens a native `pywebview` window at the local URL
- `window.pywebview.api.*` is the JS↔Python bridge (replaced `window.electronAPI`):
  - `open_file_dialog()` - native file picker returning real absolute paths
  - `show_item_in_folder(filepath)` - reveal in Finder/Explorer/file manager
  - `open_file(filepath)` - open in the OS default application
- Frontend feature-detects `window.pywebview` (replaced `isElectron`)
- No subprocess/SIGTERM lifecycle: Flask dies with the process on window close

> Note: Google Drive sync was removed (#24). There is no OAuth/`credentials.json`
> flow anymore; all state is local.

### Thumbnail Caching
- `/api/thumbnail/<id>` - Serve cached thumbnails
- Cached in `./thumbnails/` folder
- 150x150 JPEG images
- Auto-regenerate if missing or file modified

---

## API Endpoints

### Tokens
- `GET /api/tokens` - List with filters (search, image_type, species, class, source, campaign, sort_by, sort_order)
- `GET /api/tokens/<id>` - Single token details
- `PUT /api/tokens/<id>` - Update metadata
- `DELETE /api/tokens/<id>` - Delete token
- `POST /api/tokens/upload` - Upload new images
- `POST /api/tokens/bulk-update` - Batch updates
- `POST /api/tokens/bulk-delete` - Batch deletes

### Tags & Stats
- `GET /api/tags/<type>` - Get unique tag values (species, class, source, campaign)
- `GET /api/stats` - Database statistics
- `POST /api/scan` - Manual rescan

### Images
- `GET /api/thumbnail/<id>` - Thumbnail image (150x150)
- `GET /api/image/<id>` - Full-resolution image

### PDFs (Reference Mode)
- `GET /api/pdfs` - List with filters (search, image_type, source, campaign, sort_by, sort_order)
- `GET /api/pdfs/<id>` - Single PDF details
- `PUT /api/pdfs/<id>` - Update metadata (Name, ImageType, Source, Campaign, Notes)
- `DELETE /api/pdfs/<id>` - Delete PDF
- `POST /api/pdfs/add-reference` - Add a PDF by path (desktop Reference Mode)
- `GET /api/pdf/<id>` - Serve the raw PDF (browser fallback for opening)
- `GET /api/pdf-thumbnail/<id>` - Cover thumbnail rendered from page 1 (150x150)
- `GET /api/pdfs/tags/<tag_type>` - Get unique tag values (source, campaign)
- `GET /api/pdfs/stats` - PDF statistics

---

## Deployment Notes

### Web Deployment
1. Install Python dependencies: `pip install -r requirements.txt`
2. Set environment variables (if needed)
3. Run Flask: `python3 app.py --port 5000`
4. Access at `http://localhost:5000`

### Desktop Packaging
1. Install dependencies: `pip install -r requirements.txt`
2. (Optional) Build a wheel: `uv build`
3. Freeze the app: `pyinstaller image-vault.spec`
4. Standalone artifact in `dist/` (`Image Vault.app` on macOS), no Python needed to run it

### Configuration (config.json)
```json
{
  "port": 5000,
  "tokens_folder": "./tokens",
  "thumbnails_folder": "./thumbnails",
  "thumbnail_size": [150, 150],
  "auto_scan": true,
  "watch_folders": true
}
```

---

## Performance Considerations

### Database Indexes
- Indexed fields: image_type, species, class, source, campaign, filename
- Use filters in queries to leverage indexes
- Avoid full table scans

### Thumbnail Strategy
- Generate thumbnails on first access
- Cache indefinitely (invalidate on file change)
- Use JPEG for thumbnails (smaller than PNG)

### File Watching
- Watchdog monitors folders for changes
- Debounce rapid changes (1-second delay)
- Can be disabled in config for performance

---

## Known Issues & Gotchas

### JPEG Limitations
- JPEG files cannot store metadata in text chunks
- Metadata stored only in database for JPEG
- Prefer PNG format for portability

### Duplicate Detection
- Based on file hash (SHA-256)
- Hash calculated on upload
- Filename collision handled separately

### Path Handling
- A browser/webview `File` object never carries a real filesystem path
- Use `window.pywebview.api.open_file_dialog()` to get real absolute paths
- Always use absolute paths in Reference Mode; convert appropriately for display

---

## Future Improvements

### Planned Features
- [ ] Advanced search with boolean operators
- [ ] Batch image editing (crop, resize)
- [ ] Collection/folder organization
- [ ] Export to VTT platforms (Roll20, Foundry)
- [ ] Tagging shortcuts and presets
- [ ] Image comparison/deduplication UI
- [ ] Mobile-responsive design improvements

### Technical Debt
- [ ] Add database migrations system
- [ ] Improve error handling in frontend
- [ ] Add loading skeletons instead of spinners
- [ ] Implement proper logging configuration
- [ ] Add API rate limiting
- [ ] Code-sign/notarize the macOS artifact and set up a release pipeline (#30)

---

## Resources

### Documentation
- Flask: https://flask.palletsprojects.com/
- pywebview: https://pywebview.flowrl.com/
- PyInstaller: https://pyinstaller.org/
- Pillow: https://pillow.readthedocs.io/
- Selenium: https://www.selenium.dev/documentation/

### Project-Specific
- PNG Text Chunks: http://www.libpng.org/pub/png/spec/1.2/PNG-Chunks.html
- RPG Token Standards: https://roll20.net/

---

**Last Updated**: 2026-06-25
**Version**: 1.1
**Project Lead**: Todd Gerdy
