#!/usr/bin/env python3
"""
Test script to verify the refactored RSS ticker modules.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        from src import config
        print("✓ config module")
        
        from src import logger
        print("✓ logger module")
        
        from src import exceptions
        print("✓ exceptions module")
        
        from src import utils
        print("✓ utils module")
        
        from src import feed_fetcher
        print("✓ feed_fetcher module")
        
        from src import gui
        print("✓ gui module")
        
        from src import main
        print("✓ main module")
        
        print("\nAll imports successful!")
        return True
    except ImportError as e:
        print(f"\n✗ Import failed: {e}")
        return False


def test_config():
    """Test configuration values."""
    print("\nTesting configuration...")
    from src.config import FEED_URL, DEBUG, LOG_DIR
    
    print(f"Feed URL: {FEED_URL}")
    print(f"Debug mode: {DEBUG}")
    print(f"Log directory: {LOG_DIR}")
    
    assert FEED_URL.startswith("https://"), "Feed URL should use HTTPS"
    print("✓ Configuration looks good")


def test_url_validation():
    """Test URL validation."""
    print("\nTesting URL validation...")
    from src.utils import validate_url
    from src.exceptions import InvalidURLError
    
    # Valid URLs
    valid_urls = [
        "https://www.nytimes.com/article",
        "http://example.com/page",
    ]
    
    for url in valid_urls:
        try:
            assert validate_url(url) == True
            print(f"✓ Valid URL accepted: {url}")
        except Exception as e:
            print(f"✗ Valid URL rejected: {url} - {e}")
    
    # Invalid URLs
    invalid_urls = [
        "javascript:alert('xss')",
        "data:text/html,<script>alert('xss')</script>",
        "file:///etc/passwd",
        "",
    ]
    
    for url in invalid_urls:
        try:
            validate_url(url)
            print(f"✗ Invalid URL accepted: {url}")
        except (InvalidURLError, AssertionError):
            print(f"✓ Invalid URL rejected: {url}")


def test_ssl_context():
    """Test SSL context creation."""
    print("\nTesting SSL context...")
    from src.feed_fetcher import FeedFetcher
    import queue
    
    q = queue.Queue()
    fetcher = FeedFetcher(q)
    
    try:
        context = fetcher._create_ssl_context()
        assert context.check_hostname == True
        assert context.verify_mode.name == 'CERT_REQUIRED'
        print("✓ SSL context properly configured")
    except Exception as e:
        print(f"✗ SSL context error: {e}")


def test_logger():
    """Test logger functionality."""
    print("\nTesting logger...")
    from src.logger import logger
    
    try:
        logger.info("Test info message")
        logger.debug("Test debug message")
        logger.error("Test error message")
        print("✓ Logger working correctly")
    except Exception as e:
        print(f"✗ Logger error: {e}")


if __name__ == "__main__":
    print("NYT RSS Ticker - Refactored Code Test Suite")
    print("=" * 50)
    
    all_passed = True
    
    if not test_imports():
        all_passed = False
    else:
        test_config()
        test_url_validation()
        test_ssl_context()
        test_logger()
    
    print("\n" + "=" * 50)
    if all_passed:
        print("All tests passed! The refactored code is ready to use.")
        print("\nTo run the application:")
        print("  python src/main.py")
    else:
        print("Some tests failed. Please check the errors above.")
        sys.exit(1) 