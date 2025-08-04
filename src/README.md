# NYT RSS Ticker

![Python](https://img.shields.io/badge/python-3.7+-blue.svg?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-windows%20%7C%20macos%20%7C%20linux-lightgrey.svg?style=flat-square)
![GUI](https://img.shields.io/badge/GUI-tkinter-orange.svg?style=flat-square&logo=python&logoColor=white)
![RSS](https://img.shields.io/badge/RSS-NYT%20Politics-red.svg?style=flat-square&logo=rss&logoColor=white)
![Dependencies](https://img.shields.io/badge/dependencies-minimal-green.svg?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)
![Status](https://img.shields.io/badge/status-active-brightgreen.svg?style=flat-square)

A clean, modular RSS ticker that displays New York Times Politics headlines in a scrolling ticker at the bottom of your screen.

## Features

- 🔒 **Secure** - Proper SSL certificate verification with fallback for corporate environments
- 🧩 **Modular** - Clean separation of concerns across multiple modules
- 🛡️ **Safe** - URL validation prevents malicious links
- ⚡ **Responsive** - Handles network errors with exponential backoff
- 🎨 **Customizable** - Easy configuration through environment variables

## Quick Start

```bash
# Install dependencies (in your venv)
pip install -r requirements.txt

# Run the application
python src/main.py
```

## Configuration

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

```
src/
├── main.py              # Application entry point
├── config.py            # Configuration settings
├── feed_fetcher.py      # RSS feed handling
├── gui.py               # Ticker display
├── logger.py            # Logging setup
├── utils.py             # Helper functions
└── exceptions.py        # Custom exceptions
```

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