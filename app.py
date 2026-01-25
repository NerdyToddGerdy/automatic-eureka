from flask import Flask, render_template, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime
from PIL import Image
import hashlib
import argparse
from typing import Optional
import io

from database import TokenDatabase
from metadata import TokenMetadata
from scanner import TokenScanner, TokenFolderWatcher
from drive_client import DriveClient
from drive_sync import DriveSyncService
from google.oauth2.credentials import Credentials
from file_utils import calculate_file_hash_from_bytes
from cache import get_image_cache


app = Flask(__name__)
CORS(app)

# Configuration
CONFIG_FILE = 'config.json'
DEFAULT_CONFIG = {
    'token_folder': './tokens',
    'thumbnail_size': [150, 150],
    'watch_folder': True,
    'port': 5000,
    'host': '127.0.0.1'
}

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

# Global objects
db = None
scanner = None
watcher = None
drive_client = None
drive_sync = None
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
    global db, scanner, watcher, drive_client, drive_sync, image_cache

    load_config()

    # Initialize database
    db = TokenDatabase('tokens.db')

    # Initialize Google Drive client if OAuth tokens available
    oauth_tokens_json = os.environ.get('GOOGLE_OAUTH_TOKENS')
    if oauth_tokens_json:
        try:
            token_data = json.loads(oauth_tokens_json)
            credentials = Credentials(
                token=token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri=token_data.get('token_uri'),
                client_id=token_data.get('client_id'),
                client_secret=token_data.get('client_secret'),
                scopes=token_data.get('scopes')
            )
            drive_client = DriveClient(credentials)
            print("✓ Google Drive client initialized successfully")

            # Initialize Drive sync service
            drive_sync = DriveSyncService(db, drive_client)
            print("✓ Google Drive sync service initialized")
        except Exception as e:
            print(f"⚠ Warning: Could not initialize Drive client: {e}")
            print("  App will run in local-only mode")
            drive_client = None
            drive_sync = None
    else:
        print("ℹ No Google OAuth tokens found - running in local-only mode")
        drive_client = None
        drive_sync = None

    # Initialize image cache (100MB default)
    image_cache = get_image_cache(max_size_mb=100)
    print("✓ Image cache initialized (100MB)")

    # Initialize scanner
    scanner = TokenScanner(
        token_folder=config['token_folder'],
        database=db
    )

    # Perform initial scan
    print("Performing initial scan...")
    results = scanner.scan_and_sync()
    print(f"Scan complete: {results['added']} added, {results['updated']} updated, "
          f"{results['removed']} removed, {results['errors']} errors")

    # Start folder watcher if enabled
    if config.get('watch_folder', True):
        watcher = TokenFolderWatcher(scanner, config['token_folder'])
        watcher.start()


def get_thumbnail_path(token_id: int, filepath: str) -> str:
    """
    Generate or retrieve thumbnail path for a token.

    Args:
        token_id: Token ID
        filepath: Original file path

    Returns:
        Path to thumbnail file
    """
    # Create hash-based filename
    file_hash = hashlib.md5(filepath.encode()).hexdigest()
    thumbnail_filename = f"{token_id}_{file_hash}.png"
    thumbnail_path = os.path.join('thumbnails', thumbnail_filename)

    return thumbnail_path


def generate_thumbnail(filepath: str, thumbnail_path: str, size: tuple = (150, 150)):
    """
    Generate a thumbnail for an image.

    Args:
        filepath: Source image path
        thumbnail_path: Destination thumbnail path
        size: Thumbnail size (width, height)
    """
    try:
        img = Image.open(filepath)
        img.thumbnail(size, Image.Resampling.LANCZOS)
        img.save(thumbnail_path, 'PNG')
        return True
    except Exception as e:
        print(f"Error generating thumbnail for {filepath}: {e}")
        return False


