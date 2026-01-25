# Chrome E2E Tests for ImageTagger

This directory contains end-to-end (E2E) tests for the ImageTagger web interface using Selenium WebDriver with Chrome.

## Overview

The tests use the **Page Object Model** (POM) pattern to separate test logic from UI interactions, making tests more maintainable and readable.

### Test Structure

```
tests/chrome/
├── README.md                     # This file
├── __init__.py
├── page_objects/                 # Page Object Model classes
│   ├── __init__.py
│   ├── base_page.py             # Base class with common utilities
│   ├── main_page.py             # Main gallery/filter/search page
│   ├── token_modal.py           # Token editing modals
│   └── upload_modal.py          # File upload functionality
├── test_upload.py               # File upload tests (4 tests)
├── test_search_filter.py        # Search and filtering tests (7 tests)
├── test_token_edit.py           # Token CRUD tests (6 tests)
├── test_bulk_ops.py             # Bulk operations tests (4 tests)
└── test_gallery_views.py        # View switching tests (3 tests)
```

**Total: 24 E2E tests**

## Prerequisites

### 1. Install Dependencies

Install development dependencies including Selenium:

```bash
pip install -r requirements-dev.txt
```

This will install:
- `selenium==4.15.2` - WebDriver for browser automation
- `webdriver-manager==4.0.1` - Automatic ChromeDriver management
- `pytest` and related testing tools

### 2. Chrome Browser

Chrome browser must be installed on your system. ChromeDriver will be automatically downloaded and managed by `webdriver-manager`.

## Running Tests

### Run All Chrome E2E Tests

```bash
pytest tests/chrome/ -v
```

### Run Specific Test File

```bash
pytest tests/chrome/test_upload.py -v
```

### Run Specific Test

```bash
pytest tests/chrome/test_upload.py::TestFileUpload::test_upload_single_png -v
```

### Run with HTML Report

```bash
pytest tests/chrome/ -v --html=chrome_test_report.html --self-contained-html
```

## Test Modes

### Headless Mode (Default)

Tests run in headless mode by default (no visible browser window). This is ideal for CI/CD environments.

```bash
# Headless mode (default)
pytest tests/chrome/ -v
```

### Headed Mode (Visible Browser)

To see the browser during test execution (useful for debugging):

```bash
# Set HEADLESS=0 to run with visible browser
HEADLESS=0 pytest tests/chrome/ -v
```

## Environment Variables

- `HEADLESS` - Set to `0` to run tests with visible browser, `1` for headless (default: `1`)
- `TEST_PORT` - Port for Flask test server (default: `5001`)

## Test Categories

### 1. Upload Tests (`test_upload.py`)
- Upload single PNG file
- Upload single JPEG file
- Upload with image type selection
- Upload multiple files

### 2. Search & Filter Tests (`test_search_filter.py`)
- Search by filename
- Filter by image type
- Filter by species (Token-specific)
- Combined filters (type + search)
- Clear all filters
- Sort by name
- Sort by date

### 3. Token Edit Tests (`test_token_edit.py`)
- Open token modal
- Edit token display name
- Edit token species field
- Save multiple field changes
- Delete token
- Close modal without saving (discard changes)

### 4. Bulk Operations Tests (`test_bulk_ops.py`)
- Select multiple tokens
- Bulk edit tags
- Bulk delete
- Deselect all

### 5. Gallery View Tests (`test_gallery_views.py`)
- Switch to list view
- Switch to grid view
- Token count updates correctly across views

## Debugging Failed Tests

### Screenshots

When a test fails, you can capture a screenshot for debugging:

```python
# In any test, use the page object to take a screenshot
main_page.take_screenshot("failure_screenshot")
```

Screenshots are saved to `tests/chrome/screenshots/`

### Run with Verbose Output

```bash
pytest tests/chrome/ -vv
```

### Run with Print Statements

```bash
pytest tests/chrome/ -v -s
```

### Run Specific Test with Debugging

