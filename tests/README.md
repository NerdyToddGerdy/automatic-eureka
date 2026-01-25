# ImageTagger Test Suite

Comprehensive unit tests for the ImageTagger application.

## Setup

Install test dependencies:

```bash
pip install -r requirements-dev.txt
```

## Running Tests

Run all tests:
```bash
pytest
```

Run with coverage report:
```bash
pytest --cov --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_file_utils.py
pytest tests/test_database.py
```

Run specific test class:
```bash
pytest tests/test_file_utils.py::TestCalculateFileHash
```

Run specific test:
```bash
pytest tests/test_file_utils.py::TestCalculateFileHash::test_hash_consistency
```

Verbose output:
```bash
pytest -v
```

## Test Organization

- `conftest.py` - Shared pytest fixtures
- `test_file_utils.py` - Tests for file hashing, duplicate detection, file operations
- `test_database.py` - Tests for database CRUD operations, filtering, statistics
- `fixtures/` - Test fixture data (images, sample data)
- `integration/` - End-to-end integration tests (future)

## Coverage Goals

- Overall: 60%+ (initial), 80%+ (goal)
- File utils: 90%+
- Database: 90%+
- Metadata: 85%+

## Test Fixtures

### Shared Fixtures (conftest.py)
- `temp_dir` - Temporary directory for test files
- `test_db` - In-memory SQLite database
- `sample_png_path` - Test PNG file
- `sample_jpeg_path` - Test JPEG file
- `sample_metadata` - Sample metadata dictionary
- `sample_token_data` - Sample token data
- `multiple_sample_images` - Multiple test images

### Static Fixtures
- `fixtures/images/sample.png` - Static test PNG
- `fixtures/images/sample.jpg` - Static test JPEG
- `fixtures/images/sample_different.png` - Different PNG for hash testing

## Writing New Tests

Follow these patterns:

```python
class TestFeatureName:
    """Tests for feature_name."""

    def test_normal_case(self, fixture_name):
        """Should handle normal case correctly."""
        result = function_under_test(input)
        assert result == expected

    def test_edge_case(self):
        """Should handle edge case."""
        # Test edge case

    def test_error_case(self):
        """Should raise exception for invalid input."""
        with pytest.raises(ExceptionType):
            function_under_test(invalid_input)
```

## CI/CD Integration

Tests can be run in GitHub Actions or other CI/CD platforms. See `.github/workflows/test.yml` for example configuration (if available).
