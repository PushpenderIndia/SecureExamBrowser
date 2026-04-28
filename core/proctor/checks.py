"""
core/proctor/checks.py
──────────────────────
Live system checks for the intro screen.

Public surface
──────────────
  CheckStatus   – PENDING / PASSED / FAILED
  CheckResult   – status + human-readable message
  ScreenMonitor – QObject that watches screen count; emits result_changed
"""

from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication


class CheckStatus(Enum):
    PENDING = auto()
    PASSED  = auto()
    FAILED  = auto()


class CheckResult:
    def __init__(self, status: CheckStatus, message: str = "") -> None:
        self.status  = status
        self.message = message

    @property
    def passed(self) -> bool:
        return self.status is CheckStatus.PASSED


class ScreenMonitor(QObject):
    """
    Watches whether more than one screen is connected.

    Emits result_changed whenever the screen configuration changes.
    Call check() to get the current result without waiting for a signal.
    """

    result_changed = Signal(object)   # CheckResult

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(self._recheck)
            app.screenRemoved.connect(self._recheck)

    # ── public ────────────────────────────────────────────────────────────────

    def check(self) -> CheckResult:
        """Return current screen-count result (does NOT emit result_changed)."""
        return self._build_result()

    # ── private ───────────────────────────────────────────────────────────────

    @Slot()
    def _recheck(self) -> None:
        self.result_changed.emit(self._build_result())

    @staticmethod
    def _build_result() -> CheckResult:
        count = len(QGuiApplication.screens())
        if count <= 1:
            return CheckResult(CheckStatus.PASSED, "Single monitor detected")
        return CheckResult(
            CheckStatus.FAILED,
            f"{count} monitors detected — please disconnect extra displays",
        )
