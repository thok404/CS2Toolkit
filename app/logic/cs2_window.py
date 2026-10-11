"""Windows helpers for locating the CS2 window without relying on its title."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [enum_proc_type, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL


def foreground_window():
    return user32.GetForegroundWindow() or 0


def raise_overlay_window(hwnd):
    # 重新进入置顶层，不激活工具窗口或抢走游戏焦点。
    return bool(user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010))


def find_cs2_window() -> int:
    """Return the visible top-level window owned by ``cs2.exe``.

    CS2's window title follows the Steam display language (for example,
    ``反恐精英：全球攻势``), so matching the English title breaks overlays on
    localized installations.  Process ownership is stable across languages.
    """

    process_query_limited_information = 0x1000
    found: list[int] = []

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
