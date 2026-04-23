"""Platform kiosk facade.

macOS:
    Uses NSApplicationPresentationOptions to hide system chrome and block
    process-switching shortcuts.

Windows:
    Uses a low-level keyboard hook to suppress common shell-switching and
    escape shortcuts while the exam is active.

Linux:
    No-op for now.
"""

from __future__ import annotations

import sys

from .windows_kiosk import WindowsKioskMode

# ── Flag constants (stable since macOS 10.7) ──────────────────────────────────
# Mirrors NSApplicationPresentationOptions from AppKit.
# Defined here so callers need not import AppKit directly.

PRESENTATION_DEFAULT              = 0
AUTO_HIDE_DOCK                    = 1 << 0   #  1
HIDE_DOCK                         = 1 << 1   #  2  ← required by most other flags
AUTO_HIDE_MENU_BAR                = 1 << 2   #  4
HIDE_MENU_BAR                     = 1 << 3   #  8  ← requires HIDE_DOCK
DISABLE_APPLE_MENU                = 1 << 4   # 16  ← requires HIDE_DOCK
DISABLE_PROCESS_SWITCHING         = 1 << 5   # 32  ← blocks Cmd+Tab; requires HIDE_DOCK
DISABLE_FORCE_QUIT                = 1 << 6   # 64  ← blocks Cmd+Opt+Esc; requires HIDE_DOCK
DISABLE_SESSION_TERMINATION       = 1 << 7   # 128 ← blocks log-out; requires HIDE_DOCK
DISABLE_HIDE_APPLICATION          = 1 << 8   # 256
DISABLE_MENU_BAR_TRANSPARENCY     = 1 << 9   # 512

# Default preset for an exam session
EXAM_FLAGS: int = (
    HIDE_DOCK                     # required base for all flags below
    | HIDE_MENU_BAR               # removes menu bar
    | DISABLE_PROCESS_SWITCHING   # Cmd+Tab disabled
    | DISABLE_FORCE_QUIT          # Cmd+Option+Esc dialog blocked
    | DISABLE_APPLE_MENU          # Apple menu inaccessible
    | DISABLE_SESSION_TERMINATION # Log Out / Restart blocked
)


# ── KioskMode ────────────────────────────────────────────────────────────────

class _MacKioskMode:
    """Applies / removes macOS presentation options.

    Parameters
    ----------
    options:
        Bitmask of ``EXAM_FLAGS`` constants.  Defaults to :data:`EXAM_FLAGS`.
    """

    def __init__(self, options: int = EXAM_FLAGS) -> None:
        self._options = options

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def activate(self) -> None:
        """Enter kiosk mode.

        Must be called from the main thread after the main window is visible
        (i.e. inside the Qt event loop, e.g. via ``QTimer.singleShot(0, ...)``.
        """
        if sys.platform != "darwin":
            return
        try:
            self._set_options(self._options)
        except Exception:
            pass

    def deactivate(self) -> None:
        """Restore default OS presentation options."""
        if sys.platform != "darwin":
            return
        try:
            self._set_options(PRESENTATION_DEFAULT)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _set_options(flags: int) -> None:
        from AppKit import NSApp, NSApplication                # noqa: PLC0415

        app = NSApp or NSApplication.sharedApplication()
        if app is None:
            return
        app.setPresentationOptions_(flags)


class KioskMode:
    """Selects the best kiosk implementation for the active platform."""

    def __init__(self, options: int = EXAM_FLAGS) -> None:
        if sys.platform == "darwin":
            self._impl = _MacKioskMode(options=options)
        elif sys.platform == "win32":
            self._impl = WindowsKioskMode()
        else:
            self._impl = None

    def activate(self) -> None:
        if self._impl is None:
            return
        self._impl.activate()

    def deactivate(self) -> None:
        if self._impl is None:
            return
        self._impl.deactivate()
