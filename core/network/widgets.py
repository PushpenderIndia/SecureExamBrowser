"""Network UI components: WiFiDialog, NoInternetDialog, NetworkStatusWidget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .monitor import NetworkMonitor
from .wifi_manager import WiFiManager, WiFiNetwork, signal_bars

# ── Shared stylesheet ─────────────────────────────────────────────────────────

_STYLE = """
    QDialog, QWidget   { background: #1e1e2e; color: #cdd6f4; }
    QLabel             { color: #cdd6f4; font-size: 13px; }
    QLineEdit {
        background: #313244; color: #cdd6f4;
        border: 1px solid #45475a; border-radius: 4px;
        padding: 4px 8px;
    }
    QListWidget {
        background: #181825; color: #cdd6f4;
        border: 1px solid #45475a; border-radius: 4px;
        outline: none;
    }
    QListWidget::item          { padding: 7px 12px; }
    QListWidget::item:selected { background: #313244; color: #89b4fa; }
    QListWidget::item:alternate { background: #1e1e2e; }
    QPushButton {
        color: #cdd6f4; background: #313244;
        border: 1px solid #45475a; border-radius: 4px;
        padding: 5px 18px; font-weight: bold; min-width: 90px;
    }
    QPushButton:hover    { background: #89b4fa; color: #1e1e2e; }
    QPushButton:pressed  { background: #74c7ec; color: #1e1e2e; }
    QPushButton:disabled { color: #585b70; border-color: #313244; }
"""

_STATUS_ONLINE  = "color: #a6e3a1; font-weight: bold; padding: 2px 8px;"
_STATUS_OFFLINE = "color: #f38ba8; font-weight: bold; padding: 2px 8px;"

_FLAGS = Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint


# ── WiFiDialog ────────────────────────────────────────────────────────────────

class WiFiDialog(QDialog):
    """Built-in WiFi network browser and connector.

    Scans automatically on open.  Selecting a secured network reveals a
    password field.  The password field's Return key also triggers Connect.
    """

    def __init__(self, manager: WiFiManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("WiFi Networks")
        self.setWindowFlags(_FLAGS)
        self.setMinimumSize(460, 420)
        self.setStyleSheet(_STYLE)

        self._manager  = manager
        self._networks: list[WiFiNetwork] = []

        self._build_ui()
        self._manager.scan_complete.connect(self._on_scan_complete)
        self._manager.scan_error.connect(self._on_scan_error)
        self._manager.connect_result.connect(self._on_connect_result)
        # Ensure location permission is requested before the first scan
        self._manager.request_location_auth()
        self._do_scan()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(20, 20, 20, 20)

        self._status = QLabel("Scanning…")
        self._status.setStyleSheet("color: #cba6f7;")
        root.addWidget(self._status)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.currentRowChanged.connect(self._on_row_changed)
        root.addWidget(self._list)

        # Password row — hidden until a secured network is selected
        pw_row = QWidget()
        pw_layout = QHBoxLayout(pw_row)
        pw_layout.setContentsMargins(0, 0, 0, 0)
        pw_label = QLabel("Password:")
        pw_label.setFixedWidth(72)
        pw_layout.addWidget(pw_label)
        self._pw = QLineEdit()
        self._pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw.setPlaceholderText("Enter WiFi password…")
        self._pw.returnPressed.connect(self._do_connect)
        pw_layout.addWidget(self._pw)
        self._pw_row = pw_row
        self._pw_row.setVisible(False)
        root.addWidget(self._pw_row)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._refresh_btn = QPushButton("↻  Refresh")
        self._refresh_btn.clicked.connect(self._do_scan)
        btn_row.addWidget(self._refresh_btn)

        btn_row.addStretch()

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setEnabled(False)
        self._connect_btn.clicked.connect(self._do_connect)
        btn_row.addWidget(self._connect_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _do_scan(self) -> None:
        self._status.setText("⟳  Scanning for networks…")
        self._status.setStyleSheet("color: #cba6f7;")
        self._list.clear()
        self._networks.clear()
        self._connect_btn.setEnabled(False)
        self._pw_row.setVisible(False)
        self._manager.scan()

    def _do_connect(self) -> None:
        row = self._list.currentRow()
        if not (0 <= row < len(self._networks)):
            return
        net = self._networks[row]
        pw  = self._pw.text() if net.secured else ""
        self._status.setText(f'⟳  Connecting to "{net.ssid}"…')
        self._status.setStyleSheet("color: #cba6f7;")
        self._connect_btn.setEnabled(False)
        self._manager.connect(net.ssid, pw)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_scan_error(self, message: str) -> None:
        self._list.clear()
        self._networks.clear()
        self._connect_btn.setEnabled(False)
        self._pw_row.setVisible(False)
        self._status.setText(message)
        self._status.setStyleSheet("color: #fab387;")   # peach — warning

    def _on_scan_complete(self, networks: list[WiFiNetwork]) -> None:
        self._networks = networks
        self._list.clear()

        if not networks:
            self._status.setText("No networks found — try refreshing.")
            self._status.setStyleSheet("color: #f38ba8;")
            return

        for net in networks:
            lock = "🔒 " if net.secured else "    "
            mark = "  ✓" if net.connected else ""
            text = f"{lock}{net.ssid}{mark}   {signal_bars(net.signal)}"
            item = QListWidgetItem(text)
            if net.connected:
                item.setForeground(QColor("#a6e3a1"))
            self._list.addItem(item)

        self._status.setText(f"Found {len(networks)} network(s).  Select one to connect.")
        self._status.setStyleSheet("color: #cdd6f4;")

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._networks):
            net = self._networks[row]
            self._pw_row.setVisible(net.secured)
            self._pw.clear()
            self._connect_btn.setEnabled(True)
        else:
            self._pw_row.setVisible(False)
            self._connect_btn.setEnabled(False)

    def _on_connect_result(self, success: bool, message: str) -> None:
        self._connect_btn.setEnabled(True)
        if success:
            self._status.setText(f"✓  {message}")
            self._status.setStyleSheet("color: #a6e3a1;")
        else:
            self._status.setText(f"✗  {message}")
            self._status.setStyleSheet("color: #f38ba8;")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        # Disconnect to prevent stale signals reaching a closed dialog
        try:
            self._manager.scan_complete.disconnect(self._on_scan_complete)
            self._manager.scan_error.disconnect(self._on_scan_error)
            self._manager.connect_result.disconnect(self._on_connect_result)
        except RuntimeError:
            pass
        super().closeEvent(event)


# ── NoInternetDialog ──────────────────────────────────────────────────────────

class NoInternetDialog(QDialog):
    """Shown when internet is lost; provides a shortcut to WiFiDialog."""

    def __init__(
        self, manager: WiFiManager, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("No Internet Connection")
        self.setWindowFlags(_FLAGS)
        self.setMinimumWidth(380)
        self.setStyleSheet(_STYLE)
        self._manager = manager
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(28, 24, 28, 24)

        header = QLabel("⚠   No Internet Connection")
        header.setStyleSheet("color: #f38ba8; font-size: 15px; font-weight: bold;")
        root.addWidget(header)

        body = QLabel(
            "The internet connection has been lost.\n"
            "Select a WiFi network below to reconnect."
        )
        body.setWordWrap(True)
        root.addWidget(body)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        wifi_btn = QPushButton("WiFi Settings")
        wifi_btn.setToolTip("Browse and connect to a WiFi network")
        wifi_btn.clicked.connect(self._open_wifi)
        btn_row.addWidget(wifi_btn)

        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.setToolTip("Return to the exam")
        dismiss_btn.clicked.connect(self.accept)
        btn_row.addWidget(dismiss_btn)

        root.addLayout(btn_row)

    def _open_wifi(self) -> None:
        WiFiDialog(self._manager, self).exec()


# ── NetworkStatusWidget ───────────────────────────────────────────────────────

class NetworkStatusWidget(QWidget):
    """Toolbar chip showing live connection status.

    * Always clickable — opens :class:`WiFiDialog` when online,
      :class:`NoInternetDialog` when offline.
    * Going offline auto-opens :class:`NoInternetDialog`.
    """

    def __init__(
        self,
        monitor: NetworkMonitor,
        manager: WiFiManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._monitor = monitor
        self._manager = manager

        self._label = QLabel(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(self._label)

        self.setCursor(Qt.PointingHandCursor)
        monitor.connectivity_changed.connect(self._on_connectivity_changed)
        self._refresh(monitor.is_online)

    def _on_connectivity_changed(self, online: bool) -> None:
        self._refresh(online)
        if not online:
            NoInternetDialog(self._manager, self).exec()

    def _refresh(self, online: bool) -> None:
        if online:
            self._label.setText("●   Connected")
            self._label.setStyleSheet(_STATUS_ONLINE)
            self._label.setToolTip("Click to manage WiFi")
        else:
            self._label.setText("⚠   No Internet")
            self._label.setStyleSheet(_STATUS_OFFLINE)
            self._label.setToolTip("Click to reconnect")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            if self._monitor.is_online:
                WiFiDialog(self._manager, self).exec()
            else:
                NoInternetDialog(self._manager, self).exec()
        super().mousePressEvent(event)
