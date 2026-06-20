import os
from pathlib import Path
from typing import List, Callable, Optional, Dict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
import time
from metadata import TokenMetadata
from database import TokenDatabase
from datetime import datetime
import hashlib

# Supported audio extensions
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.m4a', '.flac'}

# Supported PDF extensions
PDF_EXTENSIONS = {'.pdf'}


def is_supported_audio(filepath: str) -> bool:
    """Check if file is a supported audio format."""
    lower = filepath.lower()
    return any(lower.endswith(ext) for ext in AUDIO_EXTENSIONS)


def is_supported_pdf(filepath: str) -> bool:
    """Check if file is a PDF."""
    lower = filepath.lower()
    return any(lower.endswith(ext) for ext in PDF_EXTENSIONS)


def get_pdf_page_count(filepath: str) -> Optional[int]:
    """
    Get the page count of a PDF using PyMuPDF.

    Args:
        filepath: Path to the PDF file

    Returns:
        Page count, or None on error
    """
    try:
        import fitz
        with fitz.open(filepath) as doc:
            return doc.page_count
    except Exception as e:
        print(f"Error reading PDF page count for {filepath}: {e}")
        return None


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


class TokenScanner:
    """Scans folders for PNG files and manages token inventory."""

    def __init__(self, database: TokenDatabase, token_folder: Optional[str] = None):
        """
        Initialize the scanner.

        Args:
            database: TokenDatabase instance
            token_folder: Optional path to folder for local scanning (Reference Mode doesn't need this)
        """
        self.token_folder = token_folder
        self.database = database

    def find_image_files(self) -> List[str]:
        """
        Recursively find all image files (PNG and JPEG) in the token folder.

        Returns:
            List of absolute file paths (empty if no token_folder configured)
        """
        if not self.token_folder:
            return []

        image_files = []

        for root, dirs, files in os.walk(self.token_folder):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    filepath = os.path.join(root, file)
                    image_files.append(os.path.abspath(filepath))

        return image_files

    def scan_and_sync(self, progress_callback: Optional[Callable] = None) -> dict:
        """
        Scan the token folder and sync with the database.
        PNG metadata is the source of truth.

        Args:
            progress_callback: Optional callback function for progress updates

        Returns:
            Dictionary with scan results
        """
        results = {
            'added': 0,
            'updated': 0,
            'removed': 0,
            'errors': 0
        }

        # Find all image files
        image_files = self.find_image_files()
        file_paths_set = set(image_files)

        # Process each image file
        for i, filepath in enumerate(image_files):
            try:
                if progress_callback:
                    progress_callback(i + 1, len(image_files), filepath)

                # Get file info and metadata from PNG
                file_info = TokenMetadata.get_file_info(filepath)

                if file_info is None:
                    results['errors'] += 1
                    continue

                # Check if token exists in database
                existing = self.database.get_token_by_filepath(filepath)

                if existing is None:
                    # Add DateAdded if missing
                    if not file_info.get('DateAdded'):
                        file_info['DateAdded'] = datetime.now().isoformat()
                        TokenMetadata.update_metadata(filepath, {'DateAdded': file_info['DateAdded']})

                    # CRITICAL: If ImageType is None, default to 'Token' ONLY for new files
                    if file_info.get('ImageType') is None:
                        file_info['ImageType'] = 'Token'
                        # Write this default back to PNG to maintain DB-PNG sync
                        TokenMetadata.update_metadata(filepath, {'ImageType': 'Token'})

                    # New token - add to database
                    if self.database.add_token(file_info):
                        results['added'] += 1
                    else:
                        results['errors'] += 1
                else:
                    # Check if file was modified since last scan
                    if existing['file_modified'] != file_info['file_modified']:
                        # CRITICAL: Preserve ImageType from database unless PNG has explicit value
                        # Database is source of truth; PNG may have incomplete metadata
                        if file_info.get('ImageType') is None and existing.get('ImageType'):
                            file_info['ImageType'] = existing['ImageType']

                        # File was modified - update from PNG metadata
                        if self.database.update_token_by_filepath(filepath, file_info):
                            results['updated'] += 1
                        else:
                            results['errors'] += 1

            except Exception as e:
                print(f"Error processing {filepath}: {e}")
                results['errors'] += 1

        # Check for files that are in the token folder but not in database
        # (This only applies to files in the watched token folder)
        # Files outside the token folder are managed separately via file references
        # and should not be removed during scans

        return results

    def add_new_file(self, filepath: str) -> bool:
        """
        Add a newly detected file to the database.

        Args:
            filepath: Path to the new PNG file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get file info and metadata
            file_info = TokenMetadata.get_file_info(filepath)

            if file_info is None:
                return False

            # Add DateAdded if missing
            if not file_info.get('DateAdded'):
                file_info['DateAdded'] = datetime.now().isoformat()
                TokenMetadata.update_metadata(filepath, {'DateAdded': file_info['DateAdded']})

            # Add to database
            return self.database.add_token(file_info) is not None

        except Exception as e:
            print(f"Error adding new file {filepath}: {e}")
            return False

    def update_existing_file(self, filepath: str) -> bool:
        """
        Update an existing file in the database from PNG metadata.

        Args:
            filepath: Path to the modified PNG file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get updated file info and metadata
            file_info = TokenMetadata.get_file_info(filepath)

            if file_info is None:
                return False

            # Update database
            return self.database.update_token_by_filepath(filepath, file_info)

        except Exception as e:
            print(f"Error updating file {filepath}: {e}")
            return False

    def verify_all_references(self) -> dict:
        """
        Verify all file references in the database still exist.
        Updates is_missing flag for broken references.

        Returns:
            Dictionary with verification results:
            {
                'verified': count of existing files,
                'missing': list of missing token dictionaries,
                'errors': count of errors
            }
        """
        results = {
            'verified': 0,
            'missing': [],
            'errors': 0
        }

        try:
            # Get all tokens from database
            all_tokens = self.database.get_all_tokens()

            for token in all_tokens:
                token_id = token['id']
                filepath = token['filepath']

                try:
                    # Check if file exists
                    if os.path.exists(filepath) and os.path.isfile(filepath):
                        # File exists - mark as not missing
                        self.database.mark_missing(token_id, False)
                        self.database.update_last_verified(token_id, datetime.now().isoformat())
                        results['verified'] += 1
                    else:
                        # File is missing - mark as missing
                        self.database.mark_missing(token_id, True)
                        results['missing'].append(token)
                        print(f"Missing file: {filepath}")

                except Exception as e:
                    print(f"Error verifying {filepath}: {e}")
                    results['errors'] += 1

        except Exception as e:
            print(f"Error during verification: {e}")
            results['errors'] += 1

        return results

    # ===== AUDIO FILE SCANNING METHODS =====

    def find_audio_files(self) -> List[str]:
        """
        Recursively find all audio files in the token folder.

        Returns:
            List of absolute file paths (empty if no token_folder configured)
        """
        if not self.token_folder:
            return []

        audio_files = []

        for root, dirs, files in os.walk(self.token_folder):
            for file in files:
                if is_supported_audio(file):
                    filepath = os.path.join(root, file)
                    audio_files.append(os.path.abspath(filepath))

        return audio_files

    def scan_audio_and_sync(self, progress_callback: Optional[Callable] = None) -> dict:
        """
        Scan the token folder for audio files and sync with the database.

        Args:
            progress_callback: Optional callback function for progress updates

        Returns:
            Dictionary with scan results
        """
        results = {
            'added': 0,
            'updated': 0,
            'removed': 0,
            'errors': 0
        }

        # Find all audio files
        audio_files = self.find_audio_files()

        # Process each audio file
        for i, filepath in enumerate(audio_files):
            try:
                if progress_callback:
                    progress_callback(i + 1, len(audio_files), filepath)

                # Get file info
                filename = os.path.basename(filepath)
                file_modified = datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()

                # Check if audio file exists in database
                existing = self.database.get_audio_file_by_filepath(filepath)

                if existing is None:
                    # New audio file - add to database
                    audio_meta = get_audio_metadata(filepath)

                    # Calculate file hash
                    with open(filepath, 'rb') as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()

                    audio_data = {
                        'filepath': filepath,
                        'filename': filename,
                        'Name': os.path.splitext(filename)[0],
                        'AudioType': 'Music',  # Default type
                        'DateAdded': datetime.now().isoformat(),
                        'file_modified': file_modified,
                        'file_hash': file_hash,
                        'duration_seconds': audio_meta.get('duration_seconds') if audio_meta else None,
                        'format': audio_meta.get('format') if audio_meta else os.path.splitext(filename)[1][1:].upper(),
                        'file_size': os.path.getsize(filepath)
                    }

                    if self.database.add_audio_file(audio_data):
                        results['added'] += 1
                    else:
                        results['errors'] += 1
                else:
                    # Check if file was modified since last scan
                    if existing['file_modified'] != file_modified:
                        # File was modified - update metadata
                        audio_meta = get_audio_metadata(filepath)

                        update_data = {
                            'file_modified': file_modified,
                            'duration_seconds': audio_meta.get('duration_seconds') if audio_meta else existing.get('duration_seconds'),
                            'file_size': os.path.getsize(filepath)
                        }

                        # Preserve existing tags
                        for field in ['Name', 'AudioType', 'Genre', 'Mood', 'Intensity', 'Character',
                                     'Location', 'Source', 'Campaign', 'Notes']:
                            db_field = field.lower() if field not in ['Name', 'AudioType'] else field
                            if existing.get(db_field if field.islower() else field.lower()):
                                update_data[field] = existing.get(db_field if field.islower() else field.lower())

                        if self.database.update_audio_file(existing['id'], update_data):
                            results['updated'] += 1
                        else:
                            results['errors'] += 1

            except Exception as e:
                print(f"Error processing audio file {filepath}: {e}")
                results['errors'] += 1

        return results

    def add_new_audio_file(self, filepath: str) -> bool:
        """
        Add a newly detected audio file to the database.

        Args:
            filepath: Path to the new audio file

        Returns:
            True if successful, False otherwise
        """
        try:
            if not is_supported_audio(filepath):
                return False

            filename = os.path.basename(filepath)
            file_modified = datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()

            # Get audio metadata
            audio_meta = get_audio_metadata(filepath)

            # Calculate file hash
            with open(filepath, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            audio_data = {
                'filepath': filepath,
                'filename': filename,
                'Name': os.path.splitext(filename)[0],
                'AudioType': 'Music',  # Default type
                'DateAdded': datetime.now().isoformat(),
                'file_modified': file_modified,
                'file_hash': file_hash,
                'duration_seconds': audio_meta.get('duration_seconds') if audio_meta else None,
                'format': audio_meta.get('format') if audio_meta else os.path.splitext(filename)[1][1:].upper(),
                'file_size': os.path.getsize(filepath)
            }

            return self.database.add_audio_file(audio_data) is not None

        except Exception as e:
            print(f"Error adding new audio file {filepath}: {e}")
            return False

    def update_existing_audio_file(self, filepath: str) -> bool:
        """
        Update an existing audio file in the database.

        Args:
            filepath: Path to the modified audio file

        Returns:
            True if successful, False otherwise
        """
        try:
            existing = self.database.get_audio_file_by_filepath(filepath)
            if not existing:
                return self.add_new_audio_file(filepath)

            # Get updated metadata
            audio_meta = get_audio_metadata(filepath)
            file_modified = datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()

            # Preserve existing tags
            update_data = {
                'Name': existing.get('name'),
                'AudioType': existing.get('audio_type', 'Music'),
                'Genre': existing.get('genre'),
                'Mood': existing.get('mood'),
                'Intensity': existing.get('intensity'),
                'Character': existing.get('character'),
                'Location': existing.get('location'),
                'Source': existing.get('source'),
                'Campaign': existing.get('campaign'),
                'Notes': existing.get('notes'),
                'file_modified': file_modified
            }

            return self.database.update_audio_file(existing['id'], update_data)

        except Exception as e:
            print(f"Error updating audio file {filepath}: {e}")
            return False

    def verify_all_audio_references(self) -> dict:
        """
        Verify all audio file references in the database still exist.

        Returns:
            Dictionary with verification results
        """
        results = {
            'verified': 0,
            'missing': [],
            'errors': 0
        }

        try:
            all_audio = self.database.get_all_audio_files()

            for audio in all_audio:
                audio_id = audio['id']
                filepath = audio['filepath']

                try:
                    if os.path.exists(filepath) and os.path.isfile(filepath):
                        self.database.mark_audio_missing(audio_id, False)
                        results['verified'] += 1
                    else:
                        self.database.mark_audio_missing(audio_id, True)
                        results['missing'].append(audio)
                        print(f"Missing audio file: {filepath}")

                except Exception as e:
                    print(f"Error verifying audio {filepath}: {e}")
                    results['errors'] += 1

        except Exception as e:
            print(f"Error during audio verification: {e}")
            results['errors'] += 1

        return results

    # ===== PDF FILE SCANNING METHODS =====

    def find_pdf_files(self) -> List[str]:
        """
        Recursively find all PDF files in the token folder.

        Returns:
            List of absolute file paths (empty if no token_folder configured)
        """
        if not self.token_folder:
            return []

        pdf_files = []

        for root, dirs, files in os.walk(self.token_folder):
            for file in files:
                if is_supported_pdf(file):
                    filepath = os.path.join(root, file)
                    pdf_files.append(os.path.abspath(filepath))

        return pdf_files

    def scan_pdfs_and_sync(self, progress_callback: Optional[Callable] = None) -> dict:
        """
        Scan the token folder for PDF files and sync with the database.

        Args:
            progress_callback: Optional callback function for progress updates

        Returns:
            Dictionary with scan results
        """
        results = {
            'added': 0,
            'updated': 0,
            'removed': 0,
            'errors': 0
        }

        pdf_files = self.find_pdf_files()

        for i, filepath in enumerate(pdf_files):
            try:
                if progress_callback:
                    progress_callback(i + 1, len(pdf_files), filepath)

                filename = os.path.basename(filepath)
                file_modified = datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()

                existing = self.database.get_pdf_file_by_filepath(filepath)

                if existing is None:
                    # New PDF file - add to database
                    page_count = get_pdf_page_count(filepath)

                    with open(filepath, 'rb') as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()

                    pdf_data = {
                        'filepath': filepath,
                        'filename': filename,
                        'Name': os.path.splitext(filename)[0],
                        'ImageType': 'Handout',  # Default type
                        'DateAdded': datetime.now().isoformat(),
                        'file_modified': file_modified,
                        'file_hash': file_hash,
                        'page_count': page_count
                    }

                    if self.database.add_pdf_file(pdf_data):
                        results['added'] += 1
                    else:
                        results['errors'] += 1
                else:
                    # Check if file was modified since last scan
                    if existing['file_modified'] != file_modified:
                        page_count = get_pdf_page_count(filepath)

                        update_data = {
                            'file_modified': file_modified,
                            'page_count': page_count if page_count is not None else existing.get('page_count')
                        }

                        # Preserve existing tags
                        for field in ['Name', 'ImageType', 'Source', 'Campaign', 'Notes']:
                            db_field = field.lower() if field != 'ImageType' else 'image_type'
                            if existing.get(db_field):
                                update_data[field] = existing.get(db_field)

                        if self.database.update_pdf_file(existing['id'], update_data):
                            results['updated'] += 1
                        else:
                            results['errors'] += 1

            except Exception as e:
                print(f"Error processing PDF file {filepath}: {e}")
                results['errors'] += 1

        return results

    def add_new_pdf_file(self, filepath: str) -> bool:
        """
        Add a newly detected PDF file to the database.

        Args:
            filepath: Path to the new PDF file

        Returns:
            True if successful, False otherwise
        """
        try:
            if not is_supported_pdf(filepath):
                return False

            filename = os.path.basename(filepath)
            file_modified = datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()

            page_count = get_pdf_page_count(filepath)

            with open(filepath, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            pdf_data = {
                'filepath': filepath,
                'filename': filename,
                'Name': os.path.splitext(filename)[0],
                'ImageType': 'Handout',  # Default type
                'DateAdded': datetime.now().isoformat(),
                'file_modified': file_modified,
                'file_hash': file_hash,
                'page_count': page_count
            }

            return self.database.add_pdf_file(pdf_data) is not None

        except Exception as e:
            print(f"Error adding new PDF file {filepath}: {e}")
            return False

    def update_existing_pdf_file(self, filepath: str) -> bool:
        """
        Update an existing PDF file in the database.

        Args:
            filepath: Path to the modified PDF file

        Returns:
            True if successful, False otherwise
        """
        try:
            existing = self.database.get_pdf_file_by_filepath(filepath)
            if not existing:
                return self.add_new_pdf_file(filepath)

            page_count = get_pdf_page_count(filepath)
            file_modified = datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()

            # Preserve existing tags
            update_data = {
                'Name': existing.get('name'),
                'ImageType': existing.get('image_type', 'Handout'),
                'Source': existing.get('source'),
                'Campaign': existing.get('campaign'),
                'Notes': existing.get('notes'),
                'file_modified': file_modified,
                'page_count': page_count if page_count is not None else existing.get('page_count')
            }

            return self.database.update_pdf_file(existing['id'], update_data)

        except Exception as e:
            print(f"Error updating PDF file {filepath}: {e}")
            return False

    def verify_all_pdf_references(self) -> dict:
        """
        Verify all PDF file references in the database still exist.

        Returns:
            Dictionary with verification results
        """
        results = {
            'verified': 0,
            'missing': [],
            'errors': 0
        }

        try:
            all_pdfs = self.database.get_all_pdf_files()

            for pdf in all_pdfs:
                pdf_id = pdf['id']
                filepath = pdf['filepath']

                try:
                    if os.path.exists(filepath) and os.path.isfile(filepath):
                        self.database.mark_pdf_missing(pdf_id, False)
                        results['verified'] += 1
                    else:
                        self.database.mark_pdf_missing(pdf_id, True)
                        results['missing'].append(pdf)
                        print(f"Missing PDF file: {filepath}")

                except Exception as e:
                    print(f"Error verifying PDF {filepath}: {e}")
                    results['errors'] += 1

        except Exception as e:
            print(f"Error during PDF verification: {e}")
            results['errors'] += 1

        return results


class TokenFolderEventHandler(FileSystemEventHandler):
    """Handles file system events for the token folder."""

    def __init__(self, scanner: TokenScanner, token_folder: str):
        """
        Initialize the event handler.

        Args:
            scanner: TokenScanner instance
            token_folder: Path to the token folder
        """
        self.scanner = scanner
        self.token_folder = os.path.abspath(token_folder)
        super().__init__()

    def _is_image_in_token_folder(self, filepath: str) -> bool:
        """Check if the file is an image (PNG or JPEG) in the token folder."""
        filepath = os.path.abspath(filepath)
        lower = filepath.lower()
        return ((lower.endswith('.png') or lower.endswith('.jpg') or lower.endswith('.jpeg')) and
                filepath.startswith(self.token_folder))

    def _is_audio_in_token_folder(self, filepath: str) -> bool:
        """Check if the file is an audio file in the token folder."""
        filepath = os.path.abspath(filepath)
        return is_supported_audio(filepath) and filepath.startswith(self.token_folder)

    def _is_pdf_in_token_folder(self, filepath: str) -> bool:
        """Check if the file is a PDF in the token folder."""
        filepath = os.path.abspath(filepath)
        return is_supported_pdf(filepath) and filepath.startswith(self.token_folder)

    def on_created(self, event):
        """Handle file creation events."""
        if event.is_directory:
            return

        abs_path = os.path.abspath(event.src_path)

        if self._is_image_in_token_folder(event.src_path):
            print(f"New image detected: {event.src_path}")
            # Give the file system a moment to finish writing
            time.sleep(0.5)
            self.scanner.add_new_file(abs_path)
        elif self._is_audio_in_token_folder(event.src_path):
            print(f"New audio file detected: {event.src_path}")
            time.sleep(0.5)
            self.scanner.add_new_audio_file(abs_path)
        elif self._is_pdf_in_token_folder(event.src_path):
            print(f"New PDF file detected: {event.src_path}")
            time.sleep(0.5)
            self.scanner.add_new_pdf_file(abs_path)

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        abs_path = os.path.abspath(event.src_path)

        if self._is_image_in_token_folder(event.src_path):
            print(f"Image modified: {event.src_path}")
            time.sleep(0.5)
            self.scanner.update_existing_file(abs_path)
        elif self._is_audio_in_token_folder(event.src_path):
            print(f"Audio file modified: {event.src_path}")
            time.sleep(0.5)
            self.scanner.update_existing_audio_file(abs_path)
        elif self._is_pdf_in_token_folder(event.src_path):
            print(f"PDF file modified: {event.src_path}")
            time.sleep(0.5)
            self.scanner.update_existing_pdf_file(abs_path)


class TokenFolderWatcher:
    """Watches the token folder for changes."""

    def __init__(self, scanner: TokenScanner, token_folder: str):
        """
        Initialize the folder watcher.

        Args:
            scanner: TokenScanner instance
            token_folder: Path to the token folder
        """
        self.scanner = scanner
        self.token_folder = token_folder
        self.observer = None

    def start(self):
        """Start watching the folder."""
        if self.observer is not None:
            return

        event_handler = TokenFolderEventHandler(self.scanner, self.token_folder)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.token_folder, recursive=True)
        self.observer.start()
        print(f"Started watching folder: {self.token_folder}")

    def stop(self):
        """Stop watching the folder."""
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            print("Stopped watching folder")

    def is_running(self) -> bool:
        """Check if the watcher is running."""
        return self.observer is not None and self.observer.is_alive()
