"""
Tests for metadata module.
Tests PNG/JPEG metadata read/write, format detection, and file info.
"""
import os
import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from metadata import TokenMetadata


class TestDetectImageFormat:
    """Tests for detect_image_format static method."""

    def test_png_extension(self, sample_png_path):
        assert TokenMetadata.detect_image_format(sample_png_path) == 'PNG'

    def test_jpeg_extension(self, sample_jpeg_path):
        assert TokenMetadata.detect_image_format(sample_jpeg_path) == 'JPEG'

    def test_jpg_extension(self, temp_dir):
        filepath = os.path.join(temp_dir, 'sample.jpg')
        Image.new('RGB', (10, 10), color='blue').save(filepath, 'JPEG')

        assert TokenMetadata.detect_image_format(filepath) == 'JPEG'

    def test_pil_fallback_for_unknown_extension(self, temp_dir):
        filepath = os.path.join(temp_dir, 'sample.bin')
        Image.new('RGB', (10, 10), color='red').save(filepath, 'PNG')

        assert TokenMetadata.detect_image_format(filepath) == 'PNG'

    def test_unsupported_format_raises(self, temp_dir):
        filepath = os.path.join(temp_dir, 'notes.txt')
        with open(filepath, 'w') as f:
            f.write('not an image')

        with pytest.raises(ValueError):
            TokenMetadata.detect_image_format(filepath)


class TestPngRoundTrip:
    """Tests for write_token_metadata / read_token_metadata on PNG files."""

    def test_write_then_read(self, sample_png_path, sample_metadata):
        success = TokenMetadata.write_token_metadata(sample_png_path, sample_metadata)
        assert success is True

        result = TokenMetadata.read_token_metadata(sample_png_path)

        for key, value in sample_metadata.items():
            assert result[key] == value

    def test_unwritten_fields_are_none(self, sample_png_path):
        TokenMetadata.write_token_metadata(sample_png_path, {'Name': 'Only Name'})

        result = TokenMetadata.read_token_metadata(sample_png_path)

        assert result['Name'] == 'Only Name'
        assert result['Species'] is None
        assert result['Class'] is None

    def test_does_not_default_image_type(self, sample_png_path):
        TokenMetadata.write_token_metadata(sample_png_path, {'Name': 'No Type'})

        result = TokenMetadata.read_token_metadata(sample_png_path)

        assert result['ImageType'] is None

    def test_old_prefix_backwards_compatibility(self, sample_png_path):
        img = Image.open(sample_png_path)
        pnginfo = PngInfo()
        pnginfo.add_text('TokenVault:Name', 'Legacy Token')
        pnginfo.add_text('TokenVault:Species', 'Goblin')
        img.save(sample_png_path, pnginfo=pnginfo)

        result = TokenMetadata.read_token_metadata(sample_png_path)

        assert result['Name'] == 'Legacy Token'
        assert result['Species'] == 'Goblin'

    def test_preserves_foreign_png_chunks(self, sample_png_path):
        img = Image.open(sample_png_path)
        pnginfo = PngInfo()
        pnginfo.add_text('Software', 'SomeOtherTool')
        img.save(sample_png_path, pnginfo=pnginfo)

        TokenMetadata.write_token_metadata(sample_png_path, {'Name': 'Test'})

        reopened = Image.open(sample_png_path)
        assert reopened.text.get('Software') == 'SomeOtherTool'


class TestJpegRoundTrip:
    """Tests for write_token_metadata / read_token_metadata on JPEG files."""

    def test_write_then_read(self, sample_jpeg_path, sample_metadata):
        success = TokenMetadata.write_token_metadata(sample_jpeg_path, sample_metadata)
        assert success is True

        result = TokenMetadata.read_token_metadata(sample_jpeg_path)

        for key, value in sample_metadata.items():
            assert result[key] == value

    def test_unwritten_fields_are_none(self, sample_jpeg_path):
        TokenMetadata.write_token_metadata(sample_jpeg_path, {'Name': 'JPEG Token'})

        result = TokenMetadata.read_token_metadata(sample_jpeg_path)

        assert result['Name'] == 'JPEG Token'
        assert result['Source'] is None


class TestUpdateMetadata:
    """Tests for update_metadata static method."""

    def test_updates_only_given_fields(self, sample_png_path, sample_metadata):
        TokenMetadata.write_token_metadata(sample_png_path, sample_metadata)

        success = TokenMetadata.update_metadata(sample_png_path, {'Species': 'Updated Species'})
        assert success is True

        result = TokenMetadata.read_token_metadata(sample_png_path)
        assert result['Species'] == 'Updated Species'
        assert result['Name'] == sample_metadata['Name']
        assert result['Class'] == sample_metadata['Class']

    def test_ignores_unknown_fields(self, sample_png_path, sample_metadata):
        TokenMetadata.write_token_metadata(sample_png_path, sample_metadata)

        TokenMetadata.update_metadata(sample_png_path, {'NotARealField': 'ignored'})

        result = TokenMetadata.read_token_metadata(sample_png_path)
        assert 'NotARealField' not in result


class TestAddDateIfMissing:
    """Tests for add_date_if_missing static method."""

    def test_adds_date_when_missing(self, sample_png_path):
        TokenMetadata.write_token_metadata(sample_png_path, {'Name': 'No Date'})

        TokenMetadata.add_date_if_missing(sample_png_path)

        result = TokenMetadata.read_token_metadata(sample_png_path)
        assert result['DateAdded'] is not None

    def test_does_not_overwrite_existing_date(self, sample_png_path):
        original_date = '2020-01-01T00:00:00'
        TokenMetadata.write_token_metadata(sample_png_path, {'DateAdded': original_date})

        TokenMetadata.add_date_if_missing(sample_png_path)

        result = TokenMetadata.read_token_metadata(sample_png_path)
        assert result['DateAdded'] == original_date


class TestGetFileInfo:
    """Tests for get_file_info static method."""

    def test_valid_file(self, sample_png_path, sample_metadata):
        TokenMetadata.write_token_metadata(sample_png_path, sample_metadata)

        info = TokenMetadata.get_file_info(sample_png_path)

        assert info['filepath'] == sample_png_path
        assert info['filename'] == os.path.basename(sample_png_path)
        assert info['file_size'] > 0
        assert 'file_modified' in info
        assert info['Name'] == sample_metadata['Name']

    def test_nonexistent_file_returns_none(self):
        info = TokenMetadata.get_file_info('/nonexistent/file.png')

        assert info is None


class TestErrorHandling:
    """Tests for error paths that should fail gracefully rather than raise."""

    def test_read_nonexistent_file_returns_all_none(self):
        result = TokenMetadata.read_token_metadata('/nonexistent/file.png')

        assert all(value is None for value in result.values())
        assert set(result.keys()) == set(TokenMetadata.FIELDS)

    def test_read_corrupt_file_returns_all_none(self, temp_dir):
        filepath = os.path.join(temp_dir, 'corrupt.png')
        with open(filepath, 'wb') as f:
            f.write(b'not a real png')

        result = TokenMetadata.read_token_metadata(filepath)

        assert all(value is None for value in result.values())

    def test_write_to_nonexistent_directory_returns_false(self, temp_dir, sample_metadata):
        filepath = os.path.join(temp_dir, 'missing_dir', 'sample.png')

        success = TokenMetadata.write_token_metadata(filepath, sample_metadata)

        assert success is False
