"""
Main entry point for NYT RSS Ticker application.
"""
import sys
import queue
import signal
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from gui import TickerGUI
from feed_fetcher import FeedFetcher
from logger import logger


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    logger.info(f"Received signal {signum}")
    sys.exit(0)


def main():
    """Main application entry point."""
    logger.info("Starting NYT Politics RSS ticker")
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create communication queue
    update_queue = queue.Queue()
    
    # Create and start feed fetcher
    fetcher = FeedFetcher(update_queue)
    fetcher.start()
    
    # Create GUI
    gui = TickerGUI(update_queue)
    
    # Register fetcher stop as shutdown callback
    gui.add_shutdown_callback(fetcher.stop)
    
    # Run GUI (blocks until window is closed)
    try:
        gui.run()
    except Exception as e:
        logger.exception("Fatal error in main")
        raise
    finally:
        # Ensure fetcher is stopped
        fetcher.stop()
        logger.info("Application ended")


if __name__ == "__main__":
    main() 