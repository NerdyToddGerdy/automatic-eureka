"""
Shared pytest fixtures for ImageTagger tests.
"""
import os
import pytest
import tempfile
from io import BytesIO
from PIL import Image
from database import TokenDatabase


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def test_db(temp_dir):
    """Create a test database in a temporary file."""
    import os
    db_path = os.path.join(temp_dir, 'test.db')
    db = TokenDatabase(db_path)
    yield db
    # Database connections are closed via context managers, no explicit close needed


@pytest.fixture
def sample_png_path(temp_dir):
    """Create a sample PNG file for testing."""
    filepath = os.path.join(temp_dir, 'sample.png')

    # Create a simple 100x100 red image
    img = Image.new('RGB', (100, 100), color='red')
    img.save(filepath, 'PNG')

    return filepath


@pytest.fixture
def sample_jpeg_path(temp_dir):
    """Create a sample JPEG file for testing."""
    filepath = os.path.join(temp_dir, 'sample.jpg')

    # Create a simple 100x100 blue image
    img = Image.new('RGB', (100, 100), color='blue')
    img.save(filepath, 'JPEG')

    return filepath


@pytest.fixture
def sample_png_with_metadata(temp_dir):
    """Create a PNG file with metadata for testing."""
    from metadata import TokenMetadata

    filepath = os.path.join(temp_dir, 'sample_with_meta.png')

    # Create image
    img = Image.new('RGB', (100, 100), color='green')
    img.save(filepath, 'PNG')

    # Add metadata
    metadata = {
        'Name': 'Test Token',
        'ImageType': 'Token',
        'Species': 'Dragon',
        'Class': 'Fighter',
        'Source': 'Test',
        'Campaign': 'Test Campaign'
    }
    TokenMetadata.write_token_metadata(filepath, metadata)

    return filepath


@pytest.fixture
def sample_metadata():
    """Sample metadata dictionary for testing."""
    return {
        'Name': 'Test Token',
        'ImageType': 'Token',
        'Species': 'Goblin',
        'Class': 'Warrior',
        'Source': 'Test Source',
        'Campaign': 'Test Campaign',
        'Notes': 'Test notes'
    }


@pytest.fixture
def sample_token_data():
    """Sample token data for database testing."""
    return {
        'filepath': '/test/path/token.png',
        'filename': 'token.png',
        'Name': 'Test Token',
        'ImageType': 'Token',
        'Species': 'Orc',
        'Class': 'Barbarian',
        'Source': 'Core Rulebook',
        'Campaign': 'Test Campaign',
        'Notes': 'A fearsome warrior',
        'DateAdded': '2024-01-01T12:00:00',
        'file_modified': '2024-01-01T12:00:00'
    }


@pytest.fixture
def multiple_sample_images(temp_dir):
    """Create multiple sample images for batch testing."""
    images = []
    colors = ['red', 'green', 'blue', 'yellow', 'purple']

    for i, color in enumerate(colors):
        filepath = os.path.join(temp_dir, f'sample_{i}.png')
        img = Image.new('RGB', (100, 100), color=color)
        img.save(filepath, 'PNG')
        images.append(filepath)

    return images


@pytest.fixture
def flask_app():
    """Create Flask test application."""
    import sys
    import os

    # Add parent directory to path to import app
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from app import app as flask_app

    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False

    yield flask_app


@pytest.fixture
def client(flask_app):
    """Create Flask test client."""
    return flask_app.test_client()


# ============================================================================
# CHROME E2E TEST FIXTURES
# ============================================================================

@pytest.fixture(scope="function")
def chrome_driver():
    """Create Chrome WebDriver instance for E2E testing."""
    from selenium import webdriver
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service

    options = webdriver.ChromeOptions()
    # Check environment variable for headless mode (default: headless)
    if os.getenv('HEADLESS', '1') == '1':
        options.add_argument('--headless')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')  # Required for some CI environments

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(10)  # Wait up to 10 seconds for elements

    yield driver

    # Cleanup
    driver.quit()


@pytest.fixture(scope="function")
def test_server(test_db, temp_dir):
    """Start Flask test server on port 5001 for E2E testing."""
    import subprocess
    import time
    import signal
    import sys

    # Get path to app.py
    app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.py')

    # Set environment variables for test mode
    env = os.environ.copy()
    env['FLASK_ENV'] = 'testing'
    env['DB_PATH'] = test_db.db_path
    env['TOKENS_FOLDER'] = temp_dir

    # Start Flask in background
    proc = subprocess.Popen(
        [sys.executable, app_path, '--port', '5001'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start (check if port is available)
    time.sleep(3)

    yield "http://127.0.0.1:5001"

    # Cleanup: terminate Flask process
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=5)


@pytest.fixture
def base_url(test_server):
    """Provide base URL for tests."""
    return test_server


@pytest.fixture
def populated_test_db(test_db, temp_dir):
    """Create a test database with pre-loaded tokens for filtering tests."""
    from metadata import TokenMetadata

    # Create sample images with different metadata
    test_data = [
        {'filename': 'goblin_warrior.png', 'ImageType': 'Token', 'Species': 'Goblin', 'Class': 'Warrior', 'Source': 'Core'},
        {'filename': 'elf_ranger.png', 'ImageType': 'Token', 'Species': 'Elf', 'Class': 'Ranger', 'Source': 'Core'},
        {'filename': 'dragon_red.png', 'ImageType': 'Token', 'Species': 'Dragon', 'Class': 'Sorcerer', 'Source': 'Monster Manual'},
        {'filename': 'dungeon_map.png', 'ImageType': 'Map', 'Scale': 'Large', 'Theme': 'Dungeon', 'Source': 'Custom'},
        {'filename': 'tavern_scene.png', 'ImageType': 'Scene', 'Location': 'Tavern', 'Mood': 'Cozy', 'Source': 'Core'},
    ]

    for i, data in enumerate(test_data):
        # Create image file
        filepath = os.path.join(temp_dir, data['filename'])
        colors = ['red', 'green', 'blue', 'yellow', 'purple']
        img = Image.new('RGB', (100, 100), color=colors[i])
        img.save(filepath, 'PNG')

        # Write metadata to PNG
        TokenMetadata.write_token_metadata(filepath, data)

        # Add to database
        token_data = {
            'filepath': filepath,
            'filename': data['filename'],
            **{k: v for k, v in data.items() if k != 'filename'}
        }
        test_db.add_token(token_data)

    return test_db
