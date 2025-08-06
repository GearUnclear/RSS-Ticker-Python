"""
Article memory system for tracking displayed articles across sessions.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Set, Optional
from pathlib import Path

try:
    from .logger import logger
except ImportError:
    from logger import logger


class ArticleMemory:
    """Manages persistent memory of displayed articles across sessions."""
    
    def __init__(self, memory_file: str = "article_memory.json", retention_hours: int = 48):
        """
        Initialize article memory system.
        
        Args:
            memory_file: Path to JSON file for storing memory
            retention_hours: How many hours to remember articles (default 48h)
        """
        self.memory_file = Path(memory_file)
        self.retention_hours = retention_hours
        self.memory: Dict[str, datetime] = {}
        self._dirty = False  # Track if memory needs saving
        self._last_cleanup = datetime.now(timezone.utc)
        self._load_memory()
        
    def _load_memory(self):
        """Load article memory from JSON file."""
        if not self.memory_file.exists():
            logger.debug("No existing article memory file found")
            return
            
        try:
            with open(self.memory_file, 'r') as f:
                data = json.load(f)
                
            # Convert ISO timestamps back to datetime objects (ensure UTC)
            self.memory = {}
            for url, timestamp_str in data.items():
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    # Ensure timezone awareness - assume UTC if naive
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    # Convert to UTC if not already
                    elif timestamp.tzinfo != timezone.utc:
                        timestamp = timestamp.astimezone(timezone.utc)
                    self.memory[url] = timestamp
                except ValueError:
                    logger.warning(f"Invalid timestamp for article {url}: {timestamp_str}")
                    
            logger.info(f"Loaded article memory: {len(self.memory)} articles")
            self._cleanup_old_entries()
            
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load article memory: {e}")
            self.memory = {}
            
    def _save_memory(self):
        """Save article memory to JSON file."""
        try:
            # Convert datetime objects to ISO strings for JSON serialization
            data = {url: timestamp.isoformat() for url, timestamp in self.memory.items()}
            
            with open(self.memory_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.debug(f"Saved article memory: {len(self.memory)} articles")
            
        except IOError as e:
            logger.error(f"Failed to save article memory: {e}")
            
    def _cleanup_old_entries(self):
        """Remove articles older than retention period."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.retention_hours)
        old_urls = [url for url, timestamp in self.memory.items() if timestamp < cutoff_time]
        
        for url in old_urls:
            del self.memory[url]
            
        if old_urls:
            logger.info(f"Cleaned up {len(old_urls)} old articles from memory")
            self._save_memory()
            
    def mark_article_shown(self, url: str):
        """Mark an article as having been shown."""
        if not url:
            logger.warning("Attempted to mark article with empty URL")
            return
            
        self.memory[url] = datetime.now(timezone.utc)
        self._dirty = True
        logger.debug(f"Marked article as shown: {url}")
    
    def flush_memory(self):
        """Save memory to disk if there are pending changes."""
        if self._dirty:
            self._save_memory()
            self._dirty = False
            
    def was_recently_shown(self, url: str) -> bool:
        """Check if an article was recently shown."""
        if not url or url not in self.memory:
            return False
            
        # Periodic cleanup (every 10 minutes) instead of every check
        now = datetime.now(timezone.utc)
        if (now - self._last_cleanup).total_seconds() > 600:  # 10 minutes
            self._cleanup_old_entries()
            self._last_cleanup = now
        
        # Article is considered recently shown if it's still in memory
        return url in self.memory
        
    def get_recently_shown_urls(self) -> Set[str]:
        """Get set of all recently shown article URLs."""
        self._cleanup_old_entries()
        return set(self.memory.keys())
        
    def get_memory_stats(self) -> Dict:
        """Get statistics about the memory system."""
        self._cleanup_old_entries()
        
        if not self.memory:
            return {
                'total_articles': 0,
                'oldest_article': None,
                'newest_article': None,
                'retention_hours': self.retention_hours
            }
            
        timestamps = list(self.memory.values())
        return {
            'total_articles': len(self.memory),
            'oldest_article': min(timestamps).isoformat(),
            'newest_article': max(timestamps).isoformat(),
            'retention_hours': self.retention_hours
        }
        
    def clear_memory(self):
        """Clear all article memory (for testing/reset)."""
        self.memory = {}
        if self.memory_file.exists():
            try:
                self.memory_file.unlink()
                logger.info("Cleared article memory")
            except OSError as e:
                logger.error(f"Failed to delete memory file: {e}")
    
    def reset_if_stale(self, hours_threshold: int = 72):
        """Reset memory if all articles are older than threshold."""
        if not self.memory:
            return False
            
        newest_time = max(self.memory.values())
        hours_since = (datetime.now(timezone.utc) - newest_time).total_seconds() / 3600
        
        if hours_since > hours_threshold:
            logger.warning(f"All articles older than {hours_threshold}h, resetting memory")
            self.clear_memory()
            return True
        return False