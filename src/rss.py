"""
nyt_ticker.py — NYT Politics RSS ticker (Windows 11 Fixed)
─────────────────────────────────────────────────────────────────────────────
• Black-terminal look, orange monospace text.
• Click a headline to open it in your browser.
• Bullet separator between items.
• Smooth sub-pixel scrolling.
• ⏸ icon when paused; <Space> toggles play/pause (right-click still works).
• Resilient fetch loop with exponential back-off and headline deduplication.
"""

import itertools
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from collections import deque
from datetime import datetime
from email.utils import parsedate_to_datetime
import zoneinfo
import webbrowser
import traceback
import urllib.request
import urllib.error
import socket
import ssl
import queue

import feedparser

# ─── SETTINGS ────────────────────────────────────────────────────────────────
FEED_URL          = "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml"
REFRESH_MINUTES   = 10
SCROLL_DELAY_MS   = 30          # Slower for Windows stability
PIXELS_PER_STEP   = 2           # Slightly faster movement
TICKER_HEIGHT_PX  = 36          # Slightly taller for Windows
BG_COLOR          = "#000000"
FG_COLOR          = "#FFA500"
FONT_FAMILY       = "Courier New"  # More reliable on Windows
FONT_SIZE         = 14
LOCAL_TZ          = "America/Los_Angeles"
TIME_FMT          = "%I:%M%p"   # Windows compatible
BULLET            = " • "       # Simple bullet
DEBUG             = True
# ────────────────────────────────────────────────────────────────────────────


def debug_print(msg):
    """Print debug messages if DEBUG is True."""
    if DEBUG:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def fmt_entry(entry):
    """Return (render_text, url) tuple; add NYT-style metainfo + separator."""
    try:
        title = entry.get('title', 'No title').strip()
        author = entry.get("dc_creator") or entry.get("author") or "NYT Staff"
        
        when = ""
        if "published" in entry:
            try:
                dt_local = parsedate_to_datetime(entry.published).astimezone(
                           zoneinfo.ZoneInfo(LOCAL_TZ))
                when = dt_local.strftime(TIME_FMT).strip()
            except Exception:
                pass

        parts = [title, f"— {author}"]
        if when:
            parts.append(f"({when})")
        text = " ".join(parts) + BULLET
        url = entry.get('link', '')
        return text, url
    except Exception as e:
        debug_print(f"Error formatting entry: {e}")
        return "(Error formatting entry)" + BULLET, ""


