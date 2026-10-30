"""Protect optional provider keys with Windows user-bound DPAPI."""
import ctypes as c
from ctypes import wintypes as w
from user_paths import user_dir


class Blob(c.Structure):
    _fields_ = [('size', w.DWORD), ('data', c.POINTER(c.c_ubyte))]


def _crypt(data: bytes, decrypt=False) -> bytes:
    crypt = c.WinDLL('crypt32', use_last_error=True)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [c.c_void_p]
    kernel.LocalFree.restype = c.c_void_p
    buffer = c.create_string_buffer(data)
    source = Blob(len(data), c.cast(buffer, c.POINTER(c.c_ubyte)))
    result = Blob()
    if decrypt:
        call = crypt.CryptUnprotectData
        call.argtypes = [c.POINTER(Blob), c.c_void_p, c.c_void_p, c.c_void_p, c.c_void_p, w.DWORD, c.POINTER(Blob)]
        ok = call(c.byref(source), None, None, None, None, 1, c.byref(result))
    else:
        call = crypt.CryptProtectData
        call.argtypes = [c.POINTER(Blob), w.LPCWSTR, c.c_void_p, c.c_void_p, c.c_void_p, w.DWORD, c.POINTER(Blob)]
        ok = call(c.byref(source), 'VoiceOS provider key', None, None, None, 1, c.byref(result))
    call.restype = w.BOOL
    if not ok:
        raise OSError('Windows could not protect or unlock the VoiceOS provider key.')
    try:
        return c.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(c.cast(result.data, c.c_void_p))


def save_api_key(key: str):
    path = user_dir() / 'provider-key.bin'
    path.parent.mkdir(parents=True, exist_ok=True)
    if key:
        encrypted = _crypt(key.encode('utf-8'))
        temporary = path.with_suffix('.tmp')
        temporary.write_bytes(encrypted)
        temporary.replace(path)
    elif path.exists():
        path.unlink()


def load_api_key() -> str:
    path = user_dir() / 'provider-key.bin'
    if not path.exists():
        return ''
    return _crypt(path.read_bytes(), decrypt=True).decode('utf-8')
