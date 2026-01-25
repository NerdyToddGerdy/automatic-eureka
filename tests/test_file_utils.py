"""
Tests for file_utils module.
Tests file hashing, duplicate detection, and file verification functions.
"""
import os
import pytest
from PIL import Image
from file_utils import (
    calculate_file_hash,
    verify_file_exists,
    find_duplicates,
    get_file_size_mb,
    get_file_info_summary
)


class TestCalculateFileHash:
    """Tests for calculate_file_hash function."""

    def test_hash_consistency(self, sample_png_path):
        """Same file should produce same hash on multiple calls."""
        hash1 = calculate_file_hash(sample_png_path)
        hash2 = calculate_file_hash(sample_png_path)

        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters

    def test_different_images_different_hashes(self, temp_dir):
        """Different images should produce different hashes."""
        # Create two different images
        img1_path = os.path.join(temp_dir, 'img1.png')
        img2_path = os.path.join(temp_dir, 'img2.png')

        img1 = Image.new('RGB', (100, 100), color='red')
        img1.save(img1_path, 'PNG')

        img2 = Image.new('RGB', (100, 100), color='blue')
        img2.save(img2_path, 'PNG')

        hash1 = calculate_file_hash(img1_path)
        hash2 = calculate_file_hash(img2_path)

        assert hash1 != hash2

    def test_same_pixels_different_sizes_different_hashes(self, temp_dir):
        """Same pixel pattern but different sizes should produce different hashes."""
        img1_path = os.path.join(temp_dir, 'img1.png')
        img2_path = os.path.join(temp_dir, 'img2.png')

        # Create identical color but different sizes
        img1 = Image.new('RGB', (100, 100), color='red')
        img1.save(img1_path, 'PNG')

        img2 = Image.new('RGB', (200, 200), color='red')
        img2.save(img2_path, 'PNG')

        hash1 = calculate_file_hash(img1_path)
        hash2 = calculate_file_hash(img2_path)

        assert hash1 != hash2

    def test_rgba_to_rgb_conversion(self, temp_dir):
        """RGBA images should be converted to RGB for hashing."""
        img_path = os.path.join(temp_dir, 'rgba.png')

        # Create RGBA image
        img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))
        img.save(img_path, 'PNG')

        # Should not raise exception
        hash_value = calculate_file_hash(img_path)
        assert isinstance(hash_value, str)
        assert len(hash_value) == 64

    def test_file_not_found(self):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            calculate_file_hash('/nonexistent/file.png')

    def test_invalid_image_file(self, temp_dir):
        """Should raise exception for non-image file."""
        invalid_path = os.path.join(temp_dir, 'invalid.png')

        # Create a text file with .png extension
        with open(invalid_path, 'w') as f:
            f.write('This is not an image')

        with pytest.raises(Exception):
            calculate_file_hash(invalid_path)


class TestVerifyFileExists:
    """Tests for verify_file_exists function."""

    def test_existing_file(self, sample_png_path):
        """Should return True for existing, readable file."""
        assert verify_file_exists(sample_png_path) is True

    def test_nonexistent_file(self):
        """Should return False for non-existent file."""
        assert verify_file_exists('/nonexistent/file.png') is False

    def test_directory_not_file(self, temp_dir):
        """Should return False for directory path."""
        assert verify_file_exists(temp_dir) is False

    def test_empty_path(self):
        """Should return False for empty path."""
        assert verify_file_exists('') is False