# ─── DATA FETCH THREAD ───────────────────────────────────────────────────────
def fetch_loop(update_queue):
    """Fetch RSS feed in background thread."""
    consecutive_errors = 0
    
    while True:
        try:
            debug_print(f"Fetching RSS feed from {FEED_URL}")
            
            # Create SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Create request with headers
            request = urllib.request.Request(
                FEED_URL,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/rss+xml, application/xml, text/xml, */*'
                }
            )
            
            # Fetch with timeout
            with urllib.request.urlopen(request, timeout=30, context=ssl_context) as response:
                feed_data = response.read()
                debug_print(f"Fetched {len(feed_data)} bytes")
            
            # Parse the feed
            feed = feedparser.parse(feed_data)
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                raise Exception("No entries found in feed")
            
            debug_print(f"Successfully parsed feed with {len(feed.entries)} entries")

            # Process entries
            seen = set()
            items = []
            for e in feed.entries:
                try:
                    if hasattr(e, 'title') and e.title and e.title not in seen:
                        seen.add(e.title)
                        items.append(fmt_entry(e))
                        if len(items) >= 20:
                            break
                except Exception as entry_error:
                    debug_print(f"Error processing entry: {entry_error}")
                    continue

            debug_print(f"Processed {len(items)} unique items")

            if items:
                # Send update to GUI thread via queue
                update_queue.put(('update', items))
                debug_print(f"Sent {len(items)} items to GUI")
            else:
                update_queue.put(('update', [("(No headlines available)" + BULLET, "")]))
                
            consecutive_errors = 0
            
        except Exception as exc:
            consecutive_errors += 1
            error_msg = f"Error: {type(exc).__name__}: {str(exc)}"
            debug_print(error_msg)
            if DEBUG:
                traceback.print_exc()
            
            # Send error to GUI
            update_queue.put(('error', error_msg))

        # Sleep with exponential back-off on errors
        if consecutive_errors > 0:
            sleep_sec = min(30 * consecutive_errors, 300)  # Max 5 minutes
            debug_print(f"Sleeping {sleep_sec}s due to errors")
        else:
            sleep_sec = REFRESH_MINUTES * 60
            debug_print(f"Sleeping {sleep_sec}s until next refresh")
            
        time.sleep(sleep_sec)


# ─── GUI / TICKER ────────────────────────────────────────────────────────────
class TickerGUI:
    def __init__(self, update_queue):
        self.update_queue = update_queue
        self.headlines = deque([("(Loading NYT Politics...)" + BULLET, "")])
        self.current_index = 0
        self.paused = False
        self.text_items = []  # List of {'id': canvas_id, 'url': url, 'x': position}
        self.min_gap = 80  # Minimum gap between headlines in pixels
        
        # Setup window
        self.root = tk.Tk()
        self.setup_window()
        
        # Setup UI elements
        self.setup_ui()
        
        # Start checking for updates
        self.check_updates()
        
        # Load first item after GUI is ready
        self.root.after(100, self.load_next_item)
        
        # Start scrolling
        self.root.after(1000, self.scroll_text)

    def setup_window(self):
        """Configure the main window."""
        self.root.title("NYT Politics Ticker")
        
        # Get screen dimensions
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        # Position at bottom of screen
        y_pos = self.screen_height - TICKER_HEIGHT_PX - 40  # Account for taskbar
        self.root.geometry(f"{self.screen_width}x{TICKER_HEIGHT_PX}+0+{y_pos}")
        
        # Window styling
        self.root.overrideredirect(True)  # Remove window decorations
        self.root.configure(bg=BG_COLOR)
        
        # Keep on top (Windows compatible)
        self.root.attributes("-topmost", True)
        self.root.lift()

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
        
        # Setup font (with fallback)
        try:
            self.font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE)
        except:
            debug_print(f"Font {FONT_FAMILY} not available, using default")
            self.font = tkfont.Font(family="TkDefaultFont", size=FONT_SIZE)
        
        self.text_y = TICKER_HEIGHT_PX // 2
        
        # Pause indicator
        self.pause_id = self.canvas.create_text(
            10, 5,
            text="⏸",
            font=(FONT_FAMILY, 12),
            fill=FG_COLOR,
            anchor="nw",
            state="hidden"
        )
        
        # Close button
        close_x = self.screen_width - 20
        self.canvas.create_text(
            close_x, 5,
            text="✕",
            font=(FONT_FAMILY, 14),
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
        try:
            while True:
                try:
                    msg_type, data = self.update_queue.get_nowait()
                    
                    if msg_type == 'update':
                        debug_print(f"Received {len(data)} headlines from fetch thread")
                        self.headlines.clear()
                        self.headlines.extend(data)
                        self.current_index = 0
                        # If we have no active items, load the first one
                        if not self.text_items:
                            self.load_next_item()
                    
                    elif msg_type == 'error':
                        debug_print(f"Received error: {data}")
                        self.headlines.clear()
                        self.headlines.append((f"[Error: {data}]{BULLET}", ""))
                        
                except queue.Empty:
                    break
                    
        except Exception as e:
            debug_print(f"Error checking updates: {e}")
        
        # Schedule next check
        self.root.after(500, self.check_updates)

    def should_load_next(self):
        """Check if we should load the next headline."""
        if not self.text_items:
            return True
        
        # Get the rightmost (most recently added) item
        rightmost_item = self.text_items[-1]
        
        # Don't load another item for at least 0.5 seconds after the last one
        if time.time() - rightmost_item.get('load_time', 0) < 0.5:
            return False
        
        # We need to check if the RIGHT EDGE of the last headline has moved
        # far enough LEFT to make room for a new headline with proper spacing
        try:
            bbox = self.canvas.bbox(rightmost_item['id'])
            if bbox:
                # bbox[2] is the right edge of the text
                right_edge = bbox[2]
                # Load next when right edge is at least min_gap pixels from screen edge
                should_load = right_edge <= (self.screen_width - self.min_gap)
                if DEBUG and should_load:
                    debug_print(f"Loading next: right_edge={right_edge}, threshold={self.screen_width - self.min_gap}")
                return should_load
        except Exception:
            # Fallback: estimate based on position and text length
            current_text = self.canvas.itemcget(rightmost_item['id'], "text")
            # Better estimation: ~0.6 * font_size per character for monospace
            estimated_width = len(current_text) * (FONT_SIZE * 0.6)
            right_edge = rightmost_item['x'] + estimated_width
            should_load = right_edge <= (self.screen_width - self.min_gap)
            if DEBUG and should_load:
                debug_print(f"Loading next (est): right_edge={right_edge}, threshold={self.screen_width - self.min_gap}")
            return should_load
        
        return False

    def load_next_item(self):
        """Load the next headline as a new text item."""
        try:
            if not self.headlines:
                return
            
            # Get next item
            idx = self.current_index % len(self.headlines)
            text, url = self.headlines[idx]
            self.current_index = idx + 1
            
            debug_print(f"Loading item {idx}: {text[:50]}...")
            
            # Create new text item
            text_id = self.canvas.create_text(
                float(self.screen_width), self.text_y,
                text=text,
                font=self.font,
                fill=FG_COLOR,
                anchor="w"
            )
            
            # Add to our tracking list
            self.text_items.append({
                'id': text_id,
                'url': url,
                'x': float(self.screen_width),
                'load_time': time.time()  # Track when loaded to prevent immediate reloading
            })
            
        except Exception as e:
            debug_print(f"Error loading next item: {e}")
            traceback.print_exc()

    def scroll_text(self):
        """Scroll all text items across the screen."""
        try:
            if not self.paused:
                # Move all text items
                items_to_remove = []
                
                for item in self.text_items:
                    # Move text
                    item['x'] -= PIXELS_PER_STEP
                    self.canvas.coords(item['id'], item['x'], self.text_y)
                    
                    # Check if item has scrolled completely off screen
                    try:
                        bbox = self.canvas.bbox(item['id'])
                        if bbox and bbox[2] < 0:  # Right edge is off screen
                            items_to_remove.append(item)
                    except Exception:
                        # Fallback: estimate based on position
                        current_text = self.canvas.itemcget(item['id'], "text")
                        estimated_width = len(current_text) * 8
                        if item['x'] + estimated_width < 0:
                            items_to_remove.append(item)
                
                # Remove items that have scrolled off
                for item in items_to_remove:
                    debug_print("Removing text that scrolled off screen")
                    self.canvas.delete(item['id'])
                    self.text_items.remove(item)
                
                # Load next item if there's room
                if self.should_load_next():
                    self.load_next_item()
                        
        except Exception as e:
            debug_print(f"Error in scroll: {e}")
        
        # Schedule next scroll
        self.root.after(SCROLL_DELAY_MS, self.scroll_text)

    def toggle_pause(self):
        """Toggle pause state."""
        self.paused = not self.paused
        self.canvas.itemconfig(
            self.pause_id,
            state="normal" if self.paused else "hidden"
        )
        debug_print(f"Pause toggled: {self.paused}")

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
                except Exception:
                    # Fallback: check if click is roughly in the item's area
                    current_text = self.canvas.itemcget(item['id'], "text")
                    estimated_width = len(current_text) * 8
                    if item['x'] <= click_x <= item['x'] + estimated_width:
                        clicked_item = item
                        break
            
            if clicked_item and clicked_item['url']:
                debug_print(f"Opening URL: {clicked_item['url']}")
                webbrowser.open(clicked_item['url'])
            else:
                debug_print("No clickable item found at click position")
                
        except Exception as e:
            debug_print(f"Error in open_link: {e}")

    def maintain_topmost(self):
        """Keep window on top (less aggressive for Windows)."""
        try:
            if self.root.winfo_exists():
                self.root.lift()
                self.root.attributes("-topmost", True)
        except:
            pass
        
        # Schedule next check
        self.root.after(30000, self.maintain_topmost)  # Every 30 seconds

    def close_app(self):
        """Close the application."""
        debug_print("Closing application")
        self.root.quit()

    def run(self):
        """Start the GUI main loop."""
        debug_print("Starting GUI mainloop")
        self.root.mainloop()


# ─── BOOTSTRAP ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    debug_print("Starting NYT Politics RSS ticker")
    
    # Create queue for thread communication
    update_queue = queue.Queue()
    
    # Start fetch thread
    fetch_thread = threading.Thread(
        target=fetch_loop,
        args=(update_queue,),
        daemon=True,
        name="FetchThread"
    )
    fetch_thread.start()
    debug_print("Started fetch thread")
    
    # Create and run GUI
    try:
        gui = TickerGUI(update_queue)
        gui.run()
    except Exception as e:
        debug_print(f"GUI error: {e}")
        traceback.print_exc()
    
    debug_print("Application ended")