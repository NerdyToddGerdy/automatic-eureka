"""
Base Page Object class with common utilities for all page objects.
"""
import os
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


class By:
    """CSS selector type constants, compatible with Selenium's By class."""
    ID = "id"
    CLASS_NAME = "class name"
    CSS_SELECTOR = "css selector"
    NAME = "name"
    TAG_NAME = "tag name"
    XPATH = "xpath"


class BasePage:
    """Base class for all page objects with common utilities."""

    def __init__(self, page, base_url):
        self.page = page
        self.base_url = base_url
        # Auto-accept browser confirm/alert dialogs (used by delete confirmations)
        page.on("dialog", lambda dialog: dialog.accept())

    @staticmethod
    def _to_css(locator):
        """Convert a (By.TYPE, selector) tuple to a CSS selector string."""
        by_type, value = locator
        if by_type == "id":
            return f"#{value}"
        elif by_type == "class name":
            return f".{value}"
        elif by_type == "css selector":
            return value
        elif by_type == "name":
            return f'[name="{value}"]'
        elif by_type == "tag name":
            return value
        elif by_type == "xpath":
            return f"xpath={value}"
        return value

    def navigate(self, path="/"):
        """Navigate to a specific path."""
        self.page.goto(f"{self.base_url}{path}")

    def wait_for_element(self, locator, timeout=10):
        """Wait for an element to be visible and return its Locator."""
        sel = self._to_css(locator)
        loc = self.page.locator(sel)
        loc.wait_for(state='visible', timeout=timeout * 1000)
        return loc

    def wait_for_element_clickable(self, locator, timeout=10):
        """Wait for an element to be visible (Playwright auto-waits for clickability)."""
        sel = self._to_css(locator)
        loc = self.page.locator(sel)
        loc.wait_for(state='visible', timeout=timeout * 1000)
        return loc

    def wait_for_element_hidden(self, locator, timeout=10):
        """Wait for an element to be hidden/invisible."""
        sel = self._to_css(locator)
        self.page.locator(sel).wait_for(state='hidden', timeout=timeout * 1000)
        return True

    def click(self, locator):
        """Click an element (auto-waits for actionability)."""
        sel = self._to_css(locator)
        self.page.locator(sel).click()

    def type_text(self, locator, text, clear_first=True):
        """Type text into an input field."""
        sel = self._to_css(locator)
        loc = self.page.locator(sel)
        if clear_first:
            loc.fill(text)
        else:
            loc.press_sequentially(text)

    def get_text(self, locator):
        """Get the inner text of an element."""
        sel = self._to_css(locator)
        return self.page.locator(sel).inner_text()

    def select_dropdown(self, locator, visible_text):
        """Select an option from a dropdown by visible text."""
        sel = self._to_css(locator)
        self.page.locator(sel).select_option(label=visible_text)

    def select_dropdown_by_value(self, locator, value):
        """Select an option from a dropdown by value attribute."""
        sel = self._to_css(locator)
        self.page.locator(sel).select_option(value=value)

    def is_element_visible(self, locator, timeout=2):
        """Check if an element is visible."""
        sel = self._to_css(locator)
        try:
            self.page.locator(sel).wait_for(state='visible', timeout=timeout * 1000)
            return True
        except PlaywrightTimeoutError:
            return False

    def is_element_present(self, locator, timeout=2):
        """Check if an element is present in the DOM (may not be visible)."""
        sel = self._to_css(locator)
        try:
            self.page.locator(sel).wait_for(state='attached', timeout=timeout * 1000)
            return True
        except PlaywrightTimeoutError:
            return False

    def find_elements(self, locator):
        """Find all elements matching the locator and return a list of Locators."""
        sel = self._to_css(locator)
        return self.page.locator(sel).all()

    def wait_for_text_in_element(self, locator, text, timeout=10):
        """Wait for specific text to appear in an element."""
        sel = self._to_css(locator)
        self.page.locator(sel).filter(has_text=text).wait_for(state='visible', timeout=timeout * 1000)
        return True

    def take_screenshot(self, name="screenshot"):
        """Take a screenshot and save it to the screenshots directory."""
        screenshots_dir = os.path.join(os.path.dirname(__file__), '..', 'screenshots')
        os.makedirs(screenshots_dir, exist_ok=True)
        filepath = os.path.join(screenshots_dir, f"{name}.png")
        self.page.screenshot(path=filepath)
        return filepath

    def scroll_to_element(self, locator):
        """Scroll to make an element visible in the viewport."""
        sel = self._to_css(locator)
        self.page.locator(sel).scroll_into_view_if_needed()

    def get_attribute(self, locator, attribute):
        """Get an attribute value from an element."""
        sel = self._to_css(locator)
        return self.page.locator(sel).get_attribute(attribute)

    def wait_for_page_load(self, timeout=10):
        """Wait for the page to finish loading."""
        self.page.wait_for_load_state('load', timeout=timeout * 1000)
