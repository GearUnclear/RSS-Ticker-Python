#!/usr/bin/env python3
"""
Test the feed fetcher independently to diagnose issues.
"""
import sys
import queue
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from feed_fetcher import FeedFetcher
from logger import logger

def test_feed_fetcher():
    """Test the feed fetcher."""
    print("Testing feed fetcher...")
    print("-" * 50)
    
    # Create a queue to receive updates
    update_queue = queue.Queue()
    
    # Create and start fetcher
    fetcher = FeedFetcher(update_queue)
    fetcher.start()
    
    # Wait for updates
    print("Waiting for feed updates (30 seconds max)...")
    start_time = time.time()
    
    while time.time() - start_time < 30:
        try:
            msg_type, data = update_queue.get(timeout=1)
            print(f"\nReceived {msg_type}:")
            
            if msg_type == 'update':
                print(f"  Got {len(data)} headlines")
                for i, (text, url) in enumerate(data[:3]):  # Show first 3
                    print(f"  {i+1}. {text[:80]}...")
                if len(data) > 3:
                    print(f"  ... and {len(data) - 3} more")
                break
                
            elif msg_type == 'error':
                print(f"  Error: {data}")
                
            elif msg_type == 'critical_error':
                print(f"  Critical Error: {data}")
                break
                
        except queue.Empty:
            print(".", end="", flush=True)
            
    # Stop the fetcher
    print("\n\nStopping fetcher...")
    fetcher.stop()
    
    print("\nTest complete!")

if __name__ == "__main__":
    test_feed_fetcher() 