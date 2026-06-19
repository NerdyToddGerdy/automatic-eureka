"""
Unit tests for cache.py (ImageCache LRU cache).
"""
import sys

import pytest

import cache as cache_module
from cache import ImageCache, get_image_cache


class TestGetSet:
    def test_set_then_get_returns_same_data(self):
        c = ImageCache(max_size_mb=1)
        c.set('a', b'hello', 'image/png')

        assert c.get('a') == (b'hello', 'image/png')

    def test_get_missing_key_returns_none(self):
        c = ImageCache(max_size_mb=1)

        assert c.get('missing') is None

    def test_set_default_mimetype_is_image_png(self):
        c = ImageCache(max_size_mb=1)
        c.set('a', b'hello')

        assert c.get('a') == (b'hello', 'image/png')


class TestSetReplacesExisting:
    def test_set_existing_key_replaces_without_duplicate_entry(self):
        c = ImageCache(max_size_mb=1)
        c.set('a', b'first')
        c.set('a', b'second')

        assert c.get('a') == (b'second', 'image/png')
        assert len(c.cache) == 1

    def test_set_existing_key_updates_size_accounting(self):
        c = ImageCache(max_size_mb=1)
        c.set('a', b'x' * 100)
        c.set('a', b'y' * 50)

        assert c.current_size == sys.getsizeof(b'y' * 50)


class TestEviction:
    def test_evicts_least_recently_used_first_inserted_item(self):
        payload = b'x' * 100
        item_size = sys.getsizeof(payload)
        c = ImageCache(max_size_mb=1)
        c.max_size_bytes = item_size * 2  # room for exactly 2 items

        c.set('a', payload)
        c.set('b', payload)
        c.set('c', payload)  # forces eviction of the oldest entry, 'a'

        assert c.get('a') is None
        assert c.get('b') is not None
        assert c.get('c') is not None

    def test_get_moves_item_to_most_recently_used_position(self):
        payload = b'x' * 100
        item_size = sys.getsizeof(payload)
        c = ImageCache(max_size_mb=1)
        c.max_size_bytes = item_size * 2  # room for exactly 2 items

        c.set('a', payload)
        c.set('b', payload)
        c.get('a')  # 'a' becomes most-recently-used; 'b' is now the eviction candidate
        c.set('c', payload)

        assert c.get('b') is None
        assert c.get('a') is not None
        assert c.get('c') is not None

    def test_item_larger_than_max_size_is_never_stored(self):
        c = ImageCache(max_size_mb=1)
        c.max_size_bytes = 100
        oversized = b'x' * 200  # sys.getsizeof(...) > 100

        c.set('big', oversized)

        assert c.get('big') is None
        assert c.current_size == 0
        assert len(c.cache) == 0


class TestRemove:
    def test_remove_existing_key_returns_true_and_decrements_size(self):
        c = ImageCache(max_size_mb=1)
        c.set('a', b'hello')
        size_before = c.current_size

        result = c.remove('a')

        assert result is True
        assert c.get('a') is None
        assert c.current_size == size_before - sys.getsizeof(b'hello')

    def test_remove_missing_key_returns_false_and_is_noop(self):
        c = ImageCache(max_size_mb=1)

        result = c.remove('missing')

        assert result is False
        assert c.current_size == 0


class TestClear:
    def test_clear_empties_cache_and_resets_size(self):
        c = ImageCache(max_size_mb=1)
        c.set('a', b'hello')
        c.set('b', b'world')

        c.clear()

        assert len(c.cache) == 0
        assert c.current_size == 0


class TestGetStats:
    def test_get_stats_reports_size_and_count(self):
        payload = b'x' * 100
        c = ImageCache(max_size_mb=1)
        c.set('a', payload)

        stats = c.get_stats()

        assert stats['count'] == 1
        assert stats['max_size_mb'] == 1
        assert stats['size_mb'] == round(sys.getsizeof(payload) / (1024 * 1024), 2)

    def test_get_stats_utilization_percentage(self):
        payload = b'x' * 100
        item_size = sys.getsizeof(payload)
        c = ImageCache(max_size_mb=1)
        c.max_size_bytes = item_size * 4

        c.set('a', payload)
        stats = c.get_stats()

        assert stats['utilization'] == round((item_size / (item_size * 4)) * 100, 2)

    def test_get_stats_utilization_zero_when_max_size_is_zero(self):
        c = ImageCache(max_size_mb=0)

        stats = c.get_stats()

        assert stats['utilization'] == 0


class TestGetImageCacheSingleton:
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        cache_module._image_cache = None
        yield
        cache_module._image_cache = None

    def test_returns_same_instance_on_repeated_calls(self):
        first = get_image_cache(max_size_mb=5)
        second = get_image_cache(max_size_mb=5)

        assert first is second

    def test_first_call_size_wins_over_later_calls(self):
        first = get_image_cache(max_size_mb=5)
        second = get_image_cache(max_size_mb=999)

        assert second is first
        assert second.max_size_bytes == 5 * 1024 * 1024
