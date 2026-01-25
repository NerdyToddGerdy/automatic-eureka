"""
In-memory LRU cache for images from Google Drive.
Stores images in memory to reduce API calls and improve performance.
"""

from collections import OrderedDict
from threading import Lock
from typing import Optional, Tuple
import sys


class ImageCache:
    """
    Thread-safe LRU cache for image data.

    Stores images in memory with automatic eviction when size limit reached.
    """

    def __init__(self, max_size_mb: int = 100):
        """
        Initialize the cache.

        Args:
            max_size_mb: Maximum cache size in megabytes (default 100MB)
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cache = OrderedDict()
        self.lock = Lock()
        self.current_size = 0

    def get(self, key: str) -> Optional[Tuple[bytes, str]]:
        """
        Get an image from the cache.

        Args:
            key: Cache key (typically Drive file ID)

        Returns:
            Tuple of (image_bytes, mimetype) if found, None otherwise
        """
        with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                return self.cache[key]
            return None

    def set(self, key: str, data: bytes, mimetype: str = 'image/png') -> None:
        """
        Store an image in the cache.

        Args:
            key: Cache key (typically Drive file ID)
            data: Image data as bytes
            mimetype: MIME type of the image
        """
        with self.lock:
            data_size = sys.getsizeof(data)

            # If item already exists, remove old version first
            if key in self.cache:
                old_data, _ = self.cache[key]
                self.current_size -= sys.getsizeof(old_data)
                del self.cache[key]

            # Evict items until we have space
            while self.current_size + data_size > self.max_size_bytes and self.cache:
                # Remove least recently used (first item)
                oldest_key, (oldest_data, _) = self.cache.popitem(last=False)
                self.current_size -= sys.getsizeof(oldest_data)

            # Only add if it fits in cache
            if data_size <= self.max_size_bytes:
                self.cache[key] = (data, mimetype)
                self.current_size += data_size

    def clear(self) -> None:
        """
        Clear all items from the cache.
        """
        with self.lock:
            self.cache.clear()
            self.current_size = 0

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats (size, count, hit_rate, etc.)
        """
        with self.lock:
            return {
                'size_mb': round(self.current_size / (1024 * 1024), 2),
                'max_size_mb': round(self.max_size_bytes / (1024 * 1024), 2),
                'count': len(self.cache),
                'utilization': round((self.current_size / self.max_size_bytes) * 100, 2) if self.max_size_bytes > 0 else 0
            }

    def remove(self, key: str) -> bool:
        """
        Remove a specific item from the cache.

        Args:
            key: Cache key to remove

        Returns:
            True if item was removed, False if not found
        """
        with self.lock:
            if key in self.cache:
                data, _ = self.cache[key]
                self.current_size -= sys.getsizeof(data)
                del self.cache[key]
                return True
            return False


# Global cache instance
_image_cache = None


def get_image_cache(max_size_mb: int = 100) -> ImageCache:
    """
    Get or create the global image cache instance.

    Args:
        max_size_mb: Maximum cache size in MB (only used on first call)

    Returns:
        ImageCache instance
    """
    global _image_cache
    if _image_cache is None:
        _image_cache = ImageCache(max_size_mb)
    return _image_cache
