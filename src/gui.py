"""
GUI module for NYT RSS Ticker with improved structure and resource management.
Orchestrates ScrollEngine, CategoryIndicatorManager, and DescriptionPanel.
"""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import Menu
from collections import deque
import queue
import time
import random
import webbrowser
from datetime import date
from typing import List, Dict, Optional, Tuple

try:
    from .config import (
        TICKER_HEIGHT_PX, BG_COLOR, FG_COLOR, FONT_FAMILY, FONT_SIZE,
        SCROLL_DELAY_MS, PIXELS_PER_STEP, MIN_HEADLINE_GAP, BULLET,
        PAUSE_ICON, CLOSE_ICON, FONT_SIZE_PAUSE, FONT_SIZE_CLOSE,
        TASKBAR_HEIGHT, TOPMOST_CHECK_INTERVAL, CATEGORY_COLORS,
        INDICATOR_WIDTH, INDICATOR_HEIGHT, INDICATOR_SPACING, INDICATOR_MARGIN_X, INDICATOR_MARGIN_Y,
        INDICATOR_CORNER_RADIUS, INDICATOR_ANIMATION_MS
    )
    from .exceptions import InvalidURLError
    from .logger import logger
    from .utils import validate_url, calculate_text_width
    from .settings import UserSettings
    from .scroll_engine import ScrollEngine
    from .category_ui import CategoryIndicatorManager
    from .description_panel import DescriptionPanel
except ImportError:
    # Fallback for direct execution
    from config import (
        TICKER_HEIGHT_PX, BG_COLOR, FG_COLOR, FONT_FAMILY, FONT_SIZE,
        SCROLL_DELAY_MS, PIXELS_PER_STEP, MIN_HEADLINE_GAP, BULLET,
        PAUSE_ICON, CLOSE_ICON, FONT_SIZE_PAUSE, FONT_SIZE_CLOSE,
        TASKBAR_HEIGHT, TOPMOST_CHECK_INTERVAL, CATEGORY_COLORS,
        INDICATOR_WIDTH, INDICATOR_HEIGHT, INDICATOR_SPACING, INDICATOR_MARGIN_X, INDICATOR_MARGIN_Y,
        INDICATOR_CORNER_RADIUS, INDICATOR_ANIMATION_MS
    )
    from exceptions import InvalidURLError
    from logger import logger
    from utils import validate_url, calculate_text_width
    from settings import UserSettings
    from scroll_engine import ScrollEngine
    from category_ui import CategoryIndicatorManager
    from description_panel import DescriptionPanel


