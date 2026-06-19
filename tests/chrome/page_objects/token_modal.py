"""
Page Object for the Token Detail Modal.
"""
from .base_page import BasePage, By


class TokenModal(BasePage):
    """Page object for the token detail editing modal."""

    # Modal container
    TOKEN_MODAL = (By.ID, "tokenModal")
    MODAL_CLOSE_BTN = (By.CSS_SELECTOR, "#tokenModal .modal-close")
    MODAL_CANCEL_BTN = (By.CSS_SELECTOR, "#tokenModal .modal-close-btn")

    # Image and metadata
    MODAL_IMAGE = (By.ID, "modalImage")
    MODAL_FILENAME = (By.ID, "modalFilename")
    MODAL_DATE_ADDED = (By.ID, "modalDateAdded")
    MODAL_FILE_PATH = (By.ID, "modalFilePathText")

    # Form fields
    EDIT_TOKEN_ID = (By.ID, "editTokenId")
    EDIT_NAME = (By.ID, "editName")
    EDIT_IMAGE_TYPE = (By.ID, "editImageType")
    DYNAMIC_TAG_FIELDS = (By.ID, "dynamicTagFields")
    EDIT_NOTES = (By.ID, "editNotes")

    # Form actions
    SAVE_BTN = (By.CSS_SELECTOR, "#tokenEditForm button[type='submit']")
    DELETE_BTN = (By.ID, "deleteTokenBtn")

    def __init__(self, driver, base_url):
        """Initialize the token modal page object."""
        super().__init__(driver, base_url)

    def wait_for_modal_open(self, timeout=10):
        """
        Wait for the modal to be visible.

        Args:
            timeout: Maximum wait time in seconds
        """
        self.wait_for_element(self.TOKEN_MODAL, timeout)

    def wait_for_modal_close(self, timeout=10):
        """
        Wait for the modal to be hidden.

        Args:
            timeout: Maximum wait time in seconds
        """
        self.wait_for_element_hidden(self.TOKEN_MODAL, timeout)

    def is_open(self):
        """
        Check if the modal is currently open.

        Returns:
            True if modal is visible, False otherwise
        """
        return self.is_element_visible(self.TOKEN_MODAL)

    def close(self):
        """Close the modal using the X button."""
        self.click(self.MODAL_CLOSE_BTN)
        self.wait_for_modal_close()

    def cancel(self):
        """Close the modal using the Cancel button."""
        self.click(self.MODAL_CANCEL_BTN)
        self.wait_for_modal_close()

    def get_token_name(self):
        """
        Get the current value of the display name field.

        Returns:
            Display name text
        """
        return self.get_attribute(self.EDIT_NAME, "value")

    def set_token_name(self, name):
        """
        Set the display name field.

        Args:
            name: New display name
        """
        self.type_text(self.EDIT_NAME, name)

    def get_image_type(self):
        """
        Get the currently selected image type.

        Returns:
            Selected image type value
        """
        return self.get_attribute(self.EDIT_IMAGE_TYPE, "value")

    def set_image_type(self, image_type):
        """
        Change the image type.

        Args:
            image_type: Image type to select (Token, Map, Handout, Portrait, Scene, Item)
        """
        self.select_dropdown(self.EDIT_IMAGE_TYPE, image_type)

    def get_notes(self):
        """
        Get the current notes value.

        Returns:
            Notes text
        """
        return self.get_attribute(self.EDIT_NOTES, "value")

    def set_notes(self, notes):
        """
        Set the notes field.

        Args:
            notes: Notes text
        """
        self.type_text(self.EDIT_NOTES, notes)

    def get_filename(self):
        """
        Get the displayed filename.

        Returns:
            Filename text
        """
        return self.get_text(self.MODAL_FILENAME)

    def get_file_path(self):
        """
        Get the displayed file path.

        Returns:
            File path text
        """
        return self.get_text(self.MODAL_FILE_PATH)

    def get_dynamic_field_value(self, field_name):
        """
        Get the value of a dynamic tag field (Species, Class, etc.).

        Dynamic fields use a TagDropdown widget; the value is displayed in
        .tag-dropdown-value inside the field's container.

        Args:
            field_name: Name of the field (e.g., "Species", "Class", "Scale")

        Returns:
            Field value text or None if not found
        """
        try:
            field_id = f"edit{field_name}"
            sel = f"#{field_id}Container .tag-dropdown-value"
            loc = self.page.locator(sel)
            text = loc.inner_text()
            return text if text and text != "Select or type..." else None
        except Exception:
            return None

    def set_dynamic_field_value(self, field_name, value):
        """
        Set a dynamic tag field value via the TagDropdown widget.

        Opens the dropdown, types the value in the search input, then presses
        Enter to confirm.

        Args:
            field_name: Name of the field (e.g., "Species", "Class", "Scale")
            value: Value to set
        """
        field_id = f"edit{field_name}"
        # Click the dropdown selected area to open it
        self.page.locator(f"#{field_id}Container .tag-dropdown-selected").click()
        # Type value into the search input
        search = self.page.locator(f"#{field_id}Container .tag-dropdown-search")
        search.fill(value)
        # Press Enter to confirm
        search.press("Enter")

    def save(self):
        """Save changes and close the modal."""
        self.click(self.SAVE_BTN)
        # Wait for modal to close after save
        self.wait_for_modal_close()

    def delete(self):
        """Delete the token."""
        self.click(self.DELETE_BTN)
        # Note: This may trigger a confirmation dialog in the actual app
        # Tests should handle that separately if needed

    def get_all_form_data(self):
        """
        Get all form field values.

        Returns:
            Dictionary with all field values
        """
        data = {
            'name': self.get_token_name(),
            'image_type': self.get_image_type(),
            'notes': self.get_notes(),
            'filename': self.get_filename(),
        }

        # Try to get common dynamic fields
        for field in ['Species', 'Class', 'Source', 'Campaign', 'Scale', 'Theme',
                      'Type', 'Subject', 'Style', 'Location', 'Mood', 'Rarity', 'Category']:
            value = self.get_dynamic_field_value(field)
            if value is not None:
                data[field.lower()] = value

        return data


