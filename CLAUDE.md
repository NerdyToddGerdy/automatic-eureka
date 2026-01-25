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
python app.py

# Start with specific port
python app.py --port 5000

# Development mode with debug
FLASK_ENV=development python app.py

# Start Electron (desktop mode)
npm start
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
# Install Node dependencies
npm install

# Build Electron app
npm run build

# Package for distribution
npm run dist
```

### Database Operations
```bash
# The app auto-creates tokens.db on first run
# No manual migrations needed for SQLite

# To reset database, delete and restart
rm tokens.db
python app.py
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
├── drive_client.py        # Google Drive API wrapper
├── drive_sync.py          # Google Drive synchronization
├── config.json            # Application configuration
├── templates/
│   └── index.html         # Single-page application UI
├── static/
│   ├── js/app.js          # Frontend logic & state management
│   └── css/style.css      # Dark fantasy theme styling
├── electron/
│   ├── main.js            # Electron process launcher
│   └── preload.js         # Secure Electron bridge
└── tests/
    ├── test_*.py          # Unit tests
    └── chrome/            # E2E tests (Page Object Model)
```

### Key Architectural Decisions

#### 1. Dual-Mode Architecture
**Reference Mode (Electron)**:
- Files stay in original locations
- Database maintains file paths
- No copying or duplication
- Recommended for large collections

**Copy Mode (Browser)**:
- Files copied to `./tokens/` folder
- Centralized vault approach
- Traditional file management

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
- **Google APIs** - OAuth2 and Drive integration

### Frontend
- **Vanilla JavaScript** (ES6+) - No frameworks
- **HTML5/CSS3** - Responsive design
- **Electron 32.0.0** - Desktop wrapper

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
# Use absolute paths in Reference Mode
# Use relative paths in Copy Mode
if is_reference_mode:
    token_data['filepath'] = os.path.abspath(filepath)
else:
    token_data['filepath'] = os.path.relpath(filepath, tokens_folder)
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

### ❌ Forgetting Electron Context
```javascript
// DON'T: Use browser-only APIs without checking
const path = file.path;  // Undefined in browser!

// DO: Check for Electron environment
if (window.electronAPI) {
    const path = window.electronAPI.getFileAbsolutePath(file);
}
```

---

## Testing Guidelines

### Unit Tests (tests/)
- Test database operations (CRUD, filtering, sorting)
- Test metadata read/write
- Test file utilities
- Mock external dependencies (Google Drive)
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

### Google Drive Sync
- Optional feature (requires OAuth setup)
- Uses `credentials.json` for OAuth flow
- Stores tokens in local storage (browser) or file (Electron)
- Monitors specific Drive folders
- Bidirectional sync with conflict resolution

### Electron Integration
- `preload.js` provides secure bridge to Node.js
- `window.electronAPI.isElectron` - Detect environment
- `window.electronAPI.getFileAbsolutePath(file)` - Get file path
- Flask server launched as subprocess in Electron
- OAuth tokens passed via environment variables

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

---

## Deployment Notes

### Web Deployment
1. Install Python dependencies: `pip install -r requirements.txt`
2. Set environment variables (if needed)
3. Run Flask: `python app.py --port 5000`
4. Access at `http://localhost:5000`

### Electron Packaging
1. Install Node dependencies: `npm install`
2. Build: `npm run build`
3. Package: `npm run dist`
4. Distributable in `dist/` folder

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

### Electron Path Handling
- Relative paths don't work in Electron file dialogs
- Always use absolute paths in Reference Mode
- Convert paths appropriately for display

### Google Drive Sync
- Requires user OAuth consent
- Rate limits apply (use exponential backoff)
- Large images may timeout (compress before upload)

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
- [ ] Improve Google Drive sync reliability

---

## Resources

### Documentation
- Flask: https://flask.palletsprojects.com/
- Electron: https://www.electronjs.org/
- Pillow: https://pillow.readthedocs.io/
- Selenium: https://www.selenium.dev/documentation/

### Project-Specific
- PNG Text Chunks: http://www.libpng.org/pub/png/spec/1.2/PNG-Chunks.html
- RPG Token Standards: https://roll20.net/

---

**Last Updated**: 2026-01-08
**Version**: 1.0
**Project Lead**: Todd Gerdy