def generate_thumbnail_in_memory(filepath: str, size: tuple = (150, 150)) -> Optional[bytes]:
    """Generate a thumbnail in-memory and return as bytes."""
    try:
        from io import BytesIO

        with Image.open(filepath) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)

            buffer = BytesIO()
            img.save(buffer, format='PNG', optimize=True)
            buffer.seek(0)

            return buffer.getvalue()

    except Exception as e:
        print(f"Error generating in-memory thumbnail for {filepath}: {e}")
        return None


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
    return send_from_directory('static', path)


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

            # Check if this is a Drive-stored file
            drive_file_id = token.get('drive_file_id')

            if drive_file_id and drive_client:
                # Sync to Drive custom properties (best effort)
                try:
                    # Prepare metadata for Drive (custom properties)
                    drive_metadata = {}
                    for key, value in update_data.items():
                        # Convert to string for Drive custom properties
                        if value is not None:
                            drive_metadata[key] = str(value)

                    # Update Drive file metadata
                    drive_client.update_file_metadata(drive_file_id, drive_metadata)
                    print(f"✓ Synced metadata to Drive for {token.get('filename', 'unknown')}")

                except Exception as drive_error:
                    print(f"⚠ Warning: Failed to sync metadata to Drive: {drive_error}")
                    # Don't fail the request - database is source of truth

            else:
                # Local file - mirror to PNG (best effort)
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
        if os.path.exists(token['filepath']):
            os.remove(token['filepath'])

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
        if not os.path.exists(new_filepath):
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
    """Upload one or more token files (to Drive or local)."""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': 'No files provided'}), 400

        files = request.files.getlist('files')
        image_type = request.form.get('image_type', 'Token')
        target_folder_id = request.form.get('drive_folder_id')  # Optional Drive folder

        # Validate image type
        if image_type not in IMAGE_TYPES:
            image_type = 'Token'

        # Extract tag values from form data
        tag_values = {}
        tag_fields = ['Species', 'Class', 'Source', 'Campaign',  # Token
                      'Scale', 'Theme',                           # Map
                      'Type',                                      # Handout
                      'Subject', 'Style',                          # Portrait
                      'Location', 'Mood',                          # Scene
                      'Rarity', 'Category', 'Attunement']          # Item

        for tag_field in tag_fields:
            value = request.form.get(tag_field)
            if value:
                tag_values[tag_field] = value

        results = {'added': 0, 'errors': 0, 'error_files': [], 'upload_mode': 'local'}

        # Determine upload mode (Drive or local)
        use_drive = drive_client is not None and target_folder_id is not None

        if use_drive:
            results['upload_mode'] = 'drive'

        for file in files:
            if file and is_supported_image(file.filename):
                filename = secure_filename(file.filename)

                # Prepare metadata
                metadata = {
                    'ImageType': image_type,
                    'DateAdded': datetime.now().isoformat()
                }
                metadata.update(tag_values)

                if use_drive:
                    # ===== GOOGLE DRIVE UPLOAD =====
                    try:
                        # Read file into memory
                        file_bytes = file.read()
                        file_stream = io.BytesIO(file_bytes)

                        # Determine MIME type
                        if filename.lower().endswith('.png'):
                            mimetype = 'image/png'
                        elif filename.lower().endswith(('.jpg', '.jpeg')):
                            mimetype = 'image/jpeg'
                        else:
                            mimetype = 'application/octet-stream'

                        # Calculate file hash for duplicate detection
                        from file_utils import calculate_file_hash_from_bytes
                        file_hash = calculate_file_hash_from_bytes(file_bytes)

                        # Check for duplicates
                        existing = db.find_by_hash(file_hash)
                        if existing:
                            results['errors'] += 1
                            results['error_files'].append(f"{filename} (duplicate)")
                            continue

                        # Upload to Google Drive
                        drive_result = drive_client.upload_file(
                            file_stream=file_stream,
                            filename=filename,
                            folder_id=target_folder_id,
                            metadata=metadata,
                            mimetype=mimetype
                        )

                        # Add to database
                        token_data = {
                            'drive_file_id': drive_result['id'],
                            'drive_folder_id': drive_result['parents'][0] if 'parents' in drive_result else target_folder_id,
                            'drive_web_view_link': drive_result.get('webViewLink'),
                            'drive_thumbnail_link': drive_result.get('thumbnailLink'),
                            'filepath': f"drive://{drive_result['id']}",  # Placeholder
                            'filename': filename,
                            'file_hash': file_hash,
                            'file_modified': drive_result.get('modifiedTime'),
                            'last_synced_from_drive': datetime.now().isoformat(),
                            **metadata
                        }

                        if db.add_token(token_data):
                            results['added'] += 1
                        else:
                            # Rollback: delete from Drive
                            try:
                                drive_client.delete_file(drive_result['id'])
                            except:
                                pass
                            results['errors'] += 1
                            results['error_files'].append(f"{filename} (db error)")

                    except Exception as e:
                        print(f"Error uploading {filename} to Drive: {e}")
                        results['errors'] += 1
                        results['error_files'].append(f"{filename} ({str(e)})")

                else:
                    # ===== LOCAL FILE UPLOAD (existing logic) =====
                    filepath = os.path.join(config['token_folder'], filename)

                    # Save the file
                    file.save(filepath)

                    # Write metadata to file
                    file_metadata = TokenMetadata.read_token_metadata(filepath)
                    file_metadata.update(metadata)
                    TokenMetadata.write_token_metadata(filepath, file_metadata)

                    # Add to database (will be picked up by scanner if watching)
                    if not config.get('watch_folder'):
                        if scanner.add_new_file(filepath):
                            results['added'] += 1
                        else:
                            results['errors'] += 1
                            results['error_files'].append(filename)
                    else:
                        results['added'] += 1
            else:
                results['errors'] += 1
                results['error_files'].append(file.filename if file else 'unknown')

        return jsonify({'success': True, 'results': results})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
                if not os.path.exists(filepath):
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
                    file_hash = calculate_file_hash(filepath)

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

        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Calculate hash
        file_hash = calculate_file_hash(filepath)

        # Check for existing duplicate
        existing = db.find_by_hash(file_hash)

        if existing and not overwrite_existing:
            return jsonify({
                'success': False,
                'error': 'Duplicate file exists',
                'existing_token': existing
            }), 409

        # Read metadata from PNG
        metadata = TokenMetadata.read_token_metadata(filepath)

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
        if not TokenMetadata.write_token_metadata(filepath, metadata):
            print(f"Warning: Failed to write metadata to PNG for {filepath}")
            # Continue anyway - database update is more critical

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
            'file_modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
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
                    if not os.path.exists(filepath):
                        results['errors'] += 1
                        subfolder_results['errors'] += 1
                        continue

                    # Calculate hash
                    file_hash = calculate_file_hash(filepath)

                    # Check for existing
                    existing = db.find_by_hash(file_hash)
                    overwrite_existing = (action == 'overwrite')

                    # Read and update metadata
                    metadata = TokenMetadata.read_token_metadata(filepath)
                    metadata['ImageType'] = image_type

                    # Apply tags from subfolder assignment
                    for tag_key, tag_value in tags.items():
                        if tag_value:
                            metadata[tag_key] = tag_value

                    # Add DateAdded if new
                    if not existing and not metadata.get('DateAdded'):
                        metadata['DateAdded'] = datetime.now().isoformat()

                    # Write metadata to PNG
                    TokenMetadata.write_token_metadata(filepath, metadata)

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
                        'file_modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
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

        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
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
            if os.path.exists(token['filepath']):
                os.remove(token['filepath'])

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


