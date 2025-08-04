"""
NYT RSS Ticker - A news ticker for NYT Politics RSS feed.
"""

__version__ = "1.0.0"
__author__ = "NYT RSS Ticker Team"

# Only import when used as a package
__all__ = ['TickerGUI', 'FeedFetcher', 'logger', 'setup_logger']

def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name == 'TickerGUI':
        from .gui import TickerGUI
        return TickerGUI
    elif name == 'FeedFetcher':
        from .feed_fetcher import FeedFetcher
        return FeedFetcher
    elif name == 'logger':
        from .logger import logger
        return logger
    elif name == 'setup_logger':
        from .logger import setup_logger
        return setup_logger
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}") 