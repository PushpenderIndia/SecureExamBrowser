from __future__ import annotations

from datetime import datetime

import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

_LABEL_STYLE = "color: #cdd6f4; font-size: 13px; padding: 2px 0px;"
_LOW_STYLE   = "color: #f38ba8; font-size: 13px; padding: 2px 0px;"

_REFRESH_MS = 30_000

_COLOR_CHARGING = QColor("#89b4fa")   # blue
_COLOR_NORMAL   = QColor("#a6e3a1")   # green
_COLOR_WARNING  = QColor("#f9e2af")   # yellow
_COLOR_LOW      = QColor("#f38ba8")   # red
_COLOR_OUTLINE  = QColor("#6c7086")


class BatteryIconWidget(QWidget):
    """macOS-style battery icon drawn with QPainter."""

    _BODY_W  = 26
    _BODY_H  = 13
    _NUB_W   = 3
    _NUB_H   = 6
    _PAD     = 2
    _RADIUS  = 2.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._percent = 100
        self._plugged = False
        total_w = self._BODY_W + self._NUB_W + 1
        self.setFixedSize(total_w, self._BODY_H)

    def set_state(self, percent: int, plugged: bool) -> None:
        if self._percent == percent and self._plugged == plugged:
            return
        self._percent = percent
        self._plugged = plugged
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        bw, bh = self._BODY_W, self._BODY_H
        r = self._RADIUS

        # --- body outline ---
        p.setPen(QPen(_COLOR_OUTLINE, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(0, 0, bw, bh, r, r)

        # --- nub ---
        nub_y = (bh - self._NUB_H) // 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_COLOR_OUTLINE)
        p.drawRoundedRect(bw + 1, nub_y, self._NUB_W, self._NUB_H, 1.0, 1.0)

        # --- fill ---
        if self._plugged:
            fill_color = _COLOR_CHARGING
        elif self._percent <= 10:
            fill_color = _COLOR_LOW
        elif self._percent <= 20:
            fill_color = _COLOR_WARNING
        else:
            fill_color = _COLOR_NORMAL

        pad = self._PAD
        fill_max_w = bw - 2 * pad
        fill_w = max(0, int(fill_max_w * self._percent / 100))
        if fill_w > 0:
            p.setBrush(fill_color)
            p.drawRoundedRect(pad, pad, fill_w, bh - 2 * pad, 1.0, 1.0)

        # --- bolt overlay when charging ---
        if self._plugged:
            self._draw_bolt(p, bw, bh)

        p.end()

    @staticmethod
    def _draw_bolt(p: QPainter, bw: int, bh: int) -> None:
        cx = bw / 2
        # Simple lightning bolt polygon centered in the body
        bolt = QPolygonF([
            QPointF(cx + 1.5, 2.0),
            QPointF(cx - 1.0, bh / 2 - 0.5),
            QPointF(cx + 0.5, bh / 2 - 0.5),
            QPointF(cx - 1.5, bh - 2.0),
            QPointF(cx + 1.0, bh / 2 + 0.5),
            QPointF(cx - 0.5, bh / 2 + 0.5),
        ])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1e1e2e"))
        p.drawPolygon(bolt)


class StatusWidget(QWidget):
    """Toolbar chip showing live battery icon + percentage and current date/time."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(6)

        self._battery_icon  = BatteryIconWidget(self)
        self._battery_label = QLabel(self)
        self._time_label    = QLabel(self)

        layout.addWidget(self._battery_icon)
        layout.addWidget(self._battery_label)
        layout.addSpacing(8)
        layout.addWidget(self._time_label)

        self._refresh()

        self._timer = QTimer(self)
        self._timer.setInterval(_REFRESH_MS)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        self._refresh_battery()
        self._refresh_time()

    def _refresh_battery(self) -> None:
        battery = psutil.sensors_battery()
        if battery is None:
            self._battery_icon.setVisible(False)
            self._battery_label.setVisible(False)
            return

        pct     = int(battery.percent)
        plugged = bool(battery.power_plugged)
        low     = pct <= 10 and not plugged

        self._battery_icon.set_state(pct, plugged)
        self._battery_label.setText(f"{pct}%")
        self._battery_label.setStyleSheet(_LOW_STYLE if low else _LABEL_STYLE)
        self._battery_icon.setVisible(True)
        self._battery_label.setVisible(True)

    def _refresh_time(self) -> None:
        self._time_label.setText(datetime.now().strftime("%a %d %b    %I:%M %p"))
        self._time_label.setStyleSheet(_LABEL_STYLE)
