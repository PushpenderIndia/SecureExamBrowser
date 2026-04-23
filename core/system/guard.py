"""OS-level lockdown for the exam session.

Call sequence
-------------
1. ``activate()``       — before the window is shown (sleep prevention,
                          notification suppression, taskbar hiding)
2. ``activate_kiosk()`` — after the window is visible / inside the Qt event
                          loop (platform kiosk behavior)
3. ``deactivate()``     — on app exit via QApplication.aboutToQuit

All methods are best-effort: failures are silently swallowed so a missing
binary or permission issue never crashes the exam.
"""

from __future__ import annotations

import subprocess
import sys

from .kiosk import KioskMode


class SystemGuard:
    """Combines sleep prevention, OS-chrome hiding, notification suppression,
    and platform kiosk options into one lifecycle object.

    Platform behaviour
    ------------------
    macOS   : caffeinate -di, DoNotDisturb pref, :class:`~.kiosk.KioskMode`
    Windows : SetThreadExecutionState, hide Shell_TrayWnd, block escape keys
    Linux   : xset screensaver/DPMS off, GNOME show-banners false
    """

    def __init__(self) -> None:
        self._caffeinate: subprocess.Popen | None = None
        self._taskbar_hwnd: int = 0
        self._kiosk = KioskMode()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def activate(self) -> None:
        """Sleep prevention + notification suppression + taskbar hiding.

        Safe to call before the Qt event loop starts.
        """
        try:
            if sys.platform == "darwin":
                self._mac_activate()
            elif sys.platform == "win32":
                self._win_activate()
            else:
                self._linux_activate()
        except Exception:
            pass

    def activate_kiosk(self) -> None:
        """Apply platform-specific kiosk restrictions.

        Must be called after the window is visible. Using
        ``QTimer.singleShot(0, guard.activate_kiosk)`` in ExamApp.run() keeps
        this sequencing correct for macOS and Windows.
        """
        self._kiosk.activate()

    def deactivate(self) -> None:
        """Restore all OS defaults.  Connected to QApplication.aboutToQuit."""
        self._kiosk.deactivate()
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