class TestFindDuplicates:
    """Tests for find_duplicates function."""

    def test_no_duplicates(self, test_db, sample_png_path):
        """Should return None for both duplicate checks when no duplicates exist."""
        result = find_duplicates(test_db, sample_png_path)

        assert result['content_duplicate'] is None
        assert result['name_collision'] is None
        assert result['hash'] is not None
        assert isinstance(result['hash'], str)

    def test_content_duplicate_detection(self, test_db, temp_dir):
        """Should detect content duplicate (same hash, different path)."""
        # Create two identical images with different paths
        img1_path = os.path.join(temp_dir, 'original.png')
        img2_path = os.path.join(temp_dir, 'copy.png')

        img = Image.new('RGB', (100, 100), color='red')
        img.save(img1_path, 'PNG')
        img.save(img2_path, 'PNG')

        # Add first image to database
        hash1 = calculate_file_hash(img1_path)
        token_id = test_db.add_token({
            'filepath': img1_path,
            'filename': 'original.png',
            'ImageType': 'Token'
        })
        test_db.update_file_hash(token_id, hash1)

        # Check second image for duplicates
        result = find_duplicates(test_db, img2_path)

        assert result['content_duplicate'] is not None
        assert result['content_duplicate']['filepath'] == img1_path
        assert result['hash'] == hash1

    def test_name_collision_detection(self, test_db, temp_dir):
        """Should detect name collision (same filename, different path)."""
        # Create two different images with same filename in different directories
        dir1 = os.path.join(temp_dir, 'dir1')
        dir2 = os.path.join(temp_dir, 'dir2')
        os.makedirs(dir1)
        os.makedirs(dir2)

        img1_path = os.path.join(dir1, 'token.png')
        img2_path = os.path.join(dir2, 'token.png')

        img1 = Image.new('RGB', (100, 100), color='red')
        img1.save(img1_path, 'PNG')

        img2 = Image.new('RGB', (100, 100), color='blue')
        img2.save(img2_path, 'PNG')

        # Add first image to database
        test_db.add_token({
            'filepath': img1_path,
            'filename': 'token.png',
            'ImageType': 'Token'
        })

        # Check second image for duplicates
        result = find_duplicates(test_db, img2_path)

        assert result['name_collision'] is not None
        assert result['name_collision']['filename'] == 'token.png'
        assert result['content_duplicate'] is None  # Different content

    def test_no_self_duplicate(self, test_db, sample_png_path):
        """Should not report file as duplicate of itself."""
        # Add file to database
        hash_value = calculate_file_hash(sample_png_path)
        token_id = test_db.add_token({
            'filepath': sample_png_path,
            'filename': os.path.basename(sample_png_path),
            'ImageType': 'Token'
        })
        test_db.update_file_hash(token_id, hash_value)

        # Check same file
        result = find_duplicates(test_db, sample_png_path)

        assert result['content_duplicate'] is None
        assert result['name_collision'] is None

    def test_prehashed_file(self, test_db, sample_png_path):
        """Should use provided hash instead of recalculating."""
        pre_hash = calculate_file_hash(sample_png_path)

        result = find_duplicates(test_db, sample_png_path, file_hash=pre_hash)

        assert result['hash'] == pre_hash


class TestGetFileSizeMb:
    """Tests for get_file_size_mb function."""

    def test_file_size_calculation(self, sample_png_path):
        """Should return file size in megabytes."""
        size_mb = get_file_size_mb(sample_png_path)

        assert isinstance(size_mb, float)
        assert size_mb > 0
        assert size_mb < 1  # Sample PNG should be less than 1 MB

    def test_nonexistent_file(self):
        """Should return 0.0 for non-existent file."""
        size_mb = get_file_size_mb('/nonexistent/file.png')

        assert size_mb == 0.0

    def test_size_consistency(self, sample_png_path):
        """File size should be consistent across multiple calls."""
        size1 = get_file_size_mb(sample_png_path)
        size2 = get_file_size_mb(sample_png_path)

        assert size1 == size2


class TestGetFileInfoSummary:
    """Tests for get_file_info_summary function."""

    def test_valid_file_info(self, sample_png_path):
        """Should return complete info for valid file."""
        info = get_file_info_summary(sample_png_path)

        assert info['exists'] is True
        assert 'size_mb' in info
        assert info['size_mb'] > 0
        assert info['width'] == 100
        assert info['height'] == 100
        assert info['filename'] == os.path.basename(sample_png_path)
        assert info['directory'] == os.path.dirname(sample_png_path)

    def test_nonexistent_file_info(self):
        """Should return error info for non-existent file."""
        info = get_file_info_summary('/nonexistent/file.png')

        assert info['exists'] is False
        assert 'error' in info
        assert info['filename'] == 'file.png'
        assert info['directory'] == '/nonexistent'

    def test_jpeg_file_info(self, sample_jpeg_path):
        """Should work with JPEG files too."""
        info = get_file_info_summary(sample_jpeg_path)

        assert info['exists'] is True
        assert info['width'] == 100
        assert info['height'] == 100
        assert info['filename'].endswith('.jpg')

    def test_different_sized_image(self, temp_dir):
        """Should correctly report different image dimensions."""
        img_path = os.path.join(temp_dir, 'large.png')
        img = Image.new('RGB', (500, 300), color='green')
        img.save(img_path, 'PNG')

        info = get_file_info_summary(img_path)

        assert info['width'] == 500
        assert info['height'] == 300
