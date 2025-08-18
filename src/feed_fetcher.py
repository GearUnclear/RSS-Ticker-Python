"""
RSS feed fetching module with proper error handling and SSL verification.
"""
import threading
import time
import urllib.request
import urllib.error
import ssl
import queue
import random
import asyncio
import concurrent.futures
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict
from collections import deque
import re

import feedparser

try:
    from .config import (
        FEED_URLS, REFRESH_MINUTES, MAX_HEADLINES, FETCH_TIMEOUT,
        ERROR_BACKOFF_BASE, ERROR_BACKOFF_MAX, MAX_CONSECUTIVE_ERRORS, BULLET,
        ARTICLE_POOL_SIZE, DISPLAY_SUBSET_SIZE, BREAKING_NEWS_BIAS,
        NEW_ARTICLE_PRIORITY, PRIORITY_DECAY_HOURS, MIN_COOLDOWN_CYCLES,
        CATEGORY_COLORS
    )
    from .exceptions import FeedFetchError, FeedParseError
    from .logger import logger
    from .utils import format_entry, format_error_message
    from .article_memory import ArticleMemory
except ImportError:
    # Fallback for direct execution
    from config import (
        FEED_URLS, REFRESH_MINUTES, MAX_HEADLINES, FETCH_TIMEOUT,
        ERROR_BACKOFF_BASE, ERROR_BACKOFF_MAX, MAX_CONSECUTIVE_ERRORS, BULLET,
        ARTICLE_POOL_SIZE, DISPLAY_SUBSET_SIZE, BREAKING_NEWS_BIAS,
        NEW_ARTICLE_PRIORITY, PRIORITY_DECAY_HOURS, MIN_COOLDOWN_CYCLES,
        CATEGORY_COLORS
    )
    from exceptions import FeedFetchError, FeedParseError
    from logger import logger
    from utils import format_entry, format_error_message
    from article_memory import ArticleMemory


