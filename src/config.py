"""
Configuration settings for NYT RSS Ticker.
"""
import os
from pathlib import Path

# ============================================================================
# RSS FEED CONFIGURATION
# ============================================================================
# The ticker supports ANY NUMBER of NYT RSS feeds. Just add or remove URLs 
# from the FEED_URLS list below. The system will:
# - Fetch all feeds concurrently 
# - Remove duplicate articles across feeds
# - Blend articles from different feeds together
# - Handle individual feed failures gracefully
#
# Popular NYT RSS Feed Options (uncomment the ones you want):
# ============================================================================

FEED_URLS = [
    # CURRENTLY ACTIVE FEEDS:
    "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    
    # MAIN SECTIONS - Uncomment any you want to add:
    # "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/NYRegion.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Style.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Travel.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml",
    
    # WORLD SUB-SECTIONS:
    # "https://rss.nytimes.com/services/xml/rss/nyt/Africa.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Americas.xml", 
    # "https://rss.nytimes.com/services/xml/rss/nyt/AsiaPacific.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Europe.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/MiddleEast.xml",
    
    # BUSINESS SUB-SECTIONS:
    # "https://rss.nytimes.com/services/xml/rss/nyt/EnergyEnvironment.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/SmallBusiness.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/DealBook.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/MediaandAdvertising.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/YourMoney.xml",
    
    # TECHNOLOGY SUB-SECTIONS:
    "https://rss.nytimes.com/services/xml/rss/nyt/PersonalTech.xml",
    
    # SPORTS SUB-SECTIONS:
    # "https://rss.nytimes.com/services/xml/rss/nyt/Baseball.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/CollegeBasketball.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/CollegeFootball.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Golf.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Hockey.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/ProBasketball.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/ProFootball.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Soccer.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Tennis.xml",
    
    # SCIENCE SUB-SECTIONS:
    # "https://rss.nytimes.com/services/xml/rss/nyt/Environment.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/SpaceandCosmos.xml",
    
    # ARTS SUB-SECTIONS:
    # "https://rss.nytimes.com/services/xml/rss/nyt/ArtandDesign.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Books.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Dance.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Movies.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Music.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Television.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Theater.xml",
    
    # STYLE SUB-SECTIONS:
    # "https://rss.nytimes.com/services/xml/rss/nyt/FashionandStyle.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/DiningandWine.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/Love.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/TMagazine.xml",
    
    # SPECIAL SECTIONS:
    # "https://rss.nytimes.com/services/xml/rss/nyt/Obituaries.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/MostShared.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/MostViewed.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/TheUpshot.xml",
    # "https://rss.nytimes.com/services/xml/rss/nyt/WellBlog.xml",
    
    # ALTERNATIVE: You can also just add any valid NYT RSS URL here
    # Visit https://www.nytimes.com/rss for the complete list
]

# Feed Processing Settings
REFRESH_MINUTES = 5        # How often to check for new articles
MAX_HEADLINES = 50          # Maximum headlines per feed (increased for better variety)
FETCH_TIMEOUT = 30          # Timeout for each feed request in seconds

# Breaking News Priority Settings
ARTICLE_POOL_SIZE = 75              # Size of article pool to maintain
DISPLAY_SUBSET_SIZE = 15            # Articles to show per display cycle
BREAKING_NEWS_BIAS = 0.8            # Fraction of slots reserved for high priority articles
NEW_ARTICLE_PRIORITY = 100          # Priority score for newly fetched articles
PRIORITY_DECAY_HOURS = 2            # Hours for priority to naturally decay
MIN_COOLDOWN_CYCLES = 3             # Minimum cycles before reshowing an article (reduced for better variety)

# ============================================================================
# DISPLAY SETTINGS  
# ============================================================================
SCROLL_DELAY_MS = 30          # Slower for Windows stability
PIXELS_PER_STEP = 2           # Slightly faster movement
TICKER_HEIGHT_PX = 36         # Slightly taller for Windows
MIN_HEADLINE_GAP = 80         # Minimum gap between headlines in pixels

# Colors
BG_COLOR = "#000000"
FG_COLOR = "#FFA500"

# Category Colors (warm orange-based palette)
CATEGORY_COLORS = {
    'Politics': '#FFA500',      # Original orange (flagship)
    'Technology': '#FFD700',    # Gold (complementary warm)
    'Business': '#FF8C00',      # Dark orange (deeper variant)
    'World': '#FFC850',         # Light amber (softer orange)
    'Science': '#FFAB3D',       # Tangerine (mid-tone)
    'Sports': '#FFB84D',        # Butterscotch (warm neutral)
    'Arts': '#FFA07A',          # Light salmon (subtle variation)
    'Health': '#FFE4B5',        # Moccasin (pale warm)
    'Opinion': '#F0E68C',       # Khaki (muted warm)
    'HomePage': '#FFA500',      # Default to original orange
    'Default': '#FFA500'        # Fallback color
}

# Font Settings
FONT_FAMILY = "Courier New"   # More reliable on Windows
FONT_SIZE = 14
FONT_SIZE_PAUSE = 12
FONT_SIZE_CLOSE = 14

# Time Settings
# Note: On Windows, if you get timezone errors, try these alternatives:
# LOCAL_TZ = "US/Pacific"           # Alternative format
# LOCAL_TZ = "PST8PDT"             # POSIX format  
# LOCAL_TZ = None                   # Use system local time
LOCAL_TZ = "America/Los_Angeles"
TIME_FMT = "%I:%M%p"         # Windows compatible

# Display Elements
BULLET = " • "               # Simple bullet
PAUSE_ICON = "⏸"
CLOSE_ICON = "✕"

# Window Settings
TASKBAR_HEIGHT = 40          # Estimated taskbar height
TOPMOST_CHECK_INTERVAL = 30000  # Check window on top every 30 seconds

# ============================================================================
# ERROR HANDLING
# ============================================================================
MAX_CONSECUTIVE_ERRORS = 10
ERROR_BACKOFF_BASE = 30      # Base seconds for exponential backoff
ERROR_BACKOFF_MAX = 300      # Maximum backoff in seconds

# ============================================================================
# DEBUG & LOGGING
# ============================================================================
DEBUG = os.environ.get('RSS_TICKER_DEBUG', 'True').lower() == 'true'  # Default to True for debugging

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True) 