class BulkEditModal(BasePage):
    """Page object for the bulk edit modal."""

    # Modal container
    BULK_EDIT_MODAL = (By.ID, "bulkEditModal")
    MODAL_CLOSE_BTN = (By.CSS_SELECTOR, "#bulkEditModal .modal-close")
    MODAL_CANCEL_BTN = (By.CSS_SELECTOR, "#bulkEditModal .modal-close-btn")

    # Form fields
    BULK_SPECIES = (By.ID, "bulkSpecies")
    BULK_CLASS = (By.ID, "bulkClass")
    BULK_SOURCE = (By.ID, "bulkSource")
    BULK_CAMPAIGN = (By.ID, "bulkCampaign")

    # Actions
    APPLY_BTN = (By.CSS_SELECTOR, "#bulkEditForm button[type='submit']")

    def __init__(self, driver, base_url):
        """Initialize the bulk edit modal page object."""
        super().__init__(driver, base_url)

    def wait_for_modal_open(self, timeout=10):
        """Wait for the modal to be visible."""
        self.wait_for_element(self.BULK_EDIT_MODAL, timeout)

    def wait_for_modal_close(self, timeout=10):
        """Wait for the modal to be hidden."""
        self.wait_for_element_hidden(self.BULK_EDIT_MODAL, timeout)

    def is_open(self):
        """Check if the modal is currently open."""
        return self.is_element_visible(self.BULK_EDIT_MODAL)

    def close(self):
        """Close the modal using the X button."""
        self.click(self.MODAL_CLOSE_BTN)
        self.wait_for_modal_close()

    def cancel(self):
        """Close the modal using the Cancel button."""
        self.click(self.MODAL_CANCEL_BTN)
        self.wait_for_modal_close()

    def set_species(self, species):
        """Set the species field."""
        self.type_text(self.BULK_SPECIES, species)

    def set_class(self, char_class):
        """Set the class field."""
        self.type_text(self.BULK_CLASS, char_class)

    def set_source(self, source):
        """Set the source field."""
        self.type_text(self.BULK_SOURCE, source)

    def set_campaign(self, campaign):
        """Set the campaign field."""
        self.type_text(self.BULK_CAMPAIGN, campaign)

    def apply_changes(self):
        """Apply changes and close the modal."""
        self.click(self.APPLY_BTN)
        self.wait_for_modal_close()