@app.route('/api/scan', methods=['POST'])
def rescan():
    """Manually trigger a folder scan (local or Drive)."""
    try:
        # Check if Drive sync is available and has monitored folders
        if drive_sync:
            monitored_folders = db.get_all_monitored_folders()
            if monitored_folders:
                # Use Drive sync
                print("Starting Drive sync...")
                results = drive_sync.perform_full_sync()
                return jsonify({
                    'success': True,
                    'results': results,
                    'mode': 'drive'
                })

        # Fall back to local scanner
        print("Starting local folder scan...")
        results = scanner.scan_and_sync()
        return jsonify({
            'success': True,
            'results': results,
            'mode': 'local'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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

        # Check if this is a Drive-stored image
        drive_file_id = token.get('drive_file_id')

        if drive_file_id and drive_client:
            # Try to get thumbnail from cache
            thumbnail_cache_key = f"{drive_file_id}_thumbnail"
            cached_thumbnail = image_cache.get(thumbnail_cache_key)

            if cached_thumbnail:
                thumbnail_bytes, _ = cached_thumbnail
                return send_file(
                    io.BytesIO(thumbnail_bytes),
                    mimetype='image/png',
                    as_attachment=False,
                    download_name=f'thumbnail_{token_id}.png'
                )

            # Get full image (from cache or download from Drive)
            cached_image = image_cache.get(drive_file_id)
            if cached_image:
                image_bytes, _ = cached_image
            else:
                try:
                    image_bytes = drive_client.download_file(drive_file_id)
                    # Cache full image for future use
                    image_cache.set(drive_file_id, image_bytes, 'image/png')
                except Exception as drive_error:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to download from Drive: {str(drive_error)}'
                    }), 500

            # Generate thumbnail from image bytes
            try:
                img = Image.open(io.BytesIO(image_bytes))
                img.thumbnail(tuple(config.get('thumbnail_size', [150, 150])), Image.Resampling.LANCZOS)

                buffer = io.BytesIO()
                img.save(buffer, format='PNG', optimize=True)
                buffer.seek(0)
                thumbnail_bytes = buffer.getvalue()

                # Cache the thumbnail
                image_cache.set(thumbnail_cache_key, thumbnail_bytes, 'image/png')

                return send_file(
                    io.BytesIO(thumbnail_bytes),
                    mimetype='image/png',
                    as_attachment=False,
                    download_name=f'thumbnail_{token_id}.png'
                )

            except Exception as thumb_error:
                return jsonify({
                    'success': False,
                    'error': f'Failed to generate thumbnail: {str(thumb_error)}'
                }), 500

        else:
            # Local file serving (existing logic)
            filepath = token['filepath']

            if not os.path.exists(filepath):
                return jsonify({'success': False, 'error': 'Image file not found'}), 404

            # Generate thumbnail in-memory
            thumbnail_bytes = generate_thumbnail_in_memory(
                filepath,
                tuple(config.get('thumbnail_size', [150, 150]))
            )

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

        # Check if this is a Drive-stored image
        drive_file_id = token.get('drive_file_id')

        if drive_file_id and drive_client:
            # Try to get from cache first
            cached = image_cache.get(drive_file_id)
            if cached:
                image_bytes, mimetype = cached
                return send_file(
                    io.BytesIO(image_bytes),
                    mimetype=mimetype,
                    download_name=token.get('filename', 'image.png')
                )

            # Not in cache - download from Drive
            try:
                image_bytes = drive_client.download_file(drive_file_id)

                # Detect MIME type
                filename = token.get('filename', '')
                if filename.lower().endswith('.png'):
                    mimetype = 'image/png'
                elif filename.lower().endswith(('.jpg', '.jpeg')):
                    mimetype = 'image/jpeg'
                else:
                    mimetype = 'image/png'

                # Cache the image
                image_cache.set(drive_file_id, image_bytes, mimetype)

                # Return the image
                return send_file(
                    io.BytesIO(image_bytes),
                    mimetype=mimetype,
                    download_name=filename
                )

            except Exception as drive_error:
                return jsonify({
                    'success': False,
                    'error': f'Failed to download from Drive: {str(drive_error)}'
                }), 500

        else:
            # Local file serving (existing logic)
            filepath = token['filepath']

            # Detect MIME type based on file extension
            if filepath.lower().endswith('.png'):
                mimetype = 'image/png'
            elif filepath.lower().endswith(('.jpg', '.jpeg')):
                mimetype = 'image/jpeg'
            else:
                mimetype = 'image/png'  # default fallback

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

        for key in ['token_folder', 'thumbnail_size', 'watch_folder', 'port', 'host']:
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
        if os.path.exists(audio['filepath']):
            os.remove(audio['filepath'])

        # Delete from database
        if db.delete_audio_file(audio_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete from database'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audio/upload', methods=['POST'])
