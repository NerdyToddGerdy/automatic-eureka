# Changelog

All notable changes to Image Vault are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [2.1.0] - 2026-03-15

Stability and polish release. All changes are internal improvements with no breaking changes.

### Fixed
- Electron DevTools panel no longer opens in production builds. Gated on `NODE_ENV=development` or `DEBUG_DEVTOOLS=1` env var. (#4)
- Electron now reads the port from `config.json` and passes it consistently to both the Flask subprocess and the window URL. Changing the port no longer causes a blank window. (#5)
- Replaced the fixed 2-second startup delay with a health-check loop that polls `GET /api/version` (up to 6s). App loads as soon as Flask is ready; shows an error dialog if Flask never starts. (#6)
- Quitting the app now sends `SIGTERM` to Flask with a 3-second grace period before escalating to `SIGKILL`, preventing potential database corruption on close. (#7)
- Rapid filter or search changes no longer leave stale in-flight requests. Each `loadTokens()` call cancels the previous fetch via `AbortController`. (#9)

### Performance
- Added composite indexes on `(image_type, species)`, `(image_type, class)`, `(image_type, source)`, `(image_type, campaign)`, and `date_added DESC`. Queries filtering by type and tag now use optimal index paths. Existing databases gain the indexes automatically on next startup. (#12)

---

## [2.0.0] - 2026-03-15

Major architectural release. Image Vault is now a **Reference Mode only** Electron desktop application. Copy Mode, browser-based upload, and Google Drive sync have been removed to simplify the codebase and sharpen the focus on the desktop experience.

### Removed
- **Copy Mode** — files are no longer copied into a local `tokens/` folder. All assets are referenced in place from their original locations on disk.
- **Browser upload** — the drag-and-drop upload flow in the web UI is gone. File import now requires Electron so absolute file paths are available.
- **Google Drive sync** — Drive integration (OAuth flow, folder monitoring, bidirectional sync) removed. `drive_client.py` and `drive_sync.py` remain but are not activated.
- `token_folder` removed from `config.json`.
- `tokens/` and `thumbnails/` removed from version control (now in `.gitignore`).
- Sample token and thumbnail artifacts removed from the repository.

### Changed
- `initialize_app()` simplified — no longer initialises the folder watcher or Copy Mode path logic.
- `scanner.py` — `token_folder` is now optional; scanner handles the Reference Mode-only case gracefully.
- Tag values deduplicated case-insensitively in `get_tag_values()` (`_dedupe_case_insensitive()` added to `database.py`).
- All documentation and dev-guide commands standardised to `python3`.
- Electron main process gains global EPIPE error handlers to suppress broken-pipe noise on macOS.

### Fixed
- Gallery filters (image type, species, class, source, campaign) now apply correctly after switching values.
- Upload modal now populates type-specific tag fields when an image type is selected.

### Added
- `APP_VERSION = "2.0.0"` constant in `app.py`.
- `GET /api/version` endpoint — returns `{ "version": "2.0.0" }`.
- `LICENSE` file (MIT).

---

## [1.1.0] - 2025-12

### Added
- Audio file support (MP3, WAV, OGG, M4A, FLAC) — indexing, tagging, and streaming playback.
- Audio type schemas: Music, SoundEffect, Ambience, Dialogue with type-specific tag fields.
- `GET /api/audio`, `GET /api/audio/<id>`, `GET /api/audio/stream/<id>` endpoints.
- Multi-select batch import wizard in Electron — assign type and tags to groups of files before adding.
- Case-insensitive tag autocomplete scoped to the selected image type.
- In-memory + disk thumbnail cache (`cache.py`).

### Fixed
- Duplicate file detection by SHA-256 hash now correctly handles same-content / different-name files.
- Missing file indicator shown on token cards when the source file has moved or been deleted.

---

## [1.0.0] - 2025-09

Initial release of Image Vault as an Electron desktop application wrapping a Flask backend.

### Added
- Flask backend with SQLite index (`database.py`).
- PNG metadata storage via Pillow text chunks — tags embedded directly in image files as source of truth (`metadata.py`).
- Reference Mode — files indexed in place from their original locations on disk.
- Electron desktop wrapper with secure preload bridge (`electron/main.js`, `electron/preload.js`).
- Folder scanner with Watchdog file-watcher for automatic re-indexing (`scanner.py`).
- Six image types with type-specific tag schemas: Token, Map, Handout, Portrait, Scene, Item.
- Token gallery with filtering by image type, species, class, source, and campaign.
- Single-item edit modal with dynamic type-specific tag fields.
- Bulk edit and bulk delete for multi-selected tokens.
- Thumbnail generation and caching (150×150 JPEG).
- Full REST API: `GET /api/tokens`, `PUT /api/tokens/<id>`, `DELETE /api/tokens/<id>`, and more.
- Dark fantasy UI theme.

---

[Unreleased]: https://github.com/NerdyToddGerdy/automatic-eureka/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/NerdyToddGerdy/automatic-eureka/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/NerdyToddGerdy/automatic-eureka/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/NerdyToddGerdy/automatic-eureka/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/NerdyToddGerdy/automatic-eureka/releases/tag/v1.0.0
