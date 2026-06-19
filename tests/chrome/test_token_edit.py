"""
Chrome E2E tests for token editing functionality (CRUD operations).
"""
import pytest
import requests
from .page_objects.main_page import MainPage
from .page_objects.token_modal import TokenModal


class TestTokenEdit:
    """Tests for token editing (CRUD) functionality."""

    def test_open_token_modal(self, page, app_url, populated_test_db):
        """Should open token detail modal when clicking a token card."""
        main_page = MainPage(page, app_url)
        token_modal = TokenModal(page, app_url)

        # Navigate to app
        main_page.open()

        # Click first token card
        main_page.click_token_by_index(0)

        # Verify modal opens
        token_modal.wait_for_modal_open()
        assert token_modal.is_open()

        # Verify modal contains data
        filename = token_modal.get_filename()
        assert filename != ""

    def test_edit_token_name(self, page, app_url, populated_test_db):
        """Should update token display name and save changes."""
        main_page = MainPage(page, app_url)
        token_modal = TokenModal(page, app_url)

        # Navigate and open token
        main_page.open()
        main_page.click_token_by_index(0)
        token_modal.wait_for_modal_open()

        # Get token ID for later verification
        token_id = int(token_modal.get_attribute(token_modal.EDIT_TOKEN_ID, "value"))

        # Change the name
        new_name = "Updated Token Name"
        token_modal.set_token_name(new_name)

        # Save changes
        token_modal.save()

        # Verify modal closed
        assert not token_modal.is_open()

        # Verify in database
        token = populated_test_db.get_token(token_id)
        assert token['name'] == new_name

        # API verification
        response = requests.get(f"{app_url}/api/tokens/{token_id}")
        assert response.status_code == 200
        assert response.json()['token']['name'] == new_name

    def test_edit_token_species(self, page, app_url, populated_test_db):
        """Should update token species field."""
        main_page = MainPage(page, app_url)
        token_modal = TokenModal(page, app_url)

        # Navigate and filter to show only tokens
        main_page.open()
        main_page.filter_by_image_type("Tokens")
        main_page.wait_for_loading_complete()

        # Open first token
        main_page.click_token_by_index(0)
        token_modal.wait_for_modal_open()

        # Get token ID
        token_id = int(token_modal.get_attribute(token_modal.EDIT_TOKEN_ID, "value"))

        # Update species
        new_species = "Orc"
        token_modal.set_dynamic_field_value("Species", new_species)

        # Save changes
        token_modal.save()

        # Verify in database
        token = populated_test_db.get_token(token_id)
        assert token['species'] == new_species

    def test_save_token_changes(self, page, app_url, populated_test_db):
        """Should save multiple field changes at once."""
        main_page = MainPage(page, app_url)
        token_modal = TokenModal(page, app_url)

        # Navigate and open token
        main_page.open()
        main_page.filter_by_image_type("Tokens")
        main_page.wait_for_loading_complete()
        main_page.click_token_by_index(0)
        token_modal.wait_for_modal_open()

        # Get token ID
        token_id = int(token_modal.get_attribute(token_modal.EDIT_TOKEN_ID, "value"))

        # Make multiple changes
        token_modal.set_token_name("Multi-field Update Test")
        token_modal.set_dynamic_field_value("Species", "Dwarf")
        token_modal.set_dynamic_field_value("Class", "Cleric")
        token_modal.set_notes("Updated notes for testing")

        # Save all changes
        token_modal.save()

        # Verify all changes in database
        token = populated_test_db.get_token(token_id)
        assert token['name'] == "Multi-field Update Test"
        assert token['species'] == "Dwarf"
        assert token['class'] == "Cleric"
        assert token['notes'] == "Updated notes for testing"

    def test_delete_token(self, page, app_url, populated_test_db):
        """Should delete token from modal."""
        main_page = MainPage(page, app_url)
        token_modal = TokenModal(page, app_url)

        # Navigate to app
        main_page.open()
        initial_count = main_page.get_token_count_number()

        # Open first token
        main_page.click_token_by_index(0)
        token_modal.wait_for_modal_open()

        # Get token ID before deletion
        token_id = int(token_modal.get_attribute(token_modal.EDIT_TOKEN_ID, "value"))

        # Delete the token
        token_modal.delete()

        # Wait for modal to close (it should close after deletion)
        # Note: Actual app might show a confirmation dialog - adjust if needed
        token_modal.wait_for_modal_close()

        # Refresh page to see updated gallery
        main_page.open()

        # Verify token count decreased
        new_count = main_page.get_token_count_number()
        assert new_count == initial_count - 1

        # Verify token is deleted from database
        token = populated_test_db.get_token(token_id)
        assert token is None

    def test_close_modal_without_saving(self, page, app_url, populated_test_db):
        """Should discard changes when closing modal without saving."""
        main_page = MainPage(page, app_url)
        token_modal = TokenModal(page, app_url)

        # Navigate and open token
        main_page.open()
        main_page.click_token_by_index(0)
        token_modal.wait_for_modal_open()

        # Get token ID and original name
        token_id = int(token_modal.get_attribute(token_modal.EDIT_TOKEN_ID, "value"))
        original_name = token_modal.get_token_name()

        # Make a change
        token_modal.set_token_name("This Should Not Be Saved")

        # Close without saving
        token_modal.close()

        # Verify modal is closed
        assert not token_modal.is_open()

        # Verify database was not updated
        token = populated_test_db.get_token(token_id)
        assert token['name'] == original_name or token['name'] is None

        # Reopen to verify no changes
        main_page.click_token_by_index(0)
        token_modal.wait_for_modal_open()
        current_name = token_modal.get_token_name()
        assert current_name != "This Should Not Be Saved"
