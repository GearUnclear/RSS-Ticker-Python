"""
GUI module for NYT RSS Ticker with improved structure and resource management.
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


class TickerGUI:
    """Main GUI class for the RSS ticker."""
    
    def __init__(self, update_queue: queue.Queue):
        self.update_queue = update_queue
        today_str = date.today().strftime("%B %d, %Y")
        self.headlines = deque([(f"Thanks for using Easy-RSS-🐍! • {today_str} {BULLET}", "", f"Welcome to Easy-RSS-Python! Fetching the latest news from multiple sources.", "Default")])
        self.current_index = 0
        self.paused = False
        self.show_descriptions = False  
        self.text_items: List[Dict] = []
        self._running = False
        self._shutdown_callbacks = []
        self.description_text_id = None
        
        # Smart article management with sliding window tracking
        self.sliding_window_shown = deque(maxlen=50)  # Track last 50 shown articles by URL
        self.last_article_time = {}  # URL -> timestamp of last display
        self.batch_request_count = 0  # Track batch requests for debugging
        
        # Speed control
        self.speed_multiplier = 1.0  # 1.0 = normal, 2.0 = 2x speed
        self.base_scroll_delay = SCROLL_DELAY_MS
        
        # Category filtering - Initialize with active categories only
        self.category_vars = {}  # Will hold tkinter BooleanVar instances
        # Will be set after window setup when we can detect active categories
        
        # Apple-style category indicators
        self.category_indicators = {}  # Canvas items for chips
        self.indicator_tooltips = {}   # Tooltip tracking
        self.hover_states = {}          # Track hover state to prevent re-entrance
        self.last_hover_time = {}       # Track last hover time for debouncing
        
        # Dynamic height based on description setting - now includes indicator space
        self.base_height = TICKER_HEIGHT_PX + 12  # +12px for compact indicator strip
        self.min_description_height = 30  # Minimum additional height (increased)
        self.max_description_height = 200  # Maximum additional height (increased for long descriptions)
        self.description_height = self.min_description_height
        self.current_height = self.base_height
        
        # Setup window
        self.root = tk.Tk()
        self.setup_window()
        
        # Initialize enabled categories with active categories + Default
        active_categories = self._get_active_categories()
        self.enabled_categories = set(active_categories + ['Default'])
        
        # Setup UI elements
        self.setup_ui()
        
        # Calculate initial description height
        self.calculate_optimal_description_height()
        
        # Mark as running before starting updates
        self._running = True
        
        # Start checking for updates
        self.check_updates()
        
        # Load first item after GUI is ready
        self.root.after(100, self.load_next_item)
        
        # Start scrolling
        self.root.after(1000, self.scroll_text)
        
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

        
        # Setup Apple-style category indicators
        self._setup_category_indicators()
        
        # Create context menu with submenus
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Pause/Resume", command=self.toggle_pause)
        self.context_menu.add_separator()
        
        # Show descriptions checkbox
        self.show_descriptions_var = tk.BooleanVar(value=self.show_descriptions)
        self.context_menu.add_checkbutton(
            label="Show Descriptions", 
            command=self.toggle_descriptions,
            variable=self.show_descriptions_var
        )
        
        self.context_menu.add_separator()
        
        # Speed control submenu
        self.speed_menu = Menu(self.context_menu, tearoff=0)
        self.speed_var = tk.StringVar(value="normal")
        self.speed_menu.add_radiobutton(label="Normal Speed", variable=self.speed_var, value="normal", command=self.set_normal_speed)
        self.speed_menu.add_radiobutton(label="2x Speed", variable=self.speed_var, value="double", command=self.set_double_speed)
        self.context_menu.add_cascade(label="Speed", menu=self.speed_menu)
        
        # Categories control submenu
        self.categories_menu = Menu(self.context_menu, tearoff=0)
        self._setup_category_menu()
        self.context_menu.add_cascade(label="Categories", menu=self.categories_menu)
        
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
            
        # Note: Removed broken article request queue processing that caused spam
        
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
        
        # Reset tracking for new headlines (but preserve sliding window)
        # sliding_window_shown persists across updates to prevent cross-batch repeats
        logger.debug(f"Updated headlines, sliding window has {len(self.sliding_window_shown)} recent articles")
        
        logger.info(f"Filtered to {len(filtered_items)} headlines from {len(items)} total")
        
        # Update description height based on new content
        self.calculate_optimal_description_height()
        
        # If descriptions are enabled, update the window size
        if self.show_descriptions:
            self.current_height = self.base_height + self.description_height
            self.update_window_geometry()
            self.canvas.configure(height=self.current_height)
            self.create_description_area()
        
        # If we have no active items, load the first one
        if not self.text_items:
            self.load_next_item()
            
    def _handle_error(self, error_msg: str):
        """Handle error messages."""
        logger.info(f"Displaying error: {error_msg}")
        self.headlines.clear()
        self.headlines.append((f"[Error: {error_msg}]{BULLET}", "", f"Error: {error_msg}", "Default"))
        self.calculate_optimal_description_height()
        
    def _handle_critical_error(self, error_msg: str):
        """Handle critical error messages."""
        logger.critical(f"Critical error: {error_msg}")
        self.headlines.clear()
        self.headlines.append((f"[CRITICAL: {error_msg}]{BULLET}", "", f"Critical Error: {error_msg}", "Default"))
        self.calculate_optimal_description_height()
        
    def should_load_next(self) -> bool:
        """Check if we should load the next headline."""
        if not self.text_items:
            return True
            
        # Get the rightmost (most recently added) item
        rightmost_item = self.text_items[-1]
        
        # Don't load another item too quickly
        if time.time() - rightmost_item.get('load_time', 0) < 0.5:
            return False
            
        # Check if there's enough space
        try:
            bbox = self.canvas.bbox(rightmost_item['id'])
            if bbox:
                right_edge = bbox[2]
                return right_edge <= (self.screen_width - MIN_HEADLINE_GAP)
        except tk.TclError:
            # Canvas item might be deleted, use estimation
            pass
            
        # Fallback: estimate based on position and text length
        text = rightmost_item.get('text', '')
        estimated_width = calculate_text_width(text, FONT_SIZE)
        right_edge = rightmost_item['x'] + estimated_width
        return right_edge <= (self.screen_width - MIN_HEADLINE_GAP)
        
    def load_next_item(self):
        """Load the next headline using intelligent selection."""
        if not self._running:
            return
            
        try:
            # Use time-decay scoring for article selection
            if self.headlines:
                best_article = self._select_best_available_article()
                if best_article:
                    text, url, description, category = best_article
                    
                    # Track article as shown
                    current_time = time.time()
                    self.sliding_window_shown.append(url)
                    self.last_article_time[url] = current_time
                    
                    # Check if we need more articles after this selection
                    self._check_article_supply()
                    
                    # Get color for this category
                    text_color = CATEGORY_COLORS.get(category, CATEGORY_COLORS['Default'])
                else:
                    # No suitable article found, request fresh batch
                    self._request_fresh_batch("no suitable articles")
                    return
            else:
                # No articles available, request fresh batch  
                self._request_fresh_batch("no articles available")
                return
            
            # Add subtle category prefix for clarity
            category_prefix = {
                'Politics': '[POL]',
                'Technology': '[TECH]',
                'Business': '[BIZ]',
                'World': '[WORLD]',
                'Science': '[SCI]',
                'Sports': '[SPORT]',
                'Arts': '[ARTS]',
                'Health': '[HEALTH]',
                'Opinion': '[OP]',
                'HomePage': '[TOP]'
            }.get(category, '')
            
            if category_prefix:
                display_text = f"{category_prefix} {text}"
            else:
                display_text = text
            
            logger.debug(f"Loading item: {text[:50]}... (category: {category}, color: {text_color})")
            
            # Create new text item with category color
            text_id = self.canvas.create_text(
                float(self.screen_width), self.text_y,
                text=display_text,
                font=self.font,
                fill=text_color,
                anchor="w"
            )
            
            # Add to tracking list
            self.text_items.append({
                'id': text_id,
                'url': url,
                'text': display_text,
                'description': description,
                'category': category,
                'x': float(self.screen_width),
                'load_time': time.time()
            })
            
        except Exception as e:
            logger.error(f"Error loading next item: {e}")
            
    def scroll_text(self):
        """Scroll all text items across the screen."""
        if not self._running:
            return
            
        try:
            if not self.paused:
                items_to_remove = []
                
                for item in self.text_items:
                    # Move text
                    item['x'] -= PIXELS_PER_STEP
                    self.canvas.coords(item['id'], item['x'], self.text_y)
                    
                    # Check if item has scrolled off screen
                    try:
                        bbox = self.canvas.bbox(item['id'])
                        if bbox and bbox[2] < 0:
                            items_to_remove.append(item)
                    except tk.TclError:
                        # Item might be deleted
                        items_to_remove.append(item)
                        
                # Remove items that have scrolled off
                for item in items_to_remove:
                    try:
                        self.canvas.delete(item['id'])
                    except tk.TclError:
                        pass
                    self.text_items.remove(item)
                    
                # Update description display BEFORE loading new items
                self.update_description_display()
                
                # Load next item if there's room
                if self.should_load_next():
                    self.load_next_item()
                
        except Exception as e:
            logger.error(f"Error in scroll: {e}")
            
        # Schedule next scroll with dynamic delay
        if self._running:
            current_delay = int(self.base_scroll_delay / self.speed_multiplier)
            self.root.after(current_delay, self.scroll_text)
            
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
            # This prevents "No clickable item found" when clicking indicators
            for category, info in self.category_indicators.items():
                # Check if click is within indicator bounds
                ind_x = info['x']
                ind_y = info['y']
                if (ind_x <= click_x <= ind_x + INDICATOR_WIDTH and
                    ind_y <= click_y <= ind_y + INDICATOR_HEIGHT):
                    # Click is on an indicator, let the tag handler handle it
                    # Don't log anything, just return
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
                
                # Validate URL before opening
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
            
        # Schedule next check
        if self._running:
            self.root.after(TOPMOST_CHECK_INTERVAL, self.maintain_topmost)
            
    def show_context_menu(self, event):
        """Show the right-click context menu."""
        try:
            self.context_menu.post(event.x_root, event.y_root)
        except tk.TclError:
            pass
            
    def _setup_category_indicators(self):
        """Setup compact Apple-style category micro-chips."""
        # Get only categories that have active feeds
        active_categories = self._get_active_categories()
        
        x = INDICATOR_MARGIN_X
        y = INDICATOR_MARGIN_Y
        
        # Category abbreviations for compact display
        category_abbrev = {
            'Politics': 'POL',
            'Technology': 'TECH', 
            'HomePage': 'HOME',
            'Business': 'BIZ',
            'World': 'WORLD',
            'Science': 'SCI',
            'Sports': 'SPORT',
            'Arts': 'ARTS',
            'Health': 'HEALTH',
            'Opinion': 'OP'
        }
        
        for i, category in enumerate(active_categories):
            # Calculate position
            chip_x = x + i * (INDICATOR_WIDTH + INDICATOR_SPACING)
            chip_y = y
            
            # Get category color and abbreviation
            color = CATEGORY_COLORS.get(category, CATEGORY_COLORS['Default'])
            abbrev = category_abbrev.get(category, category[:3])
            
            # Create indicator micro-chip
            is_enabled = category in self.enabled_categories
            chip_id = self._create_indicator_chip(chip_x, chip_y, color, is_enabled, category, abbrev)
            
            self.category_indicators[category] = {
                'chip_id': chip_id,
                'x': chip_x,
                'y': chip_y,
                'color': color,
                'enabled': is_enabled,
                'abbrev': abbrev
            }
    
    def _create_indicator_chip(self, x, y, color, enabled, category, abbrev):
        """Create a compact micro-chip indicator with Apple-style design."""
        # Create rounded rectangle background
        x1, y1 = x, y
        x2, y2 = x + INDICATOR_WIDTH, y + INDICATOR_HEIGHT
        
        if enabled:
            # Filled chip for enabled categories
            bg_id = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=color, outline=color, width=1,
                tags=("category_indicator", f"indicator_{category}", f"bg_{category}")
            )
            text_color = "#000000"  # Black text on colored background
        else:
            # Outline chip for disabled categories
            bg_id = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                fill="", outline=color, width=1,
                tags=("category_indicator", f"indicator_{category}", f"bg_{category}")
            )
            text_color = color  # Colored text on transparent background
        
        # Add abbreviated text label
        text_x = x + INDICATOR_WIDTH // 2
        text_y = y + INDICATOR_HEIGHT // 2
        text_id = self.canvas.create_text(
            text_x, text_y,
            text=abbrev,
            font=("Arial", 6, "bold"),  # Very small font for compact design
            fill=text_color,
            anchor="center",
            tags=("category_indicator", f"indicator_{category}", f"text_{category}")
        )
        
        # Bind click and hover events to both background and text
        self.canvas.tag_bind(f"indicator_{category}", "<Button-1>", 
                           lambda e, c=category: self._on_indicator_click(c))
        self.canvas.tag_bind(f"indicator_{category}", "<Enter>", 
                           lambda e, c=category: self._on_indicator_hover(c))
        self.canvas.tag_bind(f"indicator_{category}", "<Leave>", 
                           lambda e, c=category: self._on_indicator_leave(c))
        
        return bg_id  # Return background ID as primary identifier
    
    def _get_active_categories(self):
        """Get list of categories that actually have RSS feeds configured."""
        try:
            from .config import FEED_URLS
        except ImportError:
            from config import FEED_URLS
        
        active_categories = set()
        
        # Analyze FEED_URLS to determine which categories have feeds
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
        
        # Return sorted list for consistent ordering
        return sorted(list(active_categories))
    
    def _update_category_indicators(self):
        """Update indicator visual states based on enabled categories."""
        for category, indicator_info in self.category_indicators.items():
            is_enabled = category in self.enabled_categories
            if indicator_info['enabled'] != is_enabled:
                # State changed, update visual
                indicator_info['enabled'] = is_enabled
                self._update_indicator_visual(category, is_enabled)
    
    def _update_indicator_visual(self, category, enabled):
        """Update a single indicator's visual state with smooth transition."""
        if category not in self.category_indicators:
            return
            
        info = self.category_indicators[category]
        color = info['color']
        
        try:
            # Check if canvas items exist before trying to update them
            bg_items = self.canvas.find_withtag(f"bg_{category}")
            text_items = self.canvas.find_withtag(f"text_{category}")
            
            if not bg_items or not text_items:
                logger.warning(f"Canvas items not found for category {category} (bg: {len(bg_items)}, text: {len(text_items)})")
                return
                
            if enabled:
                # Fill the chip background
                self.canvas.itemconfig(f"bg_{category}", fill=color, outline=color, width=1)
                # Black text on colored background
                self.canvas.itemconfig(f"text_{category}", fill="#000000")
            else:
                # Make chip outline only
                self.canvas.itemconfig(f"bg_{category}", fill="", outline=color, width=1)
                # Colored text on transparent background
                self.canvas.itemconfig(f"text_{category}", fill=color)
        except tk.TclError as e:
            logger.warning(f"Error updating indicator visual for {category}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error updating indicator visual for {category}: {e}")
    
    def _on_indicator_click(self, category):
        """Handle click on category indicator for instant toggling."""
        try:
            # Toggle the category state
            if category in self.enabled_categories:
                self.enabled_categories.discard(category)
                if category in self.category_vars:
                    self.category_vars[category].set(False)
            else:
                self.enabled_categories.add(category)
                if category in self.category_vars:
                    self.category_vars[category].set(True)
            
            # Update visual immediately
            self._update_category_indicators()
            
            # Apply filter gracefully
            self._filter_current_headlines_gracefully()
            
            logger.info(f"Category {category} toggled via indicator: {'enabled' if category in self.enabled_categories else 'disabled'}")
        except Exception as e:
            logger.error(f"Error handling indicator click for {category}: {e}")
            # Don't re-raise to prevent crash
    
    def _on_indicator_hover(self, category):
        """Show tooltip with full category name and article count on hover."""
        # Check if already hovering to prevent re-entrance
        if self.hover_states.get(category, False):
            return
            
        # Debouncing: ignore if hover was triggered too recently
        current_time = time.time()
        last_time = self.last_hover_time.get(category, 0)
        if current_time - last_time < 0.1:  # 100ms debounce
            return
            
        # Set hover state and update time
        self.hover_states[category] = True
        self.last_hover_time[category] = current_time
        
        # Get article count for this category
        count = self._get_category_article_count(category)
        status = "enabled" if category in self.enabled_categories else "disabled"
        
        # Change cursor to indicate clickable
        self.canvas.configure(cursor="hand2")
        
        # Clean up any existing tooltip before creating new one
        self._cleanup_tooltip(category)
        
        # Create tooltip popup (simple implementation)
        self._show_tooltip(category, count, status)
        
        logger.debug(f"Hovering {category}: {count} articles, {status}")
    
    def _show_tooltip(self, category, count, status):
        """Show a compact tooltip with category info."""
        # Create a small tooltip rectangle near the indicator
        if category in self.category_indicators:
            info = self.category_indicators[category]
            x, y = info['x'], info['y']
            
            # Position tooltip further below the chip to prevent interference
            tooltip_x = x
            tooltip_y = y + INDICATOR_HEIGHT + 10  # Increased spacing
            
            # Prepare tooltip text
            tooltip_text = f"{category}: {count} articles ({status})"
            
            # Create text first to measure bounds
            text_id = self.canvas.create_text(
                tooltip_x, tooltip_y,
                text=tooltip_text,
                font=("Arial", 8),
                fill="#000000",  # Black text
                anchor="nw",
                tags=("tooltip", f"tooltip_text_{category}")
            )
            
            # Get text bounds for background
            bbox = self.canvas.bbox(text_id)
            if bbox:
                # Add padding around text
                padding = 3
                x1, y1, x2, y2 = bbox
                x1 -= padding
                y1 -= padding
                x2 += padding
                y2 += padding
                
                # Ensure tooltip stays within canvas bounds
                canvas_width = self.canvas.winfo_width()
                if x2 > canvas_width - 5:
                    # Shift tooltip left if it would go off-screen
                    shift = x2 - (canvas_width - 5)
                    x1 -= shift
                    x2 -= shift
                    self.canvas.coords(text_id, x1 + padding, y1 + padding)
                
                # Create background rectangle
                bg_id = self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill="#FFFFDD",  # Light yellow background
                    outline="#888888",  # Gray border
                    width=1,
                    tags=("tooltip", f"tooltip_bg_{category}")
                )
                
                # Move background behind text
                self.canvas.tag_lower(bg_id, text_id)
                
                # Store both IDs for cleanup
                self.indicator_tooltips[category] = {
                    'text': text_id,
                    'bg': bg_id
                }
            else:
                # Fallback if bbox fails
                self.indicator_tooltips[category] = {'text': text_id}
    
    def _cleanup_tooltip(self, category):
        """Clean up any existing tooltip for a category."""
        if category in self.indicator_tooltips:
            tooltip_info = self.indicator_tooltips[category]
            try:
                # Handle both single ID and dict with multiple IDs
                if isinstance(tooltip_info, dict):
                    for item_id in tooltip_info.values():
                        self.canvas.delete(item_id)
                else:
                    self.canvas.delete(tooltip_info)
            except tk.TclError:
                pass
            del self.indicator_tooltips[category]
    
    def _on_indicator_leave(self, category):
        """Remove hover effects and cleanup tooltip."""
        # Clear hover state
        self.hover_states[category] = False
        
        self.canvas.configure(cursor="")
        
        # Remove tooltip if exists
        self._cleanup_tooltip(category)
    
    def _get_category_article_count(self, category):
        """Get count of articles in a specific category."""
        if not hasattr(self, 'all_headlines'):
            return 0
            
        count = 0
        for item in self.all_headlines:
            if len(item) >= 4 and item[3] == category:
                count += 1
        return count
    
    def _setup_category_menu(self):
        """Setup category checkboxes in the context menu with article counts."""
        # Only show categories that have active RSS feeds
        available_categories = self._get_active_categories()
        
        for category in available_categories:
            var = tk.BooleanVar(value=category in self.enabled_categories)
            self.category_vars[category] = var
            
            # Get article count
            count = self._get_category_article_count(category)
            
            # Create menu item with count and visual indicator
            enabled_indicator = "●" if category in self.enabled_categories else "○"
            label = f"{enabled_indicator} {category} ({count} articles)"
            
            self.categories_menu.add_checkbutton(
                label=label,
                variable=var,
                command=lambda c=category: self.toggle_category(c)
            )
    
    def set_normal_speed(self):
        """Set scrolling to normal speed."""
        self.speed_multiplier = 1.0
        logger.info("Speed set to normal (1x)")
    
    def set_double_speed(self):
        """Set scrolling to double speed."""
        self.speed_multiplier = 2.0
        logger.info("Speed set to double (2x)")
    
    def toggle_category(self, category: str):
        """Toggle visibility of a specific category with graceful UX."""
        if self.category_vars[category].get():
            self.enabled_categories.add(category)
            logger.info(f"Enabled category: {category}")
        else:
            self.enabled_categories.discard(category)
            logger.info(f"Disabled category: {category}")
        
        # Update indicators immediately
        self._update_category_indicators()
        
        # Refresh menu labels with new counts
        self._refresh_category_menu()
        
        # Apply graceful filtering
        self._filter_current_headlines_gracefully()
    
    def _refresh_category_menu(self):
        """Refresh category menu labels with updated article counts."""
        # Clear existing menu items
        self.categories_menu.delete(0, "end")
        
        # Recreate with updated counts - only show active categories
        available_categories = self._get_active_categories()
        
        for category in available_categories:
            if category not in self.category_vars:
                continue
                
            var = self.category_vars[category]
            count = self._get_category_article_count(category)
            
            # Visual indicator and label
            enabled_indicator = "●" if category in self.enabled_categories else "○"
            label = f"{enabled_indicator} {category} ({count})"
            
            self.categories_menu.add_checkbutton(
                label=label,
                variable=var,
                command=lambda c=category: self.toggle_category(c)
            )
    
    def _filter_current_headlines_gracefully(self):
        """Apple-style graceful filtering - never disrupt current viewing experience."""
        if not hasattr(self, 'all_headlines'):
            return
            
        # CRITICAL: Never touch self.text_items (currently scrolling articles)
        # Only filter upcoming articles in self.headlines
        
        # Filter headlines by enabled categories
        filtered_headlines = []
        for item in self.all_headlines:
            if len(item) >= 4:  # Has category
                category = item[3]
                if category in self.enabled_categories:
                    filtered_headlines.append(item)
            else:  # Fallback for items without category (always show)
                filtered_headlines.append(item)
        
        # Handle empty state elegantly (Apple-style)
        if not filtered_headlines and self.enabled_categories:
            # Some categories enabled but no articles - temporary state
            empty_message = "No articles in selected categories • Loading fresh content..."
            empty_desc = "New articles will appear shortly. You can adjust categories anytime by right-clicking."
            filtered_headlines = [(empty_message, "", empty_desc, "Default")]
        elif not filtered_headlines:
            # No categories enabled - helpful guidance
            guidance_message = "Choose categories above • Right-click to select"
            guidance_desc = "Select news categories from the right-click menu to see articles."
            filtered_headlines = [(guidance_message, "", guidance_desc, "Default")]
        
        # Update headlines queue gracefully
        self.headlines.clear()
        self.headlines.extend(filtered_headlines)
        
        # Safe index management - only reset if needed
        if self.current_index >= len(self.headlines):
            self.current_index = 0
        
        # Handle description context intelligently
        self._manage_description_context()
        
        logger.info(f"Gracefully filtered: {len(filtered_headlines)} visible from {len(self.all_headlines) if hasattr(self, 'all_headlines') else 0} total")
    
    def _manage_description_context(self):
        """Intelligently manage description display during category changes."""
        if not self.show_descriptions or not self.description_text_id:
            return
            
        # Find what's currently at the reference point
        current_item = self.find_current_headline()
        
        if current_item:
            current_category = current_item.get('category', 'Default')
            # Only clear description if its category was disabled AND no enabled content is visible
            if current_category not in self.enabled_categories:
                # Check if any enabled articles are coming up
                has_enabled_upcoming = any(
                    item.get('category', 'Default') in self.enabled_categories 
                    for item in self.text_items[1:] if len(self.text_items) > 1
                )
                
                if not has_enabled_upcoming:
                    # Gracefully fade out the description
                    try:
                        self.canvas.delete(self.description_text_id)
                        self.description_text_id = None
                    except tk.TclError:
                        pass
    
    def _filter_current_headlines(self):
        """Legacy method - redirect to graceful version."""
        self._filter_current_headlines_gracefully()
    
    def toggle_descriptions(self):
        """Toggle the display of descriptions."""
        self.show_descriptions = not self.show_descriptions
        self.show_descriptions_var.set(self.show_descriptions)
        logger.info(f"Description display toggled to: {self.show_descriptions}")
        
        # Update window height
        if self.show_descriptions:
            # Recalculate optimal height in case it hasn't been done yet
            self.calculate_optimal_description_height()
            self.current_height = self.base_height + self.description_height
        else:
            self.current_height = self.base_height
            
        # Resize window and canvas
        self.update_window_geometry()
        self.canvas.configure(height=self.current_height)
        
        # Clean up description area if toggled off
        if not self.show_descriptions:
            self.canvas.delete("description")
            self.canvas.delete("separator")
            if self.description_text_id:
                self.canvas.delete(self.description_text_id)
                self.description_text_id = None
        else:
            # Create description area separator line
            self.create_description_area()
            
    def create_description_area(self):
        """Create visual separator and description area."""
        if not self.show_descriptions:
            return
            
        # Remove existing separator if any
        self.canvas.delete("separator")
        
        # Create subtle separator line
        separator_y = self.base_height + 2
        self.canvas.create_line(
            10, separator_y, self.screen_width - 10, separator_y,
            fill="#333333", width=1, tags="separator"
        )
            
    def calculate_optimal_description_height(self):
        """Calculate the optimal height for the description area based on content."""
        if not self.headlines:
            self.description_height = self.min_description_height
            return
            
        # Find the longest description
        max_description = ""
        for item in self.headlines:
            # Handle both 3-tuple and 4-tuple formats
            if len(item) >= 3:
                description = item[2]  # Description is always the 3rd element
                if len(description) > len(max_description):
                    max_description = description
                
        if not max_description:
            self.description_height = self.min_description_height
            return
            
        try:
            # Create font for measuring
            desc_font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE-2)
            
            # Available width for text (with generous margins)
            available_width = self.screen_width - 60  # More margin for better readability
            
            # Measure the text to determine how many lines are needed
            lines_needed = self.calculate_text_lines(max_description, desc_font, available_width)
            
            # Calculate height needed with better spacing
            line_height = desc_font.metrics('linespace')
            line_spacing = max(2, line_height // 8)  # Add small spacing between lines
            content_height = (lines_needed * line_height) + ((lines_needed - 1) * line_spacing)
            
            # Add generous padding (top + bottom)
            padding = 20
            needed_height = content_height + padding
            
            # Clamp to min/max bounds
            self.description_height = max(
                self.min_description_height,
                min(needed_height, self.max_description_height)
            )
            
            logger.debug(f"Calculated description height: {self.description_height}px for {lines_needed} lines (line_height={line_height}, content={content_height}, padding={padding})")
            
        except Exception as e:
            logger.warning(f"Error calculating description height: {e}")
            self.description_height = self.min_description_height
            
    def calculate_text_lines(self, text, font, width):
        """Calculate how many lines a text would need given font and width."""
        if not text:
            return 1
            
        # Handle explicit line breaks
        paragraphs = text.split('\n')
        total_lines = 0
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                total_lines += 1  # Empty line
                continue
                
            # Split into words
            words = paragraph.split()
            if not words:
                total_lines += 1
                continue
                
            lines_for_paragraph = 1
            current_line_width = 0
            
            for word in words:
                # Measure word with a space (except for last word)
                word_width = font.measure(word + " ")
                
                # Check if adding this word would exceed the width
                if current_line_width > 0 and (current_line_width + word_width) > width:
                    lines_for_paragraph += 1
                    current_line_width = word_width
                else:
                    current_line_width += word_width
            
            total_lines += lines_for_paragraph
                
        return max(total_lines, 1)
            
    def find_current_headline(self):
        """Find the headline currently at the reference point (40% from left)."""
        if not self.text_items:
            return None
            
        reference_x = self.screen_width * 0.4  # 40% from left edge (better positioning)
        current_item = None
        
        for item in self.text_items:
            try:
                bbox = self.canvas.bbox(item['id'])
                if bbox and bbox[0] <= reference_x <= bbox[2]:
                    current_item = item
                    break
            except tk.TclError:
                continue
                
        return current_item
            
    def update_description_display(self):
        """Update the description display based on current headline at reference point."""
        if not self.show_descriptions:
            return
            
        current_item = self.find_current_headline()
        new_description = current_item.get('description', '') if current_item else ''
        
        # Check if description has changed to avoid unnecessary updates
        current_description = ""
        if self.description_text_id:
            try:
                current_text = self.canvas.itemcget(self.description_text_id, 'text')
                current_description = current_text.replace('• ', '') if current_text.startswith('• ') else current_text
            except tk.TclError:
                pass
                
        if new_description == current_description:
            return
            
        # Remove existing description
        if self.description_text_id:
            self.canvas.delete(self.description_text_id)
            self.description_text_id = None
            
        if not new_description:
            return
            
        # Create description text in dedicated description area
        try:
            # Position in the center of the description area
            desc_x = self.screen_width / 2
            desc_y = self.base_height + (self.description_height / 2) + 2
            
            # Create description with smaller font
            desc_font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE-2)
            self.description_text_id = self.canvas.create_text(
                desc_x, desc_y,
                text=f"• {new_description}",
                font=desc_font,
                fill="#CCCCCC",  # Lighter color for visibility
                anchor="center",
                width=self.screen_width - 60,  # Match calculation width (60px margins)
                tags="description"
            )
        except tk.TclError:
            pass
            
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
    
    def _apply_smart_balancing(self, filtered_headlines, category_counts):
        """Apply smart category balancing when content is scarce."""
        if not self.all_headlines:
            return filtered_headlines
            
        # Category relationships for smart expansion
        category_expansion = {
            'Politics': ['HomePage', 'World'],  # Politics can expand to HomePage/World
            'Technology': ['Business'],  # Technology can expand to Business
            'HomePage': ['Politics', 'World'],  # HomePage can expand to Politics/World
            'World': ['Politics', 'HomePage'],  # World can expand to Politics/HomePage
        }
        
        expanded_headlines = list(filtered_headlines)  # Start with filtered
        added_count = 0
        
        # For each enabled category with few articles, add related content
        for enabled_category in self.enabled_categories:
            current_count = category_counts.get(enabled_category, 0)
            
            if current_count < 5:  # If category has < 5 articles
                related_categories = category_expansion.get(enabled_category, [])
                
                for related_cat in related_categories:
                    for item in self.all_headlines:
                        if len(item) >= 4 and item[3] == related_cat:
                            if item not in expanded_headlines:
                                expanded_headlines.append(item)
                                added_count += 1
                                if added_count >= 10:  # Limit expansion
                                    break
                    if added_count >= 10:
                        break
                        
        if added_count > 0:
            logger.info(f"Smart balancing added {added_count} related articles for variety")
            
        return expanded_headlines
    
    def _get_dynamic_sliding_window_size(self):
        """Calculate dynamic sliding window size based on content availability."""
        enabled_count = len(self.enabled_categories)
        total_articles = len(self.headlines)
        
        # Count articles in enabled categories
        enabled_articles = 0
        for item in self.headlines:
            if len(item) >= 4:
                text, url, description, category = item
            else:
                text, url, description = item
                category = 'Default'
            if category in self.enabled_categories:
                enabled_articles += 1
        
        # Dynamic window sizing based on content availability
        if enabled_count == 1 and enabled_articles < 30:
            # Single category with limited content
            return min(10, enabled_articles // 3)
        elif enabled_count <= 2:
            # Few categories enabled
            return min(25, enabled_articles // 2)
        else:
            # Multiple categories - use larger window
            return min(50, enabled_articles)
    
    def _select_best_available_article(self):
        """
        Select best article using 4-tier priority system.
        
        Tier 1: Fresh articles (never shown) from enabled categories - HIGHEST PRIORITY
        Tier 2: Articles outside sliding window from enabled categories 
        Tier 3: Articles in sliding window but past cooldown period
        Tier 4: EMERGENCY - Any article from enabled categories (ignore all constraints)
        """
        if not self.headlines:
            return None
            
        current_time = time.time()
        dynamic_window_size = self._get_dynamic_sliding_window_size()
        
        # Get recently shown articles for dynamic window
        recent_urls = set(list(self.sliding_window_shown)[-dynamic_window_size:])
        
        tier1_candidates = []  # Fresh articles
        tier2_candidates = []  # Outside sliding window
        tier3_candidates = []  # In window but past cooldown
        tier4_candidates = []  # Emergency fallback
        
        for item in self.headlines:
            if len(item) >= 4:
                text, url, description, category = item
            else:
                text, url, description = item
                category = 'Default'
                
            # Skip if category is disabled
            if category not in self.enabled_categories:
                continue
            
            last_shown = self.last_article_time.get(url, 0)
            time_since_shown = current_time - last_shown
            in_recent_window = url in recent_urls
            
            # Calculate base score for ranking within tiers
            time_score = min(time_since_shown / 300, 10)
            novelty_bonus = 20 if last_shown == 0 else 0
            base_score = time_score + novelty_bonus
            
            # Categorize into tiers
            if last_shown == 0:
                # Tier 1: Fresh articles (never shown)
                tier1_candidates.append((base_score, item))
            elif not in_recent_window:
                # Tier 2: Outside sliding window
                tier2_candidates.append((base_score, item))
            elif time_since_shown >= 30:  # 30 second cooldown
                # Tier 3: In window but past cooldown
                tier3_candidates.append((base_score, item))
            
            # All enabled articles are emergency candidates
            tier4_candidates.append((base_score, item))
        
        # Select from highest available tier
        candidates = None
        tier_used = 0
        
        if tier1_candidates:
            candidates = tier1_candidates
            tier_used = 1
        elif tier2_candidates:
            candidates = tier2_candidates  
            tier_used = 2
        elif tier3_candidates:
            candidates = tier3_candidates
            tier_used = 3
        elif tier4_candidates:
            candidates = tier4_candidates
            tier_used = 4
        
        if candidates:
            # Sort by score descending and return best
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_article = candidates[0][1]
            
            # Log tier usage for debugging
            if tier_used >= 3:
                logger.debug(f"Article selection using Tier {tier_used} (window size: {dynamic_window_size})")
            
            return best_article
        
        return None
    
    def _check_article_supply(self):
        """Check if we need to request fresh articles."""
        if not self.headlines:
            return
            
        # Count suitable articles remaining
        suitable_count = 0
        current_time = time.time()
        
        for item in self.headlines:
            if len(item) >= 4:
                text, url, description, category = item
            else:
                text, url, description = item
                category = 'Default'
                
            # Skip if category disabled or recently shown
            if category not in self.enabled_categories:
                continue
            if url in self.sliding_window_shown:
                continue
                
            # Check time-based availability
            last_shown = self.last_article_time.get(url, 0)
            if current_time - last_shown < 60:  # 1 minute minimum
                continue
                
            suitable_count += 1
            
        # Request fresh batch if running low
        if suitable_count < 10:
            self._request_fresh_batch(f"low supply: {suitable_count} suitable articles")
            
    def _request_fresh_batch(self, reason: str):
        """Request fresh batch of articles from fetcher."""
        logger.info(f"Requesting fresh article batch: {reason}")
        
        # Put request in update queue for fetcher to see
        # This uses the existing communication channel
        if hasattr(self, 'update_queue'):
            # For now, just log the request
            # In future, could implement fetcher batch rotation
            logger.debug(f"Would request fresh batch from fetcher: {reason}")
    
    def request_fresh_articles(self):
        """Legacy method - now redirects to smart batch request."""
        self._request_fresh_batch("manual refresh request") 