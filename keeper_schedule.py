"""Windows user-scoped credential storage and persistent schedule."""
import base64
import ctypes
import json
from ctypes import wintypes
from pathlib import Path

STATE = Path(__file__).with_name(".keeper-state")
INTERVAL = 8 * 86400


class DataBlob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.c_void_p)]


def dpapi(value, decrypt=False):
    data = base64.b64decode(value, validate=True) if decrypt else value.encode("ascii")
    buffer = ctypes.create_string_buffer(data)
    source = DataBlob(len(data), ctypes.cast(buffer, ctypes.c_void_p))
    destination = DataBlob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    operation = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(destination)):
        raise ctypes.WinError(ctypes.get_last_error())
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        result = ctypes.string_at(destination.data, destination.size)
        return result.decode("ascii") if decrypt else base64.b64encode(result).decode("ascii")
    finally:
        kernel.LocalFree(destination.data)


def load_config():
    try:
        return json.loads((STATE / "schedule.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def save_config(config):
    STATE.mkdir(exist_ok=True)
    temp = STATE / "schedule.tmp"
    temp.write_text(json.dumps(config), encoding="utf-8")
    temp.replace(STATE / "schedule.json")
