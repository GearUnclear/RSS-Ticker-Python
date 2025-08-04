"""
Logging configuration for NYT RSS Ticker.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

try:
    from .config import DEBUG, LOG_DIR
except ImportError:
    # Fallback for direct execution
    from config import DEBUG, LOG_DIR


def setup_logger(name: str = "rss_ticker") -> logging.Logger:
    """Set up and return a configured logger."""
    logger = logging.getLogger(name)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Set level based on debug setting
    logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_format = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler (only in production)
    if not DEBUG:
        log_file = LOG_DIR / f"rss_ticker_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger


# Create default logger
logger = setup_logger() 