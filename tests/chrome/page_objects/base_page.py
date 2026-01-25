"""
Base Page Object class with common utilities for all page objects.
"""
import os
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException


class BasePage:
    """Base class for all page objects with common utilities."""

    def __init__(self, driver, base_url):
        """
        Initialize the page object.

        Args:
            driver: Selenium WebDriver instance
            base_url: Base URL for the application
        """
        self.driver = driver
        self.base_url = base_url
        self.wait = WebDriverWait(driver, 10)

    def navigate(self, path="/"):
        """Navigate to a specific path."""
        url = f"{self.base_url}{path}"
        self.driver.get(url)

    def wait_for_element(self, locator, timeout=10):
        """
        Wait for an element to be present and visible.

        Args:
            locator: Tuple of (By.*, "selector")
            timeout: Maximum wait time in seconds

        Returns:
            WebElement when found

        Raises:
            TimeoutException if element not found
        """
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.visibility_of_element_located(locator))

    def wait_for_element_clickable(self, locator, timeout=10):
        """
        Wait for an element to be clickable.

        Args:
            locator: Tuple of (By.*, "selector")
            timeout: Maximum wait time in seconds

        Returns:
            WebElement when clickable
        """
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.element_to_be_clickable(locator))

    def wait_for_element_hidden(self, locator, timeout=10):
        """
        Wait for an element to be hidden/invisible.

        Args:
            locator: Tuple of (By.*, "selector")
            timeout: Maximum wait time in seconds

        Returns:
            True when element is hidden
        """
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.invisibility_of_element_located(locator))

    def click(self, locator):
        """
        Click an element after waiting for it to be clickable.

        Args:
            locator: Tuple of (By.*, "selector")
        """
        element = self.wait_for_element_clickable(locator)
        element.click()

    def type_text(self, locator, text, clear_first=True):
        """
        Type text into an input field.

        Args:
            locator: Tuple of (By.*, "selector")
            text: Text to type
            clear_first: Whether to clear the field first (default: True)
        """
        element = self.wait_for_element(locator)
        if clear_first:
            element.clear()
        element.send_keys(text)

    def get_text(self, locator):
        """
        Get text content of an element.

        Args:
            locator: Tuple of (By.*, "selector")

        Returns:
            Text content of the element
        """
        element = self.wait_for_element(locator)
        return element.text

    def select_dropdown(self, locator, visible_text):
        """
        Select an option from a dropdown by visible text.

        Args:
            locator: Tuple of (By.*, "selector")
            visible_text: The visible text of the option to select
        """
        element = self.wait_for_element(locator)
        select = Select(element)
        select.select_by_visible_text(visible_text)

    def select_dropdown_by_value(self, locator, value):
        """
        Select an option from a dropdown by value attribute.

        Args:
            locator: Tuple of (By.*, "selector")
            value: The value attribute of the option to select
        """
        element = self.wait_for_element(locator)
        select = Select(element)
        select.select_by_value(value)

    def is_element_visible(self, locator, timeout=2):
        """
        Check if an element is visible.

        Args:
            locator: Tuple of (By.*, "selector")
            timeout: Maximum wait time in seconds

        Returns:
            True if element is visible, False otherwise
        """
        try:
            wait = WebDriverWait(self.driver, timeout)
            wait.until(EC.visibility_of_element_located(locator))
            return True
        except TimeoutException:
            return False

    def is_element_present(self, locator, timeout=2):
        """
        Check if an element is present in the DOM (may not be visible).

        Args:
            locator: Tuple of (By.*, "selector")
            timeout: Maximum wait time in seconds

        Returns:
            True if element is present, False otherwise
        """
        try:
            wait = WebDriverWait(self.driver, timeout)
            wait.until(EC.presence_of_element_located(locator))
            return True
        except TimeoutException:
            return False

    def find_elements(self, locator):
        """
        Find multiple elements matching the locator.

        Args:
            locator: Tuple of (By.*, "selector")

        Returns:
            List of WebElements
        """
        return self.driver.find_elements(*locator)

    def wait_for_text_in_element(self, locator, text, timeout=10):
        """
        Wait for specific text to appear in an element.

        Args:
            locator: Tuple of (By.*, "selector")
            text: Text to wait for
            timeout: Maximum wait time in seconds

        Returns:
            True when text appears
        """
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.text_to_be_present_in_element(locator, text))

    def take_screenshot(self, name="screenshot"):
        """
        Take a screenshot and save it to the screenshots directory.

        Args:
            name: Name for the screenshot file (without extension)

        Returns:
            Path to the saved screenshot
        """
        screenshots_dir = os.path.join(os.path.dirname(__file__), '..', 'screenshots')
        os.makedirs(screenshots_dir, exist_ok=True)

        filepath = os.path.join(screenshots_dir, f"{name}.png")
        self.driver.save_screenshot(filepath)
        return filepath

    def scroll_to_element(self, locator):
        """
        Scroll to make an element visible in the viewport.

        Args:
            locator: Tuple of (By.*, "selector")
        """
        element = self.wait_for_element(locator)
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)

    def get_attribute(self, locator, attribute):
        """
        Get an attribute value from an element.

        Args:
            locator: Tuple of (By.*, "selector")
            attribute: Name of the attribute to get

        Returns:
            Attribute value
        """
        element = self.wait_for_element(locator)
        return element.get_attribute(attribute)

    def wait_for_page_load(self, timeout=10):
        """
        Wait for the page to finish loading.

        Args:
            timeout: Maximum wait time in seconds
        """
        wait = WebDriverWait(self.driver, timeout)
        wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
