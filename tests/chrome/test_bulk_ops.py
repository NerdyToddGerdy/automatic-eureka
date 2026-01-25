"""
Chrome E2E tests for bulk operations (multi-select, bulk edit, bulk delete).
"""
import pytest
from .page_objects.main_page import MainPage
from .page_objects.token_modal import BulkEditModal


class TestBulkOperations:
    """Tests for bulk operations functionality."""

    def test_select_multiple_tokens(self, chrome_driver, base_url, populated_test_db):
        """Should allow selecting multiple tokens via checkboxes."""
        main_page = MainPage(chrome_driver, base_url)

        # Navigate to app
        main_page.open()

        # Initially, bulk actions bar should not be visible
        assert not main_page.is_bulk_actions_visible()

        # Select first token
        main_page.select_token_checkbox(0)

        # Bulk actions bar should now be visible
        assert main_page.is_bulk_actions_visible()
        assert main_page.get_selected_count() == 1

        # Select second token
        main_page.select_token_checkbox(1)
        assert main_page.get_selected_count() == 2

        # Select third token
        main_page.select_token_checkbox(2)
        assert main_page.get_selected_count() == 3

    def test_bulk_edit_tags(self, chrome_driver, base_url, populated_test_db):
        """Should apply tag changes to all selected tokens."""
        main_page = MainPage(chrome_driver, base_url)
        bulk_edit_modal = BulkEditModal(chrome_driver, base_url)

        # Navigate to app
        main_page.open()

        # Filter to show only Token type
        main_page.filter_by_image_type("Tokens")
        main_page.wait_for_loading_complete()

        # Select first 2 tokens
        main_page.select_token_checkbox(0)
        main_page.select_token_checkbox(1)

        # Get token IDs before bulk edit
        tokens_before = populated_test_db.get_all_tokens(filters={'image_type': 'Token'})
        token_ids = [t['id'] for t in tokens_before[:2]]

        # Click bulk edit
        main_page.click_bulk_edit()

        # Wait for bulk edit modal
        bulk_edit_modal.wait_for_modal_open()
        assert bulk_edit_modal.is_open()

        # Set bulk tags
        bulk_edit_modal.set_species("Halfling")
        bulk_edit_modal.set_source("Custom Campaign")

        # Apply changes
        bulk_edit_modal.apply_changes()

        # Verify modal closed
        assert not bulk_edit_modal.is_open()

        # Verify both tokens were updated in database
        for token_id in token_ids:
            token = populated_test_db.get_token(token_id)
            assert token['species'] == "Halfling"
            assert token['source'] == "Custom Campaign"

    def test_bulk_delete(self, chrome_driver, base_url, populated_test_db):
        """Should delete all selected tokens."""
        main_page = MainPage(chrome_driver, base_url)

        # Navigate to app
        main_page.open()
        initial_count = main_page.get_token_count_number()

        # Select 2 tokens
        main_page.select_token_checkbox(0)
        main_page.select_token_checkbox(1)

        # Get token IDs before deletion
        all_tokens = populated_test_db.get_all_tokens()
        token_ids_to_delete = [all_tokens[0]['id'], all_tokens[1]['id']]

        # Click bulk delete
        main_page.click_bulk_delete()

        # Note: The actual app might show a confirmation dialog
        # For now, assume it deletes directly or handle confirmation separately

        # Wait for page to update
        main_page.wait_for_loading_complete()

        # Refresh to see updated count
        main_page.open()

        # Verify count decreased
        new_count = main_page.get_token_count_number()
        assert new_count == initial_count - 2

        # Verify tokens deleted from database
        for token_id in token_ids_to_delete:
            token = populated_test_db.get_token(token_id)
            assert token is None

    def test_deselect_all(self, chrome_driver, base_url, populated_test_db):
        """Should deselect all selected tokens."""
        main_page = MainPage(chrome_driver, base_url)

        # Navigate to app
        main_page.open()

        # Select multiple tokens
        main_page.select_token_checkbox(0)
        main_page.select_token_checkbox(1)
        main_page.select_token_checkbox(2)

        # Verify selection
        assert main_page.is_bulk_actions_visible()
        assert main_page.get_selected_count() == 3

        # Click deselect all
        main_page.click_deselect_all()

        # Verify bulk actions bar is hidden
        assert not main_page.is_bulk_actions_visible()

        # Verify selection count is 0
        selected_count = main_page.get_selected_count()
        assert selected_count == 0
