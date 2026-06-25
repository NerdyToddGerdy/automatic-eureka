from flask import Flask, render_template, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import sys
import json
from datetime import datetime
from PIL import Image
import hashlib
import argparse
from typing import Optional
import io
from platformdirs import user_data_dir

from database import TokenDatabase
from metadata import TokenMetadata
from scanner import TokenScanner
from file_utils import calculate_file_hash_from_bytes, safe_file_op, FileOpTimeout
from cache import get_image_cache


def get_app_dir() -> str:
    """
    Base directory for bundled assets (templates/, static/).

    Resolved against the script's own location rather than the process's
    cwd, since a packaged app's cwd is wherever the user launched it from
    (or a PyInstaller onefile temp extraction dir), not the install dir.
    """
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_user_data_dir() -> str:
    """Base directory for user state (config.json, tokens.db default)."""
    path = user_data_dir('ImageTagger', appauthor=False)
    os.makedirs(path, exist_ok=True)
    return path


APP_DIR = get_app_dir()
USER_DATA_DIR = get_user_data_dir()

app = Flask(
    __name__,
    template_folder=os.path.join(APP_DIR, 'templates'),
    static_folder=os.path.join(APP_DIR, 'static'),
)
CORS(app)

APP_VERSION = "2.1.0"

# Configuration
CONFIG_FILE = os.path.join(USER_DATA_DIR, 'config.json')
DEFAULT_CONFIG = {
    'thumbnail_size': [150, 150],
    'watch_folder': True,
    'port': 5000,
    'host': '127.0.0.1',
    'file_io_timeout_seconds': 5
}

PLACEHOLDER_THUMBNAIL_PATH = os.path.join(APP_DIR, 'static', 'img', 'missing.png')

config = DEFAULT_CONFIG.copy()

# Tag schemas for different image types
TAG_SCHEMAS = {
    'Token': ['Species', 'Class', 'Source', 'Campaign'],
    'Map': ['Scale', 'Theme', 'Source', 'Campaign'],
    'Handout': ['Type', 'Source', 'Campaign'],
    'Portrait': ['Subject', 'Style', 'Source', 'Campaign'],
    'Scene': ['Location', 'Mood', 'Source', 'Campaign'],
    'Item': ['Rarity', 'Category', 'Attunement', 'Source', 'Campaign']
}

IMAGE_TYPES = ['Token', 'Map', 'Handout', 'Portrait', 'Scene', 'Item']

# Audio file support
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}

# Tag schemas for different audio types
AUDIO_TAG_SCHEMAS = {
    'Music': ['Genre', 'Mood', 'Source', 'Campaign'],
    'SoundEffect': ['Intensity', 'Location', 'Source', 'Campaign'],
    'Ambience': ['Mood', 'Intensity', 'Location', 'Source', 'Campaign'],
    'Dialogue': ['Character', 'Source', 'Campaign']
}

AUDIO_TYPES = ['Music', 'SoundEffect', 'Ambience', 'Dialogue']

# PDF file support
PDF_EXTENSIONS = {'.pdf'}

# Global objects
db = None
scanner = None
image_cache = None


def is_supported_image(filepath: str) -> bool:
    """Check if file is PNG or JPEG."""
    lower = filepath.lower()
    return lower.endswith(('.png', '.jpg', '.jpeg'))


def is_supported_audio(filepath: str) -> bool:
    """Check if file is a supported audio format."""
    lower = filepath.lower()
    return any(lower.endswith(ext) for ext in AUDIO_EXTENSIONS)


def get_audio_metadata(filepath: str) -> Optional[dict]:
    """
    Get audio file metadata using tinytag.

    Args:
        filepath: Path to the audio file

    Returns:
        Dictionary with audio metadata or None on error
    """
    try:
        from tinytag import TinyTag
        tag = TinyTag.get(filepath)

        return {
            'duration_seconds': tag.duration,
            'format': os.path.splitext(filepath)[1][1:].upper(),
            'file_size': os.path.getsize(filepath),
            'bitrate': tag.bitrate,
            'samplerate': tag.samplerate,
            'channels': tag.channels,
            'title': tag.title,
            'artist': tag.artist,
            'album': tag.album
        }
    except Exception as e:
        print(f"Error reading audio metadata for {filepath}: {e}")
        return None


def is_supported_pdf(filepath: str) -> bool:
    """Check if file is a PDF."""
    lower = filepath.lower()
    return any(lower.endswith(ext) for ext in PDF_EXTENSIONS)


def get_pdf_metadata(filepath: str) -> Optional[dict]:
    """
    Get PDF metadata using PyMuPDF.

    Args:
        filepath: Path to the PDF file

    Returns:
        Dictionary with page_count and file_size, or None on error
    """
    try:
        import fitz
        with fitz.open(filepath) as doc:
            return {
                'page_count': doc.page_count,
                'file_size': os.path.getsize(filepath)
            }
    except Exception as e:
        print(f"Error reading PDF metadata for {filepath}: {e}")
        return None


def load_config():
    """Load configuration from file or create default."""
    global config

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded_config = json.load(f)
                config.update(loaded_config)
                print(f"Loaded configuration from {CONFIG_FILE}")
        except Exception as e:
            print(f"Error loading config: {e}. Using defaults.")
    else:
        # Create default config file
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"Created default configuration at {CONFIG_FILE}")


def save_config():
    """Save current configuration to file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def initialize_app():
    """Initialize the application components."""
    global db, scanner, image_cache

    load_config()

    # Initialize database
    db = TokenDatabase(os.environ.get('DB_PATH', os.path.join(USER_DATA_DIR, 'tokens.db')))

    # Initialize image cache (100MB default)
    image_cache = get_image_cache(max_size_mb=100)
    print("✓ Image cache initialized (100MB)")

    # Initialize scanner (Reference Mode - no local token folder needed)
    scanner = TokenScanner(database=db, file_io_timeout=get_file_io_timeout())
    print("✓ Scanner initialized (Reference Mode - files stay in original locations)")


def get_file_io_timeout() -> int:
    """Configured per-file-operation timeout in seconds (default 5)."""
    return config.get('file_io_timeout_seconds', 5)


def get_placeholder_thumbnail_bytes() -> Optional[bytes]:
    """Read the static placeholder thumbnail shown for missing/unreachable files."""
    try:
        with open(PLACEHOLDER_THUMBNAIL_PATH, 'rb') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading placeholder thumbnail: {e}")
        return None


def _read_image_thumbnail(filepath: str, size: tuple) -> bytes:
    from io import BytesIO

    with Image.open(filepath) as img:
        img.thumbnail(size, Image.Resampling.LANCZOS)

        buffer = BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)

        return buffer.getvalue()


def generate_thumbnail_in_memory(filepath: str, size: tuple = (150, 150)) -> Optional[bytes]:
    """
    Generate a thumbnail in-memory and return as bytes.

    Raises FileOpTimeout if the file is unreachable within the configured
    timeout, so callers can distinguish "network hiccup" (show a
    placeholder, mark missing) from "not a valid image" (None - fall back
    to serving the original file, as before).
    """
    try:
        return safe_file_op(_read_image_thumbnail, filepath, size, timeout=get_file_io_timeout())
    except FileOpTimeout:
        raise
    except Exception as e:
        print(f"Error generating in-memory thumbnail for {filepath}: {e}")
        return None


def _read_pdf_thumbnail(filepath: str, size: tuple) -> bytes:
    import fitz
    from io import BytesIO

    with fitz.open(filepath) as doc:
        page = doc.load_page(0)
        zoom = 96 / 72
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))

        img = Image.open(BytesIO(pix.tobytes('png')))
        img.thumbnail(size, Image.Resampling.LANCZOS)

        buffer = BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)

        return buffer.getvalue()


def generate_pdf_thumbnail_in_memory(filepath: str, size: tuple = (150, 150)) -> Optional[bytes]:
    """
    Render page 1 of a PDF to a thumbnail in-memory and return as PNG bytes.

    Raises FileOpTimeout if the file is unreachable within the configured
    timeout (see generate_thumbnail_in_memory for why this is distinct
    from a None return).
    """
    try:
        return safe_file_op(_read_pdf_thumbnail, filepath, size, timeout=get_file_io_timeout())
    except FileOpTimeout:
        raise
    except Exception as e:
        print(f"Error generating PDF thumbnail for {filepath}: {e}")
        return None


def _timeout_response(mimetype: str = 'image/png', use_placeholder: bool = False):
    """Standard response for a file that timed out: a placeholder image (thumbnails) or a 503."""
    if use_placeholder:
        placeholder = get_placeholder_thumbnail_bytes()
        if placeholder:
            return send_file(io.BytesIO(placeholder), mimetype=mimetype, as_attachment=False)
    return jsonify({'success': False, 'error': 'File temporarily unreachable (network timeout)'}), 503


def serialize_token(token, db_instance):
    """Convert database token row to API response format."""
    serialized = dict(token)

    # Split multi-value Theme for Maps
    if serialized.get('image_type') == 'Map' and serialized.get('theme'):
        serialized['theme'] = db_instance.parse_multivalue_field(serialized['theme'])

    return serialized


# Web Routes

@app.route('/')
def index():
    """Serve the main application page."""
    return render_template('index.html')


@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files."""
    return send_from_directory(os.path.join(APP_DIR, 'static'), path)


