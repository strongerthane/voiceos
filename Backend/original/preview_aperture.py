"""Preview the real VoiceOS surface without microphone or network activity.

Examples:
    python preview_aperture.py --state confirm
    python preview_aperture.py --state listening --capture listening.png --seconds 3
"""

import argparse
from pathlib import Path

import tkinter as tk
import numpy as np
from PIL import Image, ImageGrab, ImageTk
from floating_ui import VoiceOSUI


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", choices=("idle", "listening", "thinking", "executing", "confirm", "complete", "error"), default="confirm")
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--seconds", type=float, default=0)
    parser.add_argument("--stage", action="store_true", help="Place the actual overlay above a controlled preview backdrop")
    args = parser.parse_args()
    ui = VoiceOSUI({"window_title": "VoiceOS design preview"})
    stage = None
    stage_bounds = None
    if args.stage:
        stage = tk.Toplevel(ui.root)
        stage.overrideredirect(True)
        stage.attributes("-topmost", True)
        sw, sh = ui.root.winfo_screenwidth(), ui.root.winfo_screenheight()
        width, height = min(880, sw - 40), min(480, sh - 40)
        sx, sy = (sw - width) // 2, (sh - height) // 2
        stage.geometry(f"{width}x{height}+{sx}+{sy}")
        y, x = np.mgrid[-1:1:complex(height), -1:1:complex(width)]
        glow = np.exp(-((x - .7) / 1.2) ** 2 - ((y + .5) / 1.3) ** 2)
        cool = np.exp(-((x + .8) / 1.1) ** 2 - ((y - .4) / 1.2) ** 2)
        pixels = (np.zeros((height, width, 3)) + (32, 35, 43)
                  + glow[..., None] * (29, 17, 39) + cool[..., None] * (0, 14, 19))
        photo = ImageTk.PhotoImage(Image.fromarray(pixels.astype("uint8")))
        backdrop = tk.Label(stage, image=photo, bd=0)
        backdrop.image = photo
        backdrop.pack(fill="both", expand=True)
        ui.TOP_MARGIN = sy
        stage_bounds = (sx, sy, sx + width, sy + height)
        stage.update_idletasks()
        ui.root.lift()
    ui._pending_command = "draft email to Alex subject Lunch tomorrow"
    if args.state in {"thinking", "executing"}:
        ui._active_request = "Open YouTube and search for chess videos"
    ui._level = .25
    ui._set_state(args.state, "YouTube is open")

    def capture():
        if ui._resize_job:
            ui.root.after(100, capture)
            return
        ui.root.update_idletasks()
        # PrintWindow cannot capture UpdateLayeredWindow surfaces. Capture the
        # controlled stage or just the application's on-screen bounds instead.
        if stage_bounds:
            image = ImageGrab.grab(bbox=stage_bounds)
        elif ui._native and ui._native.active:
            x, y = ui.root.winfo_rootx(), ui.root.winfo_rooty()
            image = ImageGrab.grab(bbox=(x, y, x + ui.root.winfo_width(), y + ui.root.winfo_height()))
        else:
            image = ImageGrab.grab(window=ui.root.winfo_id())
        args.capture.parent.mkdir(parents=True, exist_ok=True)
        image.save(args.capture)
        print(f"Captured actual {args.state} window: {image.size}", flush=True)
        print(f"Native per-pixel glass: {bool(ui._native and ui._native.active)}", flush=True)

    if args.capture:
        ui.root.after(1000, capture)
    if args.seconds:
        ui.root.after(max(1600, round(args.seconds * 1000)), ui.root.destroy)
    ui.root.mainloop()


if __name__ == "__main__":
    main()