def upload_audio_files():
    """Upload one or more audio files."""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': 'No files provided'}), 400

        files = request.files.getlist('files')
        audio_type = request.form.get('audio_type', 'Music')

        # Validate audio type
        if audio_type not in AUDIO_TYPES:
            audio_type = 'Music'

        # Extract tag values from form data
        tag_values = {}
        tag_fields = ['Genre', 'Mood', 'Intensity', 'Character', 'Location', 'Source', 'Campaign']

        for tag_field in tag_fields:
            value = request.form.get(tag_field)
            if value:
                tag_values[tag_field] = value

        results = {'added': 0, 'errors': 0, 'error_files': []}

        for file in files:
            if file and is_supported_audio(file.filename):
                filename = secure_filename(file.filename)

                # Read file into memory FIRST to calculate hash before saving
                file_bytes = file.read()
                file_hash = hashlib.sha256(file_bytes).hexdigest()

                # Check for duplicates BEFORE saving to disk
                existing = db.find_audio_by_hash(file_hash)
                if existing:
                    results['errors'] += 1
                    results['error_files'].append(f"{filename} (duplicate)")
                    continue

                filepath = os.path.join(config['token_folder'], 'audio', filename)

                # Ensure audio folder exists
                os.makedirs(os.path.dirname(filepath), exist_ok=True)

                # Now save the file to disk
                with open(filepath, 'wb') as f:
                    f.write(file_bytes)

                # Get audio metadata
                audio_meta = get_audio_metadata(filepath)

                # Prepare audio data
                audio_data = {
                    'filepath': filepath,
                    'filename': filename,
                    'Name': os.path.splitext(filename)[0],
                    'AudioType': audio_type,
                    'DateAdded': datetime.now().isoformat(),
                    'file_modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
                    'file_hash': file_hash,
                    'duration_seconds': audio_meta.get('duration_seconds') if audio_meta else None,
                    'format': audio_meta.get('format') if audio_meta else os.path.splitext(filename)[1][1:].upper(),
                    'file_size': os.path.getsize(filepath)
                }
                audio_data.update(tag_values)

                if db.add_audio_file(audio_data):
                    results['added'] += 1
                else:
                    results['errors'] += 1
                    results['error_files'].append(filename)
            else:
                results['errors'] += 1
                results['error_files'].append(file.filename if file else 'unknown')

        return jsonify({'success': True, 'results': results})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audio/stream/<int:audio_id>', methods=['GET'])
