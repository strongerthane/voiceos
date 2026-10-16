"""Present RGBA frames with Windows per-pixel transparency.

Only the calling application's window is modified. No desktop capture,
system setting, external process, hook or extra dependency is required.
"""

import ctypes as c
from ctypes import wintypes as w
import sys

import numpy as np


def enable_dpi_awareness():
    """Keep overlay pixels sharp on scaled Windows displays."""
    if sys.platform == "win32":
        try:
            c.windll.user32.SetProcessDpiAwarenessContext(c.c_void_p(-4))
        except (AttributeError, OSError):
            pass


class BitmapHeader(c.Structure):
    _fields_ = [("size", w.DWORD), ("width", w.LONG), ("height", w.LONG),
                ("planes", w.WORD), ("bits", w.WORD), ("compression", w.DWORD),
                ("image_size", w.DWORD), ("x_resolution", w.LONG), ("y_resolution", w.LONG),
                ("colors_used", w.DWORD), ("colors_important", w.DWORD)]


class BitmapInfo(c.Structure):
    _fields_ = [("header", BitmapHeader), ("colors", w.DWORD * 3)]


class Blend(c.Structure):
    _fields_ = [("operation", c.c_ubyte), ("flags", c.c_ubyte),
                ("opacity", c.c_ubyte), ("alpha_format", c.c_ubyte)]


class LayeredGlass:
    LAYERED = 0x00080000
    EXSTYLE = -20

    def __init__(self, root):
        if sys.platform != "win32":
            raise OSError("Native glass is Windows-only")
        self.user = c.WinDLL("user32", use_last_error=True)
        self.gdi = c.WinDLL("gdi32", use_last_error=True)
        self.user.GetAncestor.argtypes = [w.HWND, w.UINT]
        self.user.GetAncestor.restype = w.HWND
        self.get_style = getattr(self.user, "GetWindowLongPtrW", self.user.GetWindowLongW)
        self.set_style = getattr(self.user, "SetWindowLongPtrW", self.user.SetWindowLongW)
        self.get_style.argtypes = [w.HWND, c.c_int]
        self.get_style.restype = c.c_ssize_t
        self.set_style.argtypes = [w.HWND, c.c_int, c.c_ssize_t]
        self.set_style.restype = c.c_ssize_t
        self.gdi.CreateCompatibleDC.argtypes = [w.HDC]
        self.gdi.CreateCompatibleDC.restype = w.HDC
        self.gdi.CreateDIBSection.argtypes = [w.HDC, c.POINTER(BitmapInfo), w.UINT,
                                            c.POINTER(c.c_void_p), w.HANDLE, w.DWORD]
        self.gdi.CreateDIBSection.restype = w.HANDLE
        self.gdi.SelectObject.argtypes = [w.HDC, w.HANDLE]
        self.gdi.SelectObject.restype = w.HANDLE
        self.gdi.DeleteObject.argtypes = [w.HANDLE]
        self.gdi.DeleteObject.restype = w.BOOL
        self.gdi.DeleteDC.argtypes = [w.HDC]
        self.gdi.DeleteDC.restype = w.BOOL
        self.user.UpdateLayeredWindow.argtypes = [w.HWND, w.HDC, c.POINTER(w.POINT),
                                                 c.POINTER(w.SIZE), w.HDC, c.POINTER(w.POINT),
                                                 w.DWORD, c.POINTER(Blend), w.DWORD]
        self.user.UpdateLayeredWindow.restype = w.BOOL
        self.hwnd = self.user.GetAncestor(root.winfo_id(), 2)
        if not self.hwnd:
            raise c.WinError(c.get_last_error())
        self.dc = self.gdi.CreateCompatibleDC(None)
        if not self.dc:
            raise c.WinError(c.get_last_error())
        self.bitmap = None
        self.old_bitmap = None
        self.buffer = c.c_void_p()
        self.size = None
        self.active = False

    def enable(self):
        if not self.active:
            style = self.get_style(self.hwnd, self.EXSTYLE)
            # Reset Tk's color-key attributes before switching to RGBA.
            self.set_style(self.hwnd, self.EXSTYLE, style & ~self.LAYERED)
            self.set_style(self.hwnd, self.EXSTYLE, style | self.LAYERED)
            self.active = True

    def disable(self):
        if self.active:
            style = self.get_style(self.hwnd, self.EXSTYLE)
            self.set_style(self.hwnd, self.EXSTYLE, style & ~self.LAYERED)
            self.set_style(self.hwnd, self.EXSTYLE, style | self.LAYERED)
            self.active = False

    def _release_bitmap(self):
        if self.bitmap:
            self.gdi.SelectObject(self.dc, self.old_bitmap)
            self.gdi.DeleteObject(self.bitmap)
            self.bitmap = None
            self.old_bitmap = None
            self.size = None

    def present(self, image):
        self.enable()
        width, height = image.size
        if self.size != image.size:
            self._release_bitmap()
            info = BitmapInfo()
            info.header = BitmapHeader(c.sizeof(BitmapHeader), width, -height, 1, 32,
                                       0, width * height * 4, 0, 0, 0, 0)
            self.bitmap = self.gdi.CreateDIBSection(self.dc, c.byref(info), 0,
                                                   c.byref(self.buffer), None, 0)
            if not self.bitmap:
                raise c.WinError(c.get_last_error())
            self.old_bitmap = self.gdi.SelectObject(self.dc, self.bitmap)
            self.size = image.size
        rgba = np.asarray(image, dtype=np.uint16).copy()
        rgba[..., :3] = (rgba[..., :3] * rgba[..., 3:4] + 127) // 255
        bgra = rgba[..., [2, 1, 0, 3]].astype("uint8").tobytes()
        c.memmove(self.buffer, bgra, len(bgra))
        size = w.SIZE(width, height)
        origin = w.POINT(0, 0)
        blend = Blend(0, 0, 255, 1)
        if not self.user.UpdateLayeredWindow(self.hwnd, None, None, c.byref(size), self.dc,
                                             c.byref(origin), 0, c.byref(blend), 2):
            raise c.WinError(c.get_last_error())

    def close(self):
        self._release_bitmap()
        if self.dc:
            self.gdi.DeleteDC(self.dc)
            self.dc = None
