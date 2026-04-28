from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QSizePolicy, QToolBar, QWidget

from .browser import SecureBrowser
from .config import ExamConfig
from .network import NetworkMonitor, NetworkStatusWidget, WiFiManager
from .proctor import ProctorOverlay
from .quit_handler import QuitHandler

_TOOLBAR_STYLE = """
    QToolBar {
        background: #1e1e2e;
        border-bottom: 1px solid #45475a;
        padding: 4px 8px;
        spacing: 6px;
    }
    QToolButton {
        color: #cdd6f4;
        background: #313244;
        border: 1px solid #45475a;
        border-radius: 4px;
        padding: 4px 12px;
        font-weight: bold;
    }
    QToolButton:hover {
        background: #f38ba8;
        color: #1e1e2e;
    }
"""


class ExamWindow(QMainWindow):
    """Top-level window that hosts the secure browser.

    Quit paths
    ----------
    * **Toolbar button** — asks for the quit password.
    * **System close** (Alt+F4, Cmd+Q, window × button) — same password check
      via ``closeEvent``.
    * **Quit URL** — browser signals ``quit_url_reached`` → silent close.
    """

    def __init__(
        self,
        config: ExamConfig,
        quit_handler: QuitHandler,
        network_monitor: NetworkMonitor,
        wifi_manager: WiFiManager,
    ) -> None:
        super().__init__()
        self.config          = config
        self.quit_handler    = quit_handler
        self._network_monitor = network_monitor
        self._wifi_manager   = wifi_manager
        self._force_close    = False
        self._exam_loaded    = False

        self.browser = SecureBrowser(config, quit_handler)
        self.setCentralWidget(self.browser)

        self._setup_window()
        self._build_toolbar()

        self.proctor_overlay = ProctorOverlay(self)

        self._connect_signals()
        self.browser.hide()
        self.proctor_overlay.show()
        QTimer.singleShot(0, self.proctor_overlay.keep_in_bounds)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle(self.config.window_title)
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.CustomizeWindowHint    # take manual control of the button set
            | Qt.WindowTitleHint        # keep the title bar strip
            | Qt.WindowStaysOnTopHint   # always on top
        )
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Exam Controls")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setStyleSheet(_TOOLBAR_STYLE)
        self.addToolBar(toolbar)

        # Left side: exam controls
        quit_action = QAction("Quit Exam", self)
        quit_action.triggered.connect(self._on_quit_action)
        toolbar.addAction(quit_action)

        toolbar.addSeparator()

        reload_action = QAction("↻  Reload", self)
        reload_action.setToolTip("Reload the current page")
        reload_action.triggered.connect(lambda: self.browser.reload())
        toolbar.addAction(reload_action)

        # Right side: network status (push via expanding spacer)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        toolbar.addWidget(
            NetworkStatusWidget(self._network_monitor, self._wifi_manager, self)
        )

    def _connect_signals(self) -> None:
        self.browser.quit_url_reached.connect(self._on_quit_url_reached)
        self.proctor_overlay.session_started.connect(self._on_proctor_session_started)
        self.proctor_overlay.quit_requested.connect(self._on_quit_app_requested)

    # ------------------------------------------------------------------
    # Quit handlers
    # ------------------------------------------------------------------

    def _on_quit_url_reached(self) -> None:
        """Called when the exam platform redirects to the quit URL."""
        self._force_close = True
        self.close()

    def _on_quit_app_requested(self) -> None:
        """Called when the student clicks Quit App on the intro screen."""
        self._force_close = True
        self.close()

    def _on_quit_action(self) -> None:
        """Called when the student clicks the toolbar Quit button."""
        if self.quit_handler.check_password(self):
            self._force_close = True
            self.close()

    def _on_proctor_session_started(self) -> None:
        if self._exam_loaded:
            return
        self._exam_loaded = True
        self.browser.show()
        self.browser.load_exam_url()
        self.proctor_overlay.enter_compact_mode()

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._force_close:
            event.accept()
            return
        if self.quit_handler.check_password(self):
            event.accept()
        else:
            event.ignore()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "proctor_overlay"):
            self.proctor_overlay.keep_in_bounds()