```bash
# Run with visible browser and verbose output
HEADLESS=0 pytest tests/chrome/test_upload.py::TestFileUpload::test_upload_single_png -vv -s
```

## Page Object Model (POM)

The tests use the Page Object Model pattern for better maintainability:

### Base Page (`base_page.py`)

Provides common utilities used by all page objects:
- `wait_for_element()` - Wait for element to be visible
- `click()` - Click an element
- `type_text()` - Type into an input field
- `select_dropdown()` - Select from dropdown
- `get_text()` - Get element text
- `take_screenshot()` - Capture screenshot
- And more...

### Main Page (`main_page.py`)

Represents the main gallery interface:
- `open()` - Navigate to the app
- `search(query)` - Enter search text
- `filter_by_image_type(type)` - Filter by image type
- `get_token_count()` - Get displayed token count
- `click_token_by_index(i)` - Open a token
- `switch_to_grid_view()` - Switch to grid view
- `switch_to_list_view()` - Switch to list view
- And more...

### Token Modal (`token_modal.py`)

Represents the token editing modal:
- `wait_for_modal_open()` - Wait for modal to appear
- `set_token_name(name)` - Change display name
- `set_dynamic_field_value(field, value)` - Set tag fields
- `save()` - Save changes
- `delete()` - Delete token
- `close()` - Close modal
- And more...

### Upload Modal (`upload_modal.py`)

Handles file uploads:
- `upload_file(path)` - Upload a single file
- `upload_multiple_files(paths)` - Upload multiple files
- `select_image_type(type)` - Select image type
- `upload_with_type(path, type)` - Complete upload workflow
- And more...

## Extending Tests

To add new tests:

1. **Create a new test file** in `tests/chrome/`
   ```python
   # tests/chrome/test_new_feature.py
   from .page_objects.main_page import MainPage

   class TestNewFeature:
       def test_something(self, chrome_driver, base_url):
           main_page = MainPage(chrome_driver, base_url)
           main_page.open()
           # Your test logic here
   ```

2. **Add new page objects** in `page_objects/` if testing new UI components

3. **Use existing fixtures** from `tests/conftest.py`:
   - `chrome_driver` - Selenium WebDriver instance
   - `base_url` - Test server URL
   - `test_db` - Fresh test database
   - `populated_test_db` - Database with sample tokens
   - `sample_png_path` - Single PNG test file
   - `sample_jpeg_path` - Single JPEG test file
   - `multiple_sample_images` - List of test images

## Continuous Integration (CI/CD)

### GitHub Actions Example

```yaml
name: Chrome E2E Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run Chrome E2E tests
        run: pytest tests/chrome/ -v --html=report.html
        env:
          HEADLESS: 1

      - name: Upload test report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: chrome-test-report
          path: report.html
```

## Troubleshooting

### ChromeDriver Issues

If you encounter ChromeDriver compatibility issues:

```bash
# Clear webdriver cache
rm -rf ~/.wdm/

# Run tests again (will download fresh ChromeDriver)
pytest tests/chrome/ -v
```

### Port Already in Use

If port 5001 is already in use:

```bash
# Find and kill the process using port 5001
lsof -ti:5001 | xargs kill -9

# Or set a different port
TEST_PORT=5002 pytest tests/chrome/ -v
```

### Timeout Issues

If tests are timing out, increase wait times in `conftest.py` or individual tests.

## Best Practices

1. **Use Page Objects** - Keep test logic separate from UI interactions
2. **Wait Explicitly** - Use `wait_for_element()` instead of `time.sleep()`
3. **Multi-Level Verification** - Verify changes in UI, API, and database
4. **Clean Up** - Fixtures handle cleanup, but ensure tests are independent
5. **Descriptive Names** - Use clear test and method names
6. **Screenshots on Failure** - Capture state when tests fail

## Additional Resources

- [Selenium Documentation](https://www.selenium.dev/documentation/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Page Object Model Pattern](https://www.selenium.dev/documentation/test_practices/encouraged/page_object_models/)
