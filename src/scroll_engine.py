"""
Scroll engine module - handles text scrolling, article selection, and supply management.
"""
import time
import random
import tkinter as tk
from collections import deque
from typing import List, Dict, Optional, Tuple

try:
    from .config import (
        PIXELS_PER_STEP, MIN_HEADLINE_GAP, FONT_SIZE, CATEGORY_COLORS,
        MAX_DISPLAY_CHARS
    )
    from .logger import logger
    from .utils import calculate_text_width
except ImportError:
    from config import (
        PIXELS_PER_STEP, MIN_HEADLINE_GAP, FONT_SIZE, CATEGORY_COLORS,
        MAX_DISPLAY_CHARS
    )
    from logger import logger
    from utils import calculate_text_width


class ScrollEngine:
    """Handles text scrolling, article selection, and article supply management."""

    def __init__(self, gui):
        """
        Args:
            gui: TickerGUI instance (used as shared state holder)
        """
        self.gui = gui

    # ------------------------------------------------------------------
    # Scrolling
    # ------------------------------------------------------------------

    def scroll_text(self):
        """Scroll all text items across the screen."""
        gui = self.gui
        if not gui._running:
            return

        try:
            if not gui.paused:
                items_to_remove = []

                for item in gui.text_items:
                    item['x'] -= PIXELS_PER_STEP
                    gui.canvas.coords(item['id'], item['x'], gui.text_y)

                    try:
                        bbox = gui.canvas.bbox(item['id'])
                        if bbox and bbox[2] < 0:
                            items_to_remove.append(item)
                    except tk.TclError:
                        items_to_remove.append(item)

                for item in items_to_remove:
                    try:
                        gui.canvas.delete(item['id'])
                    except tk.TclError:
                        pass
                    gui.text_items.remove(item)

                gui.description_panel.update_description_display()

                if self.should_load_next():
                    self.load_next_item()

        except Exception as e:
            logger.error(f"Error in scroll: {e}")

        if gui._running:
            current_delay = int(gui.base_scroll_delay / gui.speed_multiplier)
            gui.root.after(current_delay, self.scroll_text)

    def should_load_next(self) -> bool:
        """Check if we should load the next headline."""
        gui = self.gui
        if not gui.text_items:
            return True

        rightmost_item = gui.text_items[-1]

        if time.time() - rightmost_item.get('load_time', 0) < 0.5:
            return False

        try:
            bbox = gui.canvas.bbox(rightmost_item['id'])
            if bbox:
                right_edge = bbox[2]
                return right_edge <= (gui.screen_width - MIN_HEADLINE_GAP)
        except tk.TclError:
            pass

        text = rightmost_item.get('text', '')
        estimated_width = calculate_text_width(text, FONT_SIZE)
        right_edge = rightmost_item['x'] + estimated_width
        return right_edge <= (gui.screen_width - MIN_HEADLINE_GAP)

    # ------------------------------------------------------------------
    # Article loading
    # ------------------------------------------------------------------

    def load_next_item(self):
        """Load the next headline using intelligent selection."""
        gui = self.gui
        if not gui._running:
            return

        try:
            if gui.headlines:
                best_article = self._select_best_available_article()
                if best_article:
                    text, url, description, category = best_article

                    current_time = time.time()
                    gui.sliding_window_shown.append(url)
                    gui.last_article_time[url] = current_time

                    self._check_article_supply()

                    text_color = CATEGORY_COLORS.get(category, CATEGORY_COLORS['Default'])
                else:
                    self._request_fresh_batch("no suitable articles", priority='high')
                    return
            else:
                self._request_fresh_batch("no articles available", priority='critical')
                return

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

            # Truncate overly long titles
            if len(display_text) > MAX_DISPLAY_CHARS:
                display_text = display_text[:MAX_DISPLAY_CHARS - 1] + '\u2026'

            logger.debug(f"Loading item: {text[:50]}... (category: {category}, color: {text_color})")

            text_id = gui.canvas.create_text(
                float(gui.screen_width), gui.text_y,
                text=display_text,
                font=gui.font,
                fill=text_color,
                anchor="w"
            )

            gui.text_items.append({
                'id': text_id,
                'url': url,
                'text': display_text,
                'description': description,
                'category': category,
                'x': float(gui.screen_width),
                'load_time': time.time()
            })

        except Exception as e:
            logger.error(f"Error loading next item: {e}")

    # ------------------------------------------------------------------
    # Article selection (4-tier system)
    # ------------------------------------------------------------------

    def _select_best_available_article(self):
        gui = self.gui
        if not gui.headlines:
            return None

        current_time = time.time()
        dynamic_window_size = self._get_dynamic_sliding_window_size()
        recent_urls = set(list(gui.sliding_window_shown)[-dynamic_window_size:])

        tier1_candidates = []
        tier2_candidates = []
        tier3_candidates = []
        tier4_candidates = []

        for item in gui.headlines:
            if len(item) >= 4:
                text, url, description, category = item
            else:
                text, url, description = item
                category = 'Default'

            if category not in gui.enabled_categories:
                continue

            last_shown = gui.last_article_time.get(url, 0)
            time_since_shown = current_time - last_shown
            in_recent_window = url in recent_urls

            time_score = min(time_since_shown / 300, 10)
            novelty_bonus = 20 if last_shown == 0 else 0
            base_score = time_score + novelty_bonus

            if last_shown == 0:
                tier1_candidates.append((base_score, item))
            elif not in_recent_window:
                tier2_candidates.append((base_score, item))
            elif time_since_shown >= 120:
                tier3_candidates.append((base_score, item))

            tier4_candidates.append((base_score, item))

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
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_article = candidates[0][1]

            if tier_used >= 3:
                logger.debug(f"Article selection using Tier {tier_used} (window size: {dynamic_window_size})")

            return best_article

        return None

    def _apply_smart_balancing(self, filtered_headlines, category_counts):
        gui = self.gui
        if not gui.all_headlines:
            return filtered_headlines

        category_expansion = {
            'Politics': ['HomePage', 'World'],
            'Technology': ['Business'],
            'HomePage': ['Politics', 'World'],
            'World': ['Politics', 'HomePage'],
        }

        expanded_headlines = list(filtered_headlines)
        added_count = 0

        for enabled_category in gui.enabled_categories:
            current_count = category_counts.get(enabled_category, 0)

            if current_count < 5:
                related_categories = category_expansion.get(enabled_category, [])

                for related_cat in related_categories:
                    for item in gui.all_headlines:
                        if len(item) >= 4 and item[3] == related_cat:
                            if item not in expanded_headlines:
                                expanded_headlines.append(item)
                                added_count += 1
                                if added_count >= 10:
                                    break
                    if added_count >= 10:
                        break

        if added_count > 0:
            logger.info(f"Smart balancing added {added_count} related articles for variety")

        return expanded_headlines

    def _get_dynamic_sliding_window_size(self):
        gui = self.gui
        enabled_count = len(gui.enabled_categories)
        total_articles = len(gui.headlines)

        enabled_articles = 0
        for item in gui.headlines:
            if len(item) >= 4:
                text, url, description, category = item
            else:
                text, url, description = item
                category = 'Default'
            if category in gui.enabled_categories:
                enabled_articles += 1

        if enabled_count == 1 and enabled_articles < 50:
            return min(25, max(8, enabled_articles // 2))
        elif enabled_count <= 2:
            return min(35, enabled_articles // 2)
        else:
            return min(50, enabled_articles)

    # ------------------------------------------------------------------
    # Supply monitoring
    # ------------------------------------------------------------------

    def _check_article_supply(self):
        gui = self.gui
        if not gui.headlines:
            return

        current_time = time.time()
        dynamic_window_size = self._get_dynamic_sliding_window_size()
        recent_urls = set(list(gui.sliding_window_shown)[-dynamic_window_size:])

        tier_counts = {
            'tier1': 0, 'tier2': 0, 'tier3': 0, 'tier4': 0
        }
        category_counts = {}

        for item in gui.headlines:
            if len(item) >= 4:
                text, url, description, category = item
            else:
                text, url, description = item
                category = 'Default'

            if category not in gui.enabled_categories:
                continue

            if category not in category_counts:
                category_counts[category] = {'tier1': 0, 'tier2': 0, 'tier3': 0, 'tier4': 0}

            last_shown = gui.last_article_time.get(url, 0)
            time_since_shown = current_time - last_shown
            in_recent_window = url in recent_urls

            tier_counts['tier4'] += 1
            category_counts[category]['tier4'] += 1

            if last_shown == 0:
                tier_counts['tier1'] += 1
                category_counts[category]['tier1'] += 1
            elif not in_recent_window:
                tier_counts['tier2'] += 1
                category_counts[category]['tier2'] += 1
            elif time_since_shown >= 120:
                tier_counts['tier3'] += 1
                category_counts[category]['tier3'] += 1

        self._evaluate_refresh_need(tier_counts, category_counts)

    def _evaluate_refresh_need(self, tier_counts: dict, category_counts: dict):
        gui = self.gui
        enabled_count = len(gui.enabled_categories)

        thresholds = {
            'tier1_critical': max(2, enabled_count),
            'tier2_low': max(4, enabled_count * 2),
            'tier3_low': max(6, enabled_count * 3),
            'tier4_emergency': max(1, enabled_count)
        }

        if tier_counts['tier1'] < thresholds['tier1_critical']:
            self._request_fresh_batch(
                f"Tier 1 depletion: {tier_counts['tier1']} fresh articles",
                priority='critical'
            )
            return

        for category, counts in category_counts.items():
            if counts['tier1'] == 0 and counts['tier2'] <= 1:
                self._request_fresh_batch(
                    f"Category {category} nearly depleted: {counts['tier1']} fresh, {counts['tier2']} available",
                    priority='high'
                )
                return

        if tier_counts['tier2'] < thresholds['tier2_low']:
            self._request_fresh_batch(
                f"Tier 2 low: {tier_counts['tier2']} outside-window articles",
                priority='high'
            )
            return

        if tier_counts['tier3'] < thresholds['tier3_low']:
            self._request_fresh_batch(
                f"Tier 3 low: {tier_counts['tier3']} past-cooldown articles",
                priority='normal'
            )
            return

        if tier_counts['tier1'] == 0 and tier_counts['tier2'] == 0 and tier_counts['tier3'] == 0:
            if tier_counts['tier4'] < thresholds['tier4_emergency']:
                self._request_fresh_batch(
                    f"EMERGENCY: Only {tier_counts['tier4']} articles remaining",
                    priority='critical'
                )
            else:
                self._request_fresh_batch(
                    "Only Tier 4 (emergency) articles available",
                    priority='high'
                )
            return

        total_quality = tier_counts['tier1'] + tier_counts['tier2'] + tier_counts['tier3']
        if total_quality > 15:
            logger.debug(f"Article supply healthy: T1:{tier_counts['tier1']} T2:{tier_counts['tier2']} T3:{tier_counts['tier3']}")

    def _request_fresh_batch(self, reason: str, priority: str = 'normal'):
        gui = self.gui
        logger.info(f"Requesting fresh article batch: {reason} (priority: {priority})")

        if gui.fetcher:
            enabled_cats = list(gui.enabled_categories) if hasattr(gui, 'enabled_categories') else []
            gui.fetcher.request_refresh(
                priority=priority,
                reason=reason,
                categories=enabled_cats
            )
        else:
            logger.warning("No fetcher reference available for refresh request")
