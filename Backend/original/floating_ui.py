"""Compact, desktop-integrated VoiceOS overlay.

This is the active user interface used by ``ui_engine_final``. It keeps the
original VoiceAssistant contract but moves it to a small borderless bar that
expands only while VoiceOS is listening or working.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Dict, Optional
import tkinter as tk
from PIL import ImageTk
from aperture_renderer import ApertureRenderer


class VoiceOSUI:
    """A compact floating VoiceOS interface with listening/task states."""

    IDLE_SIZE = (236, 30)
    ACTIVE_SIZE = (340, 42)
    CONFIRM_SIZE = (380, 262)
    RESULT_SIZE = (380, 112)
    TASK_SIZE = (380, 92)
    TEXT_SIZE = (440, 128)
    TOP_MARGIN = 0
    KEY_COLOR = "#000001"
    PANEL = "#08090d"
    PANEL_LIGHT = "#11131b"
    HEADER = "#181b26"
    BORDER = "#2a3040"
    TEXT = "#f7f8fc"
    MUTED = "#a8afbd"
    BLUE = "#756bff"
    PURPLE = "#bd62ff"
    GREEN = "#66e6c4"
    RED = "#ff8a99"

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
        self._active_request = ""
        self._drag_origin: Optional[tuple[int, int]] = None
        self._collapse_job = None
        self._resize_job = None
        self._text_mode = False
        self._renderer = ApertureRenderer()
        self._scene = None
        self._frame_photo = None
        self._display_level = 0.0
        self._last_tick = time.perf_counter()
        self._hover_action = None
        self._focus_action = None
        self._native = None

        from native_glass import enable_dpi_awareness
        enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.title(config.get("window_title", "VoiceOS"))
        self.root.configure(bg=self.KEY_COLOR)
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        try:
            self.root.wm_attributes("-transparentcolor", self.KEY_COLOR)
        except tk.TclError:
            pass
        try:
            self.root.wm_attributes("-alpha", 1.0)
        except tk.TclError:
            pass
        self.root.bind("<Escape>", lambda _event: self.root.destroy())
        self.root.bind("<Return>", self._activate_action)
        self.root.bind("<Tab>", self._tab_action)
        self.root.bind("<space>", lambda event: self._activate_action(event)
                       if self.ui_state == "confirm" else None)
        self.root.bind("<Control-t>", self._show_text_command)

        self.canvas = tk.Canvas(self.root, bg=self.KEY_COLOR, highlightthickness=0,
                                bd=0, takefocus=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_pointer)
        self.canvas.bind("<Leave>", lambda _event: setattr(self, "_hover_action", None))
        self.canvas.bind("<ButtonPress-3>", self._start_drag)
        self.canvas.bind("<B3-Motion>", self._drag)

        # Retained public widgets keep integration with the existing main/test
        # code, but they live inside the expanded overlay rather than a window.
        self.command_entry = tk.Entry(self.root, bd=0, relief=tk.FLAT,
                                      bg=self.PANEL_LIGHT, fg=self.TEXT,
                                      insertbackground=self.TEXT,
                                      font=("Segoe UI", 10))
        self.run_button = tk.Button(self.root, text="Run", command=self._on_run_command,
                                    bd=0, bg="#303c56", fg="#ffffff",
                                    activebackground="#465676", font=("Segoe UI", 9, "bold"),
                                    cursor="hand2", relief=tk.FLAT)
        self.mic_button = tk.Button(self.root, text="Mic", command=self._on_mic_command,
                                    bd=0, bg=self.HEADER, fg=self.TEXT,
                                    activebackground=self.BORDER, font=("Segoe UI", 9),
                                    cursor="hand2", relief=tk.FLAT)
        self._entry_window = self.canvas.create_window(210, 128, window=self.command_entry,
                                                        width=168, height=28,
                                                        state="hidden")
        self._run_window = self.canvas.create_window(376, 128, window=self.run_button,
                                                      width=44, height=28, state="hidden")
        self._mic_window = self.canvas.create_window(447, 128, window=self.mic_button,
                                                      width=44, height=28, state="hidden")

        # Compatibility status objects used by current feedback integrations.
        self.status_card = tk.Frame(self.root, bg=self.PANEL)
        self.status_text = tk.Label(self.status_card, text="", bg=self.PANEL, fg=self.TEXT)
        self.transcript = tk.Text(self.root, height=1, state=tk.DISABLED)
        self._position_window(*self.IDLE_SIZE)
        self.root.update_idletasks()
        try:
            from native_glass import LayeredGlass
            self._native = LayeredGlass(self.root)
        except (OSError, AttributeError):
            pass
        self.root.bind("<Destroy>", self._release_native, add="+")
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
            progress = frame / 12
            eased = 1 - (1 - progress) ** 3
            current_width = round(start_width + (width - start_width) * eased)
            current_height = round(start_height + (height - start_height) * eased)
            x = max(16, (screen_width - current_width) // 2)
            y = self.TOP_MARGIN
            self.root.geometry(f"{current_width}x{current_height}+{x}+{y}")
            self.canvas.config(width=current_width, height=current_height)
            self._draw()
            if frame < 12:
                self._resize_job = self.root.after(16, lambda: step(frame + 1))
            else:
                self._resize_job = None

        step(1)

    def _draw(self):
        width = max(1, self.root.winfo_width())
        height = max(1, self.root.winfo_height())
        render_width, render_height = self._target_size()
        frame = self._renderer.render(
            render_width, render_height, self.ui_state, self._phase, self._display_level,
            recipient=self._extract_recipient(self._pending_command or ""),
            subject=self._extract_subject(self._pending_command or ""),
            body=self._extract_body(self._pending_command or ""),
            request=self._active_request,
            message=self._status_message, hover=self._hover_action,
            focus=self._focus_action, text_mode=self._text_mode,
        )
        # Cache the final material once per state, rather than rebuilding its
        # high-resolution geometry at every intermediate animation size.
        if width != render_width:
            frame = frame.resize((width, render_height))
        if height != render_height:
            frame = frame.crop((0, 0, width, height))
        visible = self._text_mode and self.ui_state != "confirm"
        native_drawn = False
        if self._native and not visible:
            try:
                self._native.present(frame)
                native_drawn = True
            except OSError as exc:
                print(f"Native glass fallback: {exc}")
                self._native.disable()
                self._native.close()
                self._native = None
                self.root.wm_attributes("-transparentcolor", self.KEY_COLOR)
        if not native_drawn:
            if self._native and self._native.active:
                self._native.disable()
                self.root.wm_attributes("-transparentcolor", self.KEY_COLOR)
            self._frame_photo = ImageTk.PhotoImage(frame)
            if self._scene is None:
                self._scene = self.canvas.create_image(0, 0, image=self._frame_photo, anchor="nw")
                self.canvas.tag_lower(self._scene)
            else:
                self.canvas.itemconfigure(self._scene, image=self._frame_photo)
        for item in (self._entry_window, self._run_window, self._mic_window):
            self.canvas.itemconfigure(item, state="normal" if visible else "hidden")
        if visible:
            self.canvas.coords(self._entry_window, width / 2 - 54, 91)
            self.canvas.coords(self._run_window, width / 2 + 60, 91)
            self.canvas.coords(self._mic_window, width / 2 + 115, 91)

    def _release_native(self, event):
        if event.widget is self.root and self._native:
            self._native.close()
            self._native = None

    def _on_pointer(self, event):
        self._hover_action = self._action_at(event.x, event.y)
        self.canvas.configure(cursor="hand2" if self._hover_action or self.ui_state == "idle" else "")

    def _action_at(self, x, y):
        if self.ui_state == "confirm":
            for action, (left, top, right, bottom) in self._renderer.controls(self.root.winfo_width()).items():
                if left <= x <= right and top <= y <= bottom:
                    return action
        return None

    def _tab_action(self, _event=None):
        if self.ui_state == "confirm":
            self._focus_action = "cancel" if self._focus_action == "approve" else "approve"
            self._draw()
            return "break"

    def _activate_action(self, _event=None):
        if self.ui_state == "confirm":
            if self._focus_action == "approve":
                self._approve_pending()
            elif self._focus_action == "cancel":
                self._cancel_pending()
            return "break"
        self._on_run_command()
        return "break"

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
        started = time.perf_counter()
        self._phase += min(.1, started - self._last_tick)
        self._last_tick = started
        self._display_level += (self._level - self._display_level) * .24
        self._draw()
        delay = max(10, 33 - round((time.perf_counter() - started) * 1000))
        self.root.after(delay, self._tick)

    def _set_state(self, state: str, message: str, kind: str = "info"):
        if self._collapse_job:
            self.root.after_cancel(self._collapse_job)
            self._collapse_job = None
        self.ui_state = state
        self._hover_action = None
        self._focus_action = None
        self._status_message = message
        self._status_kind = kind
        self.status_text.config(text=message)
        self.status_card_hidden = state == "idle"
        self.current_mode = "compact" if state == "idle" else "expanded"
        self.is_compact = state == "idle"
        self.is_expanded = not self.is_compact
        self._animate_to_size(*self._target_size())
        self._draw()

    def _target_size(self):
        return (self.IDLE_SIZE if self.ui_state == "idle" else self.CONFIRM_SIZE if self.ui_state == "confirm"
                else self.RESULT_SIZE if self.ui_state in {"complete", "error"}
                else self.TEXT_SIZE if self._text_mode
                else self.TASK_SIZE if self._active_request and self.ui_state in {"thinking", "executing"}
                else self.ACTIVE_SIZE)

    def _collapse(self):
        self._text_mode = False
        self._active_request = ""
        self._set_state("idle", "Ready when you are")

    def _schedule_collapse(self, milliseconds: int = 2600):
        self._collapse_job = self.root.after(milliseconds, self._collapse)

    def _on_canvas_click(self, event):
        self.root.focus_set()
        if self.ui_state == "confirm":
            action = self._action_at(event.x, event.y)
            if action == "approve":
                self._approve_pending()
            elif action == "cancel":
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

    def _show_text_command(self, _event=None):
        if self.ui_state == "confirm":
            return "break"
        self._text_mode = True
        self._set_state("thinking", "Type a request")
        self._draw()
        self.command_entry.focus_set()
        return "break"

    def _on_run_command(self):
        text = self.command_entry.get().strip()
        if text:
            self._text_mode = False
            self.command_entry.delete(0, tk.END)
            self.handle_command(text)

    def _on_mic_command(self):
        if self.ui_state == "listening":
            return
        self._text_mode = False
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
        self._active_request = command
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
