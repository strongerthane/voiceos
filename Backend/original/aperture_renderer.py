"""Soft glass surfaces and audio-reactive light for the VoiceOS aperture.

Frames carry real per-pixel opacity for the Windows compositor. The same frames
remain usable by the Tk fallback and the offline preview; no desktop screenshot,
wallpaper or external image service is involved in drawing the live interface.
"""

from __future__ import annotations

import math
import os
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont


class ApertureRenderer:
    SCALE = 3

    def __init__(self):
        self._fonts = {}

    def font(self, size, bold=False):
        key = (size, bold)
        if key not in self._fonts:
            directory = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
            filename = "seguisb.ttf" if bold else "segoeui.ttf"
            self._fonts[key] = ImageFont.truetype(os.path.join(directory, filename), round(size * self.SCALE))
        return self._fonts[key]

    @staticmethod
    def sheet_box(width):
        return (6, 42, width - 6, 258)

    def controls(self, width):
        left, top, right, bottom = self.sheet_box(width)
        return {"cancel": (left + 18, bottom - 58, left + 119, bottom - 16),
                "approve": (left + 131, bottom - 58, right - 18, bottom - 16)}

    def _surface(self, image, box, radius, opacity=208, notch=False):
        """A single translucent surface with a soft, asymmetric optical edge."""
        s = self.SCALE
        left, top, right, bottom = (round(v * s) for v in box)
        width, height = right - left, bottom - top
        y, x = np.mgrid[0:height, 0:width].astype(np.float32)
        nx, ny = x / max(1, width - 1), y / max(1, height - 1)
        qx = abs(x - (width - 1) / 2) - (width / 2 - radius * s)
        qy = abs(y - (height - 1) / 2) - (height / 2 - radius * s)
        distance = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0))
        distance += np.minimum(np.maximum(qx, qy), 0) - radius * s
        if notch:
            # Screen-edge integration: square upper shoulders, soft lower
            # corners. The material starts at y=0 rather than floating below it.
            distance = np.where(y < radius * s,
                                np.maximum(-x, x - (width - 1)), distance)
        coverage = np.clip(.5 - distance, 0, 1)
        # Light is diffuse and neutral. No inset chrome or embossed top line.
        light = np.exp(-((nx - .1) / .7) ** 2 - (ny / .6) ** 2)
        lower = np.exp(-((nx - .9) / .6) ** 2 - ((ny - 1) / .65) ** 2)
        rgb = np.zeros((height, width, 3), dtype=np.float32) + (3, 4, 6)
        rgb += light[..., None] * (7, 8, 10)
        rgb += lower[..., None] * (4, 3, 6)
        edge = np.exp(-((distance + .55 * s) / (.40 * s)) ** 2)
        brightness = .16 + .55 * np.exp(-((nx - .2) / .5) ** 2 - (ny / .3) ** 2)
        rgb += (edge * brightness)[..., None] * (60, 66, 76)
        # A restrained spectral reflection lives at the bottom edge.
        bottom_edge = edge * np.maximum(0, ny - .6) * .65
        rgb += bottom_edge[..., None] * np.stack((40 * nx, 36 * (1 - nx), 68 + nx * 0), axis=-1)
        pixels = np.empty((height, width, 4), dtype=np.uint8)
        pixels[..., :3] = np.clip(rgb, 0, 255).astype("uint8")
        pixels[..., 3] = np.clip(coverage * opacity, 0, 255).astype("uint8")
        image.alpha_composite(Image.fromarray(pixels), (left, top))

    def _text(self, image, xy, text, size=14, color=(236, 239, 248), bold=False,
              max_width=None, centered=False):
        pen = ImageDraw.Draw(image)
        font = self.font(size, bold)
        if max_width and pen.textlength(text, font) > max_width * self.SCALE:
            while text and pen.textlength(text + "…", font) > max_width * self.SCALE:
                text = text[:-1]
            text = text.rstrip() + "…"
        pen.text(tuple(round(v * self.SCALE) for v in xy), text, font=font,
                 fill=(*color, 255), anchor="mm" if centered else "lm")

    def _envelope(self, image, x, y):
        s = self.SCALE
        pen = ImageDraw.Draw(image)
        box = ((x - 9) * s, (y - 6) * s, (x + 9) * s, (y + 6) * s)
        pen.rounded_rectangle(box, radius=3 * s, outline=(201, 209, 229), width=4)
        pen.line(((x - 7) * s, (y - 4) * s, x * s, (y + 1) * s,
                  (x + 7) * s, (y - 4) * s), fill=(201, 209, 229), width=4)

    @lru_cache(maxsize=12)
    def _base(self, width, height, state, recipient, subject, message, hover, focus, text_mode, body, request):
        s = self.SCALE
        image = Image.new("RGBA", (width * s, height * s))
        idle = state == "idle"
        shell_bottom = 28 if idle else 40
        cy = shell_bottom / 2
        expanded = state in {"confirm", "complete", "error"} or text_mode or bool(request and state in {"thinking", "executing"})
        # One expanding notch, including its task/confirmation area. There is
        # no second card, connector, persistent wordmark, or empty idle panel.
        self._surface(image, (6, 0, width - 6, height - 2 if expanded else shell_bottom),
                      16, opacity=208 if expanded else 180, notch=True)
        pen = ImageDraw.Draw(image)
        pen.ellipse((20 * s, (cy - 3) * s, 26 * s, (cy + 3) * s),
                    fill=(167, 208, 240, 255))
        labels = {"listening": "Listening", "thinking": "Thinking", "executing": "Working",
                  "confirm": "Review", "complete": "Done", "error": "Retry"}
        if state in labels:
            self._text(image, (width - 69, cy), labels[state], size=9.5, color=(213, 219, 234))
        if state == "confirm":
            left, top, right, bottom = self.sheet_box(width)
            # Action details unfold within the same top-edge surface.
            # General confirmation card: works for booking, app actions, email, etc.
            self._envelope(image, left + 29, top + 29)
            # Title: action being confirmed
            self._text(image, (left + 50, top + 29), "Confirm action", size=15, bold=True)
            # The pending command / what will happen
            self._text(image, (left + 22, top + 61), "Action", size=11, color=(184, 194, 214))
            self._text(image, (left + 46, top + 61), recipient, size=13,
                       max_width=right - left - 72)
            self._text(image, (left + 22, top + 91), subject, size=18,
                       max_width=right - left - 48)
            self._text(image, (left + 22, top + 120),
                       body or "Review before continuing.", size=11,
                       color=(198, 206, 222), max_width=right - left - 44)
            for name, box in self.controls(width).items():
                primary = name == "approve"
                active = hover == name
                pen = ImageDraw.Draw(image)
                scaled = tuple(round(v * s) for v in box)
                if primary or active:
                    fill = (255, 255, 255, 255) if primary and active else (
                        (229, 235, 250, 255) if primary else (40, 46, 61, 245))
                    pen.rounded_rectangle(scaled, radius=13 * s, fill=fill)
                if focus == name:
                    pen.rounded_rectangle((scaled[0] - 3, scaled[1] - 3,
                                           scaled[2] + 3, scaled[3] + 3),
                                          radius=14 * s, outline=(169, 180, 255), width=4)
                if primary:
                    self._text(image, ((box[0] + box[2]) / 2 - 9, (box[1] + box[3]) / 2),
                               "Approve", size=13, color=(18, 22, 33), bold=True, centered=True)
                    ax, ay = box[2] - 24, (box[1] + box[3]) / 2
                    pen.line(((ax - 6) * s, ay * s, (ax + 5) * s, ay * s),
                             fill=(27, 32, 46), width=4)
                    pen.line((ax * s, (ay - 5) * s, (ax + 5) * s, ay * s,
                              ax * s, (ay + 5) * s), fill=(27, 32, 46), width=4)
                else:
                    self._text(image, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2),
                               "Cancel", size=13, color=(198, 207, 225), centered=True)
        elif state in {"complete", "error"}:
            self._text(image, (24, 60), "Completed" if state == "complete" else "Needs attention",
                       size=13, bold=True)
            self._text(image, (24, 86), message, size=12, max_width=width - 48,
                       color=(192, 203, 222))
        elif request and state in {"thinking", "executing"} and not text_mode:
            self._text(image, (24, 65), request, size=12, max_width=width - 48,
                       color=(215, 222, 239))
        return image.resize((width, height), Image.Resampling.LANCZOS)

    @staticmethod
    def _moving_reflection(image, box, phase):
        left, top, right, bottom = box
        left, top = max(0, left), max(0, top)
        right, bottom = min(image.width, right), min(image.height, bottom)
        if right <= left or bottom <= top:
            return
        pixels = np.array(image.crop((left, top, right, bottom)))
        x = np.linspace(0, 1, right - left, dtype=np.float32)[None, :]
        y = np.linspace(0, 1, bottom - top, dtype=np.float32)[:, None]
        # Diffuse illumination only: no drawn diagonal lines across the card.
        center = .5 + .25 * math.sin(phase * .22)
        light = np.exp(-((x - center) / .4) ** 2 - ((y - .04) / .7) ** 2)
        fade = np.sin(x * math.pi) ** 2 * np.sin(y * math.pi) ** 2
        illumination = (light * fade)[..., None] * (3, 6, 10)
        pixels[..., :3] = np.clip(pixels[..., :3] + illumination *
                                  (pixels[..., 3:4] / 255), 0, 255).astype("uint8")
        image.paste(Image.fromarray(pixels), (left, top))

    @staticmethod
    def _light_field(width, height, phase, level, idle=False):
        """Continuous light ribbons: soft volumes, bright crests, broad bloom."""
        x = np.linspace(0, 1, width, dtype=np.float32)[None, :]
        y = np.linspace(-1, 1, height, dtype=np.float32)[:, None]
        emission = np.zeros((height, width, 3), dtype=np.float32)
        gain = .24 if idle else .65 + .45 * min(1., max(0., level) * 4)
        colors = ((.04, .68, 1.), (.16, .91, 1.), (.48, .30, 1.), (1., .28, .81))
        for i, color in enumerate(colors):
            center = .32 + i * .12 + .045 * math.sin(phase * .65 + i * 1.3)
            envelope = np.exp(-((x - center) / (.125 + i * .004)) ** 2)
            extent = (.47 + .16 * math.sin(phase * 1.2 + i)) * gain * envelope
            bias = .13 * np.sin(x * 9 - phase * .8 + i) * envelope
            distance = np.abs(y - bias)
            edge = np.exp(-((distance - extent) / .034) ** 2) * envelope
            volume = np.exp(-(distance / (extent + .012)) ** 4) * envelope
            bloom = np.exp(-((distance - extent) / .24) ** 2) * envelope * .28
            intensity = edge * .65 + volume * .70 + bloom
            emission += intensity[..., None] * np.asarray(color, dtype=np.float32)
            emission += (edge * .17)[..., None] * (.55, .75, 1.)
        taper = np.maximum(0., np.sin(x * math.pi)) ** 2
        spine = np.exp(-(y / .028) ** 2) * taper * .40
        emission += spine[..., None] * (.44, .65, .94)
        return Image.fromarray(np.clip(emission * 215, 0, 255).astype("uint8"))

    def render(self, width, height, state="idle", phase=0., level=0., recipient="",
               subject="", message="", hover=None, focus=None, text_mode=False, body="", request=""):
        image = self._base(width, height, state, recipient, subject, message,
                           hover, focus, text_mode, body, request).copy()
        idle = state == "idle"
        cy = 14 if idle else 20
        left, right = (46, width - 26) if idle else (66, width - 82)
        wave_height = 18 if idle else 30
        top = cy - wave_height // 2
        box = (left, top, right, top + wave_height)
        wave = self._light_field(right - left, wave_height, phase, level, idle)
        patch = image.crop(box)
        rgb = ImageChops.add(patch.convert("RGB"), wave).convert("RGBA")
        rgb.putalpha(patch.getchannel("A"))
        image.paste(rgb, (left, top))
        self._moving_reflection(image, (10, 1, width - 10, 26 if idle else 38), phase)
        if state == "confirm":
            self._moving_reflection(image, self.sheet_box(width), phase)
        elif state in {"complete", "error"} or text_mode:
            self._moving_reflection(image, (10, 42, width - 10, height - 4), phase)
        return image
