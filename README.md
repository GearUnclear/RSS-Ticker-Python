# Real-Time News Ticker: A Sleek Desktop RSS Feed Viewer

**Stay informed with a constant stream of news headlines right on your desktop. This highly customizable, always-on-top news ticker brings the latest articles from your favorite RSS feeds directly to your screen.**

Tired of constantly switching tabs to check the news? This Python-based desktop widget provides a seamless, uninterrupted flow of information, perfect for news junkies, professionals, and anyone who wants to stay updated without the distraction of a full browser window.

_Keywords: RSS Ticker, News Ticker, Desktop Widget, News Feed, RSS Reader, Python, Tkinter, Real-time News, NYT, GitHub Stars_

---

<!-- 
**TODO:** Add a screenshot or an animated GIF here to showcase the ticker in action! 
A great visual is key to attracting users.
-->

## ✨ Key Features

*   **Always-on-Top Display**: The ticker bar stays visible above your other windows, ensuring you never miss a breaking story.
*   **Multiple RSS Feeds**: Aggregate news from multiple sources. The application fetches articles concurrently, removes duplicates, and blends them into a single, smooth-scrolling ticker.
*   **Highly Customizable**: Tailor the experience to your liking!
    *   **Feeds**: Easily add or remove any RSS feed URL in the configuration file. Comes pre-configured with several New York Times sections.
    *   **Appearance**: Change the colors, fonts, size, and scroll speed to match your desktop theme.
*   **Interactive & User-Friendly**:
    *   **Click to Open**: Click any headline to instantly open the full article in your default web browser.
    *   **Pause/Resume**: Right-click the ticker to pause and resume the scrolling.
    *   **Show Descriptions**: Toggle on-the-fly to see a brief description of the current headline directly in the ticker.
*   **Lightweight & Cross-Platform**: Built with Python and its standard `tkinter` library, it runs on Windows, macOS, and Linux.

## 🚀 Installation

Getting started is simple. All you need is Python 3.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/your-repo-name.git
    cd your-repo-name
    ```

2.  **Install the required dependency:**
    The application uses `feedparser` to handle RSS feeds.
    ```bash
    pip install -r requirements.txt
    ```
    _(Note: `tkinter` is usually included with Python. If not, you may need to install it separately, e.g., `sudo apt-get install python3-tk` on Debian/Ubuntu)._

3.  **Run the application:**
    ```bash
    python src/main.py
    ```
    The news ticker will appear at the bottom of your screen.

## ⚙️ Configuration

You can customize the ticker by editing the `src/config.py` file. The file is well-commented and allows you to change a wide range of settings.

### Adding & Changing RSS Feeds

To change the news sources, simply edit the `FEED_URLS` list in `src/config.py`. You can add any valid RSS feed URL.

```python
# src/config.py

FEED_URLS = [
    # Add your favorite RSS feeds here
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "http://feeds.bbci.co.uk/news/rss.xml",
    # "https://feeds.arstechnica.com/arstechnica/index",
]
```

### Customizing Appearance

Modify variables like `BG_COLOR`, `FG_COLOR`, `FONT_FAMILY`, `FONT_SIZE`, `SCROLL_DELAY_MS`, and `TICKER_HEIGHT_PX` to change the look and feel.

```python
# src/config.py

# Colors
BG_COLOR = "#000000"  # Black background
FG_COLOR = "#FFA500"  # Orange text

# Font Settings
FONT_FAMILY = "Courier New"
FONT_SIZE = 14

# Behavior
SCROLL_DELAY_MS = 30  # Lower is faster
```

## 🖱️ How to Use

*   **Left-Click a headline**: Opens the full article in your browser.
*   **Right-Click the ticker**: Opens a context menu with options to:
    *   `Pause/Resume` the scrolling.
    *   `Show/Hide Descriptions` for the headlines.
*   **Press `Esc`**: Closes the application.

## 🤝 Contributing

Contributions are welcome! Whether it's adding new features, improving performance, or fixing bugs, please feel free to open an issue or submit a pull request.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

<p align="center">
  Made with ❤️ for the love of news.
  <br>
  If you find this project useful, please consider giving it a ⭐️ on GitHub!
</p>
