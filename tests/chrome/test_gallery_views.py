"""
Chrome E2E tests for gallery view switching (grid vs list view).
"""
import pytest
from .page_objects.main_page import MainPage


class TestGalleryViews:
    """Tests for gallery view switching functionality."""

    def test_switch_to_list_view(self, chrome_driver, base_url, populated_test_db):
        """Should switch from grid view to list view."""
        main_page = MainPage(chrome_driver, base_url)

        # Navigate to app
        main_page.open()

        # Initially should be in grid view
        assert main_page.is_grid_view_active()
        assert not main_page.is_list_view_active()

        # Switch to list view
        main_page.switch_to_list_view()

        # Wait a moment for view to change
        main_page.wait_for_loading_complete()

        # Verify list view is now active
        assert main_page.is_list_view_active()
        assert not main_page.is_grid_view_active()

        # Verify tokens are still displayed
        cards = main_page.get_token_cards()
        assert len(cards) == 5

    def test_switch_to_grid_view(self, chrome_driver, base_url, populated_test_db):
        """Should switch from list view to grid view."""
        main_page = MainPage(chrome_driver, base_url)

        # Navigate to app
        main_page.open()

        # Switch to list view first
        main_page.switch_to_list_view()
        main_page.wait_for_loading_complete()
        assert main_page.is_list_view_active()

        # Switch back to grid view
        main_page.switch_to_grid_view()
        main_page.wait_for_loading_complete()

        # Verify grid view is active
        assert main_page.is_grid_view_active()
        assert not main_page.is_list_view_active()

        # Verify tokens are still displayed
        cards = main_page.get_token_cards()
        assert len(cards) == 5

    def test_token_count_updates(self, chrome_driver, base_url, populated_test_db):
        """Should maintain correct token count when switching views."""
        main_page = MainPage(chrome_driver, base_url)

        # Navigate to app
        main_page.open()

        # Check initial count in grid view
        count_grid = main_page.get_token_count()
        assert "5 tokens" in count_grid

        # Switch to list view
        main_page.switch_to_list_view()
        main_page.wait_for_loading_complete()

        # Count should remain the same
        count_list = main_page.get_token_count()
        assert count_list == count_grid

        # Apply a filter
        main_page.filter_by_image_type("Tokens")
        main_page.wait_for_loading_complete()

        # Count should update (3 tokens)
        count_filtered = main_page.get_token_count()
        assert "3 tokens" in count_filtered

        # Switch back to grid view
        main_page.switch_to_grid_view()
        main_page.wait_for_loading_complete()

        # Filter should persist and count should remain the same
        count_grid_filtered = main_page.get_token_count()
        assert count_grid_filtered == count_filtered
        assert "3 tokens" in count_grid_filtered
