from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import wintypes


if sys.platform == "win32":
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
        wintypes.LPARAM,
        ctypes.c_int,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
else:  # pragma: no cover - import safety on non-Windows platforms
    user32 = None
    kernel32 = None
    LowLevelKeyboardProc = None

WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_QUIT = 0x0012
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_F4 = 0x73
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_SNAPSHOT = 0x2C
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_SHIFT = 0x10
LLKHF_ALTDOWN = 0x20


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class WindowsKioskMode:
    """Best-effort Windows kiosk hardening using a global keyboard hook."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._hook_id: int | None = None
        self._hook_proc = (
            LowLevelKeyboardProc(self._keyboard_proc)
            if LowLevelKeyboardProc is not None
            else None
        )
        self._started = threading.Event()
        self._stop_requested = threading.Event()

    def activate(self) -> None:
        if sys.platform != "win32" or user32 is None or kernel32 is None:
            return
        if self._thread and self._thread.is_alive():
            return

        self._started.clear()
        self._stop_requested.clear()
        self._thread = threading.Thread(
            target=self._run_message_loop,
            name="windows-kiosk-hook",
            daemon=True,
        )
        self._thread.start()
        self._started.wait(timeout=2)

    def deactivate(self) -> None:
        if sys.platform != "win32" or user32 is None:
            return
        self._stop_requested.set()
        if self._thread_id is not None:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

        if self._thread:
            self._thread.join(timeout=2)

        self._thread = None
        self._thread_id = None
        self._hook_id = None

    def _run_message_loop(self) -> None:
        assert user32 is not None
        assert kernel32 is not None
        assert self._hook_proc is not None
        self._thread_id = kernel32.GetCurrentThreadId()
        self._hook_id = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._hook_proc,
            kernel32.GetModuleHandleW(None),
            0,
        )
        self._started.set()

        if not self._hook_id:
            return

        msg = wintypes.MSG()
        while not self._stop_requested.is_set():
            result = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if result in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if self._hook_id:
            user32.UnhookWindowsHookEx(self._hook_id)
            self._hook_id = None

    def _keyboard_proc(
        self,
        n_code: int,
        w_param: int,
        l_param: int,
    ) -> int:
        assert user32 is not None
        if n_code != HC_ACTION:
            return user32.CallNextHookEx(self._hook_id or 0, n_code, w_param, l_param)

        if w_param not in (WM_KEYDOWN, WM_SYSKEYDOWN):
            return user32.CallNextHookEx(self._hook_id or 0, n_code, w_param, l_param)

        key_data = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        if self._should_block(key_data):
            return 1

        return user32.CallNextHookEx(self._hook_id or 0, n_code, w_param, l_param)

    def _should_block(self, key_data: KBDLLHOOKSTRUCT) -> bool:
        vk_code = key_data.vkCode
        alt_down = bool(key_data.flags & LLKHF_ALTDOWN)
        ctrl_down = self._is_key_down(VK_CONTROL)
        shift_down = self._is_key_down(VK_SHIFT)

        if vk_code in (VK_LWIN, VK_RWIN, VK_SNAPSHOT):
            return True
        if alt_down and vk_code in (VK_TAB, VK_ESCAPE, VK_F4):
            return True
        if ctrl_down and vk_code == VK_ESCAPE:
            return True
        if ctrl_down and shift_down and vk_code == VK_ESCAPE:
            return True
        return False

    @staticmethod
    def _is_key_down(vk_code: int) -> bool:
        assert user32 is not None
        return bool(user32.GetAsyncKeyState(vk_code) & 0x8000)
