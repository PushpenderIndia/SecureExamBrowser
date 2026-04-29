from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

_LABEL_STYLE = "color: #f9e2af; font-size: 12px; padding: 2px 8px;"


class AutoExit(QObject):
    """Fires `triggered` once when `duration_minutes` elapses.

    The timer starts at construction time.  Connect `triggered` to whatever
    close/quit logic the caller needs.
    """

    triggered = Signal()

    def __init__(self, duration_minutes: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._end_time = datetime.now() + timedelta(minutes=duration_minutes)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(duration_minutes * 60 * 1000)
        self._timer.timeout.connect(self.triggered)
        self._timer.start()

    @property
    def end_time(self) -> datetime:
        return self._end_time

    def formatted_end_time(self) -> str:
        return self._end_time.strftime("%I:%M %p")


class AutoExitWidget(QWidget):
    """Toolbar chip that displays the scheduled auto-exit time."""

    def __init__(self, auto_exit: AutoExit, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)

        label = QLabel(f"Auto Exit at:  {auto_exit.formatted_end_time()}", self)
        label.setStyleSheet(_LABEL_STYLE)
        label.setToolTip("The exam will close automatically at this time")
        layout.addWidget(label)
