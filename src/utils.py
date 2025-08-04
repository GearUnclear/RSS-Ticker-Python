"""
Utility functions for NYT RSS Ticker.
"""
import re
from urllib.parse import urlparse
from typing import Tuple, Optional
from datetime import datetime
from email.utils import parsedate_to_datetime
import zoneinfo

try:
    from .config import LOCAL_TZ, TIME_FMT, BULLET
    from .exceptions import InvalidURLError
    from .logger import logger
except ImportError:
    # Fallback for direct execution
    from config import LOCAL_TZ, TIME_FMT, BULLET
    from exceptions import InvalidURLError
    from logger import logger


def validate_url(url: str) -> bool:
    """
    Validate if a URL is safe to open.
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is valid and safe
        
    Raises:
        InvalidURLError: If URL is invalid or potentially unsafe
    """
    if not url:
        return False
        
    try:
        result = urlparse(url)
        
        # Check for valid scheme
        if result.scheme not in ('http', 'https'):
            raise InvalidURLError(f"Invalid URL scheme: {result.scheme}")
            
        # Check for valid netloc
        if not result.netloc:
            raise InvalidURLError("Invalid URL: missing domain")
            
        # Basic check for suspicious patterns
        suspicious_patterns = [
            r'javascript:',
            r'data:',
            r'file:',
            r'about:',
            r'<script',
            r'onclick',
            r'onerror'
        ]
        
        url_lower = url.lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, url_lower):
                raise InvalidURLError(f"Potentially unsafe URL pattern: {pattern}")
                
        return True
        
    except Exception as e:
        if isinstance(e, InvalidURLError):
            raise
        raise InvalidURLError(f"URL validation failed: {str(e)}")


def format_entry(entry: dict) -> Tuple[str, str]:
    """
    Format an RSS entry for display.
    
    Args:
        entry: RSS entry dict from feedparser
        
    Returns:
        Tuple of (display_text, url)
    """
    try:
        title = entry.get('title', 'No title').strip()
        author = entry.get("dc_creator") or entry.get("author") or "NYT Staff"
        
        when = ""
        if "published" in entry:
            try:
                dt_local = parsedate_to_datetime(entry.published).astimezone(
                    zoneinfo.ZoneInfo(LOCAL_TZ)
                )
                when = dt_local.strftime(TIME_FMT).strip()
            except Exception as e:
                logger.debug(f"Failed to parse date: {e}")
        
        parts = [title, f"— {author}"]
        if when:
            parts.append(f"({when})")
            
        text = " ".join(parts) + BULLET
        url = entry.get('link', '')
        
        return text, url
        
    except Exception as e:
        logger.error(f"Error formatting entry: {e}")
        return f"(Error formatting entry){BULLET}", ""


def calculate_text_width(text: str, font_size: int) -> int:
    """
    Estimate the width of text in pixels.
    
    Args:
        text: Text to measure
        font_size: Font size in points
        
    Returns:
        Estimated width in pixels
    """
    # For monospace fonts, approximate width is ~0.6 * font_size per character
    return int(len(text) * font_size * 0.6)


def format_error_message(error: Exception) -> str:
    """
    Format an exception into a user-friendly error message.
    
    Args:
        error: Exception to format
        
    Returns:
        Formatted error message
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    # Simplify common error messages
    if "certificate verify failed" in error_msg.lower():
        return "SSL Certificate Error"
    elif "connection" in error_msg.lower():
        return "Connection Error"
    elif "timeout" in error_msg.lower():
        return "Connection Timeout"
    else:
        return f"{error_type}: {error_msg}" 