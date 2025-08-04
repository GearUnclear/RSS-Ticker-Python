#!/usr/bin/env python3
"""
Test script for multiple RSS feed functionality.
"""
import sys
import queue
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from feed_fetcher import FeedFetcher
from logger import logger

def main():
    """Test the multiple feed functionality."""
    print("Testing multiple RSS feed functionality...")
    print("=" * 50)
    
    # Create a test queue
    test_queue = queue.Queue()
    
    # Create feed fetcher
    fetcher = FeedFetcher(test_queue)
    
    try:
        # Test fetching all feeds
        print("Fetching from all configured feeds...")
        items = fetcher._fetch_all_feeds()
        
        if items:
            print(f"\nSuccessfully fetched {len(items)} unique items after deduplication:")
            print("-" * 50)
            for i, (text, url) in enumerate(items[:10], 1):  # Show first 10
                print(f"{i:2d}. {text[:80]}{'...' if len(text) > 80 else ''}")
                if url:
                    print(f"    URL: {url}")
                print()
            
            if len(items) > 10:
                print(f"... and {len(items) - 10} more items")
        else:
            print("No items fetched.")
            
    except Exception as e:
        print(f"Error during test: {e}")
        logger.exception("Test failed")
        return 1
        
    print("\nTest completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 