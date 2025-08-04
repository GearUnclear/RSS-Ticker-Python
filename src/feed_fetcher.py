"""
RSS feed fetching module with proper error handling and SSL verification.
"""
import threading
import time
import urllib.request
import urllib.error
import ssl
import queue
from typing import List, Tuple, Optional

import feedparser

try:
    from .config import (
        FEED_URLS, REFRESH_MINUTES, MAX_HEADLINES, FETCH_TIMEOUT,
        ERROR_BACKOFF_BASE, ERROR_BACKOFF_MAX, MAX_CONSECUTIVE_ERRORS, BULLET
    )
    from .exceptions import FeedFetchError, FeedParseError
    from .logger import logger
    from .utils import format_entry, format_error_message
except ImportError:
    # Fallback for direct execution
    from config import (
        FEED_URLS, REFRESH_MINUTES, MAX_HEADLINES, FETCH_TIMEOUT,
        ERROR_BACKOFF_BASE, ERROR_BACKOFF_MAX, MAX_CONSECUTIVE_ERRORS, BULLET
    )
    from exceptions import FeedFetchError, FeedParseError
    from logger import logger
    from utils import format_entry, format_error_message


class FeedFetcher:
    """Handles RSS feed fetching with proper error handling and SSL verification."""
    
    def __init__(self, update_queue: queue.Queue):
        self.update_queue = update_queue
        self.consecutive_errors = 0
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ssl_verify_failed = False
        
    def start(self):
        """Start the feed fetching thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Feed fetcher already running")
            return
            
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._fetch_loop,
            daemon=True,
            name="FeedFetcher"
        )
        self._thread.start()
        logger.info("Feed fetcher thread started")
        
    def stop(self):
        """Stop the feed fetching thread gracefully."""
        logger.info("Stopping feed fetcher...")
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                logger.warning("Feed fetcher thread did not stop gracefully")
                
    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create a secure SSL context."""
        context = ssl.create_default_context()
        
        if self._ssl_verify_failed:
            # If SSL verification failed before, disable it with a warning
            logger.warning("SSL verification disabled due to previous failures. This is less secure.")
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        else:
            # Enable hostname checking and certificate verification
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            
        return context
        
    def _fetch_feed(self, feed_url: str) -> bytes:
        """
        Fetch the RSS feed data from a specific URL.
        
        Args:
            feed_url: The URL to fetch the feed from
        
        Returns:
            Raw feed data as bytes
            
        Raises:
            FeedFetchError: If fetching fails
        """
        try:
            logger.debug(f"Fetching RSS feed from {feed_url}")
            
            # Create request with proper headers
            request = urllib.request.Request(
                feed_url,
                headers={
                    'User-Agent': 'NYT RSS Ticker/1.0',
                    'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Cache-Control': 'no-cache'
                }
            )
            
            # Use secure SSL context
            ssl_context = self._create_ssl_context()
            
            # Fetch with timeout
            with urllib.request.urlopen(
                request, 
                timeout=FETCH_TIMEOUT, 
                context=ssl_context
            ) as response:
                feed_data = response.read()
                logger.debug(f"Fetched {len(feed_data)} bytes")
                return feed_data
                
        except urllib.error.URLError as e:
            # Check if it's an SSL certificate error
            if "certificate verify failed" in str(e).lower() and not self._ssl_verify_failed:
                logger.warning("SSL certificate verification failed. Retrying without verification...")
                self._ssl_verify_failed = True
                # Retry the fetch
                return self._fetch_feed(feed_url)
            raise FeedFetchError(f"Network error: {str(e)}")
        except Exception as e:
            raise FeedFetchError(f"Unexpected error fetching feed: {str(e)}")
            
    def _parse_feed(self, feed_data: bytes) -> List[Tuple[str, str]]:
        """
        Parse RSS feed data into formatted entries.
        
        Args:
            feed_data: Raw feed data
            
        Returns:
            List of (display_text, url) tuples
            
        Raises:
            FeedParseError: If parsing fails
        """
        try:
            feed = feedparser.parse(feed_data)
            
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                raise FeedParseError("No entries found in feed")
                
            logger.info(f"Successfully parsed feed with {len(feed.entries)} entries")
            
            # Process entries with deduplication
            seen_titles = set()
            items = []
            
            for entry in feed.entries:
                try:
                    title = entry.get('title', '').strip()
                    if title and title not in seen_titles:
                        seen_titles.add(title)
                        items.append(format_entry(entry))
                        
                        if len(items) >= MAX_HEADLINES:
                            break
                            
                except Exception as e:
                    logger.warning(f"Error processing entry: {e}")
                    continue
                    
            logger.info(f"Processed {len(items)} unique items")
            return items
            
        except FeedParseError:
            raise
        except Exception as e:
            raise FeedParseError(f"Failed to parse feed: {str(e)}")
            
    def _fetch_all_feeds(self) -> List[Tuple[str, str]]:
        """
        Fetch and process all configured feeds, removing duplicates across feeds
        and intermixing the results.
        
        Returns:
            List of (display_text, url) tuples from all feeds combined
        """
        all_entries = []
        feed_entries = {}  # Store entries by feed URL for debugging
        
        # Fetch each feed
        for feed_url in FEED_URLS:
            try:
                logger.info(f"Fetching feed: {feed_url}")
                feed_data = self._fetch_feed(feed_url)
                entries = self._parse_feed(feed_data)
                feed_entries[feed_url] = entries
                all_entries.extend([(entry, feed_url) for entry in entries])
                logger.info(f"Fetched {len(entries)} entries from {feed_url}")
            except (FeedFetchError, FeedParseError) as e:
                logger.warning(f"Failed to fetch {feed_url}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error fetching {feed_url}: {e}")
                continue
        
        if not all_entries:
            logger.warning("No entries fetched from any feed")
            return []
        
        # Remove duplicates across feeds and intermix
        return self._deduplicate_and_intermix(all_entries)
    
    def _deduplicate_and_intermix(self, all_entries: List[Tuple[Tuple[str, str], str]]) -> List[Tuple[str, str]]:
        """
        Remove duplicate entries across feeds and intermix the remaining entries.
        
        Args:
            all_entries: List of ((display_text, url), feed_url) tuples
            
        Returns:
            List of (display_text, url) tuples with duplicates removed and entries intermixed
        """
        # Group entries by feed
        feed_groups = {}
        for (entry, feed_url) in all_entries:
            if feed_url not in feed_groups:
                feed_groups[feed_url] = []
            feed_groups[feed_url].append(entry)
        
        # Extract titles for duplicate detection
        def extract_title(entry_text: str) -> str:
            """Extract just the title part from the formatted entry text."""
            # Title is everything before the first "—"
            title_part = entry_text.split(' — ')[0].strip()
            return title_part.lower()
        
        # Find duplicates across feeds
        seen_titles = set()
        unique_entries_by_feed = {}
        
        for feed_url, entries in feed_groups.items():
            unique_entries_by_feed[feed_url] = []
            for display_text, url in entries:
                title = extract_title(display_text)
                if title not in seen_titles:
                    seen_titles.add(title)
                    unique_entries_by_feed[feed_url].append((display_text, url))
                else:
                    logger.debug(f"Removing duplicate: {title}")
        
        # Intermix entries from different feeds
        result = []
        feed_urls = list(unique_entries_by_feed.keys())
        feed_indices = {url: 0 for url in feed_urls}
        
        # Round-robin through feeds until all entries are added
        while any(feed_indices[url] < len(unique_entries_by_feed[url]) for url in feed_urls):
            for feed_url in feed_urls:
                if feed_indices[feed_url] < len(unique_entries_by_feed[feed_url]):
                    result.append(unique_entries_by_feed[feed_url][feed_indices[feed_url]])
                    feed_indices[feed_url] += 1
                    
                    # Limit total entries
                    if len(result) >= MAX_HEADLINES:
                        break
            
            if len(result) >= MAX_HEADLINES:
                break
        
        logger.info(f"Final result: {len(result)} unique entries after deduplication and intermixing")
        return result
            
    def _fetch_loop(self):
        """Main fetch loop that runs in background thread."""
        logger.info("Feed fetch loop started")
        
        # Fetch immediately on startup
        initial_fetch = True
        
        while not self._stop_event.is_set():
            try:
                # Fetch and parse all feeds
                items = self._fetch_all_feeds()
                
                if items:
                    self.update_queue.put(('update', items))
                    logger.info(f"Sent {len(items)} items to GUI")
                else:
                    self.update_queue.put(('update', [(f"(No headlines available){BULLET}", "")]))
                    
                # Reset error counter on success
                self.consecutive_errors = 0
                
            except (FeedFetchError, FeedParseError) as e:
                self._handle_error(e)
                
            except Exception as e:
                logger.exception("Unexpected error in fetch loop")
                self._handle_error(e)
                
            # Calculate sleep time
            if initial_fetch:
                # After initial fetch, wait the normal interval
                initial_fetch = False
                sleep_time = REFRESH_MINUTES * 60
            else:
                sleep_time = self._calculate_sleep_time()
            
            # Sleep with periodic checks for stop event
            elapsed = 0
            while elapsed < sleep_time and not self._stop_event.is_set():
                time.sleep(1)
                elapsed += 1
                
        logger.info("Feed fetch loop stopped")
        
    def _handle_error(self, error: Exception):
        """Handle errors during fetching."""
        self.consecutive_errors += 1
        error_msg = format_error_message(error)
        logger.error(f"Fetch error ({self.consecutive_errors}): {error_msg}")
        
        # Send error to GUI
        self.update_queue.put(('error', error_msg))
        
        # Check if we've exceeded max errors
        if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            logger.critical(f"Exceeded maximum consecutive errors ({MAX_CONSECUTIVE_ERRORS})")
            self.update_queue.put(('critical_error', "Too many errors. Please check your connection."))
            
    def _calculate_sleep_time(self) -> int:
        """Calculate sleep time with exponential backoff on errors."""
        if self.consecutive_errors > 0:
            # Exponential backoff with maximum
            sleep_sec = min(
                ERROR_BACKOFF_BASE * self.consecutive_errors,
                ERROR_BACKOFF_MAX
            )
            logger.info(f"Sleeping {sleep_sec}s due to {self.consecutive_errors} errors")
        else:
            sleep_sec = REFRESH_MINUTES * 60
            logger.debug(f"Sleeping {sleep_sec}s until next refresh")
            
        return sleep_sec 