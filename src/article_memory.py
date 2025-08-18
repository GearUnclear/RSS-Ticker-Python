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
    
    def __init__(self, memory_file: str = "article_memory.json", retention_hours: int = 168):
        """
        Initialize article memory system.
        
        Args:
            memory_file: Path to JSON file for storing memory
            retention_hours: How many hours to remember articles (default 168h = 7 days)
        """
        self.memory_file = Path(memory_file)
        self.retention_hours = retention_hours
        # Enhanced memory structure: {url: {'last_shown': datetime, 'frequency': int, 'sessions': [datetime, ...]}}
        self.memory: Dict[str, Dict] = {}
        self._dirty = False  # Track if memory needs saving
        self._last_cleanup = datetime.now(timezone.utc)
        self._session_start = datetime.now(timezone.utc)  # Track current session
        self._load_memory()
        
    def _load_memory(self):
        """Load article memory from JSON file with migration support."""
        if not self.memory_file.exists():
            logger.debug("No existing article memory file found")
            return
            
        try:
            with open(self.memory_file, 'r') as f:
                data = json.load(f)
                
            self.memory = {}
            
            # Handle both old format (url: timestamp) and new format (url: {last_shown, frequency, sessions})
            for url, entry in data.items():
                try:
                    if isinstance(entry, str):
                        # Old format: migrate to new structure
                        timestamp = datetime.fromisoformat(entry)
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=timezone.utc)
                        elif timestamp.tzinfo != timezone.utc:
                            timestamp = timestamp.astimezone(timezone.utc)
                            
                        self.memory[url] = {
                            'last_shown': timestamp,
                            'frequency': 1,  # Assume shown once
                            'sessions': [timestamp]
                        }
                        logger.debug(f"Migrated old format for article: {url}")
                        
                    elif isinstance(entry, dict):
                        # New format: parse enhanced structure
                        last_shown = datetime.fromisoformat(entry['last_shown'])
                        if last_shown.tzinfo is None:
                            last_shown = last_shown.replace(tzinfo=timezone.utc)
                        elif last_shown.tzinfo != timezone.utc:
                            last_shown = last_shown.astimezone(timezone.utc)
                            
                        # Parse session timestamps
                        sessions = []
                        for session_str in entry.get('sessions', [entry['last_shown']]):
                            session_time = datetime.fromisoformat(session_str)
                            if session_time.tzinfo is None:
                                session_time = session_time.replace(tzinfo=timezone.utc)
                            elif session_time.tzinfo != timezone.utc:
                                session_time = session_time.astimezone(timezone.utc)
                            sessions.append(session_time)
                            
                        self.memory[url] = {
                            'last_shown': last_shown,
                            'frequency': entry.get('frequency', len(sessions)),
                            'sessions': sessions
                        }
                        
                except ValueError as e:
                    logger.warning(f"Invalid entry for article {url}: {e}")
                    continue
                    
            logger.info(f"Loaded article memory: {len(self.memory)} articles")
            self._cleanup_old_entries()
            
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load article memory: {e}")
            self.memory = {}
            
    def _save_memory(self):
        """Save article memory to JSON file."""
        try:
            # Convert enhanced structure to JSON serializable format
            data = {}
            for url, entry in self.memory.items():
                data[url] = {
                    'last_shown': entry['last_shown'].isoformat(),
                    'frequency': entry['frequency'],
                    'sessions': [session.isoformat() for session in entry['sessions']]
                }
            
            with open(self.memory_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.debug(f"Saved article memory: {len(self.memory)} articles")
            
        except IOError as e:
            logger.error(f"Failed to save article memory: {e}")
            
    def _cleanup_old_entries(self):
        """Remove articles older than retention period."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.retention_hours)
        old_urls = [url for url, entry in self.memory.items() if entry['last_shown'] < cutoff_time]
        
        for url in old_urls:
            del self.memory[url]
            
        if old_urls:
            logger.info(f"Cleaned up {len(old_urls)} old articles from memory")
            self._save_memory()
            
    def mark_article_shown(self, url: str):
        """Mark an article as having been shown with frequency tracking."""
        if not url:
            logger.warning("Attempted to mark article with empty URL")
            return
            
        now = datetime.now(timezone.utc)
        
        if url in self.memory:
            # Update existing entry
            entry = self.memory[url]
            entry['last_shown'] = now
            entry['frequency'] += 1
            
            # Add to sessions if this is a new session (6+ hours gap)
            if not entry['sessions'] or (now - entry['sessions'][-1]).total_seconds() > 21600:  # 6 hours
                entry['sessions'].append(now)
                logger.debug(f"New session detected for article: {url}")
        else:
            # Create new entry
            self.memory[url] = {
                'last_shown': now,
                'frequency': 1,
                'sessions': [now]
            }
            
        self._dirty = True
        logger.debug(f"Marked article as shown: {url} (frequency: {self.memory[url]['frequency']})")
    
    def flush_memory(self):
        """Save memory to disk if there are pending changes."""
        if self._dirty:
            self._save_memory()
            self._dirty = False
            
    def was_recently_shown(self, url: str) -> bool:
        """Check if an article was recently shown (backward compatibility)."""
        if not url or url not in self.memory:
            return False
            
        # Periodic cleanup (every 10 minutes) instead of every check
        now = datetime.now(timezone.utc)
        if (now - self._last_cleanup).total_seconds() > 600:  # 10 minutes
            self._cleanup_old_entries()
            self._last_cleanup = now
        
        # Article is considered recently shown if it's still in memory
        return url in self.memory
    
    def get_article_penalty_factor(self, url: str) -> float:
        """
        Calculate penalty factor for cross-session articles with graduated penalties.
        
        Returns:
            Penalty factor between 0.0 and 1.0 (1.0 = no penalty, 0.2 = 80% penalty)
        """
        if not url or url not in self.memory:
            return 1.0  # No penalty for new articles
            
        entry = self.memory[url]
        now = datetime.now(timezone.utc)
        hours_since_shown = (now - entry['last_shown']).total_seconds() / 3600
        
        # Graduated penalties based on recency
        if hours_since_shown < 6:  # Very recent (< 6 hours)
            recency_factor = 0.2  # 80% penalty
        elif hours_since_shown < 24:  # Recent (6-24 hours)
            recency_factor = 0.5  # 50% penalty
        elif hours_since_shown < 72:  # Medium (1-3 days)
            recency_factor = 0.7  # 30% penalty
        else:  # Old (3+ days)
            recency_factor = 0.8  # 20% penalty
            
        # Frequency penalty (more showings = more penalty)
        frequency = entry['frequency']
        if frequency == 1:
            frequency_factor = 1.0  # No additional penalty
        elif frequency == 2:
            frequency_factor = 0.8  # 20% additional penalty
        elif frequency <= 5:
            frequency_factor = 0.6  # 40% additional penalty
        else:
            frequency_factor = 0.4  # 60% additional penalty for frequently shown
            
        # Session gap bonus (not shown for multiple sessions gets bonus)
        session_count = len(entry['sessions'])
        latest_session = entry['sessions'][-1] if entry['sessions'] else entry['last_shown']
        sessions_since_last = max(1, int((now - latest_session).total_seconds() / 21600))  # 6-hour sessions
        
        if sessions_since_last >= 3:  # 3+ sessions ago
            session_bonus = 1.2  # 20% bonus
        elif sessions_since_last >= 2:  # 2 sessions ago
            session_bonus = 1.1  # 10% bonus
        else:
            session_bonus = 1.0  # No bonus
            
        # Combine all factors
        total_factor = recency_factor * frequency_factor * session_bonus
        
        # Clamp between 0.1 and 1.2 (never completely eliminate, allow slight bonus)
        return max(0.1, min(1.2, total_factor))
        
    def get_recently_shown_urls(self) -> Set[str]:
        """Get set of all recently shown article URLs."""
        self._cleanup_old_entries()
        return set(self.memory.keys())
        
    def get_memory_stats(self) -> Dict:
        """Get enhanced statistics about the memory system with age buckets and frequency."""
        self._cleanup_old_entries()
        
        if not self.memory:
            return {
                'total_articles': 0,
                'oldest_article': None,
                'newest_article': None,
                'retention_hours': self.retention_hours,
                'age_buckets': {'<6h': 0, '6-24h': 0, '1-3d': 0, '3-7d': 0},
                'frequency_distribution': {'1x': 0, '2x': 0, '3-5x': 0, '6+x': 0},
                'avg_frequency': 0,
                'total_sessions': 0
            }
            
        now = datetime.now(timezone.utc)
        timestamps = [entry['last_shown'] for entry in self.memory.values()]
        
        # Age bucket analysis
        age_buckets = {'<6h': 0, '6-24h': 0, '1-3d': 0, '3-7d': 0}
        for entry in self.memory.values():
            hours_ago = (now - entry['last_shown']).total_seconds() / 3600
            if hours_ago < 6:
                age_buckets['<6h'] += 1
            elif hours_ago < 24:
                age_buckets['6-24h'] += 1
            elif hours_ago < 72:
                age_buckets['1-3d'] += 1
            else:
                age_buckets['3-7d'] += 1
                
        # Frequency distribution
        frequency_dist = {'1x': 0, '2x': 0, '3-5x': 0, '6+x': 0}
        total_frequency = 0
        total_sessions = 0
        
        for entry in self.memory.values():
            freq = entry['frequency']
            total_frequency += freq
            total_sessions += len(entry['sessions'])
            
            if freq == 1:
                frequency_dist['1x'] += 1
            elif freq == 2:
                frequency_dist['2x'] += 1
            elif freq <= 5:
                frequency_dist['3-5x'] += 1
            else:
                frequency_dist['6+x'] += 1
        
        return {
            'total_articles': len(self.memory),
            'oldest_article': min(timestamps).isoformat(),
            'newest_article': max(timestamps).isoformat(),
            'retention_hours': self.retention_hours,
            'age_buckets': age_buckets,
            'frequency_distribution': frequency_dist,
            'avg_frequency': round(total_frequency / len(self.memory), 2),
            'total_sessions': total_sessions
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
    
    def reset_if_stale(self, hours_threshold: int = 168):
        """Reset memory if all articles are older than threshold (default 7 days)."""
        if not self.memory:
            return False
            
        newest_time = max(entry['last_shown'] for entry in self.memory.values())
        hours_since = (datetime.now(timezone.utc) - newest_time).total_seconds() / 3600
        
        if hours_since > hours_threshold:
            logger.warning(f"All articles older than {hours_threshold}h, resetting memory")
            self.clear_memory()
            return True
        return False