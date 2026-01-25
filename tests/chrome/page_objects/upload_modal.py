"""
Page Object for Upload functionality and Image Type Selection Modal.
"""
from selenium.webdriver.common.by import By
from .base_page import BasePage


class UploadModal(BasePage):
    """Page object for file upload and image type selection."""

    # File inputs (hidden elements)
    FILE_INPUT = (By.ID, "fileInput")
    FOLDER_INPUT = (By.ID, "folderInput")

    # Image Type Selection Modal
    IMAGE_TYPE_MODAL = (By.ID, "imageTypeModal")
    MODAL_CLOSE_BTN = (By.CSS_SELECTOR, "#imageTypeModal .modal-close")

    # Image type radio buttons
    TYPE_TOKEN = (By.CSS_SELECTOR, "input[name='imageType'][value='Token']")
    TYPE_MAP = (By.CSS_SELECTOR, "input[name='imageType'][value='Map']")
    TYPE_HANDOUT = (By.CSS_SELECTOR, "input[name='imageType'][value='Handout']")
    TYPE_PORTRAIT = (By.CSS_SELECTOR, "input[name='imageType'][value='Portrait']")
    TYPE_SCENE = (By.CSS_SELECTOR, "input[name='imageType'][value='Scene']")
    TYPE_ITEM = (By.CSS_SELECTOR, "input[name='imageType'][value='Item']")

    # Form submission
    IMAGE_TYPE_FORM = (By.ID, "imageTypeForm")
    CONTINUE_BTN = (By.CSS_SELECTOR, "#imageTypeForm button[type='submit']")

    # Success/error messages (these might be dynamically added)
    SUCCESS_MESSAGE = (By.CLASS_NAME, "success-message")
    ERROR_MESSAGE = (By.CLASS_NAME, "error-message")

    def __init__(self, driver, base_url):
        """Initialize the upload modal page object."""
        super().__init__(driver, base_url)

    def upload_file(self, file_path):
        """
        Upload a file by sending the file path to the hidden file input.

        Args:
            file_path: Absolute path to the file to upload

        Note:
            This triggers the file selection. The image type modal may appear next.
        """
        file_input = self.driver.find_element(*self.FILE_INPUT)
        file_input.send_keys(file_path)

    def upload_multiple_files(self, file_paths):
        """
        Upload multiple files at once.

        Args:
            file_paths: List of absolute paths to files to upload
        """
        file_input = self.driver.find_element(*self.FILE_INPUT)
        # Join paths with newline for multiple file upload
        file_input.send_keys('\n'.join(file_paths))

    def wait_for_image_type_modal(self, timeout=10):
        """
        Wait for the image type selection modal to appear.

        Args:
            timeout: Maximum wait time in seconds
        """
        self.wait_for_element(self.IMAGE_TYPE_MODAL, timeout)

    def is_image_type_modal_open(self):
        """
        Check if the image type selection modal is open.

        Returns:
            True if modal is visible, False otherwise
        """
        return self.is_element_visible(self.IMAGE_TYPE_MODAL)

    def select_image_type(self, image_type):
        """
        Select an image type in the modal.

        Args:
            image_type: Type to select ('Token', 'Map', 'Handout', 'Portrait', 'Scene', 'Item')
        """
        type_mapping = {
            'Token': self.TYPE_TOKEN,
            'Map': self.TYPE_MAP,
            'Handout': self.TYPE_HANDOUT,
            'Portrait': self.TYPE_PORTRAIT,
            'Scene': self.TYPE_SCENE,
            'Item': self.TYPE_ITEM
        }

        if image_type not in type_mapping:
            raise ValueError(f"Invalid image type: {image_type}")

        locator = type_mapping[image_type]
        self.click(locator)

    def submit_image_type(self):
        """Submit the image type form and proceed with upload."""
        # Find and click the submit button
        submit_btn = self.driver.find_element(*self.CONTINUE_BTN)
        submit_btn.click()
        # Wait for modal to close
        self.wait_for_element_hidden(self.IMAGE_TYPE_MODAL)

    def select_and_submit_image_type(self, image_type):
        """
        Convenience method to select image type and submit in one call.

        Args:
            image_type: Type to select ('Token', 'Map', etc.)
        """
        self.wait_for_image_type_modal()
        self.select_image_type(image_type)
        self.submit_image_type()

    def upload_with_type(self, file_path, image_type):
        """
        Complete upload workflow: upload file and select image type.

        Args:
            file_path: Absolute path to the file to upload
            image_type: Image type to select

        Note:
            This is a convenience method that combines upload_file and image type selection.
        """
        self.upload_file(file_path)
        self.select_and_submit_image_type(image_type)

    def upload_multiple_with_type(self, file_paths, image_type):
        """
        Upload multiple files and select image type.

        Args:
            file_paths: List of absolute paths to files
            image_type: Image type to apply to all files
        """
        self.upload_multiple_files(file_paths)
        self.select_and_submit_image_type(image_type)

    def close_image_type_modal(self):
        """Close the image type modal without uploading."""
        self.click(self.MODAL_CLOSE_BTN)
        self.wait_for_element_hidden(self.IMAGE_TYPE_MODAL)

    def wait_for_upload_success(self, timeout=10):
        """
        Wait for upload success indication.

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            True if success message appears
        """
        try:
            self.wait_for_element(self.SUCCESS_MESSAGE, timeout)
            return True
        except:
            return False

    def wait_for_upload_error(self, timeout=5):
        """
        Wait for upload error message.

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            True if error message appears
        """
        try:
            self.wait_for_element(self.ERROR_MESSAGE, timeout)
            return True
        except:
            return False

    def get_success_message(self):
        """
        Get the success message text.

        Returns:
            Success message text or None if not present
        """
        if self.is_element_visible(self.SUCCESS_MESSAGE):
            return self.get_text(self.SUCCESS_MESSAGE)
        return None

    def get_error_message(self):
        """
        Get the error message text.

        Returns:
            Error message text or None if not present
        """
        if self.is_element_visible(self.ERROR_MESSAGE):
            return self.get_text(self.ERROR_MESSAGE)
        return None
