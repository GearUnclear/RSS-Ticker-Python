"""
Configuration settings for NYT RSS Ticker.
"""
import os
from pathlib import Path

# RSS Feed Settings
FEED_URLS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
]
REFRESH_MINUTES = 10
MAX_HEADLINES = 20
FETCH_TIMEOUT = 30

# Display Settings
SCROLL_DELAY_MS = 30          # Slower for Windows stability
PIXELS_PER_STEP = 2           # Slightly faster movement
TICKER_HEIGHT_PX = 36         # Slightly taller for Windows
MIN_HEADLINE_GAP = 80         # Minimum gap between headlines in pixels

# Colors
BG_COLOR = "#000000"
FG_COLOR = "#FFA500"

# Font Settings
FONT_FAMILY = "Courier New"   # More reliable on Windows
FONT_SIZE = 14
FONT_SIZE_PAUSE = 12
FONT_SIZE_CLOSE = 14

# Time Settings
LOCAL_TZ = "America/Los_Angeles"
TIME_FMT = "%I:%M%p"         # Windows compatible

# Display Elements
BULLET = " • "               # Simple bullet
PAUSE_ICON = "⏸"
CLOSE_ICON = "✕"

# Window Settings
TASKBAR_HEIGHT = 40          # Estimated taskbar height
TOPMOST_CHECK_INTERVAL = 30000  # Check window on top every 30 seconds

# Error Handling
MAX_CONSECUTIVE_ERRORS = 10
ERROR_BACKOFF_BASE = 30      # Base seconds for exponential backoff
ERROR_BACKOFF_MAX = 300      # Maximum backoff in seconds

# Debug Settings
DEBUG = os.environ.get('RSS_TICKER_DEBUG', 'True').lower() == 'true'  # Default to True for debugging

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True) 