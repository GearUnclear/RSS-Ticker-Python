"""
Custom exceptions for NYT RSS Ticker.
"""


class RSSTickerError(Exception):
    """Base exception for RSS Ticker application."""
    pass


class FeedFetchError(RSSTickerError):
    """Error fetching RSS feed."""
    pass


class FeedParseError(RSSTickerError):
    """Error parsing RSS feed."""
    pass


class InvalidURLError(RSSTickerError):
    """Invalid URL provided."""
    pass


class ShutdownError(RSSTickerError):
    """Error during application shutdown."""
    pass 