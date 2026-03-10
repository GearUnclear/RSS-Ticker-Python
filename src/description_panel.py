"""
Description panel module - handles the description area below the ticker.
"""
import tkinter as tk
import tkinter.font as tkfont
from typing import Optional

try:
    from .config import FONT_FAMILY, FONT_SIZE, BG_COLOR
    from .logger import logger
except ImportError:
    from config import FONT_FAMILY, FONT_SIZE, BG_COLOR
    from logger import logger


class DescriptionPanel:
    """Manages the description display area below the scrolling ticker."""

    def __init__(self, gui):
        self.gui = gui

    def toggle_descriptions(self):
        gui = self.gui
        gui.show_descriptions = not gui.show_descriptions
        gui.show_descriptions_var.set(gui.show_descriptions)
        logger.info(f"Description display toggled to: {gui.show_descriptions}")

        if gui.show_descriptions:
            self.calculate_optimal_description_height()
            gui.current_height = gui.base_height + gui.description_height
        else:
            gui.current_height = gui.base_height

        gui.update_window_geometry()
        gui.canvas.configure(height=gui.current_height)

        if not gui.show_descriptions:
            gui.canvas.delete("description")
            gui.canvas.delete("separator")
            if gui.description_text_id:
                gui.canvas.delete(gui.description_text_id)
                gui.description_text_id = None
        else:
            self.create_description_area()

        if gui.settings:
            gui.settings.show_descriptions = gui.show_descriptions

    def create_description_area(self):
        gui = self.gui
        if not gui.show_descriptions:
            return

        gui.canvas.delete("separator")

        separator_y = gui.base_height + 2
        gui.canvas.create_line(
            10, separator_y, gui.screen_width - 10, separator_y,
            fill="#333333", width=1, tags="separator"
        )

    def calculate_optimal_description_height(self):
        gui = self.gui
        if not gui.headlines:
            gui.description_height = gui.min_description_height
            return

        max_description = ""
        for item in gui.headlines:
            if len(item) >= 3:
                description = item[2]
                if len(description) > len(max_description):
                    max_description = description

        if not max_description:
            gui.description_height = gui.min_description_height
            return

        try:
            desc_font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE - 2)
            available_width = gui.screen_width - 60
            lines_needed = self.calculate_text_lines(max_description, desc_font, available_width)

            line_height = desc_font.metrics('linespace')
            line_spacing = max(2, line_height // 8)
            content_height = (lines_needed * line_height) + ((lines_needed - 1) * line_spacing)
            padding = 20
            needed_height = content_height + padding

            gui.description_height = max(
                gui.min_description_height,
                min(needed_height, gui.max_description_height)
            )

            logger.debug(f"Calculated description height: {gui.description_height}px for {lines_needed} lines")

        except Exception as e:
            logger.warning(f"Error calculating description height: {e}")
            gui.description_height = gui.min_description_height

    def calculate_text_lines(self, text, font, width):
        if not text:
            return 1

        paragraphs = text.split('\n')
        total_lines = 0

        for paragraph in paragraphs:
            if not paragraph.strip():
                total_lines += 1
                continue

            words = paragraph.split()
            if not words:
                total_lines += 1
                continue

            lines_for_paragraph = 1
            current_line_width = 0

            for word in words:
                word_width = font.measure(word + " ")
                if current_line_width > 0 and (current_line_width + word_width) > width:
                    lines_for_paragraph += 1
                    current_line_width = word_width
                else:
                    current_line_width += word_width

            total_lines += lines_for_paragraph

        return max(total_lines, 1)

    def find_current_headline(self):
        gui = self.gui
        if not gui.text_items:
            return None

        reference_x = gui.screen_width * 0.4
        current_item = None

        for item in gui.text_items:
            try:
                bbox = gui.canvas.bbox(item['id'])
                if bbox and bbox[0] <= reference_x <= bbox[2]:
                    current_item = item
                    break
            except tk.TclError:
                continue

        return current_item

    def update_description_display(self):
        gui = self.gui
        if not gui.show_descriptions:
            return

        current_item = self.find_current_headline()
        new_description = current_item.get('description', '') if current_item else ''

        current_description = ""
        if gui.description_text_id:
            try:
                current_text = gui.canvas.itemcget(gui.description_text_id, 'text')
                current_description = current_text.replace('\u2022 ', '') if current_text.startswith('\u2022 ') else current_text
            except tk.TclError:
                pass

        if new_description == current_description:
            return

        if gui.description_text_id:
            gui.canvas.delete(gui.description_text_id)
            gui.description_text_id = None

        if not new_description:
            return

        try:
            desc_x = gui.screen_width / 2
            desc_y = gui.base_height + (gui.description_height / 2) + 2

            desc_font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE - 2)
            gui.description_text_id = gui.canvas.create_text(
                desc_x, desc_y,
                text=f"\u2022 {new_description}",
                font=desc_font,
                fill="#CCCCCC",
                anchor="center",
                width=gui.screen_width - 60,
                tags="description"
            )
        except tk.TclError:
            pass
