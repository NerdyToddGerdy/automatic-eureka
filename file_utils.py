"""
File utilities for Image Vault.
Handles file hashing, duplicate detection, and file verification.
"""

import hashlib
import os
import threading
from PIL import Image
import io
from typing import Optional, Dict

DEFAULT_FILE_IO_TIMEOUT = 5  # seconds


class FileOpTimeout(Exception):
    """Raised when a safe_file_op-wrapped call exceeds its timeout."""


def safe_file_op(fn, *args, timeout=DEFAULT_FILE_IO_TIMEOUT, **kwargs):
    """
    Run fn(*args, **kwargs) in a background thread, bounded to `timeout`
    seconds, so a hung syscall (dead NAS/SMB mount, ejected drive) can't
    block the caller forever.

    Raises FileOpTimeout if it doesn't finish in time. Any other exception
    raised by fn propagates normally, so existing error handling at call
    sites is unaffected.

    Deliberately uses a raw daemon threading.Thread rather than
    concurrent.futures.ThreadPoolExecutor. Python can't forcibly kill a
    thread stuck in a blocking syscall, and ThreadPoolExecutor has two traps
    for that case: (1) its context manager calls shutdown(wait=True) on
    exit, which blocks until the stuck worker finishes - i.e. for the exact
    same unbounded duration this function exists to avoid - regardless of
    the future's own timeout; and (2) its worker threads are non-daemon and
    registered with a process-wide atexit hook that joins every worker ever
    created, so a single permanently-stuck call would hang the whole
    process at shutdown, not just this call. A daemon thread that we simply
    abandon on timeout has neither problem: the calling thread is never
    blocked past `timeout`, and the interpreter won't wait for daemon
    threads on exit.
    """
    result: dict = {}

    def _runner():
        try:
            result['value'] = fn(*args, **kwargs)
        except Exception as e:
            result['error'] = e

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        # Still running - abandon it (it's a daemon thread, so this won't
        # block process exit) and report the timeout to the caller.
        raise FileOpTimeout(f"Timed out after {timeout}s")

    if 'error' in result:
        raise result['error']

    return result.get('value')


def calculate_file_hash(filepath: str) -> str:
    """
    Calculate SHA-256 hash of PNG image pixel data.

    Hashes the actual image pixels (not raw file bytes) to detect content duplicates
    even if metadata differs (EXIF, timestamps, software tags).

    Args:
        filepath: Path to the PNG file

    Returns:
        SHA-256 hash as hexadecimal string

    Raises:
        FileNotFoundError: If file doesn't exist
        Exception: If file can't be opened or processed
    """
    try:
        # Open image and convert to RGB (normalize format)
        with Image.open(filepath) as img:
            # Convert to RGB to normalize (handles RGBA, grayscale, etc.)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Get pixel data as bytes
            pixel_data = img.tobytes()

            # Calculate hash of pixel data
            hash_obj = hashlib.sha256()
            hash_obj.update(pixel_data)

            # Also include image dimensions to differentiate resized versions
            dimensions = f"{img.width}x{img.height}".encode()
            hash_obj.update(dimensions)

            return hash_obj.hexdigest()

    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {filepath}")
    except Exception as e:
        raise Exception(f"Error calculating hash for {filepath}: {str(e)}")


def calculate_file_hash_from_bytes(file_bytes: bytes) -> str:
    """
    Calculate SHA-256 hash of image pixel data from bytes in memory.

    Same as calculate_file_hash() but works with in-memory bytes.
    Useful for Drive uploads where file hasn't been saved to disk yet.

    Args:
        file_bytes: Image file contents as bytes

    Returns:
        SHA-256 hash as hexadecimal string

    Raises:
        Exception: If bytes can't be processed as an image
    """
    try:
        # Create BytesIO from bytes
        file_stream = io.BytesIO(file_bytes)

        # Open image and convert to RGB (normalize format)
        with Image.open(file_stream) as img:
            # Convert to RGB to normalize (handles RGBA, grayscale, etc.)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Get pixel data as bytes
            pixel_data = img.tobytes()

            # Calculate hash of pixel data
            hash_obj = hashlib.sha256()
            hash_obj.update(pixel_data)

            # Also include image dimensions to differentiate resized versions
            dimensions = f"{img.width}x{img.height}".encode()
            hash_obj.update(dimensions)

            return hash_obj.hexdigest()

    except Exception as e:
        raise Exception(f"Error calculating hash from bytes: {str(e)}")


def verify_file_exists(filepath: str) -> bool:
    """
    Check if file exists and is readable.

    Args:
        filepath: Path to check

    Returns:
        True if file exists and is readable, False otherwise
    """
    try:
        return os.path.isfile(filepath) and os.access(filepath, os.R_OK)
    except Exception:
        return False


def find_duplicates(db, filepath: str, file_hash: str = None) -> Dict[str, Optional[Dict]]:
    """
    Check for duplicate files by both content hash and filename.

    Args:
        db: TokenDatabase instance
        filepath: Path to the file being checked
        file_hash: Pre-calculated hash (optional, will calculate if not provided)

    Returns:
        Dictionary with duplicate information:
        {
            'content_duplicate': token_dict or None,  # Same hash
            'name_collision': token_dict or None,     # Same filename (different path)
            'hash': file_hash
        }
    """
    result = {
        'content_duplicate': None,
        'name_collision': None,
        'hash': None
    }

    try:
        # Calculate hash if not provided
        if file_hash is None:
            file_hash = calculate_file_hash(filepath)

        result['hash'] = file_hash

        # Check for content duplicate (same hash)
        content_dup = db.find_by_hash(file_hash)
        if content_dup and content_dup['filepath'] != filepath:
            result['content_duplicate'] = content_dup

        # Check for filename collision (same basename, different path)
        filename = os.path.basename(filepath)
        name_collision = db.find_by_filename(filename)

        # Filter out exact path match and only include if paths differ
        if name_collision:
            for token in name_collision:
                if token['filepath'] != filepath:
                    result['name_collision'] = token
                    break

        return result

    except Exception as e:
        print(f"Error checking duplicates for {filepath}: {e}")
        return result


def get_file_size_mb(filepath: str) -> float:
    """
    Get file size in megabytes.

    Args:
        filepath: Path to file

    Returns:
        File size in MB, or 0 if error
    """
    try:
        size_bytes = os.path.getsize(filepath)
        return size_bytes / (1024 * 1024)
    except Exception:
        return 0.0


def get_file_info_summary(filepath: str) -> Dict:
    """
    Get summary information about a file.

    Args:
        filepath: Path to file

    Returns:
        Dictionary with file information
    """
    try:
        stat = os.stat(filepath)

        with Image.open(filepath) as img:
            width, height = img.size

        return {
            'exists': True,
            'size_mb': stat.st_size / (1024 * 1024),
            'width': width,
            'height': height,
            'filename': os.path.basename(filepath),
            'directory': os.path.dirname(filepath)
        }
    except Exception as e:
        return {
            'exists': False,
            'error': str(e),
            'filename': os.path.basename(filepath) if filepath else 'Unknown',
            'directory': os.path.dirname(filepath) if filepath else 'Unknown'
        }
