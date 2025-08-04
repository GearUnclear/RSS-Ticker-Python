"""
GUI module for NYT RSS Ticker with improved structure and resource management.
"""
import tkinter as tk
import tkinter.font as tkfont
from collections import deque
import queue
import time
import webbrowser
from typing import List, Dict, Optional, Tuple

try:
    from .config import (
        TICKER_HEIGHT_PX, BG_COLOR, FG_COLOR, FONT_FAMILY, FONT_SIZE,
        SCROLL_DELAY_MS, PIXELS_PER_STEP, MIN_HEADLINE_GAP, BULLET,
        PAUSE_ICON, CLOSE_ICON, FONT_SIZE_PAUSE, FONT_SIZE_CLOSE,
        TASKBAR_HEIGHT, TOPMOST_CHECK_INTERVAL
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
        TASKBAR_HEIGHT, TOPMOST_CHECK_INTERVAL
    )
    from exceptions import InvalidURLError
    from logger import logger
    from utils import validate_url, calculate_text_width


class TickerGUI:
    """Main GUI class for the RSS ticker."""
    
    def __init__(self, update_queue: queue.Queue):
        self.update_queue = update_queue
        self.headlines = deque([(f"(Loading NYT Politics...){BULLET}", "")])
        self.current_index = 0
        self.paused = False
        self.text_items: List[Dict] = []
        self._running = False
        self._shutdown_callbacks = []
        
        # Setup window
        self.root = tk.Tk()
        self.setup_window()
        
        # Setup UI elements
        self.setup_ui()
        
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
        y_pos = self.screen_height - TICKER_HEIGHT_PX - TASKBAR_HEIGHT
        self.root.geometry(f"{self.screen_width}x{TICKER_HEIGHT_PX}+0+{y_pos}")
        
        # Window styling
        self.root.overrideredirect(True)  # Remove window decorations
        self.root.configure(bg=BG_COLOR)
        
        # Keep on top
        self.root.attributes("-topmost", True)
        self.root.lift()
        
        # Set up proper window close handling
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        
    def setup_ui(self):
        """Create UI elements."""
        # Main canvas
        self.canvas = tk.Canvas(
            self.root,
            bg=BG_COLOR,
            height=TICKER_HEIGHT_PX,
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
            
        self.text_y = TICKER_HEIGHT_PX // 2
        
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
        self.root.bind("<Button-3>", lambda e: self.toggle_pause())
        self.root.bind("<space>", lambda e: self.toggle_pause())
        self.canvas.bind("<Button-1>", self.open_link)
        self.canvas.tag_bind("close_btn", "<Button-1>", lambda e: self.close_app())
        
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
            
    def _handle_update(self, items: List[Tuple[str, str]]):
        """Handle headline updates."""
        logger.info(f"Received {len(items)} headlines from fetch thread")
        self.headlines.clear()
        self.headlines.extend(items)
        self.current_index = 0
        
        # If we have no active items, load the first one
        if not self.text_items:
            self.load_next_item()
            
    def _handle_error(self, error_msg: str):
        """Handle error messages."""
        logger.info(f"Displaying error: {error_msg}")
        self.headlines.clear()
        self.headlines.append((f"[Error: {error_msg}]{BULLET}", ""))
        
    def _handle_critical_error(self, error_msg: str):
        """Handle critical error messages."""
        logger.critical(f"Critical error: {error_msg}")
        self.headlines.clear()
        self.headlines.append((f"[CRITICAL: {error_msg}]{BULLET}", ""))
        
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
            text, url = self.headlines[idx]
            self.current_index = idx + 1
            
            logger.debug(f"Loading item {idx}: {text[:50]}...")
            
            # Create new text item
            text_id = self.canvas.create_text(
                float(self.screen_width), self.text_y,
                text=text,
                font=self.font,
                fill=FG_COLOR,
                anchor="w"
            )
            
            # Add to tracking list
            self.text_items.append({
                'id': text_id,
                'url': url,
                'text': text,
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