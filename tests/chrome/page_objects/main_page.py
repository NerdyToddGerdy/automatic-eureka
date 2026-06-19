"""
Page Object for the main ImageTagger gallery interface.
"""
from .base_page import BasePage, By


class MainPage(BasePage):
    """Page object for the main gallery/filter/search page."""

    # Header buttons
    UPLOAD_BTN = (By.ID, "uploadBtn")
    DRIVE_BTN = (By.ID, "driveBtn")
    SCAN_BTN = (By.ID, "scanBtn")
    STATS_BTN = (By.ID, "statsBtn")

    # Search and filters
    SEARCH_INPUT = (By.ID, "searchInput")
    IMAGE_TYPE_FILTER = (By.ID, "imageTypeFilter")
    SPECIES_FILTER_CONTAINER = (By.ID, "speciesFilterContainer")
    CLASS_FILTER_CONTAINER = (By.ID, "classFilterContainer")
    THEME_FILTER_CONTAINER = (By.ID, "themeFilterContainer")
    SOURCE_FILTER_CONTAINER = (By.ID, "sourceFilterContainer")
    CAMPAIGN_FILTER_CONTAINER = (By.ID, "campaignFilterContainer")
    SORT_BY = (By.ID, "sortBy")
    CLEAR_FILTERS_BTN = (By.ID, "clearFiltersBtn")

    # Bulk actions
    BULK_ACTIONS_BAR = (By.ID, "bulkActionsBar")
    SELECTED_COUNT = (By.ID, "selectedCount")
    BULK_EDIT_BTN = (By.ID, "bulkEditBtn")
    BULK_DELETE_BTN = (By.ID, "bulkDeleteBtn")
    DESELECT_ALL_BTN = (By.ID, "deselectAllBtn")

    # View controls
    GRID_VIEW_BTN = (By.ID, "gridViewBtn")
    LIST_VIEW_BTN = (By.ID, "listViewBtn")
    TOKEN_COUNT = (By.ID, "tokenCount")

    # Gallery
    TOKEN_GALLERY = (By.ID, "tokenGallery")
    TOKEN_CARDS = (By.CLASS_NAME, "token-card")
    LOADING_INDICATOR = (By.ID, "loadingIndicator")

    # Mode indicator
    MODE_INDICATOR = (By.ID, "modeIndicator")

    def __init__(self, driver, base_url):
        """Initialize the main page object."""
        super().__init__(driver, base_url)

    def open(self):
        """Navigate to the main page."""
        self.navigate("/")
        self.wait_for_page_load()

    def search(self, query):
        """
        Enter a search query.

        Args:
            query: Search text to type
        """
        self.type_text(self.SEARCH_INPUT, query)

    def clear_search(self):
        """Clear the search input."""
        self.type_text(self.SEARCH_INPUT, "", clear_first=True)

    def filter_by_image_type(self, image_type):
        """
        Filter by image type.

        Args:
            image_type: Image type to select (e.g., "Tokens", "Maps", "All Types")
        """
        self.select_dropdown(self.IMAGE_TYPE_FILTER, image_type)

    def sort_by(self, sort_option):
        """
        Change sort order.

        Args:
            sort_option: Sort option text (e.g., "Sort by Name", "Sort by Date Added")
        """
        self.select_dropdown(self.SORT_BY, sort_option)

    def click_clear_filters(self):
        """Click the clear filters button."""
        self.click(self.CLEAR_FILTERS_BTN)

    def get_token_count(self):
        """
        Get the displayed token count.

        Returns:
            Token count text (e.g., "5 tokens")
        """
        return self.get_text(self.TOKEN_COUNT)

    def get_token_cards(self):
        """
        Get all visible token cards.

        Returns:
            List of WebElements representing token cards
        """
        return self.find_elements(self.TOKEN_CARDS)

    def get_token_count_number(self):
        """
        Get the token count as a number.

        Returns:
            Integer count of tokens
        """
        text = self.get_token_count()
        # Extract number from "5 tokens" or "1 token"
        return int(text.split()[0])

    def click_token_by_index(self, index):
        """
        Click a token card by its index.

        Args:
            index: Zero-based index of the token to click
        """
        cards = self.get_token_cards()
        if index < len(cards):
            cards[index].click()
        else:
            raise IndexError(f"Token index {index} out of range (only {len(cards)} tokens)")

    def click_upload_button(self):
        """Click the upload button."""
        self.click(self.UPLOAD_BTN)

    def click_stats_button(self):
        """Click the stats button."""
        self.click(self.STATS_BTN)

    def click_scan_button(self):
        """Click the rescan button."""
        self.click(self.SCAN_BTN)

    def switch_to_grid_view(self):
        """Switch to grid view."""
        self.click(self.GRID_VIEW_BTN)

    def switch_to_list_view(self):
        """Switch to list view."""
        self.click(self.LIST_VIEW_BTN)

    def is_grid_view_active(self):
        """
        Check if grid view is currently active.

        Returns:
            True if grid view is active, False otherwise
        """
        btn = self.wait_for_element(self.GRID_VIEW_BTN)
        return "active" in btn.get_attribute("class")

    def is_list_view_active(self):
        """
        Check if list view is currently active.

        Returns:
            True if list view is active, False otherwise
        """
        btn = self.wait_for_element(self.LIST_VIEW_BTN)
        return "active" in btn.get_attribute("class")

    def select_token_checkbox(self, index):
        """
        Select a token's checkbox for bulk operations.

        Args:
            index: Zero-based index of the token to select
        """
        cards = self.get_token_cards()
        if index < len(cards):
            checkbox = cards[index].locator("input[type='checkbox']")
            if not checkbox.is_checked():
                checkbox.click()
        else:
            raise IndexError(f"Token index {index} out of range")

    def get_selected_count(self):
        """
        Get the number of selected tokens.

        Returns:
            Integer count of selected tokens
        """
        if self.is_element_visible(self.BULK_ACTIONS_BAR):
            text = self.get_text(self.SELECTED_COUNT)
            return int(text)
        return 0

    def click_bulk_edit(self):
        """Click the bulk edit button."""
        self.click(self.BULK_EDIT_BTN)

    def click_bulk_delete(self):
        """Click the bulk delete button."""
        self.click(self.BULK_DELETE_BTN)

    def click_deselect_all(self):
        """Click the deselect all button."""
        self.click(self.DESELECT_ALL_BTN)

    def is_bulk_actions_visible(self):
        """
        Check if bulk actions bar is visible.

        Returns:
            True if bulk actions bar is visible, False otherwise
        """
        return self.is_element_visible(self.BULK_ACTIONS_BAR)

    def wait_for_loading_complete(self, timeout=10):
        """
        Wait for the gallery to finish loading.

        Uses network idle to handle debounced API calls (e.g., search with 300ms debounce).
        """
        self.page.wait_for_load_state('networkidle', timeout=timeout * 1000)

    def is_gallery_empty(self):
        """
        Check if the gallery is empty (no tokens displayed).

        Returns:
            True if gallery has no tokens, False otherwise
        """
        cards = self.get_token_cards()
        return len(cards) == 0