def stream_audio(audio_id):
    """Stream an audio file for playback."""
    try:
        audio = db.get_audio_file(audio_id)
        if not audio:
            return jsonify({'success': False, 'error': 'Audio file not found'}), 404

        filepath = audio['filepath']
        if not os.path.exists(filepath):
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

        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': 'File not found'}), 404

        if not is_supported_audio(filepath):
            return jsonify({'success': False, 'error': 'Unsupported audio format'}), 400

        # Calculate hash
        file_hash = calculate_file_hash(filepath)

        # Check for existing duplicate
        existing = db.find_audio_by_hash(file_hash)

        if existing and not overwrite_existing:
            return jsonify({
                'success': False,
                'error': 'Duplicate file exists',
                'existing_audio': existing
            }), 409

        # Get audio metadata
        audio_meta = get_audio_metadata(filepath)

        # Prepare audio data
        audio_data = {
            'filepath': filepath,
            'filename': os.path.basename(filepath),
            'Name': os.path.splitext(os.path.basename(filepath))[0],
            'AudioType': audio_type,
            'DateAdded': datetime.now().isoformat(),
            'file_modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
            'file_hash': file_hash,
            'duration_seconds': audio_meta.get('duration_seconds') if audio_meta else None,
            'format': audio_meta.get('format') if audio_meta else os.path.splitext(filepath)[1][1:].upper(),
            'file_size': os.path.getsize(filepath)
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


# ===== GOOGLE DRIVE ENDPOINTS =====

@app.route('/api/drive/folders', methods=['GET'])
def get_drive_folders():
    """
    Browse folders in Google Drive.
    Query params:
        parent_id (optional): Parent folder ID to list subfolders
    """
    if not drive_client:
        return jsonify({'success': False, 'error': 'Google Drive not connected'}), 503

    try:
        parent_id = request.args.get('parent_id')
        folders = drive_client.list_folders(parent_folder_id=parent_id)

        return jsonify({
            'success': True,
            'folders': folders
        })

    except Exception as e:
        print(f"Error listing Drive folders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/drive/folders/monitored', methods=['GET'])
def get_monitored_folders():
    """Get all folders currently being monitored."""
    try:
        folders = db.get_all_monitored_folders()
        return jsonify({
            'success': True,
            'folders': folders
        })

    except Exception as e:
        print(f"Error getting monitored folders: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/drive/folders/monitor', methods=['POST'])
def add_monitored_folder():
    """
    Add a folder to the monitored folders list.
    Body: {folder_id, folder_name, folder_path (optional)}
    """
    if not drive_client:
        return jsonify({'success': False, 'error': 'Google Drive not connected'}), 503

    try:
        data = request.get_json()
        folder_id = data.get('folder_id')
        folder_name = data.get('folder_name')
        folder_path = data.get('folder_path')

        if not folder_id or not folder_name:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        # Check if already monitored
        if db.is_folder_monitored(folder_id):
            return jsonify({'success': False, 'error': 'Folder is already being monitored'}), 400

        # Add to database
        result_id = db.add_monitored_folder(folder_id, folder_name, folder_path)

        if result_id:
            return jsonify({
                'success': True,
                'message': f'Folder "{folder_name}" added to monitored folders',
                'folder_id': result_id
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to add folder'}), 500

    except Exception as e:
        print(f"Error adding monitored folder: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/drive/folders/monitor/<folder_id>', methods=['DELETE'])
def remove_monitored_folder(folder_id):
    """Remove a folder from the monitored folders list."""
    try:
        success = db.remove_monitored_folder(folder_id)

        if success:
            return jsonify({
                'success': True,
                'message': 'Folder removed from monitoring'
            })
        else:
            return jsonify({'success': False, 'error': 'Folder not found'}), 404

    except Exception as e:
        print(f"Error removing monitored folder: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/drive/status', methods=['GET'])
def get_drive_status():
    """Get Google Drive connection status."""
    if not drive_client:
        return jsonify({
            'connected': False,
            'message': 'Google Drive not connected'
        })

    try:
        # Test connection by getting Drive info
        about = drive_client.get_about()
        return jsonify({
            'connected': True,
            'user': about.get('user', {}),
            'storage': about.get('storageQuota', {})
        })

    except Exception as e:
        return jsonify({
            'connected': False,
            'error': str(e)
        }), 500


def cleanup():
    """Cleanup resources on shutdown."""
    global watcher

    if watcher:
        watcher.stop()


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
    print(f"Token folder: {os.path.abspath(config['token_folder'])}")
    print(f"Folder watching: {'enabled' if config.get('watch_folder') else 'disabled'}")
    print("\nPress Ctrl+C to stop\n")

    # Run the Flask app
    app.run(host=host, port=port, debug=True)
