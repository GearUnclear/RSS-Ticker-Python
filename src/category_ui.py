"""
Category UI module - handles category indicators, tooltips, and category filtering.
"""
import time
import tkinter as tk
from tkinter import Menu
from typing import Dict, List

try:
    from .config import (
        CATEGORY_COLORS, INDICATOR_WIDTH, INDICATOR_HEIGHT,
        INDICATOR_SPACING, INDICATOR_MARGIN_X, INDICATOR_MARGIN_Y,
        INDICATOR_CORNER_RADIUS, INDICATOR_ANIMATION_MS
    )
    from .logger import logger
except ImportError:
    from config import (
        CATEGORY_COLORS, INDICATOR_WIDTH, INDICATOR_HEIGHT,
        INDICATOR_SPACING, INDICATOR_MARGIN_X, INDICATOR_MARGIN_Y,
        INDICATOR_CORNER_RADIUS, INDICATOR_ANIMATION_MS
    )
    from logger import logger


class CategoryIndicatorManager:
    """Manages Apple-style category indicator chips and category filtering."""

    def __init__(self, gui):
        self.gui = gui

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup_category_indicators(self):
        gui = self.gui
        active_categories = gui._get_active_categories()

        x = INDICATOR_MARGIN_X
        y = INDICATOR_MARGIN_Y

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
            chip_x = x + i * (INDICATOR_WIDTH + INDICATOR_SPACING)
            chip_y = y

            color = CATEGORY_COLORS.get(category, CATEGORY_COLORS['Default'])
            abbrev = category_abbrev.get(category, category[:3])

            is_enabled = category in gui.enabled_categories
            chip_id = self._create_indicator_chip(chip_x, chip_y, color, is_enabled, category, abbrev)

            gui.category_indicators[category] = {
                'chip_id': chip_id,
                'x': chip_x,
                'y': chip_y,
                'color': color,
                'enabled': is_enabled,
                'abbrev': abbrev
            }

    def _create_indicator_chip(self, x, y, color, enabled, category, abbrev):
        gui = self.gui
        x1, y1 = x, y
        x2, y2 = x + INDICATOR_WIDTH, y + INDICATOR_HEIGHT

        if enabled:
            bg_id = gui.canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=color, outline=color, width=1,
                tags=("category_indicator", f"indicator_{category}", f"bg_{category}")
            )
            text_color = "#000000"
        else:
            bg_id = gui.canvas.create_rectangle(
                x1, y1, x2, y2,
                fill="", outline=color, width=1,
                tags=("category_indicator", f"indicator_{category}", f"bg_{category}")
            )
            text_color = color

        text_x = x + INDICATOR_WIDTH // 2
        text_y = y + INDICATOR_HEIGHT // 2
        gui.canvas.create_text(
            text_x, text_y,
            text=abbrev,
            font=("Arial", 6, "bold"),
            fill=text_color,
            anchor="center",
            tags=("category_indicator", f"indicator_{category}", f"text_{category}")
        )

        gui.canvas.tag_bind(f"indicator_{category}", "<Button-1>",
                           lambda e, c=category: self.on_indicator_click(c))
        gui.canvas.tag_bind(f"indicator_{category}", "<Enter>",
                           lambda e, c=category: self._on_indicator_hover(c))
        gui.canvas.tag_bind(f"indicator_{category}", "<Leave>",
                           lambda e, c=category: self._on_indicator_leave(c))

        return bg_id

    # ------------------------------------------------------------------
    # Indicator visuals
    # ------------------------------------------------------------------

    def update_category_indicators(self):
        gui = self.gui
        for category, indicator_info in gui.category_indicators.items():
            is_enabled = category in gui.enabled_categories
            if indicator_info['enabled'] != is_enabled:
                indicator_info['enabled'] = is_enabled
                self._update_indicator_visual(category, is_enabled)

    def _update_indicator_visual(self, category, enabled):
        gui = self.gui
        if category not in gui.category_indicators:
            return

        info = gui.category_indicators[category]
        color = info['color']

        try:
            bg_items = gui.canvas.find_withtag(f"bg_{category}")
            text_items = gui.canvas.find_withtag(f"text_{category}")

            if not bg_items or not text_items:
                logger.warning(f"Canvas items not found for category {category}")
                return

            if enabled:
                gui.canvas.itemconfig(f"bg_{category}", fill=color, outline=color, width=1)
                gui.canvas.itemconfig(f"text_{category}", fill="#000000")
            else:
                gui.canvas.itemconfig(f"bg_{category}", fill="", outline=color, width=1)
                gui.canvas.itemconfig(f"text_{category}", fill=color)
        except tk.TclError as e:
            logger.warning(f"Error updating indicator visual for {category}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error updating indicator visual for {category}: {e}")

    # ------------------------------------------------------------------
    # Click / hover / tooltip
    # ------------------------------------------------------------------

    def on_indicator_click(self, category):
        gui = self.gui
        try:
            if category in gui.enabled_categories:
                gui.enabled_categories.discard(category)
                if category in gui.category_vars:
                    gui.category_vars[category].set(False)
            else:
                gui.enabled_categories.add(category)
                if category in gui.category_vars:
                    gui.category_vars[category].set(True)

            self.update_category_indicators()
            self.filter_current_headlines_gracefully()

            if gui.settings:
                gui.settings.enabled_categories = sorted(gui.enabled_categories)

            logger.info(f"Category {category} toggled via indicator: {'enabled' if category in gui.enabled_categories else 'disabled'}")
        except Exception as e:
            logger.error(f"Error handling indicator click for {category}: {e}")

    def _on_indicator_hover(self, category):
        gui = self.gui
        if gui.hover_states.get(category, False):
            return

        current_time = time.time()
        last_time = gui.last_hover_time.get(category, 0)
        if current_time - last_time < 0.1:
            return

        gui.hover_states[category] = True
        gui.last_hover_time[category] = current_time

        count = self._get_category_article_count(category)
        status = "enabled" if category in gui.enabled_categories else "disabled"

        gui.canvas.configure(cursor="hand2")
        self._cleanup_tooltip(category)
        self._show_tooltip(category, count, status)

        logger.debug(f"Hovering {category}: {count} articles, {status}")

    def _show_tooltip(self, category, count, status):
        gui = self.gui
        if category not in gui.category_indicators:
            return

        info = gui.category_indicators[category]
        x, y = info['x'], info['y']

        tooltip_x = x
        tooltip_y = y + INDICATOR_HEIGHT + 10

        # Build tooltip text, including feed health if available
        tooltip_text = f"{category}: {count} articles ({status})"
        if gui.fetcher:
            cat_health = gui.fetcher.get_category_health().get(category)
            if cat_health:
                last = cat_health['last_success']
                if last > 0:
                    minutes_ago = int((time.time() - last) / 60)
                    tooltip_text += f"\nUpdated: {minutes_ago}m ago ({cat_health['healthy_feeds']}/{cat_health['feeds']} feeds OK)"
                if cat_health['errors']:
                    tooltip_text += f"\nWarning: {len(cat_health['errors'])} feed(s) failing"

        text_id = gui.canvas.create_text(
            tooltip_x, tooltip_y,
            text=tooltip_text,
            font=("Arial", 8),
            fill="#000000",
            anchor="nw",
            tags=("tooltip", f"tooltip_text_{category}")
        )

        bbox = gui.canvas.bbox(text_id)
        if bbox:
            padding = 3
            x1, y1, x2, y2 = bbox
            x1 -= padding
            y1 -= padding
            x2 += padding
            y2 += padding

            canvas_width = gui.canvas.winfo_width()
            if x2 > canvas_width - 5:
                shift = x2 - (canvas_width - 5)
                x1 -= shift
                x2 -= shift
                gui.canvas.coords(text_id, x1 + padding, y1 + padding)

            bg_id = gui.canvas.create_rectangle(
                x1, y1, x2, y2,
                fill="#FFFFDD",
                outline="#888888",
                width=1,
                tags=("tooltip", f"tooltip_bg_{category}")
            )

            gui.canvas.tag_lower(bg_id, text_id)

            gui.indicator_tooltips[category] = {
                'text': text_id,
                'bg': bg_id
            }
        else:
            gui.indicator_tooltips[category] = {'text': text_id}

    def _cleanup_tooltip(self, category):
        gui = self.gui
        if category in gui.indicator_tooltips:
            tooltip_info = gui.indicator_tooltips[category]
            try:
                if isinstance(tooltip_info, dict):
                    for item_id in tooltip_info.values():
                        gui.canvas.delete(item_id)
                else:
                    gui.canvas.delete(tooltip_info)
            except tk.TclError:
                pass
            del gui.indicator_tooltips[category]

    def _on_indicator_leave(self, category):
        gui = self.gui
        gui.hover_states[category] = False
        gui.canvas.configure(cursor="")
        self._cleanup_tooltip(category)

    def _get_category_article_count(self, category):
        gui = self.gui
        if not hasattr(gui, 'all_headlines'):
            return 0
        count = 0
        for item in gui.all_headlines:
            if len(item) >= 4 and item[3] == category:
                count += 1
        return count

    # ------------------------------------------------------------------
    # Category menu
    # ------------------------------------------------------------------

    def setup_category_menu(self):
        gui = self.gui
        available_categories = gui._get_active_categories()

        for category in available_categories:
            var = tk.BooleanVar(value=category in gui.enabled_categories)
            gui.category_vars[category] = var

            count = self._get_category_article_count(category)
            enabled_indicator = "\u25cf" if category in gui.enabled_categories else "\u25cb"
            label = f"{enabled_indicator} {category} ({count} articles)"

            gui.categories_menu.add_checkbutton(
                label=label,
                variable=var,
                command=lambda c=category: self.toggle_category(c)
            )

    def toggle_category(self, category: str):
        gui = self.gui
        if gui.category_vars[category].get():
            gui.enabled_categories.add(category)
            logger.info(f"Enabled category: {category}")
        else:
            gui.enabled_categories.discard(category)
            logger.info(f"Disabled category: {category}")

        self.update_category_indicators()
        self.refresh_category_menu()
        self.filter_current_headlines_gracefully()

        if gui.settings:
            gui.settings.enabled_categories = sorted(gui.enabled_categories)

    def refresh_category_menu(self):
        gui = self.gui
        gui.categories_menu.delete(0, "end")

        available_categories = gui._get_active_categories()

        for category in available_categories:
            if category not in gui.category_vars:
                continue

            var = gui.category_vars[category]
            count = self._get_category_article_count(category)

            enabled_indicator = "\u25cf" if category in gui.enabled_categories else "\u25cb"
            label = f"{enabled_indicator} {category} ({count})"

            gui.categories_menu.add_checkbutton(
                label=label,
                variable=var,
                command=lambda c=category: self.toggle_category(c)
            )

    # ------------------------------------------------------------------
    # Graceful filtering
    # ------------------------------------------------------------------

    def filter_current_headlines_gracefully(self):
        gui = self.gui
        if not hasattr(gui, 'all_headlines'):
            return

        filtered_headlines = []
        for item in gui.all_headlines:
            if len(item) >= 4:
                category = item[3]
                if category in gui.enabled_categories:
                    filtered_headlines.append(item)
            else:
                filtered_headlines.append(item)

        if not filtered_headlines and gui.enabled_categories:
            empty_message = "No articles in selected categories \u2022 Loading fresh content..."
            empty_desc = "New articles will appear shortly. You can adjust categories anytime by right-clicking."
            filtered_headlines = [(empty_message, "", empty_desc, "Default")]
        elif not filtered_headlines:
            guidance_message = "Choose categories above \u2022 Right-click to select"
            guidance_desc = "Select news categories from the right-click menu to see articles."
            filtered_headlines = [(guidance_message, "", guidance_desc, "Default")]

        gui.headlines.clear()
        gui.headlines.extend(filtered_headlines)

        if gui.current_index >= len(gui.headlines):
            gui.current_index = 0

        self._manage_description_context()

        logger.info(f"Gracefully filtered: {len(filtered_headlines)} visible from {len(gui.all_headlines) if hasattr(gui, 'all_headlines') else 0} total")

    def _manage_description_context(self):
        gui = self.gui
        if not gui.show_descriptions or not gui.description_text_id:
            return

        current_item = gui.description_panel.find_current_headline()

        if current_item:
            current_category = current_item.get('category', 'Default')
            if current_category not in gui.enabled_categories:
                has_enabled_upcoming = any(
                    item.get('category', 'Default') in gui.enabled_categories
                    for item in gui.text_items[1:] if len(gui.text_items) > 1
                )

                if not has_enabled_upcoming:
                    try:
                        gui.canvas.delete(gui.description_text_id)
                        gui.description_text_id = None
                    except tk.TclError:
                        pass
