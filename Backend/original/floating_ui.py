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

    IDLE_SIZE = (348, 58)
    ACTIVE_SIZE = (480, 242)
    CONFIRM_SIZE = (480, 292)
    TOP_MARGIN = 18
    KEY_COLOR = "#000001"
    PANEL = "#172133"
    PANEL_LIGHT = "#202c41"
    TEXT = "#f7f9ff"
    MUTED = "#98a2b8"
    BLUE = "#75a7ff"
    PURPLE = "#b79cff"
    GREEN = "#7be0ad"
    RED = "#ff8f9f"

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.theme = config.get("theme", "dark")
        self.background_color = config.get("background_color", self.PANEL)
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
                                      bg="#26354d", fg=self.TEXT,
                                      insertbackground=self.TEXT,
                                      font=("Segoe UI", 10))
        self.run_button = tk.Button(self.root, text="Run", command=self._on_run_command,
                                    bd=0, bg="#9cc4ff", fg="#0b1020",
                                    activebackground="#a9c7ff", font=("Segoe UI", 9, "bold"))
        self.mic_button = tk.Button(self.root, text="Mic", command=self._on_mic_command,
                                    bd=0, bg="#26354d", fg=self.TEXT,
                                    activebackground="#364a6a", font=("Segoe UI", 9))
        self._entry_window = self.canvas.create_window(190, 202, window=self.command_entry,
                                                        width=250, height=30,
                                                        state="hidden")
        self._run_window = self.canvas.create_window(340, 202, window=self.run_button,
                                                      width=52, height=30, state="hidden")
        self._mic_window = self.canvas.create_window(402, 202, window=self.mic_button,
                                                      width=52, height=30, state="hidden")

        # Compatibility status objects used by current feedback integrations.
        self.status_card = tk.Frame(self.root, bg=self.PANEL)
        self.status_text = tk.Label(self.status_card, text="", bg=self.PANEL, fg=self.TEXT)
        self.transcript = tk.Text(self.root, height=1, state=tk.DISABLED)
        self._position_window(*self.IDLE_SIZE)
        self._draw()
        self.root.after(45, self._tick)

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
        """Layered, slowly moving highlights that give the overlay a glass feel."""
        radius = 22
        self._rounded(self.canvas, 7, 9, width - 1, height - 1, radius + 2,
                      fill="#080d17", outline="", tags="ui")
        self._rounded(self.canvas, 4, 4, width - 5, height - 5, radius,
                      fill=self.PANEL, outline="#71809b", width=1, tags="ui")

        drift = (math.sin(self._phase * 0.43) + 1) / 2
        shimmer_x = -90 + int((width + 120) * drift)
        glow_color = self.BLUE if self.ui_state in {"idle", "listening"} else self.PURPLE
        # Kept within the panel bounds so the glints appear submerged in glass.
        self.canvas.create_oval(max(13, shimmer_x - 82), 9,
                                min(width - 13, shimmer_x + 70), min(height - 8, 76),
                                fill="#24395b" if glow_color == self.BLUE else "#3a3157",
                                outline="", tags="ui")
        self.canvas.create_oval(max(13, width - shimmer_x // 2 - 44), max(8, height - 54),
                                min(width - 13, width - shimmer_x // 2 + 92), height - 8,
                                fill="#26334c", outline="", tags="ui")
        self._rounded(self.canvas, 10, 8, width - 12, min(35, height - 10), 15,
                      fill="#2c3b55", outline="#92a5c8", width=1, tags="ui")
        wave_y = 42 + int(math.sin(self._phase * 0.7) * 4)
        self.canvas.create_arc(18, wave_y - 24, width - 18, wave_y + 34,
                               start=188, extent=164, style=tk.ARC,
                               outline="#91aee0", width=1, tags="ui")
        self.canvas.create_line(24, 12, width - 42, 12, fill="#d5e4ff", width=1, tags="ui")

    def _draw_idle(self, width: int):
        glow = self.BLUE if self._status_kind != "error" else self.RED
        self.canvas.create_oval(18, 18, 40, 40, fill=glow, outline="", tags="ui")
        self.canvas.create_oval(24, 24, 34, 34, fill="#f8fbff", outline="", tags="ui")
        self.canvas.create_text(52, 23, text="VOICEOS", anchor="w", fill=self.TEXT,
                                font=("Segoe UI", 10, "bold"), tags="ui")
        self.canvas.create_text(52, 38, text=self._status_message, anchor="w",
                                fill=self.MUTED, font=("Segoe UI", 8), tags="ui")
        self.canvas.create_text(width - 24, 29, text="⌁", fill=self.BLUE,
                                font=("Segoe UI Symbol", 20), tags="ui")

    def _draw_active(self, width: int, height: int):
        color = self.BLUE if self.ui_state == "listening" else self.PURPLE
        label = {"listening": "Listening", "thinking": "Thinking",
                 "executing": "Working", "complete": "Completed",
                 "error": "Couldn’t complete", "confirm": "Confirm action"}.get(self.ui_state, "VoiceOS")
        self.canvas.create_oval(20, 18, 36, 34, fill=color, outline="", tags="ui")
        self.canvas.create_text(46, 21, text=label, anchor="w", fill=self.TEXT,
                                font=("Segoe UI", 11, "bold"), tags="ui")
        self.canvas.create_text(46, 39, text=self._status_message, anchor="w", fill=self.MUTED,
                                width=390, font=("Segoe UI", 9), tags="ui")
        self.canvas.create_text(width - 26, 27, text="×", fill=self.MUTED,
                                font=("Segoe UI", 15), tags="ui")
        if self.ui_state in {"listening", "thinking", "executing"}:
            self._draw_waveform(color, width)
        else:
            self._draw_result(color, width)
        if self.ui_state == "confirm":
            self._draw_confirmation(width)
        else:
            self.canvas.itemconfigure(self._entry_window, state="normal")
            self.canvas.itemconfigure(self._run_window, state="normal")
            self.canvas.itemconfigure(self._mic_window, state="normal")

    def _draw_waveform(self, color: str, width: int):
        middle = 113
        self.canvas.create_line(36, middle, width - 36, middle, fill="#273045", width=1, tags="ui")
        for index, x in enumerate(range(42, width - 36, 10)):
            pulse = abs(math.sin(self._phase + index * 0.58))
            amplitude = 8 + pulse * (12 + self._level * 48)
            self.canvas.create_line(x, middle - amplitude, x, middle + amplitude,
                                    fill=color, width=4, capstyle=tk.ROUND, tags="ui")
        detail = "Speak naturally — I’ll stop after a short pause." if self.ui_state == "listening" else "I’m processing your request."
        self.canvas.create_text(width // 2, 160, text=detail, fill=self.MUTED,
                                font=("Segoe UI", 9), tags="ui")

    def _draw_result(self, color: str, width: int):
        self._rounded(self.canvas, 24, 76, width - 24, 167, 16,
                      fill=self.PANEL_LIGHT, outline="#30394d", tags="ui")
        mark = "✓" if self.ui_state == "complete" else "!"
        self.canvas.create_text(51, 122, text=mark, fill=color,
                                font=("Segoe UI", 25, "bold"), tags="ui")
        self.canvas.create_text(77, 105, text="VoiceOS", anchor="w", fill=self.TEXT,
                                font=("Segoe UI", 10, "bold"), tags="ui")
        self.canvas.create_text(77, 130, text=self._status_message, anchor="w", fill=self.MUTED,
                                width=330, font=("Segoe UI", 9), tags="ui")

    def _draw_confirmation(self, width: int):
        self.canvas.itemconfigure(self._entry_window, state="hidden")
        self.canvas.itemconfigure(self._run_window, state="hidden")
        self.canvas.itemconfigure(self._mic_window, state="hidden")
        self._rounded(self.canvas, 24, 76, width - 24, 244, 16,
                      fill=self.PANEL_LIGHT, outline="#46516a", tags="ui")
        command = self._pending_command or ""
        recipient = self._extract_recipient(command)
        subject = self._extract_subject(command)
        self.canvas.create_text(44, 101, text="Email draft", anchor="w", fill=self.TEXT,
                                font=("Segoe UI", 10, "bold"), tags="ui")
        self.canvas.create_text(44, 129, text=f"To: {recipient}", anchor="w", fill=self.MUTED,
                                font=("Segoe UI", 9), tags="ui")
        self.canvas.create_text(44, 151, text=f"Subject: {subject}", anchor="w", fill=self.MUTED,
                                font=("Segoe UI", 9), tags="ui")
        self.canvas.create_text(44, 181, text="Review this draft action before VoiceOS continues.", anchor="w",
                                fill=self.MUTED, font=("Segoe UI", 8), tags="ui")
        self.canvas.create_text(335, 216, text="Cancel", fill=self.MUTED,
                                font=("Segoe UI", 9, "bold"), tags=("ui", "cancel"))
        self._rounded(self.canvas, 371, 196, 440, 232, 11, fill=self.BLUE, outline="", tags=("ui", "approve"))
        self.canvas.create_text(405, 214, text="Approve", fill="#09101f",
                                font=("Segoe UI", 9, "bold"), tags=("ui", "approve"))

    @staticmethod
    def _extract_recipient(command: str) -> str:
        match = re.search(r"\bto\s+(.+?)(?:\s+(?:about|subject|with|saying)\b|$)", command, re.I)
        return match.group(1).strip().title() if match else "Recipient to be resolved"

    @staticmethod
    def _extract_subject(command: str) -> str:
        match = re.search(r"\b(?:about|subject)\s+(.+)$", command, re.I)
        return match.group(1).strip().capitalize() if match else "Draft requested by voice"

    def _tick(self):
        self._phase += 0.24
        # Glass highlights drift even while VoiceOS is idle; active states add
        # the faster waveform animation on top of that motion.
        self._draw()
        self.root.after(45, self._tick)

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
        if event.x > self.root.winfo_width() - 52 and event.y < 56:
            self.root.destroy()
            return
        if self.ui_state == "confirm":
            if event.x >= 368 and event.y >= 188:
                self._approve_pending()
            elif 292 <= event.x <= 366 and event.y >= 188:
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