class TickerGUI:
    """Main GUI class for the RSS ticker."""

    def __init__(self, update_queue: queue.Queue, fetcher=None):
        self.update_queue = update_queue
        self.fetcher = fetcher  # Reference to FeedFetcher for bidirectional communication
        today_str = date.today().strftime("%B %d, %Y")
        self.headlines = deque([(f"Thanks for using Easy-RSS-! {BULLET} {today_str} {BULLET}", "", f"Welcome to Easy-RSS-Python! Fetching the latest news from multiple sources.", "Default")])
        self.current_index = 0
        self.paused = False
        self.text_items: List[Dict] = []
        self._running = False
        self._shutdown_callbacks = []
        self.description_text_id = None

        # Load persisted settings
        self.settings = UserSettings()
        self.show_descriptions = self.settings.show_descriptions
        self.speed_multiplier = self.settings.speed_multiplier

        # Smart article management with sliding window tracking
        self.sliding_window_shown = deque(maxlen=50)  # Track last 50 shown articles by URL
        self.last_article_time = {}  # URL -> timestamp of last display
        self.batch_request_count = 0  # Track batch requests for debugging

        # Speed control
        self.base_scroll_delay = SCROLL_DELAY_MS

        # Category filtering - Initialize with active categories only
        self.category_vars = {}  # Will hold tkinter BooleanVar instances

        # Apple-style category indicators
        self.category_indicators = {}  # Canvas items for chips
        self.indicator_tooltips = {}   # Tooltip tracking
        self.hover_states = {}          # Track hover state to prevent re-entrance
        self.last_hover_time = {}       # Track last hover time for debouncing

        # Dynamic height based on description setting - now includes indicator space
        self.base_height = TICKER_HEIGHT_PX + 12  # +12px for compact indicator strip
        self.min_description_height = 30
        self.max_description_height = 200
        self.description_height = self.min_description_height
        self.current_height = self.base_height

        # Setup window
        self.root = tk.Tk()
        self.setup_window()

        # Initialize enabled categories with active categories + Default
        active_categories = self._get_active_categories()
        saved_cats = self.settings.enabled_categories
        if saved_cats is not None:
            # Restore only categories that are still active
            self.enabled_categories = set(c for c in saved_cats if c in active_categories) | {'Default'}
        else:
            self.enabled_categories = set(active_categories + ['Default'])

        # Instantiate helper modules (composition pattern)
        self.scroll_engine = ScrollEngine(self)
        self.category_manager = CategoryIndicatorManager(self)
        self.description_panel = DescriptionPanel(self)

        # Setup UI elements
        self.setup_ui()

        # Calculate initial description height
        self.description_panel.calculate_optimal_description_height()

        # Mark as running before starting updates
        self._running = True

        # Start checking for updates
        self.check_updates()

        # Load first item after GUI is ready
        self.root.after(100, self.scroll_engine.load_next_item)

        # Start scrolling
        self.root.after(1000, self.scroll_engine.scroll_text)

    def add_shutdown_callback(self, callback):
        """Add a callback to be called on shutdown."""
        self._shutdown_callbacks.append(callback)

    def setup_window(self):
        """Configure the main window."""
        self.root.title("NYT Politics Ticker")

        # Get screen dimensions
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        # Position at bottom of screen
        self.update_window_geometry()

        # Window styling
        self.root.overrideredirect(True)  # Remove window decorations
        self.root.configure(bg=BG_COLOR)

        # Keep on top
        self.root.attributes("-topmost", True)
        self.root.lift()

        # Set up proper window close handling
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

    def update_window_geometry(self):
        """Update window geometry based on current settings."""
        y_pos = self.screen_height - self.current_height - TASKBAR_HEIGHT
        self.root.geometry(f"{self.screen_width}x{self.current_height}+0+{y_pos}")

    def setup_ui(self):
        """Create UI elements."""
        # Main canvas
        self.canvas = tk.Canvas(
            self.root,
            bg=BG_COLOR,
            height=self.current_height,
            width=self.screen_width,
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Setup font with proper error handling
        try:
            self.font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE)
        except tk.TclError:
            logger.warning(f"Font {FONT_FAMILY} not available, using default")
            self.font = tkfont.Font(family="TkDefaultFont", size=FONT_SIZE)

        self.text_y = (self.base_height + 12) // 2  # Position below indicator strip (12px buffer)

        # Pause indicator
        self.pause_id = self.canvas.create_text(
            10, 5,
            text=PAUSE_ICON,
            font=(FONT_FAMILY, FONT_SIZE_PAUSE),
            fill=FG_COLOR,
            anchor="nw",
            state="hidden"
        )

        # Bind events
        self.root.bind("<Escape>", lambda e: self.close_app())
        self.root.bind("<Button-3>", self.show_context_menu)
        self.root.bind("<space>", lambda e: self.toggle_pause())
        self.canvas.bind("<Button-1>", self.open_link)

        # Keyboard navigation (item 7)
        self.root.bind("<Right>", lambda e: self.skip_to_next_article())
        self.root.bind("<Left>", lambda e: self.peek_article_description())

        # Setup Apple-style category indicators
        self.category_manager.setup_category_indicators()

        # Create context menu with submenus
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Pause/Resume", command=self.toggle_pause)
        self.context_menu.add_separator()

        # Show descriptions checkbox
        self.show_descriptions_var = tk.BooleanVar(value=self.show_descriptions)
        self.context_menu.add_checkbutton(
            label="Show Descriptions",
            command=self.description_panel.toggle_descriptions,
            variable=self.show_descriptions_var
        )

        self.context_menu.add_separator()

        # Speed control submenu
        self.speed_menu = Menu(self.context_menu, tearoff=0)
        self.speed_var = tk.StringVar(value="double" if self.speed_multiplier == 2.0 else "normal")
        self.speed_menu.add_radiobutton(label="Normal Speed", variable=self.speed_var, value="normal", command=self.set_normal_speed)
        self.speed_menu.add_radiobutton(label="2x Speed", variable=self.speed_var, value="double", command=self.set_double_speed)
        self.context_menu.add_cascade(label="Speed", menu=self.speed_menu)

        # Categories control submenu
        self.categories_menu = Menu(self.context_menu, tearoff=0)
        self.category_manager.setup_category_menu()
        self.context_menu.add_cascade(label="Categories", menu=self.categories_menu)

        self.context_menu.add_separator()
        self.context_menu.add_command(label="Skip Article (\u2192)", command=self.skip_to_next_article)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Exit", command=self.close_app)

        # Keep window on top periodically
        self.maintain_topmost()

    def check_updates(self):
        """Check for updates from the fetch thread."""
        if not self._running:
            return

        try:
            # Process all pending updates
            updates_processed = 0
            while updates_processed < 10:  # Limit to prevent blocking
                try:
                    msg_type, data = self.update_queue.get_nowait()
                    updates_processed += 1

                    if msg_type == 'update':
                        self._handle_update(data)
                    elif msg_type == 'error':
                        self._handle_error(data)
                    elif msg_type == 'critical_error':
                        self._handle_critical_error(data)

                except queue.Empty:
                    break

        except Exception as e:
            logger.error(f"Error checking updates: {e}")

        # Schedule next check
        if self._running:
            self.root.after(500, self.check_updates)

    def _handle_update(self, items: List[Tuple[str, str, str, str]]):
        """Handle headline updates."""
        logger.info(f"Received {len(items)} headlines from fetch thread")

        # Store all headlines for filtering
        self.all_headlines = items

        # Filter by enabled categories
        filtered_items = []
        for item in items:
            if len(item) >= 4:  # Has category
                category = item[3]
                if category in self.enabled_categories:
                    filtered_items.append(item)
            else:  # Fallback for items without category
                filtered_items.append(item)

        # Shuffle for variety while maintaining some structure
        random.shuffle(filtered_items)

        self.headlines.clear()
        self.headlines.extend(filtered_items)
        self.current_index = 0

        logger.debug(f"Updated headlines, sliding window has {len(self.sliding_window_shown)} recent articles")
        logger.info(f"Filtered to {len(filtered_items)} headlines from {len(items)} total")

        # Update description height based on new content
        self.description_panel.calculate_optimal_description_height()

        # If descriptions are enabled, update the window size
        if self.show_descriptions:
            self.current_height = self.base_height + self.description_height
            self.update_window_geometry()
            self.canvas.configure(height=self.current_height)
            self.description_panel.create_description_area()

        # If we have no active items, load the first one
        if not self.text_items:
            self.scroll_engine.load_next_item()

    def _handle_error(self, error_msg: str):
        """Handle error messages."""
        logger.info(f"Displaying error: {error_msg}")
        self.headlines.clear()
        self.headlines.append((f"[Error: {error_msg}]{BULLET}", "", f"Error: {error_msg}", "Default"))
        self.description_panel.calculate_optimal_description_height()

    def _handle_critical_error(self, error_msg: str):
        """Handle critical error messages."""
        logger.critical(f"Critical error: {error_msg}")
        self.headlines.clear()
        self.headlines.append((f"[CRITICAL: {error_msg}]{BULLET}", "", f"Critical Error: {error_msg}", "Default"))
        self.description_panel.calculate_optimal_description_height()

    def toggle_pause(self):
        """Toggle pause state."""
        self.paused = not self.paused
        self.canvas.itemconfig(
            self.pause_id,
            state="normal" if self.paused else "hidden"
        )
        logger.info(f"Pause toggled: {self.paused}")

    def open_link(self, event):
        """Open the URL of the clicked headline."""
        try:
            click_x = event.x
            click_y = event.y

            # First check if click is on a category indicator
            for category, info in self.category_indicators.items():
                ind_x = info['x']
                ind_y = info['y']
                if (ind_x <= click_x <= ind_x + INDICATOR_WIDTH and
                    ind_y <= click_y <= ind_y + INDICATOR_HEIGHT):
                    return

            # Find which text item was clicked
            clicked_item = None

            for item in self.text_items:
                try:
                    bbox = self.canvas.bbox(item['id'])
                    if bbox and bbox[0] <= click_x <= bbox[2]:
                        clicked_item = item
                        break
                except tk.TclError:
                    continue

            if clicked_item and clicked_item['url']:
                url = clicked_item['url']

                try:
                    if validate_url(url):
                        logger.info(f"Opening URL: {url}")
                        webbrowser.open(url)
                    else:
                        logger.warning(f"Invalid URL: {url}")
                except InvalidURLError as e:
                    logger.error(f"URL validation failed: {e}")
            else:
                logger.debug("No clickable item found at click position")

        except Exception as e:
            logger.error(f"Error in open_link: {e}")

    def maintain_topmost(self):
        """Keep window on top periodically."""
        if not self._running:
            return

        try:
            if self.root.winfo_exists():
                self.root.lift()
                self.root.attributes("-topmost", True)
        except tk.TclError:
            pass

        if self._running:
            self.root.after(TOPMOST_CHECK_INTERVAL, self.maintain_topmost)

    def show_context_menu(self, event):
        """Show the right-click context menu."""
        try:
            self.context_menu.post(event.x_root, event.y_root)
        except tk.TclError:
            pass

    def _get_active_categories(self):
        """Get list of categories that actually have RSS feeds configured."""
        try:
            from .config import FEED_URLS
        except ImportError:
            from config import FEED_URLS

        active_categories = set()

        for feed_url in FEED_URLS:
            if 'techcrunch.com' in feed_url or 'wired.com' in feed_url:
                active_categories.add('Technology')
            elif 'politico.com' in feed_url:
                active_categories.add('Politics')
            elif '/Politics.xml' in feed_url:
                active_categories.add('Politics')
            elif '/HomePage.xml' in feed_url:
                active_categories.add('HomePage')
            elif '/Technology.xml' in feed_url or '/PersonalTech.xml' in feed_url:
                active_categories.add('Technology')
            elif '/Business.xml' in feed_url:
                active_categories.add('Business')
            elif '/World.xml' in feed_url or '/US.xml' in feed_url:
                active_categories.add('World')
            elif '/Science.xml' in feed_url:
                active_categories.add('Science')
            elif '/Sports.xml' in feed_url:
                active_categories.add('Sports')
            elif '/Arts.xml' in feed_url or '/Style.xml' in feed_url:
                active_categories.add('Arts')
            elif '/Health.xml' in feed_url:
                active_categories.add('Health')
            elif '/Opinion.xml' in feed_url:
                active_categories.add('Opinion')

        return sorted(list(active_categories))

    def set_normal_speed(self):
        """Set scrolling to normal speed."""
        self.speed_multiplier = 1.0
        self.settings.speed_multiplier = 1.0
        logger.info("Speed set to normal (1x)")

    def set_double_speed(self):
        """Set scrolling to double speed."""
        self.speed_multiplier = 2.0
        self.settings.speed_multiplier = 2.0
        logger.info("Speed set to double (2x)")

    # ------------------------------------------------------------------
    # Keyboard navigation (item 7)
    # ------------------------------------------------------------------

    def skip_to_next_article(self):
        """Skip the current (leftmost visible) article instantly."""
        if not self.text_items:
            return

        # Find leftmost visible item (smallest x where right edge > 0)
        best_item = None
        best_x = float('inf')
        for item in self.text_items:
            try:
                bbox = self.canvas.bbox(item['id'])
                if bbox and bbox[2] > 0 and item['x'] < best_x:
                    best_x = item['x']
                    best_item = item
            except tk.TclError:
                continue

        if best_item:
            try:
                bbox = self.canvas.bbox(best_item['id'])
                if bbox:
                    width = bbox[2] - bbox[0]
                    best_item['x'] = -(width + 10)
                    self.canvas.coords(best_item['id'], best_item['x'], self.text_y)
            except tk.TclError:
                pass

    def peek_article_description(self):
        """Temporarily show the current article's description for 3 seconds."""
        if self.show_descriptions:
            return  # Already showing descriptions permanently

        current_item = self.description_panel.find_current_headline()
        if not current_item:
            return

        description = current_item.get('description', '')
        if not description:
            return

        # Pause scrolling during peek
        was_paused = self.paused
        self.paused = True
        self.canvas.itemconfig(self.pause_id, state="normal")

        try:
            desc_font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE - 2)
            # Show description centered below the ticker bar
            desc_y = self.base_height + 15
            peek_id = self.canvas.create_text(
                self.screen_width / 2, desc_y,
                text=f"\u2022 {description}",
                font=desc_font,
                fill="#CCCCCC",
                anchor="n",
                width=self.screen_width - 60,
                tags="peek_description"
            )

            # Get text bbox to create background
            bbox = self.canvas.bbox(peek_id)
            if bbox:
                pad = 5
                bg_id = self.canvas.create_rectangle(
                    bbox[0] - pad, bbox[1] - pad,
                    bbox[2] + pad, bbox[3] + pad,
                    fill=BG_COLOR, outline="#333333",
                    tags="peek_description"
                )
                self.canvas.tag_lower(bg_id, peek_id)
        except tk.TclError:
            return

        def _cleanup_peek():
            try:
                self.canvas.delete("peek_description")
            except tk.TclError:
                pass
            if not was_paused:
                self.paused = False
                self.canvas.itemconfig(self.pause_id, state="hidden")

        self.root.after(3000, _cleanup_peek)

    # ------------------------------------------------------------------
    # Backward-compatible delegation methods
    # ------------------------------------------------------------------

    def scroll_text(self):
        self.scroll_engine.scroll_text()

    def should_load_next(self) -> bool:
        return self.scroll_engine.should_load_next()

    def load_next_item(self):
        self.scroll_engine.load_next_item()

    def _select_best_available_article(self):
        return self.scroll_engine._select_best_available_article()

    def _apply_smart_balancing(self, filtered_headlines, category_counts):
        return self.scroll_engine._apply_smart_balancing(filtered_headlines, category_counts)

    def _get_dynamic_sliding_window_size(self):
        return self.scroll_engine._get_dynamic_sliding_window_size()

    def _check_article_supply(self):
        self.scroll_engine._check_article_supply()

    def _evaluate_refresh_need(self, tier_counts, category_counts):
        self.scroll_engine._evaluate_refresh_need(tier_counts, category_counts)

    def _request_fresh_batch(self, reason, priority='normal'):
        self.scroll_engine._request_fresh_batch(reason, priority)

    def request_fresh_articles(self):
        self._request_fresh_batch("manual refresh request")

    def _setup_category_indicators(self):
        self.category_manager.setup_category_indicators()

    def _create_indicator_chip(self, x, y, color, enabled, category, abbrev):
        return self.category_manager._create_indicator_chip(x, y, color, enabled, category, abbrev)

    def _update_category_indicators(self):
        self.category_manager.update_category_indicators()

    def _update_indicator_visual(self, category, enabled):
        self.category_manager._update_indicator_visual(category, enabled)

    def _on_indicator_click(self, category):
        self.category_manager.on_indicator_click(category)

    def _on_indicator_hover(self, category):
        self.category_manager._on_indicator_hover(category)

    def _show_tooltip(self, category, count, status):
        self.category_manager._show_tooltip(category, count, status)

    def _cleanup_tooltip(self, category):
        self.category_manager._cleanup_tooltip(category)

    def _on_indicator_leave(self, category):
        self.category_manager._on_indicator_leave(category)

    def _get_category_article_count(self, category):
        return self.category_manager._get_category_article_count(category)

    def _setup_category_menu(self):
        self.category_manager.setup_category_menu()

    def _refresh_category_menu(self):
        self.category_manager.refresh_category_menu()

    def toggle_category(self, category):
        self.category_manager.toggle_category(category)

    def _filter_current_headlines_gracefully(self):
        self.category_manager.filter_current_headlines_gracefully()

    def _filter_current_headlines(self):
        self._filter_current_headlines_gracefully()

    def _manage_description_context(self):
        self.category_manager._manage_description_context()

    def toggle_descriptions(self):
        self.description_panel.toggle_descriptions()

    def create_description_area(self):
        self.description_panel.create_description_area()

    def calculate_optimal_description_height(self):
        self.description_panel.calculate_optimal_description_height()

    def calculate_text_lines(self, text, font, width):
        return self.description_panel.calculate_text_lines(text, font, width)

    def find_current_headline(self):
        return self.description_panel.find_current_headline()

    def update_description_display(self):
        self.description_panel.update_description_display()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close_app(self):
        """Close the application gracefully."""
        logger.info("Closing application...")
        self._running = False

        # Call shutdown callbacks
        for callback in self._shutdown_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in shutdown callback: {e}")

        # Clean up canvas items
        try:
            self.canvas.delete("all")
        except tk.TclError:
            pass

        # Quit the main loop
        self.root.quit()

    def run(self):
        """Start the GUI main loop."""
        logger.info("Starting GUI mainloop")

        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            self.close_app()
        except Exception as e:
            logger.exception("Unexpected error in GUI mainloop")
            raise
        finally:
            self._running = False
            logger.info("GUI mainloop ended")
