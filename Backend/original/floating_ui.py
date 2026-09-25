"""Compact, desktop-integrated VoiceOS overlay.

This is the active user interface used by ``ui_engine_final``. It keeps the
original VoiceAssistant contract but moves it to a small borderless bar that
expands only while VoiceOS is listening or working.
"""

from __future__ import annotations

import math
import re
import threading
import time
from typing import Any, Dict, Optional
import tkinter as tk


class VoiceOSUI:
    """A compact floating VoiceOS interface with listening/task states."""

    IDLE_SIZE = (390, 70)
    ACTIVE_SIZE = (520, 220)
    CONFIRM_SIZE = (620, 360)
    TOP_MARGIN = 18
    KEY_COLOR = "#000001"
    PANEL = "#181b24"
    PANEL_LIGHT = "#222631"
    HEADER = "#20242e"
    BORDER = "#737b8d"
    TEXT = "#f4f6fb"
    MUTED = "#c3c9d4"
    BLUE = "#1a73e8"
    PURPLE = "#8ab4f8"
    GREEN = "#81c995"
    RED = "#f28b82"

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.theme = config.get("theme", "dark")
        self.background_color = self.PANEL
        self.text_color = config.get("text_color", self.TEXT)
        self.accent_color = config.get("accent_color", self.BLUE)
        self.assistant = None
        self.current_mode = "compact"
        self.is_compact = True
        self.is_expanded = False
        self.ui_state = "idle"
        self.status_card_hidden = True
        self._level = 0.0
        self._phase = 0.0
        self._status_message = "Ready when you are"
        self._status_kind = "info"
        self._pending_command: Optional[str] = None
        self._drag_origin: Optional[tuple[int, int]] = None
        self._collapse_job = None
        self._resize_job = None

        self.root = tk.Tk()
        self.root.title(config.get("window_title", "VoiceOS"))
        self.root.configure(bg=self.KEY_COLOR)
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        try:
            self.root.wm_attributes("-transparentcolor", self.KEY_COLOR)
        except tk.TclError:
            pass
        self.root.bind("<Escape>", lambda _event: self.root.destroy())
        self.root.bind("<Return>", lambda _event: self._on_run_command())

        self.canvas = tk.Canvas(self.root, bg=self.KEY_COLOR, highlightthickness=0,
                                bd=0, takefocus=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<ButtonPress-3>", self._start_drag)
        self.canvas.bind("<B3-Motion>", self._drag)

        # Retained public widgets keep integration with the existing main/test
        # code, but they live inside the expanded overlay rather than a window.
        self.command_entry = tk.Entry(self.root, bd=0, relief=tk.FLAT,
                                      bg=self.PANEL_LIGHT, fg=self.TEXT,
                                      insertbackground=self.TEXT,
                                      font=("Segoe UI", 10))
        self.run_button = tk.Button(self.root, text="Run", command=self._on_run_command,
                                    bd=0, bg=self.BLUE, fg="#ffffff",
                                    activebackground="#4285f4", font=("Segoe UI", 9, "bold"),
                                    cursor="hand2", relief=tk.FLAT)
        self.mic_button = tk.Button(self.root, text="Mic", command=self._on_mic_command,
                                    bd=0, bg=self.HEADER, fg=self.TEXT,
                                    activebackground=self.BORDER, font=("Segoe UI", 9),
                                    cursor="hand2", relief=tk.FLAT)
        self._entry_window = self.canvas.create_window(206, 191, window=self.command_entry,
                                                        width=278, height=34,
                                                        state="hidden")
        self._run_window = self.canvas.create_window(378, 191, window=self.run_button,
                                                      width=58, height=34, state="hidden")
        self._mic_window = self.canvas.create_window(447, 191, window=self.mic_button,
                                                      width=64, height=34, state="hidden")

        # Compatibility status objects used by current feedback integrations.
        self.status_card = tk.Frame(self.root, bg=self.PANEL)
        self.status_text = tk.Label(self.status_card, text="", bg=self.PANEL, fg=self.TEXT)
        self.transcript = tk.Text(self.root, height=1, state=tk.DISABLED)
        self._position_window(*self.IDLE_SIZE)
        self._draw()
        self.root.after(33, self._tick)

    def _position_window(self, width: int, height: int):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(16, (screen_width - width) // 2)
        y = self.TOP_MARGIN
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.canvas.config(width=width, height=height)

    def _animate_to_size(self, width: int, height: int):
        """Ease the overlay between its compact and active dimensions."""
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self.root.update_idletasks()
        start_width = max(1, self.root.winfo_width())
        start_height = max(1, self.root.winfo_height())
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        def step(frame: int):
            progress = frame / 8
            eased = 1 - (1 - progress) ** 3
            current_width = round(start_width + (width - start_width) * eased)
            current_height = round(start_height + (height - start_height) * eased)
            x = max(16, (screen_width - current_width) // 2)
            y = self.TOP_MARGIN
            self.root.geometry(f"{current_width}x{current_height}+{x}+{y}")
            self.canvas.config(width=current_width, height=current_height)
            if frame < 8:
                self._resize_job = self.root.after(18, lambda: step(frame + 1))
            else:
                self._resize_job = None

        step(1)

    @staticmethod
    def _rounded(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int,
                 radius: int, **kwargs):
        points = [x1 + radius, y1, x2 - radius, y1, x2, y1,
                  x2, y1 + radius, x2, y2 - radius, x2, y2,
                  x2 - radius, y2, x1 + radius, y2, x1, y2,
                  x1, y2 - radius, x1, y1 + radius, x1, y1]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _draw(self):
        self.canvas.delete("ui")
        width, height = ((self.CONFIRM_SIZE if self.ui_state == "confirm" else self.ACTIVE_SIZE)
                         if self.ui_state != "idle" else self.IDLE_SIZE)
        self._draw_liquid_glass(width, height)
        if self.ui_state == "idle":
            self._draw_idle(width)
        else:
            self._draw_active(width, height)

    def _draw_liquid_glass(self, width: int, height: int):
        """Render a smoked liquid-glass capsule with specular and color rims."""
        self._rounded(self.canvas, 7, 10, width - 1, height - 1, 26,
                      fill="#07090e", outline="", tags="ui")
        self._rounded(self.canvas, 4, 4, width - 5, height - 7, 25,
                      fill="#171a22", outline="#82899a", width=1, tags="ui")
        self._rounded(self.canvas, 6, 5, width - 7, height - 9, 23,
                      fill="#20232c", outline="#343a48", width=1, tags="ui")
        self._rounded(self.canvas, 9, 7, width - 10, height - 12, 21,
                      fill=self.PANEL, outline="#282d38", width=1, tags="ui")

        # Broad, low-contrast reflection on the smoked surface, capped by a
        # directional hairline like the reference engine's specular highlight.
        shimmer = (math.sin(self._phase * 0.28) + 1) / 2
        shimmer_x = 28 + int((width - 100) * shimmer)
        self._rounded(self.canvas, shimmer_x, 8, shimmer_x + 94, 11, 2,
                      fill="#414858", outline="", tags="ui")
        self._draw_glass_hairline(width)
        self._draw_accent_edge(width, height)

    def _draw_accent_edge(self, width: int, height: int):
        self._draw_spectral_rim(width, height - 8, width - 56, 2)

    def _draw_glass_hairline(self, width: int):
        stops = ("#f5f8ff", "#a8b8d8", "#66728a", "#b8c5df", "#f5f8ff")
        left, right = 26, width - 40
        for index in range(len(stops) - 1):
            x1 = round(left + (right - left) * index / (len(stops) - 1))
            x2 = round(left + (right - left) * (index + 1) / (len(stops) - 1))
            self.canvas.create_line(x1, 6, x2, 6,
                                    fill=self._mix_color(stops[index], stops[index + 1], 0.5),
                                    width=1, tags="ui")

    def _draw_spectral_rim(self, width: int, y: int, span: int, line_width: int):
        colors = ("#36a5ff", "#54d9ff", "#7987ff", "#bd68ff", "#f07bdc")
        left, right = (width - span) // 2, (width + span) // 2
        segment = (right - left) / (len(colors) - 1)
        for index, color in enumerate(colors[:-1]):
            x1 = round(left + index * segment)
            x2 = round(left + (index + 1) * segment)
            end = colors[index + 1]
            self.canvas.create_line(x1, y, x2, y,
                                    fill=self._dim_color(color), width=line_width + 4,
                                    capstyle=tk.ROUND, tags="ui")
            self.canvas.create_line(x1, y, x2, y,
                                    fill=self._mix_color(color, end, 0.5),
                                    width=line_width, capstyle=tk.ROUND, tags="ui")

    @staticmethod
    def _mix_color(start: str, end: str, amount: float) -> str:
        channels = [
            round(int(start[offset:offset + 2], 16) * (1 - amount)
                  + int(end[offset:offset + 2], 16) * amount)
            for offset in (1, 3, 5)
        ]
        return "#{:02x}{:02x}{:02x}".format(*channels)

    def _draw_idle(self, width: int):
        glow = self.BLUE if self._status_kind != "error" else self.RED
        self.canvas.create_oval(17, 19, 49, 51, fill="#172b49", outline="", tags="ui")
        self.canvas.create_oval(20, 22, 46, 48, fill=glow, outline="", tags="ui")
        self.canvas.create_oval(28, 30, 38, 40, fill="#f8fbff", outline="", tags="ui")
        self.canvas.create_text(62, 27, text="VoiceOS", anchor="w", fill="#f7f8fc",
                                font=("Segoe UI", 12, "bold"), tags="ui")
        self.canvas.create_text(62, 46, text=self._status_message, anchor="w",
                                fill="#c7cddd", font=("Segoe UI", 10), tags="ui")
        self._draw_siri_wave(width - 48, 35, 27, mini=True)

    def _draw_active(self, width: int, height: int):
        if self.ui_state == "confirm":
            self._draw_confirmation(width, height)
            return

        color = self.GREEN if self.ui_state == "complete" else self.RED if self.ui_state == "error" else self.BLUE
        label = {"listening": "Listening", "thinking": "Thinking",
                 "executing": "Working", "complete": "Completed",
                 "error": "Couldn’t complete", "confirm": "Confirm action"}.get(self.ui_state, "VoiceOS")
        self.canvas.create_oval(22, 14, 40, 32, fill=color, outline="", tags="ui")
        self.canvas.create_text(50, 22, text=label, anchor="w", fill=self.TEXT,
                                font=("Segoe UI", 12, "bold"), tags="ui")
        self.canvas.create_text(50, 42, text=self._status_message, anchor="w", fill=self.MUTED,
                                width=420, font=("Segoe UI", 10), tags="ui")
        self.canvas.create_text(width - 27, 27, text="×", fill="#aeb7c9",
                                font=("Segoe UI", 15), tags="ui")
        if self.ui_state in {"listening", "thinking", "executing"}:
            self._draw_waveform(color, width)
        else:
            self._draw_result(color, width)
        self.canvas.itemconfigure(self._entry_window, state="normal")
        self.canvas.itemconfigure(self._run_window, state="normal")
        self.canvas.itemconfigure(self._mic_window, state="normal")

    def _draw_waveform(self, color: str, width: int):
        self._draw_siri_wave(width // 2, 112, width - 110)
        detail = "Speak naturally — I’ll stop after a short pause." if self.ui_state == "listening" else "I’m processing your request."
        self.canvas.create_text(width // 2, 163, text=detail, fill="#d2d7e0",
                                font=("Segoe UI", 10), tags="ui")

    def _draw_siri_wave(self, center_x: int, center_y: int, span: int, mini: bool = False):
        """Draw a luminous, fluid waveform with a moving spectral gradient."""
        count = 19 if mini else 55
        amplitude_scale = 4 if mini else 24
        points = []
        for index in range(count):
            position = index / (count - 1)
            distance = abs(position * 2 - 1)
            envelope = 0.1 + 0.9 * (1 - distance) ** 1.2
            wave = (0.62 * math.sin(position * 15 - self._phase * 1.7)
                    + 0.24 * math.sin(position * 25 + self._phase * 1.1)
                    + 0.14 * math.sin(position * 37 - self._phase * 0.8))
            amplitude = wave * envelope * amplitude_scale
            x = center_x - span / 2 + position * span
            y = center_y - amplitude
            points.append((x, y))

        coordinates = [coordinate for point in points for coordinate in point]
        self.canvas.create_line(*coordinates, fill="#38275e",
                                width=9 if mini else 19, capstyle=tk.ROUND,
                                joinstyle=tk.ROUND, smooth=True, splinesteps=16,
                                tags="ui")
        self.canvas.create_line(*coordinates, fill="#2769b8",
                                width=5 if mini else 9, capstyle=tk.ROUND,
                                joinstyle=tk.ROUND, smooth=True, splinesteps=16,
                                tags="ui")

        chunk_size = 4
        for start in range(0, len(points) - 1, chunk_size - 1):
            segment = points[start:min(start + chunk_size, len(points))]
            segment_coordinates = [coordinate for point in segment for coordinate in point]
            position = (start + (len(segment) - 1) / 2) / (len(points) - 1)
            color = self._spectrum_color(position)
            self.canvas.create_line(*segment_coordinates,
                                    fill=self._dim_color(color),
                                    width=8 if mini else 14,
                                    capstyle=tk.ROUND, joinstyle=tk.ROUND,
                                    smooth=True, splinesteps=12, tags="ui")
            self.canvas.create_line(*segment_coordinates, fill=color,
                                    width=2 if mini else 4,
                                    capstyle=tk.ROUND, joinstyle=tk.ROUND,
                                    smooth=True, splinesteps=12, tags="ui")
        if not mini:
            self.canvas.create_line(*coordinates, fill="#bceaff", width=1,
                                    capstyle=tk.ROUND, joinstyle=tk.ROUND,
                                    smooth=True, splinesteps=16, tags="ui")

    @staticmethod
    def _dim_color(color: str) -> str:
        rgb = tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
        return "#{:02x}{:02x}{:02x}".format(*(channel // 3 for channel in rgb))

    def _spectrum_color(self, position: float) -> str:
        """Interpolate a moving blue-cyan-violet-pink listening spectrum."""
        colors = ("#28a5ff", "#36e0ee", "#617dff", "#a45cff", "#f45bd7", "#28a5ff")
        point = (position * (len(colors) - 1) + self._phase * 0.045) % (len(colors) - 1)
        index = int(point)
        blend = point - index
        start = colors[index]
        end = colors[min(index + 1, len(colors) - 1)]
        channels = [
            round(int(start[offset:offset + 2], 16) * (1 - blend)
                  + int(end[offset:offset + 2], 16) * blend)
            for offset in (1, 3, 5)
        ]
        return "#{:02x}{:02x}{:02x}".format(*channels)

    def _draw_result(self, color: str, width: int):
        self._rounded(self.canvas, 24, 76, width - 24, 167, 16,
                      fill=self.PANEL_LIGHT, outline=self.HEADER, tags="ui")
        mark = "✓" if self.ui_state == "complete" else "!"
        self.canvas.create_text(51, 122, text=mark, fill=color,
                                font=("Segoe UI", 25, "bold"), tags="ui")
        self.canvas.create_text(77, 105, text="VoiceOS", anchor="w", fill=self.TEXT,
                                font=("Segoe UI", 10, "bold"), tags="ui")
        self.canvas.create_text(77, 130, text=self._status_message, anchor="w", fill=self.MUTED,
                                width=330, font=("Segoe UI", 9), tags="ui")

    def _draw_confirmation(self, width: int, height: int):
        self.canvas.itemconfigure(self._entry_window, state="hidden")
        self.canvas.itemconfigure(self._run_window, state="hidden")
        self.canvas.itemconfigure(self._mic_window, state="hidden")

        # A luminous blue surround frames a Gmail-inspired draft preview.
        card_left, card_top = 34, 34
        card_right, card_bottom = width - 34, height - 32
        self._rounded(self.canvas, card_left - 7, card_top - 4,
                      card_right + 7, card_bottom + 8, 26,
                      fill="#123d91", outline="#1761d5", width=2, tags="ui")
        self._rounded(self.canvas, card_left, card_top,
                      card_right, card_bottom, 22,
                      fill="#202124", outline="#667085", width=1, tags="ui")

        header_bottom = card_top + 44
        self._rounded(self.canvas, card_left + 1, card_top + 1,
                      card_right - 1, header_bottom + 12, 21,
                      fill="#3c4043", outline="", tags="ui")
        self.canvas.create_rectangle(card_left + 1, header_bottom - 3,
                                     card_right - 1, header_bottom + 12,
                                     fill="#3c4043", outline="", tags="ui")
        self.canvas.create_oval(card_left + 18, card_top + 13,
                                card_left + 35, card_top + 30,
                                fill="#f7f7f7", outline="", tags="ui")
        self.canvas.create_text(card_left + 26.5, card_top + 21,
                                text="M", fill="#d93025",
                                font=("Segoe UI", 9, "bold"), tags="ui")
        self.canvas.create_text(card_left + 48, card_top + 22,
                                text="New Message", anchor="w", fill="#f1f3f4",
                                font=("Segoe UI", 11, "bold"), tags="ui")
        self.canvas.create_text(card_right - 20, card_top + 22, text="×",
                                fill="#bdc1c6", font=("Segoe UI", 16),
                                tags="ui")

        command = self._pending_command or ""
        recipient = self._extract_recipient(command)
        subject = self._extract_subject(command)

        to_y = header_bottom + 25
        subject_y = to_y + 40
        body_top = subject_y + 27
        footer_y = card_bottom - 39
        self.canvas.create_text(card_left + 20, to_y, text="To",
                                anchor="w", fill="#bdc1c6",
                                font=("Segoe UI", 10), tags="ui")
        chip_left = card_left + 57
        chip_right = min(card_right - 20, chip_left + max(116, min(300, len(recipient) * 7 + 24)))
        self._rounded(self.canvas, chip_left, to_y - 15, chip_right, to_y + 13, 14,
                      fill="#303b4a", outline="", tags="ui")
        self.canvas.create_text(chip_left + 12, to_y - 1,
                                text=recipient, anchor="w", fill="#d7e3f4",
                                width=chip_right - chip_left - 20,
                                font=("Segoe UI", 9), tags="ui")
        self.canvas.create_line(card_left + 18, to_y + 22, card_right - 18, to_y + 22,
                                fill="#3c4043", tags="ui")

        self.canvas.create_text(card_left + 20, subject_y, text=subject,
                                anchor="w", fill="#e8eaed",
                                width=card_right - card_left - 40,
                                font=("Segoe UI", 10), tags="ui")
        self.canvas.create_line(card_left + 18, subject_y + 17,
                                card_right - 18, subject_y + 17,
                                fill="#3c4043", tags="ui")

        body = self._extract_body(command) or ""
        self.canvas.create_text(card_left + 20, body_top, text=body,
                                anchor="nw", fill="#e8eaed",
                                width=card_right - card_left - 40,
                                font=("Segoe UI", 10), tags="ui")
        self.canvas.create_text(card_left + 20, footer_y - 12,
                                text="This opens a draft in your mail app. Review and send it there.",
                                anchor="w", fill="#9aa0a6",
                                font=("Segoe UI", 8), tags="ui")
        self.canvas.create_text(width - 205, footer_y + 8, text="Cancel",
                                fill="#bdc1c6", font=("Segoe UI", 9, "bold"),
                                tags=("ui", "cancel"))
        button_left, button_right = width - 168, width - 47
        self._rounded(self.canvas, button_left, footer_y - 10,
                      button_right, footer_y + 27, 13,
                      fill="#1a73e8", outline="", tags=("ui", "approve"))
        self.canvas.create_text((button_left + button_right) / 2, footer_y + 8,
                                text="Open draft", fill="#ffffff",
                                font=("Segoe UI", 9, "bold"), tags=("ui", "approve"))

    @staticmethod
    def _extract_recipient(command: str) -> str:
        match = re.search(r"\bto\s+(.+?)(?:\s+(?:about|subject|with|saying)\b|$)", command, re.I)
        if not match:
            return "Recipient to be resolved"
        recipient = match.group(1).strip()
        return recipient if "@" in recipient else recipient.title()

    @staticmethod
    def _extract_subject(command: str) -> str:
        match = re.search(r"\b(?:about|subject)\s+(.+?)(?:\s+(?:saying|with body)\b|$)", command, re.I)
        return match.group(1).strip() if match else "Draft requested by voice"

    @staticmethod
    def _extract_body(command: str) -> str:
        match = re.search(r"\b(?:saying|with body)\s+(.+)$", command, re.I)
        return match.group(1).strip() if match else ""

    def _tick(self):
        self._phase += 0.24
        self._draw()
        self.root.after(33, self._tick)

    def _set_state(self, state: str, message: str, kind: str = "info"):
        if self._collapse_job:
            self.root.after_cancel(self._collapse_job)
            self._collapse_job = None
        self.ui_state = state
        self._status_message = message
        self._status_kind = kind
        self.status_text.config(text=message)
        self.status_card_hidden = state == "idle"
        self.current_mode = "compact" if state == "idle" else "expanded"
        self.is_compact = state == "idle"
        self.is_expanded = not self.is_compact
        self._animate_to_size(*(self.IDLE_SIZE if state == "idle" else
                                self.CONFIRM_SIZE if state == "confirm" else self.ACTIVE_SIZE))
        self._draw()

    def _collapse(self):
        self._set_state("idle", "Ready when you are")

    def _schedule_collapse(self, milliseconds: int = 2600):
        self._collapse_job = self.root.after(milliseconds, self._collapse)

    def _on_canvas_click(self, event):
        if self.ui_state == "confirm" and event.x >= self.root.winfo_width() - 68 and event.y < 62:
            self.root.destroy()
            return
        if event.x > self.root.winfo_width() - 52 and event.y < 56:
            self.root.destroy()
            return
        if self.ui_state == "confirm":
            height = self.root.winfo_height()
            width = self.root.winfo_width()
            if width - 168 <= event.x <= width - 47 and height - 81 <= event.y <= height - 44:
                self._approve_pending()
            elif width - 255 <= event.x < width - 176 and height - 81 <= event.y <= height - 44:
                self._cancel_pending()
            return
        if self.ui_state == "idle":
            self._on_mic_command()

    def _start_drag(self, event):
        self._drag_origin = (event.x_root, event.y_root)

    def _drag(self, event):
        if not self._drag_origin:
            return
        dx = event.x_root - self._drag_origin[0]
        dy = event.y_root - self._drag_origin[1]
        x, y = self.root.winfo_x() + dx, self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
        self._drag_origin = (event.x_root, event.y_root)

    def _set_level_threadsafe(self, level: float):
        self.root.after(0, lambda: setattr(self, "_level", level))

    def set_mode(self, mode: str):
        if mode not in {"compact", "expanded"}:
            return
        if mode == "compact":
            self._collapse()
        elif self.ui_state == "idle":
            self._set_state("thinking", "Ready for a command")

    def set_mode_compact(self):
        self.set_mode("compact")

    def set_mode_expanded(self):
        self.set_mode("expanded")

    def toggle_mode(self) -> str:
        self.set_mode("expanded" if self.is_compact else "compact")
        return self.current_mode

    toggle_expanded_mode = toggle_mode

    def show_status_card(self, message: str, card_type: str = "success"):
        state = "complete" if card_type == "success" else "error" if card_type == "error" else "thinking"
        self._set_state(state, message, card_type)
        self._schedule_collapse(2500 if state in {"complete", "error"} else 3500)

    def animate_ui_element(self, element: str, effect: str = "fade", duration: float = 0.5):
        self._draw()

    def trigger_animation(self, event: str, duration: float = 1.0):
        self.animate_ui_element(event, "fade", duration)

    def trigger_voice_feedback(self):
        self._set_state("listening", "Speak naturally — I’m listening")

    def attach_assistant(self, assistant):
        self.assistant = assistant
        return self

    def _on_run_command(self):
        text = self.command_entry.get().strip()
        if text:
            self.command_entry.delete(0, tk.END)
            self.handle_command(text)

    def _on_mic_command(self):
        if self.ui_state == "listening":
            return
        self._set_state("listening", "Speak naturally — I’m listening")
        threading.Thread(target=self._mic_worker, daemon=True).start()

    def _mic_worker(self):
        try:
            from voice_io import listen
            text = listen(on_level=self._set_level_threadsafe)
        except Exception as exc:
            print(f"mic error: {exc}")
            text = None
        if text:
            self.root.after(0, lambda: self.handle_command(text))
        else:
            self.root.after(0, lambda: self.show_status_card("No speech was captured. Try again when ready.", "error"))

    @staticmethod
    def _needs_confirmation(text: str) -> bool:
        lowered = text.lower()
        return any(term in lowered for term in ("send email", "draft email", "compose email", "email to"))

    def handle_command(self, text: str):
        if not text or not text.strip():
            return None
        command = text.strip()
        self._log_transcript(f"You: {command}")
        if self._needs_confirmation(command):
            self._pending_command = command
            self._set_state("confirm", "Review the action before continuing")
            return None
        self._execute_command(command)
        return None

    def _approve_pending(self):
        command, self._pending_command = self._pending_command, None
        if command:
            self._execute_command(command)

    def _cancel_pending(self):
        self._pending_command = None
        self.show_status_card("Action cancelled", "error")

    def _execute_command(self, text: str):
        if self.assistant is None:
            self.show_status_card("AI layer not attached — launch with ui_engine_final.py", "error")
            return
        self._set_state("thinking", "Understanding your request")
        threading.Thread(target=self._command_worker, args=(text,), daemon=True).start()

    def _command_worker(self, text: str):
        try:
            self.root.after(0, lambda: self._set_state("executing", "Executing your request"))
            result = self.assistant.handle(text)
            ok = bool(result.get("ok"))
            detail = " ".join(str(result.get("detail", "")).split())[:160]
        except Exception as exc:
            ok, detail = False, f"Error: {exc}"
        self.root.after(0, lambda: self._show_command_result(ok, detail))

    def _show_command_result(self, ok: bool, detail: str):
        self._log_transcript(("Done: " if ok else "Failed: ") + (detail or "No detail returned"))
        self.show_status_card(detail or ("Done" if ok else "Failed"), "success" if ok else "error")

    def _log_transcript(self, line: str):
        self.transcript.config(state=tk.NORMAL)
        self.transcript.insert(tk.END, line + "\n")
        self.transcript.see(tk.END)
        self.transcript.config(state=tk.DISABLED)


class RPY:
    """Compatibility placeholder retained for old test scripts."""
    pass
