# NYT RSS Ticker

![Python](https://img.shields.io/badge/python-3.7+-blue.svg?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-windows%20%7C%20macos%20%7C%20linux-lightgrey.svg?style=flat-square)
![GUI](https://img.shields.io/badge/GUI-tkinter-orange.svg?style=flat-square&logo=python&logoColor=white)
![RSS](https://img.shields.io/badge/RSS-NYT%20Politics-red.svg?style=flat-square&logo=rss&logoColor=white)
![Dependencies](https://img.shields.io/badge/dependencies-minimal-green.svg?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)
![Status](https://img.shields.io/badge/status-active-brightgreen.svg?style=flat-square)

A clean, modular RSS ticker that displays New York Times headlines from any number of RSS feeds in a scrolling ticker at the bottom of your screen.

## Features

- 📰 **Multi-Feed Support** - Add any number of NYT RSS feeds (Politics, World, Business, Sports, Arts, etc.)
- 🔒 **Secure** - Proper SSL certificate verification with fallback for corporate environments
- 🧩 **Modular** - Clean separation of concerns across multiple modules
- 🛡️ **Safe** - URL validation prevents malicious links
- ⚡ **Responsive** - Handles network errors with exponential backoff
- 🎨 **Customizable** - Easy configuration through environment variables
- 🔄 **Smart Deduplication** - Removes duplicate articles across multiple feeds
- 🎯 **Intermixed Display** - Blends articles from different feeds seamlessly

## Quick Start

```bash
# Install dependencies (in your venv)
pip install -r requirements.txt

# Run the application
python src/main.py
```

## Configuration

### Adding More RSS Feeds

The application supports any number of NYT RSS feeds. To customize your feeds:

1. **Edit `src/config.py`** and modify the `FEED_URLS` list
2. **Uncomment feeds you want** - Over 50 NYT RSS feeds are pre-configured as comments
3. **Or add your own** - Any valid NYT RSS URL from https://www.nytimes.com/rss

**Example - Adding more feeds:**
```python
FEED_URLS = [
    # Currently active:
    "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    
    # Add more by uncommenting:
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml",
    # ... many more available
]
```

**Popular feed categories available:**
- **Main Sections**: World, U.S., Business, Technology, Sports, Science, Health, Arts, Style, Travel, Opinion
- **World**: Africa, Americas, Asia Pacific, Europe, Middle East  
- **Business**: Energy & Environment, Small Business, Economy, DealBook
- **Sports**: Baseball, Basketball, Football, Soccer, Tennis, Golf, Hockey
- **Arts**: Movies, Music, Television, Theater, Books, Art & Design
- **Special**: Most Shared, Most Viewed, Obituaries, The Upshot

### Environment Variables

Control the application with environment variables:

```bash
# Enable debug logging
RSS_TICKER_DEBUG=true python src/main.py

# Or set permanently
export RSS_TICKER_DEBUG=true
```

## Controls

- **Space** or **Right-click** - Pause/unpause scrolling
- **Click headline** - Open article in browser
- **Escape** or **X button** - Close application

## Project Structure

The application follows a clean, modular architecture with clear separation of concerns:

### Core Files

**`main.py`** - Application Entry Point
- Initializes the application and orchestrates all components
- Sets up signal handlers for graceful shutdown (SIGINT, SIGTERM)
- Creates communication queue for thread-safe data passing between feed fetcher and GUI
- Instantiates and starts the `FeedFetcher` background thread
- Creates and runs the `TickerGUI` main interface
- Handles exception logging and ensures proper cleanup on exit

**`config.py`** - Configuration Management
- Centralized configuration for all application settings
- RSS feed URLs (supports any number of NYT feeds with 50+ pre-configured options)
- Display parameters: scroll speed, ticker height, colors, fonts, timing
- Network settings: timeouts, refresh intervals, error handling limits
- Window positioning and behavior settings
- Debug mode control via environment variables
- Automatic log directory creation

**`feed_fetcher.py`** - RSS Feed Processing Engine
- Background thread implementation for non-blocking feed retrieval
- SSL certificate handling with automatic fallback for corporate environments
- HTTP request management with proper headers and user agent
- Multi-feed support with intelligent deduplication across feeds
- Error handling with exponential backoff retry logic
- Feed parsing using feedparser with robust error recovery
- Entry formatting and data validation
- Thread-safe communication with GUI via queue system

**`gui.py`** - Ticker Display Interface
- Complete tkinter-based GUI implementation
- Full-screen bottom ticker positioning with taskbar awareness
- Smooth horizontal scrolling animation system
- Multi-item display management with proper spacing
- Click-to-open functionality for article links
- Pause/unpause controls (space bar or right-click)
- Dynamic text loading based on available screen space
- Window management: always-on-top, no decorations, escape to close
- Resource cleanup and memory management

### Support Modules

**`logger.py`** - Logging Infrastructure
- Configurable logging system with console and file output
- Debug mode support with detailed logging
- Date-based log file rotation
- Formatted output for both console and file logging
- UTF-8 encoding support for international characters

**`utils.py`** - Helper Functions
- URL validation with security checks against malicious patterns
- RSS entry formatting with author, timestamp, and title processing
- Text width calculation for layout positioning
- Error message formatting for user-friendly display
- Timezone handling for publication dates

**`exceptions.py`** - Custom Exception Hierarchy
- `RSSTickerError`: Base exception class
- `FeedFetchError`: Network and retrieval errors
- `FeedParseError`: RSS parsing and data errors
- `InvalidURLError`: URL validation failures
- `ShutdownError`: Application cleanup errors

**`rss_wrapper.py`** - Backward Compatibility
- Wrapper script maintaining interface compatibility with legacy rss.py
- Allows seamless transition from old to new codebase
- Path management for proper module imports

**`__init__.py`** - Package Initialization
- Package metadata (version, author)
- Lazy import system to prevent circular dependencies
- Public API definition with `__all__` specification
- Dynamic attribute access for modular imports

## Dependencies

- **Python 3.7+** (for timezone support)
- **feedparser** - RSS feed parsing
- **tkinter** - GUI (included with Python)

## Troubleshooting

### "Loading..." stuck forever
- Check your internet connection
- Corporate firewalls may block RSS feeds
- Enable debug mode to see detailed error messages

### SSL Certificate Errors
The application automatically handles corporate SSL certificate issues by falling back to unverified connections when needed.

### Font Issues
If the default font isn't available, the application will automatically fall back to the system default font.

## Development

Run tests:
```bash
python test_feed.py
```

The codebase follows clean architecture principles with proper error handling, logging, and resource management. 