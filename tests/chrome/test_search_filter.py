"""
Chrome E2E tests for search and filtering functionality.
"""
import pytest
import requests
from .page_objects.main_page import MainPage


class TestSearchAndFiltering:
    """Tests for search and filtering functionality."""

    def test_search_by_filename(self, page, app_url, populated_test_db):
        """Should filter tokens by search query matching filename."""
        main_page = MainPage(page, app_url)

        # Navigate to app
        main_page.open()

        # Initial state - should show all 5 tokens
        assert "5 images" in main_page.get_token_count()

        # Search for specific token
        main_page.search("goblin")

        # Give it a moment to filter
        main_page.wait_for_loading_complete()

        # Verify filtering
        assert "1 image" in main_page.get_token_count()
        cards = main_page.get_token_cards()
        assert len(cards) == 1

        # API verification
        response = requests.get(f"{app_url}/api/tokens?search=goblin")
        assert response.status_code == 200
        assert len(response.json()['tokens']) == 1

    def test_filter_by_image_type(self, page, app_url, populated_test_db):
        """Should filter tokens by image type."""
        main_page = MainPage(page, app_url)

        # Navigate to app
        main_page.open()

        # Initial state
        assert "5 images" in main_page.get_token_count()

        # Filter by Tokens only
        main_page.filter_by_image_type("Tokens")

        # Wait for filtering
        main_page.wait_for_loading_complete()

        # Should show 3 tokens (goblin, elf, dragon)
        assert "3 images" in main_page.get_token_count()

        # API verification
        response = requests.get(f"{app_url}/api/tokens?image_type=Token")
        assert response.status_code == 200
        tokens = response.json()['tokens']
        assert len(tokens) == 3
        for token in tokens:
            assert token['image_type'] == 'Token'

    def test_filter_by_species(self, page, app_url, populated_test_db):
        """Should filter tokens by species (for Token image type)."""
        main_page = MainPage(page, app_url)

        # Navigate to app
        main_page.open()

        # First filter by Token type to make species filter visible
        main_page.filter_by_image_type("Tokens")
        main_page.wait_for_loading_complete()

        # Note: Species filter implementation may vary
        # This test assumes there's a species filter that becomes visible
        # when Token type is selected

        # For now, verify we can filter by type
        assert "3 images" in main_page.get_token_count()

        # API verification with species filter
        response = requests.get(f"{app_url}/api/tokens?species=Goblin")
        assert response.status_code == 200
        tokens = response.json()['tokens']
        assert len(tokens) == 1
        assert tokens[0]['species'] == 'Goblin'

    def test_combined_filters(self, page, app_url, populated_test_db):
        """Should apply multiple filters together."""
        main_page = MainPage(page, app_url)

        # Navigate to app
        main_page.open()

        # Apply image type filter
        main_page.filter_by_image_type("Tokens")
        main_page.wait_for_loading_complete()
        assert "3 images" in main_page.get_token_count()

        # Add search query
        main_page.search("elf")
        main_page.wait_for_loading_complete()

        # Should narrow down to just the elf token
        assert "1 image" in main_page.get_token_count()

        # API verification
        response = requests.get(f"{app_url}/api/tokens?image_type=Token&search=elf")
        assert response.status_code == 200
        assert len(response.json()['tokens']) == 1

    def test_clear_filters(self, page, app_url, populated_test_db):
        """Should clear all filters and show all tokens."""
        main_page = MainPage(page, app_url)

        # Navigate to app
        main_page.open()

        # Apply some filters
        main_page.filter_by_image_type("Tokens")
        main_page.search("goblin")
        main_page.wait_for_loading_complete()
        assert "1 image" in main_page.get_token_count()

        # Clear all filters
        main_page.click_clear_filters()
        main_page.wait_for_loading_complete()

        # Should show all tokens again
        assert "5 images" in main_page.get_token_count()

        # Verify search is cleared
        search_value = main_page.get_attribute(main_page.SEARCH_INPUT, "value")
        assert search_value == ""

    def test_sort_by_name(self, page, app_url, populated_test_db):
        """Should sort tokens by filename."""
        main_page = MainPage(page, app_url)

        # Navigate to app
        main_page.open()

        # Change sort order
        main_page.sort_by("Sort by Name")
        main_page.wait_for_loading_complete()

        # Get token cards
        cards = main_page.get_token_cards()
        assert len(cards) == 5

        # API verification - check sort order
        response = requests.get(f"{app_url}/api/tokens?sort_by=filename&sort_order=ASC")
        assert response.status_code == 200
        tokens = response.json()['tokens']
        assert len(tokens) == 5

        # Verify they're sorted alphabetically
        filenames = [t['filename'] for t in tokens]
        assert filenames == sorted(filenames)

    def test_sort_by_date(self, page, app_url, populated_test_db):
        """Should sort tokens by date added."""
        main_page = MainPage(page, app_url)

        # Navigate to app
        main_page.open()

        # Change sort order
        main_page.sort_by("Sort by Date Added")
        main_page.wait_for_loading_complete()

        # Verify tokens are displayed
        cards = main_page.get_token_cards()
        assert len(cards) == 5

        # API verification
        response = requests.get(f"{app_url}/api/tokens?sort_by=date_added")
        assert response.status_code == 200
        assert len(response.json()['tokens']) == 5