# API Endpoints

@app.route('/api/tokens', methods=['GET'])
def get_tokens():
    """
    Get all tokens with optional filtering and sorting.

    Query parameters:
        - image_type: Filter by image type
        - species: Filter by species
        - class: Filter by class
        - source: Filter by source
        - campaign: Filter by campaign
        - search: Search term for name/filename
        - sort_by: Field to sort by (default: filename)
        - sort_order: ASC or DESC (default: ASC)
    """
    try:
        # Get query parameters
        search = request.args.get('search')
        sort_by = request.args.get('sort_by', 'filename')
        sort_order = request.args.get('sort_order', 'ASC')

        # Build filters - handle comma-separated multi-values
        filters = {}
        multi_value_fields = ['species', 'class', 'theme', 'source', 'campaign']

        for field in multi_value_fields:
            value = request.args.get(field)
            if value:
                # Split comma-separated values
                filters[field] = [v.strip() for v in value.split(',') if v.strip()]

        # Image type is still single-select
        image_type = request.args.get('image_type')
        if image_type:
            filters['image_type'] = image_type

        # Get tokens - combine search with filters
        tokens = db.get_all_tokens_with_multi_filters(
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            search_term=search
        )

        # Serialize tokens to handle multi-value fields
        serialized_tokens = [serialize_token(t, db) for t in tokens]

        return jsonify({
            'success': True,
            'tokens': serialized_tokens,
            'count': len(serialized_tokens)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tokens/<int:token_id>', methods=['GET'])
def get_token(token_id):
    """Get a single token by ID."""
    try:
        token = db.get_token(token_id)

        if token:
            return jsonify({'success': True, 'token': serialize_token(token, db)})
        else:
            return jsonify({'success': False, 'error': 'Token not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tokens/<int:token_id>', methods=['PUT'])
def update_token(token_id):
    """
    Update a token's metadata.

    Body should contain metadata fields to update.
    """
    try:
        data = request.get_json()

        # Get the token
        token = db.get_token(token_id)
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404

        # Update database FIRST (database is source of truth)
        update_data = {}
        for field in ['Name', 'ImageType', 'Species', 'Class', 'Source', 'Campaign', 'Notes',
                     'Scale', 'Theme', 'Type', 'Subject', 'Style', 'Location', 'Mood',
                     'Rarity', 'Category', 'Attunement']:
            if field in data:
                value = data[field]

                # Handle Theme for Maps as multi-value
                if field == 'Theme' and data.get('ImageType') == 'Map':
                    if isinstance(value, list):
                        value = db.format_multivalue_field(value)

                update_data[field] = value

        if update_data:
            # Update database first (database is source of truth)
            if not db.update_token(token_id, update_data):
                return jsonify({'success': False, 'error': 'Failed to update database'}), 500

            # Mirror to PNG (best effort)
            try:
                current_metadata = TokenMetadata.read_token_metadata(token['filepath'])
                current_metadata.update(update_data)

                if not TokenMetadata.write_token_metadata(token['filepath'], current_metadata):
                    print(f"⚠ Warning: Failed to write metadata to PNG for {token['filepath']}")
                    # Don't fail the request - database is source of truth

            except Exception as png_error:
                print(f"⚠ Warning: Failed to update PNG metadata: {png_error}")
                # Don't fail the request - database is source of truth

            updated_token = db.get_token(token_id)
            return jsonify({'success': True, 'token': serialize_token(updated_token, db)})
        else:
            return jsonify({'success': False, 'error': 'No fields to update'}), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tokens/<int:token_id>', methods=['DELETE'])
def delete_token(token_id):
    """Delete a token and its file."""
    try:
        token = db.get_token(token_id)
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404

        # Delete the file
        def _remove_if_exists():
            if os.path.exists(token['filepath']):
                os.remove(token['filepath'])

        try:
            safe_file_op(_remove_if_exists, timeout=get_file_io_timeout())
        except FileOpTimeout:
            print(f"Timeout removing file (possible network issue): {token['filepath']}")

        # Delete from database
        if db.delete_token(token_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete from database'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tokens/<int:token_id>/update-path', methods=['POST'])
def update_token_path(token_id):
    """
    Update the file path for a token (for repairing broken references).
    Verifies the new file exists and updates the database.
    """
    try:
        data = request.get_json()
        new_filepath = data.get('filepath')

        if not new_filepath:
            return jsonify({'success': False, 'error': 'filepath is required'}), 400

        # Get existing token
        token = db.get_token(token_id)
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404

        # Verify new file exists
        try:
            new_file_exists = safe_file_op(os.path.exists, new_filepath, timeout=get_file_io_timeout())
        except FileOpTimeout:
            return jsonify({'success': False, 'error': 'File could not be accessed (network timeout)'}), 503

        if not new_file_exists:
            return jsonify({'success': False, 'error': 'File does not exist at specified path'}), 400

        # Verify it's a supported image file
        if not is_supported_image(new_filepath):
            return jsonify({'success': False, 'error': 'File must be a PNG or JPEG image'}), 400

        # Get current token data
        from metadata import TokenMetadata
        file_info = TokenMetadata.get_file_info(new_filepath)

        if file_info is None:
            return jsonify({'success': False, 'error': 'Unable to read file metadata'}), 400

        # Update filepath in token data
        token.update(file_info)

        # Update database
        if db.update_token(token_id, token):
            # Mark as not missing and update verification timestamp
            from datetime import datetime
            db.mark_missing(token_id, False)
            db.update_last_verified(token_id, datetime.now().isoformat())

            # Calculate and update hash
            from file_utils import calculate_file_hash
            try:
                file_hash = calculate_file_hash(new_filepath)
                db.update_file_hash(token_id, file_hash)
            except:
                pass  # Hash update is optional

            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to update database'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tokens/upload', methods=['POST'])
def upload_tokens():
    """
    Legacy upload endpoint - browser mode is no longer supported.
    Use /api/tokens/add-reference instead (Electron desktop app required).
    """
    return jsonify({
        'success': False,
        'error': 'Browser upload mode is no longer supported. Please use the Electron desktop app with reference mode. Use /api/tokens/add-reference to add files by path.'
    }), 400


@app.route('/api/tokens/check-duplicates', methods=['POST'])
def check_duplicates():
    """
    Check uploaded files for duplicates WITHOUT saving them.
    Accepts either multipart files or JSON with file paths.
    Returns duplicate information for each file.
    """
    try:
        from file_utils import calculate_file_hash, find_duplicates
        import tempfile

        duplicates_found = []

        # Handle multipart file upload
        if 'files' in request.files:
            files = request.files.getlist('files')

            for file in files:
                if not file or not is_supported_image(file.filename):
                    continue

                # Determine file extension for temporary file
                ext = '.png'
                if file.filename.lower().endswith('.jpg'):
                    ext = '.jpg'
                elif file.filename.lower().endswith('.jpeg'):
                    ext = '.jpeg'

                # Save to temporary location to calculate hash
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    file.save(tmp.name)
                    tmp_path = tmp.name

                try:
                    # Calculate hash
                    file_hash = calculate_file_hash(tmp_path)

                    # Check for duplicates
                    dup_info = find_duplicates(db, tmp_path, file_hash)

                    duplicates_found.append({
                        'filename': file.filename,
                        'hash': file_hash,
                        'content_duplicate': dup_info['content_duplicate'],
                        'name_collision': dup_info['name_collision']
                    })

                finally:
                    # Clean up temp file
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)

        # Handle JSON with file paths
        elif request.is_json:
            data = request.get_json()
            filepaths = data.get('filepaths', [])

            for filepath in filepaths:
                try:
                    file_exists = safe_file_op(os.path.exists, filepath, timeout=get_file_io_timeout())
                except FileOpTimeout:
                    duplicates_found.append({
                        'filename': os.path.basename(filepath),
                        'error': 'File could not be accessed (network timeout)',
                        'hash': None,
                        'content_duplicate': None,
                        'name_collision': None
                    })
                    continue

                if not file_exists:
                    duplicates_found.append({
                        'filename': os.path.basename(filepath),
                        'error': 'File not found',
                        'hash': None,
                        'content_duplicate': None,
                        'name_collision': None
                    })
                    continue

                try:
                    # Calculate hash
                    file_hash = safe_file_op(calculate_file_hash, filepath, timeout=get_file_io_timeout())

                    # Check for duplicates
                    dup_info = find_duplicates(db, filepath, file_hash)

                    duplicates_found.append({
                        'filename': os.path.basename(filepath),
                        'filepath': filepath,
                        'hash': file_hash,
                        'content_duplicate': dup_info['content_duplicate'],
                        'name_collision': dup_info['name_collision']
                    })

                except Exception as e:
                    duplicates_found.append({
                        'filename': os.path.basename(filepath),
                        'error': str(e),
                        'hash': None,
                        'content_duplicate': None,
                        'name_collision': None
                    })

        else:
            return jsonify({'success': False, 'error': 'No files or filepaths provided'}), 400

        return jsonify({
            'success': True,
            'duplicates': duplicates_found
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tokens/add-reference', methods=['POST'])
def add_file_reference():
    """
    Add file reference without copying the file.
    Stores a reference to the file in its original location.
    """
    try:
        from file_utils import calculate_file_hash, get_file_info_summary
        from metadata import TokenMetadata
        from datetime import datetime

        data = request.get_json()
        filepath = data.get('filepath')
        overwrite_existing = data.get('overwrite_existing', False)
        image_type = data.get('image_type', 'Token')  # Get image type from request

        # Validate image type
        if image_type not in IMAGE_TYPES:
            image_type = 'Token'  # Fallback to default

        # Extract tag values from request data
        tag_fields = ['Species', 'Class', 'Source', 'Campaign',  # Token
                      'Scale', 'Theme',                           # Map
                      'Type',                                      # Handout
                      'Subject', 'Style',                          # Portrait
                      'Location', 'Mood',                          # Scene
                      'Rarity', 'Category', 'Attunement']          # Item

        tag_values = {}
        for tag_field in tag_fields:
            value = data.get(tag_field)
            if value:  # Only include non-empty values
                tag_values[tag_field] = value

        if not filepath:
            return jsonify({'success': False, 'error': 'No filepath provided'}), 400

        try:
            file_exists = safe_file_op(os.path.exists, filepath, timeout=get_file_io_timeout())
        except FileOpTimeout:
            return jsonify({'success': False, 'error': 'File could not be accessed (network timeout)'}), 503

        if not file_exists:
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Calculate hash
        try:
            file_hash = safe_file_op(calculate_file_hash, filepath, timeout=get_file_io_timeout())
        except FileOpTimeout:
            return jsonify({'success': False, 'error': 'File could not be read (network timeout)'}), 503

        # Check for existing duplicate by hash
        existing = db.find_by_hash(file_hash)

        if existing and not overwrite_existing:
            return jsonify({
                'success': False,
                'error': 'Duplicate file exists',
                'existing_token': existing
            }), 409

        # Also check if filepath already exists in database (different hash = file was modified)
        existing_by_path = db.get_token_by_filepath(filepath)
        if existing_by_path and not overwrite_existing:
            # File already tracked - update instead of failing
            overwrite_existing = True
            existing = existing_by_path

        try:
            # Read metadata from PNG
            metadata = safe_file_op(TokenMetadata.read_token_metadata, filepath, timeout=get_file_io_timeout())

            # ALWAYS write metadata to PNG to keep DB and PNG in sync
            # Database is source of truth; PNG mirrors it
            metadata['ImageType'] = image_type

            # Add tag values to metadata
            for tag_key, tag_value in tag_values.items():
                if tag_value:
                    metadata[tag_key] = tag_value

            # Add DateAdded if not present (only for new files)
            if not existing and not metadata.get('DateAdded'):
                metadata['DateAdded'] = datetime.now().isoformat()

            # ALWAYS write updated metadata back to PNG
            if not safe_file_op(TokenMetadata.write_token_metadata, filepath, metadata, timeout=get_file_io_timeout()):
                print(f"Warning: Failed to write metadata to PNG for {filepath}")
                # Continue anyway - database update is more critical
        except FileOpTimeout:
            return jsonify({'success': False, 'error': 'File could not be read (network timeout)'}), 503

        try:
            file_modified = datetime.fromtimestamp(
                safe_file_op(os.path.getmtime, filepath, timeout=get_file_io_timeout())
            ).isoformat()
        except FileOpTimeout:
            return jsonify({'success': False, 'error': 'File could not be accessed (network timeout)'}), 503

        # Prepare token data
        token_data = {
            'filepath': filepath,
            'filename': os.path.basename(filepath),
            'Name': metadata.get('Name'),
            'ImageType': image_type,  # Use the selected type
            'Species': metadata.get('Species'),
            'Class': metadata.get('Class'),
            'Source': metadata.get('Source'),
            'Campaign': metadata.get('Campaign'),
            'Notes': metadata.get('Notes'),
            'DateAdded': metadata.get('DateAdded'),
            'file_modified': file_modified,
            'Scale': metadata.get('Scale'),
            'Theme': metadata.get('Theme'),
            'Type': metadata.get('Type'),
            'Subject': metadata.get('Subject'),
            'Style': metadata.get('Style'),
            'Location': metadata.get('Location'),
            'Mood': metadata.get('Mood'),
            'Rarity': metadata.get('Rarity'),
            'Category': metadata.get('Category'),
            'Attunement': metadata.get('Attunement')
        }

        # Add to database
        if overwrite_existing and existing:
            # Update existing entry
            success = db.update_token(existing['id'], token_data)
            token_id = existing['id']
        else:
            # Add new entry
            token_id = db.add_token(token_data)
            success = token_id is not None

        if success:
            # Update hash and verification
            if token_id:
                db.update_file_hash(token_id, file_hash)
                db.mark_missing(token_id, False)
                db.update_last_verified(token_id)

            return jsonify({
                'success': True,
                'token_id': token_id,
                'message': 'File reference added successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to add file reference'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tokens/add-references-batch', methods=['POST'])
def add_file_references_batch():
    """
    Add multiple file references with per-subfolder tag assignments.
    Handles the entire wizard result in one transaction.
    """
    try:
        from file_utils import calculate_file_hash
        from metadata import TokenMetadata
        from datetime import datetime

        data = request.get_json()
        subfolder_assignments = data.get('subfolder_assignments', [])

        if not subfolder_assignments:
            return jsonify({'success': False, 'error': 'No subfolder assignments provided'}), 400

        results = {
            'total_processed': 0,
            'added': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'timed_out': 0,
            'by_subfolder': {}
        }

        # Process each subfolder's files
        for assignment in subfolder_assignments:
            subfolder_path = assignment.get('subfolder_path')
            image_type = assignment.get('image_type', 'Token')
            tags = assignment.get('tags', {})
            files = assignment.get('files', [])

            subfolder_results = {
                'added': 0,
                'updated': 0,
                'skipped': 0,
                'errors': 0
            }

            for file_entry in files:
                filepath = file_entry.get('filepath')
                action = file_entry.get('action', 'add')
                new_filename = file_entry.get('new_filename')  # Optional rename

                results['total_processed'] += 1

                if action == 'skip':
                    results['skipped'] += 1
                    subfolder_results['skipped'] += 1
                    continue

                try:
                    if not safe_file_op(os.path.exists, filepath, timeout=get_file_io_timeout()):
                        results['errors'] += 1
                        subfolder_results['errors'] += 1
                        continue

                    # Calculate hash
                    file_hash = safe_file_op(calculate_file_hash, filepath, timeout=get_file_io_timeout())

                    # Check for existing
                    existing = db.find_by_hash(file_hash)
                    overwrite_existing = (action == 'overwrite')

                    # Read and update metadata
                    metadata = safe_file_op(TokenMetadata.read_token_metadata, filepath, timeout=get_file_io_timeout())
                    metadata['ImageType'] = image_type

                    # Apply tags from subfolder assignment
                    for tag_key, tag_value in tags.items():
                        if tag_value:
                            metadata[tag_key] = tag_value

                    # Add DateAdded if new
                    if not existing and not metadata.get('DateAdded'):
                        metadata['DateAdded'] = datetime.now().isoformat()

                    # Write metadata to PNG
                    safe_file_op(TokenMetadata.write_token_metadata, filepath, metadata, timeout=get_file_io_timeout())

                    # Determine filename: use new_filename if provided (rename case), otherwise use basename
                    display_filename = secure_filename(new_filename) if new_filename else os.path.basename(filepath)

                    # Prepare token data
                    token_data = {
                        'filepath': filepath,  # Original path stays the same (reference in place)
                        'filename': display_filename,  # Display name may be different for renames
                        'Name': metadata.get('Name'),
                        'ImageType': image_type,
                        'Species': metadata.get('Species'),
                        'Class': metadata.get('Class'),
                        'Source': metadata.get('Source'),
                        'Campaign': metadata.get('Campaign'),
                        'Notes': metadata.get('Notes'),
                        'DateAdded': metadata.get('DateAdded'),
                        'file_modified': datetime.fromtimestamp(
                            safe_file_op(os.path.getmtime, filepath, timeout=get_file_io_timeout())
                        ).isoformat(),
                        'Scale': metadata.get('Scale'),
                        'Theme': metadata.get('Theme'),
                        'Type': metadata.get('Type'),
                        'Subject': metadata.get('Subject'),
                        'Style': metadata.get('Style'),
                        'Location': metadata.get('Location'),
                        'Mood': metadata.get('Mood'),
                        'Rarity': metadata.get('Rarity'),
                        'Category': metadata.get('Category'),
                        'Attunement': metadata.get('Attunement')
                    }

                    # Add or update in database
                    if overwrite_existing and existing:
                        success = db.update_token(existing['id'], token_data)
                        token_id = existing['id']
                        if success:
                            results['updated'] += 1
                            subfolder_results['updated'] += 1
                    else:
                        token_id = db.add_token(token_data)
                        success = token_id is not None
                        if success:
                            results['added'] += 1
                            subfolder_results['added'] += 1

                    # Update hash and verification
                    if success and token_id:
                        db.update_file_hash(token_id, file_hash)
                        db.mark_missing(token_id, False)
                        db.update_last_verified(token_id)

                except FileOpTimeout:
                    print(f"Timeout accessing file (possible network issue): {filepath}")
                    results['timed_out'] += 1
                    subfolder_results['errors'] += 1
                except Exception as e:
                    print(f"Error processing {filepath}: {e}")
                    results['errors'] += 1
                    subfolder_results['errors'] += 1

            results['by_subfolder'][subfolder_path] = subfolder_results

        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tokens/scan-folder', methods=['POST'])
def scan_folder():
    """
    Scan a folder for PNG files without moving them.
    Returns list of found files with duplicate information.
    """
    try:
        from file_utils import calculate_file_hash, find_duplicates

        data = request.get_json()
        folder_path = data.get('folder_path')
        recursive = data.get('recursive', True)
        group_by_subfolder = data.get('group_by_subfolder', False)

        if not folder_path:
            return jsonify({'success': False, 'error': 'No folder_path provided'}), 400

        def _folder_is_valid():
            return os.path.exists(folder_path) and os.path.isdir(folder_path)

        try:
            folder_valid = safe_file_op(_folder_is_valid, timeout=get_file_io_timeout())
        except FileOpTimeout:
            return jsonify({'success': False, 'error': 'Folder could not be accessed (network timeout)'}), 503

        if not folder_valid:
            return jsonify({'success': False, 'error': 'Folder not found'}), 404

        files_found = []
        subfolder_groups = {}  # key: subfolder_path, value: list of files

        # Scan for PNG files
        if recursive:
            for root, dirs, files in os.walk(folder_path):
                for filename in files:
                    if is_supported_image(filename):
                        filepath = os.path.join(root, filename)

                        if group_by_subfolder:
                            # Group by immediate parent directory relative to root
                            relative_path = os.path.relpath(root, folder_path)
                            if relative_path == '.':
                                group_key = folder_path  # Root level files
                            else:
                                # Use first-level subfolder as group key
                                first_level = relative_path.split(os.sep)[0]
                                group_key = os.path.join(folder_path, first_level)

                            if group_key not in subfolder_groups:
                                subfolder_groups[group_key] = []
                            subfolder_groups[group_key].append(filepath)
                        else:
                            files_found.append(filepath)
        else:
            for filename in os.listdir(folder_path):
                filepath = os.path.join(folder_path, filename)
                if os.path.isfile(filepath) and is_supported_image(filename):
                    if group_by_subfolder:
                        group_key = folder_path
                        if group_key not in subfolder_groups:
                            subfolder_groups[group_key] = []
                        subfolder_groups[group_key].append(filepath)
                    else:
                        files_found.append(filepath)

        # Process results based on grouping mode
        if group_by_subfolder:
            # Build subfolder structure with duplicate checks
            subfolders = []
            for subfolder_path, file_list in subfolder_groups.items():
                files_with_duplicates = []
                for filepath in file_list:
                    try:
                        file_hash = calculate_file_hash(filepath)
                        dup_info = find_duplicates(db, filepath, file_hash)

                        files_with_duplicates.append({
                            'filepath': filepath,
                            'filename': os.path.basename(filepath),
                            'hash': file_hash,
                            'content_duplicate': dup_info['content_duplicate'],
                            'name_collision': dup_info['name_collision']
                        })
                    except Exception as e:
                        files_with_duplicates.append({
                            'filepath': filepath,
                            'filename': os.path.basename(filepath),
                            'error': str(e),
                            'hash': None,
                            'content_duplicate': None,
                            'name_collision': None
                        })

                # Get relative display name for subfolder
                if subfolder_path == folder_path:
                    display_name = "(Root folder)"
                else:
                    display_name = os.path.relpath(subfolder_path, folder_path)

                subfolders.append({
                    'path': subfolder_path,
                    'display_name': display_name,
                    'file_count': len(file_list),
                    'files': files_with_duplicates
                })

            return jsonify({
                'success': True,
                'folder': folder_path,
                'grouped_by_subfolder': True,
                'subfolder_count': len(subfolders),
                'total_files': sum(len(sf['files']) for sf in subfolders),
                'subfolders': subfolders
            })
        else:
            # Original flat list behavior (backwards compatible)
            results = []
            for filepath in files_found:
                try:
                    file_hash = calculate_file_hash(filepath)
                    dup_info = find_duplicates(db, filepath, file_hash)

                    results.append({
                        'filepath': filepath,
                        'filename': os.path.basename(filepath),
                        'hash': file_hash,
                        'content_duplicate': dup_info['content_duplicate'],
                        'name_collision': dup_info['name_collision']
                    })

                except Exception as e:
                    results.append({
                        'filepath': filepath,
                        'filename': os.path.basename(filepath),
                        'error': str(e),
                        'hash': None,
                        'content_duplicate': None,
                        'name_collision': None
                    })

            return jsonify({
                'success': True,
                'folder': folder_path,
                'grouped_by_subfolder': False,
                'files_found': len(results),
                'results': results
            })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tokens/bulk-update', methods=['POST'])
def bulk_update_tokens():
    """Update multiple tokens at once."""
    try:
        data = request.get_json()
        token_ids = data.get('token_ids', [])
        updates = data.get('updates', {})

        results = {'updated': 0, 'errors': 0}

        for token_id in token_ids:
            token = db.get_token(token_id)
            if not token:
                results['errors'] += 1
                continue

            # Update PNG metadata
            metadata_updates = {k: v for k, v in updates.items()
                                if k in ['Name', 'ImageType', 'Species', 'Class', 'Source', 'Campaign', 'Notes',
                                        'Scale', 'Theme', 'Type', 'Subject', 'Style', 'Location', 'Mood',
                                        'Rarity', 'Category', 'Attunement']}

            if metadata_updates:
                if TokenMetadata.update_metadata(token['filepath'], metadata_updates):
                    # Update database from PNG
                    file_info = TokenMetadata.get_file_info(token['filepath'])
                    if db.update_token(token_id, file_info):
                        results['updated'] += 1
                    else:
                        results['errors'] += 1
                else:
                    results['errors'] += 1

        return jsonify({'success': True, 'results': results})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tokens/bulk-delete', methods=['POST'])
def bulk_delete_tokens():
    """Delete multiple tokens at once."""
    try:
        data = request.get_json()
        token_ids = data.get('token_ids', [])

        results = {'deleted': 0, 'errors': 0}

        for token_id in token_ids:
            token = db.get_token(token_id)
            if not token:
                results['errors'] += 1
                continue

            # Delete file
            def _remove_if_exists():
                if os.path.exists(token['filepath']):
                    os.remove(token['filepath'])

            try:
                safe_file_op(_remove_if_exists, timeout=get_file_io_timeout())
            except FileOpTimeout:
                print(f"Timeout removing file (possible network issue): {token['filepath']}")

            # Delete from database
            if db.delete_token(token_id):
                results['deleted'] += 1
            else:
                results['errors'] += 1

        return jsonify({'success': True, 'results': results})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tags/<tag_type>', methods=['GET'])
def get_tag_values(tag_type):
    """Get all unique values for a specific tag type."""
    try:
        values = db.get_tag_values(tag_type)
        return jsonify({'success': True, 'values': values})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/image-types', methods=['GET'])
def get_image_types():
    """Get list of valid image types."""
    return jsonify({'success': True, 'image_types': IMAGE_TYPES})


@app.route('/api/tag-schema/<image_type>', methods=['GET'])
def get_tag_schema(image_type):
    """Get tag schema for a specific image type."""
    try:
        if image_type not in TAG_SCHEMAS:
            return jsonify({'success': False, 'error': 'Invalid image type'}), 400

        return jsonify({'success': True, 'schema': TAG_SCHEMAS[image_type]})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tags/<image_type>/<tag_type>', methods=['GET'])
def get_tags_by_type(image_type, tag_type):
    """Get unique tag values filtered by image type."""
    try:
        values = db.get_tag_values_by_type(image_type, tag_type)
        return jsonify({'success': True, 'values': values})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tags/<field>/manage', methods=['GET'])
def get_tag_manage(field):
    """Get tag values with token counts for the tag manager."""
    try:
        valid_fields = ['species', 'class', 'source', 'campaign', 'scale', 'theme',
                        'type', 'subject', 'style', 'location', 'mood', 'rarity', 'category', 'attunement']
        if field not in valid_fields:
            return jsonify({'success': False, 'error': 'Invalid field'}), 400
        values = db.get_tag_value_counts(field)
        return jsonify({'success': True, 'values': values})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tags/<field>/rename', methods=['PUT'])
def rename_tag_value(field):
    """Rename a tag value across all tokens (DB + PNG metadata)."""
    try:
        valid_fields = ['species', 'class', 'source', 'campaign', 'scale', 'theme',
                        'type', 'subject', 'style', 'location', 'mood', 'rarity', 'category', 'attunement']
        if field not in valid_fields:
            return jsonify({'success': False, 'error': 'Invalid field'}), 400

        data = request.get_json()
        old_val = data.get('from', '').strip()
        new_val = data.get('to', '').strip()

        if not old_val or not new_val:
            return jsonify({'success': False, 'error': 'Both "from" and "to" values are required'}), 400
        if old_val == new_val:
            return jsonify({'success': False, 'error': 'Values are identical'}), 400

        affected = db.rename_tag_value(field, old_val, new_val)

        field_to_meta = {
            'species': 'Species', 'class': 'Class', 'source': 'Source',
            'campaign': 'Campaign', 'scale': 'Scale', 'theme': 'Theme',
            'type': 'Type', 'subject': 'Subject', 'style': 'Style',
            'location': 'Location', 'mood': 'Mood', 'rarity': 'Rarity',
            'category': 'Category', 'attunement': 'Attunement'
        }
        meta_key = field_to_meta[field]

        updated = 0
        failures = []
        for token in affected:
            filepath = token['filepath']
            try:
                if safe_file_op(os.path.exists, filepath, timeout=get_file_io_timeout()):
                    current = safe_file_op(TokenMetadata.read_token_metadata, filepath, timeout=get_file_io_timeout())
                    current[meta_key] = new_val
                    safe_file_op(TokenMetadata.write_token_metadata, filepath, current, timeout=get_file_io_timeout())
                updated += 1
            except Exception as e:
                app.logger.error(f"Failed to rewrite PNG {filepath}: {e}")
                failures.append(filepath)

        return jsonify({'success': True, 'updated': updated, 'errors': len(failures), 'failures': failures})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/scan', methods=['POST'])
def rescan():
    """Manually trigger a folder scan."""
    try:
        print("Starting local folder scan...")
        results = scanner.scan_and_sync()
        pdf_results = scanner.scan_pdfs_and_sync()

        response = {
            'success': True,
            'results': results,
            'mode': 'local'
        }

        timed_out = results.get('timed_out', 0) + pdf_results.get('timed_out', 0)
        if timed_out > 0:
            response['warning'] = f"{timed_out} file(s) could not be accessed (network timeout)"

        return jsonify(response)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/version', methods=['GET'])
def get_version():
    """Get application version."""
    return jsonify({'success': True, 'version': APP_VERSION})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get database statistics."""
    try:
        stats = db.get_stats()
        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/verify', methods=['POST'])
def verify_files():
    """
    Verify all file references in the database.
    Checks if files still exist at their stored paths.
    Updates is_missing flag for broken references.
    """
    try:
        results = scanner.verify_all_references()

        return jsonify({
            'success': True,
            'verified': results['verified'],
            'missing': results['missing'],
            'missing_count': len(results['missing']),
            'errors': results['errors']
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/thumbnail/<int:token_id>', methods=['GET'])
def get_thumbnail(token_id):
    """Generate and return thumbnail on-demand."""
    try:
        token = db.get_token(token_id)
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404

        filepath = token['filepath']

        try:
            file_exists = safe_file_op(os.path.exists, filepath, timeout=get_file_io_timeout())
        except FileOpTimeout:
            db.mark_missing(token_id, True)
            return _timeout_response('image/png', use_placeholder=True)

        if not file_exists:
            return jsonify({'success': False, 'error': 'Image file not found'}), 404

        # Generate thumbnail in-memory
        try:
            thumbnail_bytes = generate_thumbnail_in_memory(
                filepath,
                tuple(config.get('thumbnail_size', [150, 150]))
            )
        except FileOpTimeout:
            db.mark_missing(token_id, True)
            return _timeout_response('image/png', use_placeholder=True)

        if thumbnail_bytes is None:
            # Fallback: return original image
            return send_file(filepath, mimetype='image/png')

        # Return thumbnail from memory
        return send_file(
            io.BytesIO(thumbnail_bytes),
            mimetype='image/png',
            as_attachment=False,
            download_name=f'thumbnail_{token_id}.png'
        )

    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/image/<int:token_id>', methods=['GET'])
def get_image(token_id):
    """Get the full-size image for a token."""
    try:
        token = db.get_token(token_id)
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404

        filepath = token['filepath']

        # Detect MIME type based on file extension
        if filepath.lower().endswith('.png'):
            mimetype = 'image/png'
        elif filepath.lower().endswith(('.jpg', '.jpeg')):
            mimetype = 'image/jpeg'
        else:
            mimetype = 'image/png'  # default fallback

        try:
            file_exists = safe_file_op(os.path.exists, filepath, timeout=get_file_io_timeout())
        except FileOpTimeout:
            db.mark_missing(token_id, True)
            return _timeout_response(mimetype, use_placeholder=False)

        if not file_exists:
            return jsonify({'success': False, 'error': 'Image file not found'}), 404

        return send_file(filepath, mimetype=mimetype)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tokens/<int:token_id>/filepath', methods=['GET'])
def get_token_filepath(token_id):
    """Get the absolute file path for a token."""
    try:
        token = db.get_token(token_id)
        if not token:
            return jsonify({'success': False, 'error': 'Token not found'}), 404

        # Return absolute path
        absolute_path = os.path.abspath(token['filepath'])
        return jsonify({'success': True, 'filepath': absolute_path})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/export', methods=['GET'])
def export_inventory():
    """Export inventory metadata as JSON."""
    try:
        tokens = db.get_all_tokens()

        export_data = {
            'exported_at': datetime.now().isoformat(),
            'total_tokens': len(tokens),
            'tokens': tokens
        }

        return jsonify(export_data)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration."""
    return jsonify({'success': True, 'config': config})


@app.route('/api/config', methods=['PUT'])
def update_config():
    """Update configuration."""
    try:
        data = request.get_json()

        for key in ['thumbnail_size', 'watch_folder', 'port', 'host', 'file_io_timeout_seconds']:
            if key in data:
                config[key] = data[key]

        if save_config():
            return jsonify({'success': True, 'message': 'Configuration updated. Restart required for some changes.'})
        else:
            return jsonify({'success': False, 'error': 'Failed to save configuration'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===== AUDIO FILE ENDPOINTS =====

@app.route('/api/audio', methods=['GET'])
def get_audio_files():
    """
    Get all audio files with optional filtering and sorting.

    Query parameters:
        - audio_type: Filter by audio type (Music, SoundEffect, Ambience, Dialogue)
        - genre: Filter by genre
        - mood: Filter by mood
        - source: Filter by source
        - campaign: Filter by campaign
        - search: Search term for name/filename
        - sort_by: Field to sort by (default: filename)
        - sort_order: ASC or DESC (default: ASC)
    """
    try:
        search = request.args.get('search')
        sort_by = request.args.get('sort_by', 'filename')
        sort_order = request.args.get('sort_order', 'ASC')

        # Build filters
        filters = {}
        filter_fields = ['audio_type', 'genre', 'mood', 'intensity', 'character', 'location', 'source', 'campaign']

        for field in filter_fields:
            value = request.args.get(field)
            if value:
                filters[field] = value

        audio_files = db.get_all_audio_files(
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            search_term=search
        )

        return jsonify({
            'success': True,
            'audio_files': audio_files,
            'count': len(audio_files)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audio/<int:audio_id>', methods=['GET'])
def get_audio_file(audio_id):
    """Get a single audio file by ID."""
    try:
        audio = db.get_audio_file(audio_id)

        if audio:
            return jsonify({'success': True, 'audio': audio})
        else:
            return jsonify({'success': False, 'error': 'Audio file not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audio/<int:audio_id>', methods=['PUT'])
def update_audio_file(audio_id):
    """Update an audio file's metadata."""
    try:
        data = request.get_json()

        audio = db.get_audio_file(audio_id)
        if not audio:
            return jsonify({'success': False, 'error': 'Audio file not found'}), 404

        # Build update data
        update_data = {}
        for field in ['Name', 'AudioType', 'Genre', 'Mood', 'Intensity', 'Character',
                     'Location', 'Source', 'Campaign', 'Notes']:
            if field in data:
                update_data[field] = data[field]

        if update_data:
            if not db.update_audio_file(audio_id, update_data):
                return jsonify({'success': False, 'error': 'Failed to update audio file'}), 500

            updated_audio = db.get_audio_file(audio_id)
            return jsonify({'success': True, 'audio': updated_audio})
        else:
            return jsonify({'success': False, 'error': 'No fields to update'}), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audio/<int:audio_id>', methods=['DELETE'])
def delete_audio_file(audio_id):
    """Delete an audio file and its record."""
    try:
        audio = db.get_audio_file(audio_id)
        if not audio:
            return jsonify({'success': False, 'error': 'Audio file not found'}), 404

        # Delete the file
        def _remove_if_exists():
            if os.path.exists(audio['filepath']):
                os.remove(audio['filepath'])

        try:
            safe_file_op(_remove_if_exists, timeout=get_file_io_timeout())
        except FileOpTimeout:
            print(f"Timeout removing file (possible network issue): {audio['filepath']}")

        # Delete from database
        if db.delete_audio_file(audio_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete from database'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audio/upload', methods=['POST'])
def upload_audio_files():
    """
    Legacy upload endpoint - browser mode is no longer supported.
    Use /api/audio/add-reference instead (Electron desktop app required).
    """
    return jsonify({
        'success': False,
        'error': 'Browser upload mode is no longer supported. Please use the Electron desktop app with reference mode. Use /api/audio/add-reference to add files by path.'
    }), 400


@app.route('/api/audio/stream/<int:audio_id>', methods=['GET'])
def stream_audio(audio_id):
    """Stream an audio file for playback."""
    try:
        audio = db.get_audio_file(audio_id)
        if not audio:
            return jsonify({'success': False, 'error': 'Audio file not found'}), 404

        filepath = audio['filepath']

        try:
            file_exists = safe_file_op(os.path.exists, filepath, timeout=get_file_io_timeout())
        except FileOpTimeout:
            db.mark_audio_missing(audio_id, True)
            return _timeout_response(use_placeholder=False)

        if not file_exists:
            return jsonify({'success': False, 'error': 'Audio file not found on disk'}), 404

        # Determine MIME type
        ext = os.path.splitext(filepath)[1].lower()
        mime_types = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.ogg': 'audio/ogg',
            '.m4a': 'audio/mp4',
            '.flac': 'audio/flac'
        }
        mimetype = mime_types.get(ext, 'audio/mpeg')

        return send_file(filepath, mimetype=mimetype)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audio-types', methods=['GET'])
def get_audio_types():
    """Get list of valid audio types."""
    return jsonify({'success': True, 'audio_types': AUDIO_TYPES})


@app.route('/api/audio-tag-schema/<audio_type>', methods=['GET'])
def get_audio_tag_schema(audio_type):
    """Get tag schema for a specific audio type."""
    try:
        if audio_type not in AUDIO_TAG_SCHEMAS:
            return jsonify({'success': False, 'error': 'Invalid audio type'}), 400

        return jsonify({'success': True, 'schema': AUDIO_TAG_SCHEMAS[audio_type]})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audio/tags/<tag_type>', methods=['GET'])
def get_audio_tag_values_endpoint(tag_type):
    """Get unique tag values for audio files."""
    try:
        values = db.get_audio_tag_values(tag_type)
        return jsonify({'success': True, 'values': values})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audio/tags/<audio_type>/<tag_type>', methods=['GET'])
def get_audio_tags_by_type(audio_type, tag_type):
    """Get unique audio tag values filtered by audio type."""
    try:
        values = db.get_audio_tag_values_by_type(audio_type, tag_type)
        return jsonify({'success': True, 'values': values})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audio/add-reference', methods=['POST'])
def add_audio_file_reference():
    """Add an audio file reference without copying the file."""
    try:
        from file_utils import calculate_file_hash

        data = request.get_json()
        filepath = data.get('filepath')
        overwrite_existing = data.get('overwrite_existing', False)
        audio_type = data.get('audio_type', 'Music')

        if audio_type not in AUDIO_TYPES:
            audio_type = 'Music'

        # Extract tag values
        tag_fields = ['Genre', 'Mood', 'Intensity', 'Character', 'Location', 'Source', 'Campaign']
        tag_values = {}
        for tag_field in tag_fields:
            value = data.get(tag_field)
            if value:
                tag_values[tag_field] = value

        if not filepath:
            return jsonify({'success': False, 'error': 'No filepath provided'}), 400

        try:
            file_exists = safe_file_op(os.path.exists, filepath, timeout=get_file_io_timeout())
        except FileOpTimeout:
            return jsonify({'success': False, 'error': 'File could not be accessed (network timeout)'}), 503

        if not file_exists:
            return jsonify({'success': False, 'error': 'File not found'}), 404

        if not is_supported_audio(filepath):
            return jsonify({'success': False, 'error': 'Unsupported audio format'}), 400

        try:
            # Calculate hash
            file_hash = safe_file_op(calculate_file_hash, filepath, timeout=get_file_io_timeout())

            # Get audio metadata
            audio_meta = safe_file_op(get_audio_metadata, filepath, timeout=get_file_io_timeout())

            file_modified = datetime.fromtimestamp(
                safe_file_op(os.path.getmtime, filepath, timeout=get_file_io_timeout())
            ).isoformat()
            file_size = safe_file_op(os.path.getsize, filepath, timeout=get_file_io_timeout())
        except FileOpTimeout:
            return jsonify({'success': False, 'error': 'File could not be read (network timeout)'}), 503

        # Check for existing duplicate
        existing = db.find_audio_by_hash(file_hash)

        if existing and not overwrite_existing:
            return jsonify({
                'success': False,
                'error': 'Duplicate file exists',
                'existing_audio': existing
            }), 409

        # Prepare audio data
        audio_data = {
            'filepath': filepath,
            'filename': os.path.basename(filepath),
            'Name': os.path.splitext(os.path.basename(filepath))[0],
            'AudioType': audio_type,
            'DateAdded': datetime.now().isoformat(),
            'file_modified': file_modified,
            'file_hash': file_hash,
            'duration_seconds': audio_meta.get('duration_seconds') if audio_meta else None,
            'format': audio_meta.get('format') if audio_meta else os.path.splitext(filepath)[1][1:].upper(),
            'file_size': file_size
        }
        audio_data.update(tag_values)

        # Add or update in database
        if overwrite_existing and existing:
            success = db.update_audio_file(existing['id'], audio_data)
            audio_id = existing['id']
        else:
            audio_id = db.add_audio_file(audio_data)
            success = audio_id is not None

        if success:
            if audio_id:
                db.update_audio_file_hash(audio_id, file_hash)
                db.mark_audio_missing(audio_id, False)

            return jsonify({
                'success': True,
                'audio_id': audio_id,
                'message': 'Audio file reference added successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to add audio file reference'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audio/stats', methods=['GET'])
def get_audio_stats():
    """Get audio file statistics."""
    try:
        stats = db.get_audio_stats()
        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===== PDF FILE ENDPOINTS =====

@app.route('/api/pdfs', methods=['GET'])
def get_pdf_files():
    """
    Get all PDF files with optional filtering and sorting.

    Query parameters:
        - image_type: Filter by image type
        - source: Filter by source
        - campaign: Filter by campaign
        - search: Search term for name/filename/notes
        - sort_by: Field to sort by (default: filename)
        - sort_order: ASC or DESC (default: ASC)
    """
    try:
        search = request.args.get('search')
        sort_by = request.args.get('sort_by', 'filename')
        sort_order = request.args.get('sort_order', 'ASC')

        filters = {}
        for field in ['image_type', 'source', 'campaign']:
            value = request.args.get(field)
            if value:
                filters[field] = value

        pdf_files = db.get_all_pdf_files(
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            search_term=search
        )

        return jsonify({
            'success': True,
            'pdf_files': pdf_files,
            'count': len(pdf_files)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pdfs/<int:pdf_id>', methods=['GET'])
def get_pdf_file(pdf_id):
    """Get a single PDF file by ID."""
    try:
        pdf = db.get_pdf_file(pdf_id)

        if pdf:
            return jsonify({'success': True, 'pdf': pdf})
        else:
            return jsonify({'success': False, 'error': 'PDF file not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pdfs/<int:pdf_id>', methods=['PUT'])
def update_pdf_file(pdf_id):
    """Update a PDF file's metadata."""
    try:
        data = request.get_json()

        pdf = db.get_pdf_file(pdf_id)
        if not pdf:
            return jsonify({'success': False, 'error': 'PDF file not found'}), 404

        update_data = {}
        for field in ['Name', 'ImageType', 'Source', 'Campaign', 'Notes']:
            if field in data:
                update_data[field] = data[field]

        if update_data:
            if not db.update_pdf_file(pdf_id, update_data):
                return jsonify({'success': False, 'error': 'Failed to update PDF file'}), 500

            updated_pdf = db.get_pdf_file(pdf_id)
            return jsonify({'success': True, 'pdf': updated_pdf})
        else:
            return jsonify({'success': False, 'error': 'No fields to update'}), 400

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pdfs/<int:pdf_id>', methods=['DELETE'])
def delete_pdf_file(pdf_id):
    """Delete a PDF file and its record."""
    try:
        pdf = db.get_pdf_file(pdf_id)
        if not pdf:
            return jsonify({'success': False, 'error': 'PDF file not found'}), 404

        def _remove_if_exists():
            if os.path.exists(pdf['filepath']):
                os.remove(pdf['filepath'])

        try:
            safe_file_op(_remove_if_exists, timeout=get_file_io_timeout())
        except FileOpTimeout:
            print(f"Timeout removing file (possible network issue): {pdf['filepath']}")

        if db.delete_pdf_file(pdf_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete from database'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pdf/<int:pdf_id>', methods=['GET'])
def serve_pdf(pdf_id):
    """Serve a PDF file directly (browser fallback for opening PDFs)."""
    try:
        pdf = db.get_pdf_file(pdf_id)
        if not pdf:
            return jsonify({'success': False, 'error': 'PDF file not found'}), 404

        filepath = pdf['filepath']

        try:
            file_exists = safe_file_op(os.path.exists, filepath, timeout=get_file_io_timeout())
        except FileOpTimeout:
            db.mark_pdf_missing(pdf_id, True)
            return _timeout_response('application/pdf', use_placeholder=False)

        if not file_exists:
            return jsonify({'success': False, 'error': 'PDF file not found on disk'}), 404

        return send_file(filepath, mimetype='application/pdf')

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pdf-thumbnail/<int:pdf_id>', methods=['GET'])
def get_pdf_thumbnail(pdf_id):
    """Generate and return a PDF cover thumbnail on-demand."""
    try:
        pdf = db.get_pdf_file(pdf_id)
        if not pdf:
            return jsonify({'success': False, 'error': 'PDF file not found'}), 404

        filepath = pdf['filepath']

        try:
            file_exists = safe_file_op(os.path.exists, filepath, timeout=get_file_io_timeout())
        except FileOpTimeout:
            db.mark_pdf_missing(pdf_id, True)
            return _timeout_response('image/png', use_placeholder=True)

        if not file_exists:
            return jsonify({'success': False, 'error': 'PDF file not found on disk'}), 404

        try:
            thumbnail_bytes = generate_pdf_thumbnail_in_memory(
                filepath,
                tuple(config.get('thumbnail_size', [150, 150]))
            )
        except FileOpTimeout:
            db.mark_pdf_missing(pdf_id, True)
            return _timeout_response('image/png', use_placeholder=True)

        if thumbnail_bytes is None:
            return jsonify({'success': False, 'error': 'Failed to generate thumbnail'}), 500

        return send_file(
            io.BytesIO(thumbnail_bytes),
            mimetype='image/png',
            as_attachment=False,
            download_name=f'pdf_thumbnail_{pdf_id}.png'
        )

    except Exception as e:
        print(f"Error generating PDF thumbnail: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pdfs/tags/<tag_type>', methods=['GET'])
def get_pdf_tag_values_endpoint(tag_type):
    """Get unique tag values for PDF files."""
    try:
        values = db.get_pdf_tag_values(tag_type)
        return jsonify({'success': True, 'values': values})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pdfs/add-reference', methods=['POST'])
def add_pdf_file_reference():
    """Add a PDF file reference without copying the file."""
    try:
        data = request.get_json()
        filepath = data.get('filepath')
        overwrite_existing = data.get('overwrite_existing', False)
        image_type = data.get('image_type', 'Handout')

        if image_type not in IMAGE_TYPES:
            image_type = 'Handout'

        tag_fields = ['Source', 'Campaign']
        tag_values = {}
        for tag_field in tag_fields:
            value = data.get(tag_field)
            if value:
                tag_values[tag_field] = value

        if not filepath:
            return jsonify({'success': False, 'error': 'No filepath provided'}), 400

        try:
            file_exists = safe_file_op(os.path.exists, filepath, timeout=get_file_io_timeout())
        except FileOpTimeout:
            return jsonify({'success': False, 'error': 'File could not be accessed (network timeout)'}), 503

        if not file_exists:
            return jsonify({'success': False, 'error': 'File not found'}), 404

        if not is_supported_pdf(filepath):
            return jsonify({'success': False, 'error': 'Unsupported file format'}), 400

        def _hash_pdf():
            with open(filepath, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()

        try:
            file_hash = safe_file_op(_hash_pdf, timeout=get_file_io_timeout())
            pdf_meta = safe_file_op(get_pdf_metadata, filepath, timeout=get_file_io_timeout())
            file_modified = datetime.fromtimestamp(
                safe_file_op(os.path.getmtime, filepath, timeout=get_file_io_timeout())
            ).isoformat()
        except FileOpTimeout:
            return jsonify({'success': False, 'error': 'File could not be read (network timeout)'}), 503

        existing = db.find_pdf_by_hash(file_hash)

        if existing and not overwrite_existing:
            return jsonify({
                'success': False,
                'error': 'Duplicate file exists',
                'existing_pdf': existing
            }), 409

        pdf_data = {
            'filepath': filepath,
            'filename': os.path.basename(filepath),
            'Name': os.path.splitext(os.path.basename(filepath))[0],
            'ImageType': image_type,
            'DateAdded': datetime.now().isoformat(),
            'file_modified': file_modified,
            'file_hash': file_hash,
            'page_count': pdf_meta.get('page_count') if pdf_meta else None
        }
        pdf_data.update(tag_values)

        if overwrite_existing and existing:
            success = db.update_pdf_file(existing['id'], pdf_data)
            pdf_id = existing['id']
        else:
            pdf_id = db.add_pdf_file(pdf_data)
            success = pdf_id is not None

        if success:
            if pdf_id:
                db.update_pdf_file_hash(pdf_id, file_hash)
                db.mark_pdf_missing(pdf_id, False)

            return jsonify({
                'success': True,
                'pdf_id': pdf_id,
                'message': 'PDF file reference added successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to add PDF file reference'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/pdfs/stats', methods=['GET'])
def get_pdf_stats():
    """Get PDF file statistics."""
    try:
        stats = db.get_pdf_stats()
        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def cleanup():
    """Cleanup resources on shutdown."""
    pass  # No cleanup needed in Reference Mode


if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Image Vault - Character Image Manager')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--port', type=int, help='Port to run on')
    parser.add_argument('--host', type=str, help='Host to bind to')
    args = parser.parse_args()

    # Override config file location if specified
    if args.config:
        CONFIG_FILE = args.config

    # Initialize the application
    initialize_app()

    # Override port/host if specified via command line
    port = args.port if args.port else config['port']
    host = args.host if args.host else config['host']

    # Register cleanup handler
    import atexit
    atexit.register(cleanup)

    print(f"\nImage Vault is running!")
    print(f"Open your browser to: http://{host}:{port}")
    print("\nPress Ctrl+C to stop\n")

    # Run the Flask app
    # Debug mode disabled by default to prevent high CPU usage from auto-reloader
    # Enable with: FLASK_DEBUG=true python3 app.py
    debug_mode = os.environ.get('FLASK_DEBUG', '').lower() == 'true'
    app.run(host=host, port=port, debug=debug_mode)
