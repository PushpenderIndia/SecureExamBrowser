"""OS-level lockdown for the exam session.

activate()   — call before the window is shown
deactivate() — call on app exit (connect to QApplication.aboutToQuit)

All methods are best-effort: failures are silently swallowed so a missing
binary or permission issue never crashes the exam.
"""

from __future__ import annotations

import subprocess
import sys


class SystemGuard:
    """Prevents sleep, hides OS chrome, and suppresses notifications.

    Platform behaviour
    ------------------
    macOS   : caffeinate -di (keep display + system awake),
              write doNotDisturb pref + restart NotificationCenter
    Windows : SetThreadExecutionState (keep display on),
              hide Shell_TrayWnd taskbar via user32
    Linux   : xset s off / -dpms (disable screensaver + DPMS),
              gsettings GNOME show-banners false
    """

    def __init__(self) -> None:
        self._caffeinate: subprocess.Popen | None = None
        self._taskbar_hwnd: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def activate(self) -> None:
        try:
            if sys.platform == "darwin":
                self._mac_activate()
            elif sys.platform == "win32":
                self._win_activate()
            else:
                self._linux_activate()
        except Exception:
            pass

    def deactivate(self) -> None:
        try:
            if sys.platform == "darwin":
                self._mac_deactivate()
            elif sys.platform == "win32":
                self._win_deactivate()
            else:
                self._linux_deactivate()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # macOS
    # ------------------------------------------------------------------

    def _mac_activate(self) -> None:
        # Keep display (-d) and system (-i) awake for the life of this process
        self._caffeinate = subprocess.Popen(
            ["caffeinate", "-di"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Suppress Notification Center banners
        subprocess.run(
            ["defaults", "write", "com.apple.notificationcenterui",
             "doNotDisturb", "-bool", "true"],
            capture_output=True,
        )
        subprocess.run(["killall", "NotificationCenter"], capture_output=True)

    def _mac_deactivate(self) -> None:
        if self._caffeinate:
            self._caffeinate.terminate()
            self._caffeinate = None
        subprocess.run(
            ["defaults", "write", "com.apple.notificationcenterui",
             "doNotDisturb", "-bool", "false"],
            capture_output=True,
        )
        subprocess.run(["killall", "NotificationCenter"], capture_output=True)

    # ------------------------------------------------------------------
    # Windows
    # ------------------------------------------------------------------

    def _win_activate(self) -> None:
        import ctypes
        ES_CONTINUOUS       = 0x80000000
        ES_SYSTEM_REQUIRED  = 0x00000001
        ES_DISPLAY_REQUIRED = 0x00000002
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )
        hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
        if hwnd:
            self._taskbar_hwnd = hwnd
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE

    def _win_deactivate(self) -> None:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)  # ES_CONTINUOUS only
        if self._taskbar_hwnd:
            ctypes.windll.user32.ShowWindow(self._taskbar_hwnd, 5)  # SW_SHOW
            self._taskbar_hwnd = 0

    # ------------------------------------------------------------------
    # Linux
    # ------------------------------------------------------------------

    def _linux_activate(self) -> None:
        for cmd in (
            ["xset", "s", "off"],
            ["xset", "-dpms"],
            ["xset", "s", "noblank"],
        ):
            subprocess.run(cmd, capture_output=True)
        subprocess.run(
            ["gsettings", "set",
             "org.gnome.desktop.notifications", "show-banners", "false"],
            capture_output=True,
        )

    def _linux_deactivate(self) -> None:
        for cmd in (["xset", "s", "on"], ["xset", "+dpms"]):
            subprocess.run(cmd, capture_output=True)
        subprocess.run(
            ["gsettings", "set",
             "org.gnome.desktop.notifications", "show-banners", "true"],
            capture_output=True,
        )
