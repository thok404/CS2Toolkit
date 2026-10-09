"""Windows helpers for locating the CS2 window without relying on its title."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


def find_cs2_window() -> int:
    """Return the visible top-level window owned by ``cs2.exe``.

    CS2's window title follows the Steam display language (for example,
    ``反恐精英：全球攻势``), so matching the English title breaks overlays on
    localized installations.  Process ownership is stable across languages.
    """

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    process_query_limited_information = 0x1000
    found: list[int] = []

    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def process_name(pid: int) -> str:
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return ""
        try:
            buffer = ctypes.create_unicode_buffer(260)
            size = wintypes.DWORD(len(buffer))
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return buffer.value
            return ""
        finally:
            kernel32.CloseHandle(handle)

    @enum_proc_type
    def enum_windows(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if os.path.basename(process_name(pid.value)).lower() == "cs2.exe":
            if user32.GetWindowTextLengthW(hwnd) > 0:
                found.append(hwnd)
                return False
        return True

    user32.EnumWindows(enum_windows, 0)
    return found[0] if found else 0
