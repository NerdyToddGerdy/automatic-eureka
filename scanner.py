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

from file_utils import safe_file_op, FileOpTimeout, DEFAULT_FILE_IO_TIMEOUT

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

        # tinytag doesn't raise for content it can't actually parse (e.g. a
        # file with an audio extension but garbage bytes) -- it just returns
        # a tag with every field None. A real audio file always has a
        # duration, so treat a None duration as a parse failure.
        if tag.duration is None:
            return None

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

    def __init__(self, database: TokenDatabase, token_folder: Optional[str] = None,
                 file_io_timeout: int = DEFAULT_FILE_IO_TIMEOUT):
        """
        Initialize the scanner.

        Args:
            database: TokenDatabase instance
            token_folder: Optional path to folder for local scanning (Reference Mode doesn't need this)
            file_io_timeout: Per-file-operation timeout in seconds, so a hung NAS/SMB mount
                can't block a scan or verification pass indefinitely
        """
        self.token_folder = token_folder
        self.database = database
        self.file_io_timeout = file_io_timeout

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
            'errors': 0,
            'timed_out': 0
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
                file_info = safe_file_op(TokenMetadata.get_file_info, filepath, timeout=self.file_io_timeout)

                if file_info is None:
                    results['errors'] += 1
                    continue

                # Check if token exists in database
                existing = self.database.get_token_by_filepath(filepath)

                if existing is None:
                    wrote_metadata = False

                    # Add DateAdded if missing
                    if not file_info.get('DateAdded'):
                        file_info['DateAdded'] = datetime.now().isoformat()
                        safe_file_op(TokenMetadata.update_metadata, filepath,
                                     {'DateAdded': file_info['DateAdded']}, timeout=self.file_io_timeout)
                        wrote_metadata = True

                    # CRITICAL: If ImageType is None, default to 'Token' ONLY for new files
                    if file_info.get('ImageType') is None:
                        file_info['ImageType'] = 'Token'
                        # Write this default back to PNG to maintain DB-PNG sync
                        safe_file_op(TokenMetadata.update_metadata, filepath,
                                     {'ImageType': 'Token'}, timeout=self.file_io_timeout)
                        wrote_metadata = True

                    # Our own metadata write-back above bumps the file's mtime on
                    # disk; re-stat so the mtime we store matches reality, or the
                    # next scan sees a mismatch and wrongly treats this as modified.
                    if wrote_metadata:
                        new_mtime = safe_file_op(os.path.getmtime, filepath, timeout=self.file_io_timeout)
                        file_info['file_modified'] = datetime.fromtimestamp(new_mtime).isoformat()

                    # New token - add to database
                    if self.database.add_token(file_info):
                        results['added'] += 1
                    else:
                        results['errors'] += 1
                else:
                    # Check if file was modified since last scan
                    if existing['file_modified'] != file_info['file_modified']:
                        # CRITICAL: Preserve ImageType from database unless PNG has explicit value
                        # Database is source of truth; PNG may have incomplete metadata.
                        # existing comes from a DB row (snake_case columns), file_info from
                        # PNG metadata (PascalCase keys) -- don't mix the two up here.
                        if file_info.get('ImageType') is None and existing.get('image_type'):
                            file_info['ImageType'] = existing['image_type']

                        # File was modified - update from PNG metadata
                        if self.database.update_token_by_filepath(filepath, file_info):
                            results['updated'] += 1
                        else:
                            results['errors'] += 1

            except FileOpTimeout:
                print(f"Timeout accessing file (possible network issue): {filepath}")
                results['timed_out'] += 1
                existing = self.database.get_token_by_filepath(filepath)
                if existing:
                    self.database.mark_missing(existing['id'], True)
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
            file_info = safe_file_op(TokenMetadata.get_file_info, filepath, timeout=self.file_io_timeout)

            if file_info is None:
                return False

            # Add DateAdded if missing
            if not file_info.get('DateAdded'):
                file_info['DateAdded'] = datetime.now().isoformat()
                safe_file_op(TokenMetadata.update_metadata, filepath,
                             {'DateAdded': file_info['DateAdded']}, timeout=self.file_io_timeout)

            # Add to database
            return self.database.add_token(file_info) is not None

        except FileOpTimeout:
            print(f"Timeout adding new file (possible network issue): {filepath}")
            return False
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
            file_info = safe_file_op(TokenMetadata.get_file_info, filepath, timeout=self.file_io_timeout)

            if file_info is None:
                return False

            # Update database
            return self.database.update_token_by_filepath(filepath, file_info)

        except FileOpTimeout:
            print(f"Timeout updating file (possible network issue): {filepath}")
            return False
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
            'errors': 0,
            'timed_out': 0
        }

        try:
            # Get all tokens from database
            all_tokens = self.database.get_all_tokens()

            for token in all_tokens:
                token_id = token['id']
                filepath = token['filepath']

                try:
                    # Check if file exists
                    def _check():
                        return os.path.exists(filepath) and os.path.isfile(filepath)

                    if safe_file_op(_check, timeout=self.file_io_timeout):
                        # File exists - mark as not missing
                        self.database.mark_missing(token_id, False)
                        self.database.update_last_verified(token_id, datetime.now().isoformat())
                        results['verified'] += 1
                    else:
                        # File is missing - mark as missing
                        self.database.mark_missing(token_id, True)
                        results['missing'].append(token)
                        print(f"Missing file: {filepath}")

                except FileOpTimeout:
                    print(f"Timeout verifying file (possible network issue): {filepath}")
                    results['timed_out'] += 1
                    self.database.mark_missing(token_id, True)
                    results['missing'].append(token)
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
            'errors': 0,
            'timed_out': 0
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
                file_modified = datetime.fromtimestamp(
                    safe_file_op(os.path.getmtime, filepath, timeout=self.file_io_timeout)
                ).isoformat()

                # Check if audio file exists in database
                existing = self.database.get_audio_file_by_filepath(filepath)

                if existing is None:
                    # New audio file - add to database
                    audio_meta = safe_file_op(get_audio_metadata, filepath, timeout=self.file_io_timeout)

                    # Calculate file hash
                    def _hash():
                        with open(filepath, 'rb') as f:
                            return hashlib.sha256(f.read()).hexdigest()
                    file_hash = safe_file_op(_hash, timeout=self.file_io_timeout)

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
                        'file_size': safe_file_op(os.path.getsize, filepath, timeout=self.file_io_timeout)
                    }

                    if self.database.add_audio_file(audio_data):
                        results['added'] += 1
                    else:
                        results['errors'] += 1
                else:
                    # Check if file was modified since last scan
                    if existing['file_modified'] != file_modified:
                        # File was modified - update metadata
                        audio_meta = safe_file_op(get_audio_metadata, filepath, timeout=self.file_io_timeout)

                        update_data = {
                            'file_modified': file_modified,
                            'duration_seconds': audio_meta.get('duration_seconds') if audio_meta else existing.get('duration_seconds'),
                            'file_size': safe_file_op(os.path.getsize, filepath, timeout=self.file_io_timeout)
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

            except FileOpTimeout:
                print(f"Timeout accessing audio file (possible network issue): {filepath}")
                results['timed_out'] += 1
                existing = self.database.get_audio_file_by_filepath(filepath)
                if existing:
                    self.database.mark_audio_missing(existing['id'], True)
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
            file_modified = datetime.fromtimestamp(
                safe_file_op(os.path.getmtime, filepath, timeout=self.file_io_timeout)
            ).isoformat()

            # Get audio metadata
            audio_meta = safe_file_op(get_audio_metadata, filepath, timeout=self.file_io_timeout)

            # Calculate file hash
            def _hash():
                with open(filepath, 'rb') as f:
                    return hashlib.sha256(f.read()).hexdigest()
            file_hash = safe_file_op(_hash, timeout=self.file_io_timeout)

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
                'file_size': safe_file_op(os.path.getsize, filepath, timeout=self.file_io_timeout)
            }

            return self.database.add_audio_file(audio_data) is not None

        except FileOpTimeout:
            print(f"Timeout adding new audio file (possible network issue): {filepath}")
            return False
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
            audio_meta = safe_file_op(get_audio_metadata, filepath, timeout=self.file_io_timeout)
            file_modified = datetime.fromtimestamp(
                safe_file_op(os.path.getmtime, filepath, timeout=self.file_io_timeout)
            ).isoformat()

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

        except FileOpTimeout:
            print(f"Timeout updating audio file (possible network issue): {filepath}")
            return False
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
            'errors': 0,
            'timed_out': 0
        }

        try:
            all_audio = self.database.get_all_audio_files()

            for audio in all_audio:
                audio_id = audio['id']
                filepath = audio['filepath']

                try:
                    def _check():
                        return os.path.exists(filepath) and os.path.isfile(filepath)

                    if safe_file_op(_check, timeout=self.file_io_timeout):
                        self.database.mark_audio_missing(audio_id, False)
                        results['verified'] += 1
                    else:
                        self.database.mark_audio_missing(audio_id, True)
                        results['missing'].append(audio)
                        print(f"Missing audio file: {filepath}")

                except FileOpTimeout:
                    print(f"Timeout verifying audio file (possible network issue): {filepath}")
                    results['timed_out'] += 1
                    self.database.mark_audio_missing(audio_id, True)
                    results['missing'].append(audio)
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
            'errors': 0,
            'timed_out': 0
        }

        pdf_files = self.find_pdf_files()

        for i, filepath in enumerate(pdf_files):
            try:
                if progress_callback:
                    progress_callback(i + 1, len(pdf_files), filepath)

                filename = os.path.basename(filepath)
                file_modified = datetime.fromtimestamp(
                    safe_file_op(os.path.getmtime, filepath, timeout=self.file_io_timeout)
                ).isoformat()

                existing = self.database.get_pdf_file_by_filepath(filepath)

                def _hash():
                    with open(filepath, 'rb') as f:
                        return hashlib.sha256(f.read()).hexdigest()

                if existing is None:
                    # New PDF file - add to database
                    page_count = safe_file_op(get_pdf_page_count, filepath, timeout=self.file_io_timeout)
                    file_hash = safe_file_op(_hash, timeout=self.file_io_timeout)

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
                        page_count = safe_file_op(get_pdf_page_count, filepath, timeout=self.file_io_timeout)

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

            except FileOpTimeout:
                print(f"Timeout accessing PDF file (possible network issue): {filepath}")
                results['timed_out'] += 1
                existing = self.database.get_pdf_file_by_filepath(filepath)
                if existing:
                    self.database.mark_pdf_missing(existing['id'], True)
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
            file_modified = datetime.fromtimestamp(
                safe_file_op(os.path.getmtime, filepath, timeout=self.file_io_timeout)
            ).isoformat()

            page_count = safe_file_op(get_pdf_page_count, filepath, timeout=self.file_io_timeout)

            def _hash():
                with open(filepath, 'rb') as f:
                    return hashlib.sha256(f.read()).hexdigest()
            file_hash = safe_file_op(_hash, timeout=self.file_io_timeout)

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

        except FileOpTimeout:
            print(f"Timeout adding new PDF file (possible network issue): {filepath}")
            return False
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

            page_count = safe_file_op(get_pdf_page_count, filepath, timeout=self.file_io_timeout)
            file_modified = datetime.fromtimestamp(
                safe_file_op(os.path.getmtime, filepath, timeout=self.file_io_timeout)
            ).isoformat()

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

        except FileOpTimeout:
            print(f"Timeout updating PDF file (possible network issue): {filepath}")
            return False
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
            'errors': 0,
            'timed_out': 0
        }

        try:
            all_pdfs = self.database.get_all_pdf_files()

            for pdf in all_pdfs:
                pdf_id = pdf['id']
                filepath = pdf['filepath']

                try:
                    def _check():
                        return os.path.exists(filepath) and os.path.isfile(filepath)

                    if safe_file_op(_check, timeout=self.file_io_timeout):
                        self.database.mark_pdf_missing(pdf_id, False)
                        results['verified'] += 1
                    else:
                        self.database.mark_pdf_missing(pdf_id, True)
                        results['missing'].append(pdf)
                        print(f"Missing PDF file: {filepath}")

                except FileOpTimeout:
                    print(f"Timeout verifying PDF file (possible network issue): {filepath}")
                    results['timed_out'] += 1
                    self.database.mark_pdf_missing(pdf_id, True)
                    results['missing'].append(pdf)
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