class FeedFetcher:
    """Handles RSS feed fetching with proper error handling and SSL verification."""
    
    def __init__(self, update_queue: queue.Queue):
        self.update_queue = update_queue
        self.consecutive_errors = 0
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._ssl_verify_failed = False
        
        # Enhanced article pool with direct access
        self.article_pool: List[Dict] = []
        self.display_cycle_count = 0
        self.article_pool_lock = threading.Lock()  # Thread safety for pool access
        
        # Global sliding window for cross-session continuity
        self.global_shown_articles = deque(maxlen=200)  # Track 200 recent articles globally
        
        # Long-term article memory across sessions
        self.article_memory = ArticleMemory()
        logger.info(f"Article memory initialized: {self.article_memory.get_memory_stats()}")
        
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
            
    def _parse_feed(self, feed_data: bytes) -> List[Tuple[str, str, str]]:
        """
        Parse RSS feed data into formatted entries.
        
        Args:
            feed_data: Raw feed data
            
        Returns:
            List of (display_text, url, description) tuples
            
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
            
    def _extract_category_from_url(self, feed_url: str) -> str:
        """
        Extract category from feed URL.
        
        Args:
            feed_url: RSS feed URL
            
        Returns:
            Category name
        """
        # Check for external tech feeds
        if 'techcrunch.com' in feed_url or 'wired.com' in feed_url:
            return 'Technology'
            
        # Check for external politics feeds
        if 'politico.com' in feed_url:
            return 'Politics'
            
        # Extract category from NYT URL pattern
        match = re.search(r'/rss/nyt/([^/.]+)\.xml', feed_url)
        if match:
            category = match.group(1)
            # Map URL segments to display categories
            category_map = {
                'Politics': 'Politics',
                'HomePage': 'HomePage',
                'Technology': 'Technology',
                'PersonalTech': 'Technology',
                'Business': 'Business',
                'World': 'World',
                'Science': 'Science',
                'Sports': 'Sports',
                'Arts': 'Arts',
                'Health': 'Health',
                'Opinion': 'Opinion',
                'US': 'World',
                'NYRegion': 'World',
                'Style': 'Arts',
                'Travel': 'Arts',
                'Movies': 'Arts',
                'Books': 'Arts',
                'Theater': 'Arts',
                'Music': 'Arts'
            }
            return category_map.get(category, 'Default')
        return 'Default'
    
    def _fetch_single_feed(self, feed_url: str) -> Tuple[str, List[Tuple[str, str, str, str]]]:
        """
        Fetch and parse a single feed.
        
        Args:
            feed_url: URL of the feed to fetch
            
        Returns:
            Tuple of (feed_url, list of (display_text, url, description, category) tuples)
        """
        try:
            logger.info(f"Fetching feed: {feed_url}")
            feed_data = self._fetch_feed(feed_url)
            entries = self._parse_feed(feed_data)
            
            # Add category to each entry
            category = self._extract_category_from_url(feed_url)
            categorized_entries = [(text, url, desc, category) for text, url, desc in entries]
            
            logger.info(f"Fetched {len(entries)} entries from {feed_url} (category: {category})")
            return (feed_url, categorized_entries)
        except (FeedFetchError, FeedParseError) as e:
            logger.warning(f"Failed to fetch {feed_url}: {e}")
            return (feed_url, [])
        except Exception as e:
            logger.error(f"Unexpected error fetching {feed_url}: {e}")
            return (feed_url, [])
    
    def _fetch_all_feeds(self) -> List[Tuple[str, str, str, str]]:
        """
        Fetch and process all configured feeds concurrently, removing duplicates
        across feeds and intermixing the results.
        
        Returns:
            List of (display_text, url, description, category) tuples from all feeds combined
        """
        all_entries = []
        feed_entries = {}  # Store entries by feed URL for debugging
        
        # Fetch all feeds concurrently
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(FEED_URLS))) as executor:
            # Submit all feed fetches
            future_to_url = {executor.submit(self._fetch_single_feed, url): url for url in FEED_URLS}
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_url):
                feed_url = future_to_url[future]
                try:
                    feed_url, entries = future.result(timeout=FETCH_TIMEOUT)
                    if entries:
                        feed_entries[feed_url] = entries
                        all_entries.extend([(entry, feed_url) for entry in entries])
                except Exception as e:
                    logger.error(f"Feed fetch failed for {feed_url}: {e}")
        
        fetch_time = time.time() - start_time
        logger.info(f"Fetched all feeds in {fetch_time:.2f} seconds (concurrent)")
        
        if not all_entries:
            logger.warning("No entries fetched from any feed")
            return []
        
        # Remove duplicates across feeds and intermix
        return self._deduplicate_and_intermix(all_entries)
    
    def _deduplicate_and_intermix(self, all_entries: List[Tuple[Tuple[str, str, str, str], str]]) -> List[Tuple[str, str, str, str]]:
        """
        Remove duplicate entries across feeds and intermix the remaining entries.
        
        Args:
            all_entries: List of ((display_text, url, description, category), feed_url) tuples
            
        Returns:
            List of (display_text, url, description, category) tuples with duplicates removed and entries intermixed
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
            for display_text, url, description, category in entries:
                title = extract_title(display_text)
                if title not in seen_titles:
                    seen_titles.add(title)
                    unique_entries_by_feed[feed_url].append((display_text, url, description, category))
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
                new_items = self._fetch_all_feeds()
                
                if new_items:
                    # Update article pool with new items
                    self._update_article_pool(new_items)
                    
                    # Select articles for display with breaking news bias
                    display_items = self._select_articles_for_display()
                    
                    # Send ALL articles to GUI, let GUI select dynamically
                    if display_items:
                        # Send larger batch for GUI to choose from
                        all_available = self._get_all_available_articles()
                        random.shuffle(all_available)
                        self.update_queue.put(('update', all_available[:100]))  # Send up to 100 articles
                        logger.info(f"Sent {len(all_available[:100])} available articles to GUI")
                    else:
                        self.update_queue.put(('update', [(f"(No headlines available){BULLET}", "", "", "Default")]))
                else:
                    # Send available articles from existing pool
                    all_available = self._get_all_available_articles()
                    if all_available:
                        random.shuffle(all_available)
                        self.update_queue.put(('update', all_available[:100]))
                        logger.info(f"Sent {len(all_available[:100])} pooled articles to GUI")
                    else:
                        self.update_queue.put(('update', [(f"(No headlines available){BULLET}", "", "", "Default")]))
                    
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
    
    def _calculate_priority_score(self, article: Dict, adaptive_mode: bool = False) -> float:
        """
        Calculate priority score for an article based on age and display history.
        
        Args:
            article: Article dictionary with metadata
            adaptive_mode: If True, use reduced cooldown for emergency variety
            
        Returns:
            Priority score (higher = more likely to be shown)
        """
        now = datetime.now()
        url = article.get('url', '')
        
        # Check if article was recently shown in previous sessions
        recently_shown_globally = self.article_memory.was_recently_shown(url)
        
        # New article gets maximum priority, but penalized if shown recently in another session
        if article['display_count'] == 0:
            hours_since_fetch = (now - article['first_seen']).total_seconds() / 3600
            
            if hours_since_fetch < 0.5:  # Very fresh (< 30 minutes)
                base_score = NEW_ARTICLE_PRIORITY
            elif hours_since_fetch < 2:  # Recent (< 2 hours)
                base_score = NEW_ARTICLE_PRIORITY * 0.9
            else:  # Older but unseen in this session
                base_score = NEW_ARTICLE_PRIORITY * 0.7
                
            # Light penalty for articles shown in previous sessions (new in current session)
            if recently_shown_globally:
                base_score *= 0.7  # Light penalty - 30% reduction for cross-session articles
                logger.debug(f"New article {url[:50]}... lightly penalized for recent global display")
                
            return base_score
        
        # Determine effective cooldown period (adaptive mode reduces it)
        effective_cooldown = MIN_COOLDOWN_CYCLES
        if adaptive_mode:
            effective_cooldown = max(1, MIN_COOLDOWN_CYCLES - 1)  # Reduce by 1, minimum 1
            
        # Previously shown articles have zero priority during cooldown
        cycles_since_display = self.display_cycle_count - article['last_displayed_cycle']
        if cycles_since_display < effective_cooldown:
            return 0  # Zero priority during cooldown - prevents selection
        
        # Gradual priority recovery after cooldown
        cooldown_bonus = min(cycles_since_display - effective_cooldown, 10) * 3
        base_priority = 30 + cooldown_bonus  # Higher base to compete with new articles
        
        # Age penalty for older articles
        hours_since_fetch = (now - article['first_seen']).total_seconds() / 3600
        age_penalty = min(hours_since_fetch / PRIORITY_DECAY_HOURS, 1) * 15
        
        # Heavy penalty for globally recent articles that were also shown in current session
        final_priority = max(base_priority - age_penalty, 10)  # Minimum priority of 10
        if recently_shown_globally:
            final_priority *= 0.3  # Heavy penalty - 70% reduction for repeatedly shown articles
            
        return final_priority
    
    def _update_article_pool(self, new_articles: List[Tuple[str, str, str, str]]):
        """
        Update the article pool with new articles, maintaining priority metadata.
        
        Args:
            new_articles: List of (display_text, url, description, category) tuples
        """
        now = datetime.now()
        
        # Track existing articles by URL to avoid duplicates
        existing_urls = {article['url'] for article in self.article_pool}
        
        # Add new articles to pool
        for display_text, url, description, category in new_articles:
            if url not in existing_urls:
                article = {
                    'display_text': display_text,
                    'url': url,
                    'description': description,
                    'category': category,
                    'first_seen': now,
                    'display_count': 0,
                    'last_displayed_cycle': 0
                }
                self.article_pool.append(article)
                logger.debug(f"Added new article to pool: {display_text[:50]}... (category: {category})")
        
        # Remove oldest articles if pool is too large
        if len(self.article_pool) > ARTICLE_POOL_SIZE:
            # Sort by priority (lowest first) and remove the lowest priority articles
            self.article_pool.sort(key=self._calculate_priority_score)
            removed_count = len(self.article_pool) - ARTICLE_POOL_SIZE
            self.article_pool = self.article_pool[removed_count:]
            logger.debug(f"Removed {removed_count} low-priority articles from pool")
        
        logger.info(f"Article pool updated: {len(self.article_pool)} articles total")
        
        # Log detailed pool statistics every 5 cycles
        if self.display_cycle_count % 5 == 0:
            pool_stats = self.get_pool_statistics()
            logger.info(f"Pool stats: {pool_stats}")
    
    def _select_articles_for_display(self) -> List[Tuple[str, str, str, str]]:
        """
        Select articles for display using breaking news bias and priority scoring.
        Implements adaptive cooldown when running low on variety.
        
        Returns:
            List of (display_text, url, description, category) tuples selected for display
        """
        if not self.article_pool:
            return []
        
        # First pass: try normal priority scoring
        scored_articles = []
        for article in self.article_pool:
            score = self._calculate_priority_score(article, adaptive_mode=False)
            if score > 0:  # Only include articles with positive priority
                scored_articles.append((article, score))
        
        # Check if we need emergency variety mode (adaptive cooldown)
        adaptive_mode = len(scored_articles) < 10  # Emergency threshold (increased)
        
        if adaptive_mode:
            logger.warning(f"Emergency variety mode activated: only {len(scored_articles)} articles available")
            # Recalculate with adaptive mode (reduced cooldown)
            scored_articles = []
            for article in self.article_pool:
                score = self._calculate_priority_score(article, adaptive_mode=True)
                if score > 0:
                    scored_articles.append((article, score))
            logger.info(f"Adaptive mode increased available articles to: {len(scored_articles)}")
        
        logger.debug(f"Available articles for selection: {len(scored_articles)}/{len(self.article_pool)} (adaptive={adaptive_mode})")
        
        if not scored_articles:
            logger.error("No articles available even in emergency mode - all articles exhausted")
            # Last resort: reset display counts to allow immediate re-display
            if len(self.article_pool) > 0:
                logger.warning("CRITICAL: Resetting article display counts to prevent empty ticker")
                oldest_articles = sorted(self.article_pool, 
                                        key=lambda x: x['last_displayed_cycle'])[:DISPLAY_SUBSET_SIZE]
                for article in oldest_articles:
                    article['last_displayed_cycle'] = 0  # Reset to allow immediate display
                    scored_articles.append((article, 50))  # Give medium priority
                logger.info(f"Reset {len(scored_articles)} oldest articles for emergency display")
            
            if not scored_articles:
                return []  # Truly no articles available
        
        # Sort by priority score (highest first)
        scored_articles.sort(key=lambda x: x[1], reverse=True)
        
        # Apply breaking news bias
        high_priority_slots = int(DISPLAY_SUBSET_SIZE * BREAKING_NEWS_BIAS)
        variety_slots = DISPLAY_SUBSET_SIZE - high_priority_slots
        
        selected_articles = []
        
        # Fill high priority slots with top-scored articles (priority >= 60)
        high_priority_candidates = [item for item in scored_articles if item[1] >= 60]
        if high_priority_candidates:
            # Randomize among high priority to avoid same order
            random.shuffle(high_priority_candidates)
            for article, score in high_priority_candidates[:high_priority_slots]:
                selected_articles.append(article)
        
        # Always shuffle selected articles to prevent predictable patterns
        random.shuffle(selected_articles)
        
        # Fill remaining slots with variety (weighted random selection)
        remaining_candidates = [item for item in scored_articles 
                              if item[0] not in selected_articles and item[1] > 0]
        
        if remaining_candidates and variety_slots > 0:
            # Fill up to available slots or articles, whichever is smaller
            slots_to_fill = min(variety_slots, len(remaining_candidates))
            
            if slots_to_fill > 0:
                # Weighted random selection based on scores
                weights = [max(score, 1) for _, score in remaining_candidates]
                variety_articles = random.choices(
                    [article for article, _ in remaining_candidates],
                    weights=weights,
                    k=slots_to_fill
                )
                selected_articles.extend(variety_articles)
        
        # Update display metadata for selected articles
        self.display_cycle_count += 1
        marked_urls = 0
        
        # Further shuffle final selection for maximum variety
        random.shuffle(selected_articles)
        
        for article in selected_articles:
            article['display_count'] += 1
            article['last_displayed_cycle'] = self.display_cycle_count
            
            # Mark article in global memory
            url = article.get('url', '')
            if url:
                self.article_memory.mark_article_shown(url)
                marked_urls += 1
            else:
                logger.warning(f"Article missing URL: {article.get('display_text', '')[:50]}...")
        
        # Batch save all marked articles
        self.article_memory.flush_memory()
        logger.debug(f"Flushed {marked_urls} articles to persistent memory")
        
        # Convert back to tuple format
        result = [(article['display_text'], article['url'], article['description'], article.get('category', 'Default')) 
                 for article in selected_articles]
        
        logger.info(f"Selected {len(result)} articles for display (cycle {self.display_cycle_count}, adaptive={adaptive_mode})")
        logger.debug(f"Available for selection: {len(scored_articles)}, High priority: {len([x for x in scored_articles if x[1] >= 60])}")
        
        # Log memory stats periodically
        if self.display_cycle_count % 10 == 0:
            memory_stats = self.article_memory.get_memory_stats()
            logger.info(f"Article memory stats: {memory_stats}")
        
        return result
    
    def get_pool_statistics(self) -> Dict:
        """Get detailed statistics about the article pool state."""
        if not self.article_pool:
            return {
                'total_articles': 0,
                'new_articles': 0,
                'articles_in_cooldown': 0,
                'available_articles': 0,
                'globally_recent_articles': 0
            }
        
        stats = {
            'total_articles': len(self.article_pool),
            'new_articles': 0,
            'articles_in_cooldown': 0,
            'available_articles': 0,
            'globally_recent_articles': 0
        }
        
        for article in self.article_pool:
            url = article.get('url', '')
            
            # Check if new (never displayed in current session)
            if article['display_count'] == 0:
                stats['new_articles'] += 1
            
            # Check if in session cooldown
            cycles_since = self.display_cycle_count - article['last_displayed_cycle']
            if article['display_count'] > 0 and cycles_since < MIN_COOLDOWN_CYCLES:
                stats['articles_in_cooldown'] += 1
            
            # Check if globally recent
            if self.article_memory.was_recently_shown(url):
                stats['globally_recent_articles'] += 1
            
            # Check if available (would get score > 0)
            score = self._calculate_priority_score(article, adaptive_mode=False)
            if score > 0:
                stats['available_articles'] += 1
        
        return stats
    
    def _get_all_available_articles(self) -> List[Tuple[str, str, str, str]]:
        """Get all articles from pool in displayable format."""
        with self.article_pool_lock:
            all_articles = []
            current_time = time.time()
            
            for article in self.article_pool:
                # Convert to tuple format for GUI
                article_tuple = (
                    article['display_text'],
                    article['url'],
                    article['description'], 
                    article.get('category', 'Default')
                )
                all_articles.append(article_tuple)
                
            logger.debug(f"Retrieved {len(all_articles)} articles from pool")
            return all_articles
    
    def get_article_by_criteria(self, enabled_categories: List[str], 
                               recently_shown: List[str],
                               last_shown_times: Dict[str, float]) -> Optional[Tuple[str, str, str, str]]:
        """Get best article based on GUI criteria with time-decay scoring."""
        with self.article_pool_lock:
            if not self.article_pool:
                return None
                
            current_time = time.time()
            best_score = -1
            best_article = None
            
            for article in self.article_pool:
                url = article['url']
                category = article.get('category', 'Default')
                
                # Skip disabled categories
                if category not in enabled_categories:
                    continue
                    
                # Calculate comprehensive score
                score = self._calculate_gui_article_score(
                    article, current_time, recently_shown, last_shown_times
                )
                
                if score > best_score:
                    best_score = score
                    best_article = article
                    
            if best_article:
                # Mark as shown in global tracking
                self.global_shown_articles.append(best_article['url'])
                return (
                    best_article['display_text'],
                    best_article['url'],
                    best_article['description'],
                    best_article.get('category', 'Default')
                )
                
            return None
    
    def _calculate_gui_article_score(self, article: Dict, current_time: float,
                                   recently_shown: List[str], 
                                   last_shown_times: Dict[str, float]) -> float:
        """Calculate article score for GUI selection with advanced criteria."""
        url = article['url']
        
        # Base time decay score
        last_shown = last_shown_times.get(url, 0)
        time_since_shown = current_time - last_shown if last_shown else float('inf')
        
        # Time decay: more time = higher score
        if time_since_shown == float('inf'):
            time_score = 50  # Never shown bonus
        else:
            time_score = min(time_since_shown / 60, 30)  # Max 30 points after 30 minutes
            
        # Heavy penalty for recently shown articles
        recent_penalty = -1000 if url in recently_shown else 0
        
        # Global sliding window penalty
        global_recent_penalty = -500 if url in self.global_shown_articles else 0
        
        # Article freshness bonus
        hours_since_fetch = (datetime.now() - article['first_seen']).total_seconds() / 3600
        freshness_bonus = max(10 - hours_since_fetch, 0)  # Bonus for articles < 10 hours old
        
        # Display count penalty (prefer less-shown articles)
        display_penalty = -article['display_count'] * 5
        
        total_score = time_score + recent_penalty + global_recent_penalty + freshness_bonus + display_penalty
        
        return total_score 