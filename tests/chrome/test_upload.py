"""
Chrome E2E tests for file upload functionality.

NOTE: Browser-mode file upload (/api/tokens/upload) is disabled in the current
app version. These tests require the reference-mode upload flow (Electron only)
and are marked xfail until a browser-compatible upload path is restored.
"""
import os
import pytest
from .page_objects.main_page import MainPage
from .page_objects.upload_modal import UploadModal

_UPLOAD_REASON = (
    "Browser upload endpoint (/api/tokens/upload) is disabled; "
    "app now requires Electron reference mode for uploads."
)


class TestFileUpload:
    """Tests for file upload functionality."""

    @pytest.mark.xfail(reason=_UPLOAD_REASON, strict=False)
    def test_upload_single_png(self, page, app_url, sample_png_path, test_db):
        """Should successfully upload a single PNG file."""
        main_page = MainPage(page, app_url)
        upload_modal = UploadModal(page, app_url)

        # Navigate to the app
        main_page.open()

        # Initial state - should be empty
        assert main_page.is_gallery_empty()
        assert "0 images" in main_page.get_token_count()

        # Click upload button and upload file
        main_page.click_upload_button()
        upload_modal.upload_with_type(sample_png_path, 'Token')

        # Wait for upload to complete
        main_page.wait_for_loading_complete()

        # Verify token appears in gallery
        assert "1 image" in main_page.get_token_count()
        assert not main_page.is_gallery_empty()

        # Verify in database
        tokens = test_db.get_all_tokens()
        assert len(tokens) == 1
        assert tokens[0]['filename'] == os.path.basename(sample_png_path)
        assert tokens[0]['image_type'] == 'Token'

    @pytest.mark.xfail(reason=_UPLOAD_REASON, strict=False)
    def test_upload_single_jpeg(self, page, app_url, sample_jpeg_path, test_db):
        """Should successfully upload a single JPEG file."""
        main_page = MainPage(page, app_url)
        upload_modal = UploadModal(page, app_url)

        # Navigate to the app
        main_page.open()

        # Upload JPEG file
        main_page.click_upload_button()
        upload_modal.upload_with_type(sample_jpeg_path, 'Portrait')

        # Wait for upload to complete
        main_page.wait_for_loading_complete()

        # Verify token appears
        assert "1 image" in main_page.get_token_count()

        # Verify in database
        tokens = test_db.get_all_tokens()
        assert len(tokens) == 1
        assert tokens[0]['filename'] == os.path.basename(sample_jpeg_path)
        assert tokens[0]['image_type'] == 'Portrait'

    @pytest.mark.xfail(reason=_UPLOAD_REASON, strict=False)
    def test_upload_with_image_type_selection(self, page, app_url, sample_png_path, test_db):
        """Should allow selecting different image types during upload."""
        main_page = MainPage(page, app_url)
        upload_modal = UploadModal(page, app_url)

        # Navigate to the app
        main_page.open()

        # Upload as Map type
        main_page.click_upload_button()
        upload_modal.upload_file(sample_png_path)

        # Wait for image type modal
        upload_modal.wait_for_image_type_modal()
        assert upload_modal.is_image_type_modal_open()

        # Select Map type
        upload_modal.select_image_type('Map')
        upload_modal.submit_image_type()

        # Wait for upload to complete
        main_page.wait_for_loading_complete()

        # Verify correct image type was set
        tokens = test_db.get_all_tokens()
        assert len(tokens) == 1
        assert tokens[0]['image_type'] == 'Map'

    @pytest.mark.xfail(reason=_UPLOAD_REASON, strict=False)
    def test_upload_multiple_files(self, page, app_url, multiple_sample_images, test_db):
        """Should allow uploading multiple files at once."""
        main_page = MainPage(page, app_url)
        upload_modal = UploadModal(page, app_url)

        # Navigate to the app
        main_page.open()

        # Upload multiple files
        main_page.click_upload_button()
        upload_modal.upload_multiple_with_type(multiple_sample_images, 'Token')

        # Wait for upload to complete
        main_page.wait_for_loading_complete()

        # Verify all files uploaded
        expected_count = len(multiple_sample_images)
        assert f"{expected_count} images" in main_page.get_token_count()

        # Verify in database
        tokens = test_db.get_all_tokens()
        assert len(tokens) == expected_count

        # Verify all have correct image type
        for token in tokens:
            assert token['image_type'] == 'Token'
