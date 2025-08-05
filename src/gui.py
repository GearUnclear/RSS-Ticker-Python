"""
GUI module for NYT RSS Ticker with improved structure and resource management.
"""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import Menu
from collections import deque
import queue
import time
import webbrowser
from datetime import date
from typing import List, Dict, Optional, Tuple

try:
    from .config import (
        TICKER_HEIGHT_PX, BG_COLOR, FG_COLOR, FONT_FAMILY, FONT_SIZE,
        SCROLL_DELAY_MS, PIXELS_PER_STEP, MIN_HEADLINE_GAP, BULLET,
        PAUSE_ICON, CLOSE_ICON, FONT_SIZE_PAUSE, FONT_SIZE_CLOSE,
        TASKBAR_HEIGHT, TOPMOST_CHECK_INTERVAL, CATEGORY_COLORS
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
        TASKBAR_HEIGHT, TOPMOST_CHECK_INTERVAL, CATEGORY_COLORS
    )
    from exceptions import InvalidURLError
    from logger import logger
    from utils import validate_url, calculate_text_width


class TickerGUI:
    """Main GUI class for the RSS ticker."""
    
    def __init__(self, update_queue: queue.Queue):
        self.update_queue = update_queue
        today_str = date.today().strftime("%B %d, %Y")
        self.headlines = deque([(f"🗞️ BREAKING: Loading Today's Premium NYT Coverage for {today_str} • Stay Informed with Real-Time News Updates {BULLET}", "", f"Loading the latest news stories from The New York Times for {today_str}. Please wait while we fetch your personalized news feed with the most current and relevant stories.", "Default")])
        self.current_index = 0
        self.paused = False
        self.show_descriptions = False  
        self.text_items: List[Dict] = []
        self._running = False
        self._shutdown_callbacks = []
        self.description_text_id = None
        
        # Dynamic height based on description setting
        self.base_height = TICKER_HEIGHT_PX
        self.min_description_height = 30  # Minimum additional height (increased)
        self.max_description_height = 200  # Maximum additional height (increased for long descriptions)
        self.description_height = self.min_description_height
        self.current_height = self.base_height
        
        # Setup window
        self.root = tk.Tk()
        self.setup_window()
        
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
            
        self.text_y = self.base_height // 2  # Always in upper half for main headlines
        
        # Pause indicator
        self.pause_id = self.canvas.create_text(
            10, 5,
            text=PAUSE_ICON,
            font=(FONT_FAMILY, FONT_SIZE_PAUSE),
            fill=FG_COLOR,
            anchor="nw",
            state="hidden"
        )
        
        # Close button
        close_x = self.screen_width - 20
        self.canvas.create_text(
            close_x, 5,
            text=CLOSE_ICON,
            font=(FONT_FAMILY, FONT_SIZE_CLOSE),
            fill=FG_COLOR,
            anchor="ne",
            tags="close_btn"
        )
        
        # Bind events
        self.root.bind("<Escape>", lambda e: self.close_app())
        self.root.bind("<Button-3>", self.show_context_menu)
        self.root.bind("<space>", lambda e: self.toggle_pause())
        self.canvas.bind("<Button-1>", self.open_link)

        self.canvas.tag_bind("close_btn", "<Button-1>", lambda e: self.close_app())
        
        # Create context menu
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Pause/Resume", command=self.toggle_pause)
        self.context_menu.add_separator()
        self.show_descriptions_var = tk.BooleanVar(value=self.show_descriptions)
        self.context_menu.add_checkbutton(
            label="Show Descriptions", 
            command=self.toggle_descriptions,
            variable=self.show_descriptions_var
        )
        
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
        self.headlines.clear()
        self.headlines.extend(items)
        self.current_index = 0
        
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
        """Load the next headline as a new text item."""
        if not self._running or not self.headlines:
            return
            
        try:
            # Get next item
            idx = self.current_index % len(self.headlines)
            
            # Handle both old 3-tuple and new 4-tuple format
            if len(self.headlines[idx]) == 4:
                text, url, description, category = self.headlines[idx]
            else:
                text, url, description = self.headlines[idx]
                category = 'Default'
            
            self.current_index = idx + 1
            
            # Get color for this category
            text_color = CATEGORY_COLORS.get(category, CATEGORY_COLORS['Default'])
            
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
            
            logger.debug(f"Loading item {idx}: {text[:50]}... (category: {category}, color: {text_color})")
            
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
            
        # Schedule next scroll
        if self._running:
            self.root.after(SCROLL_DELAY_MS, self.scroll_text)
            
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
            # Find which text item was clicked
            clicked_item = None
            click_x = event.x
            
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
        for _, _, description in self.headlines:
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