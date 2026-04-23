from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QToolBar

from .browser import SecureBrowser
from .config import ExamConfig
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
    * **Toolbar button / keyboard shortcut** — asks for the quit password.
    * **System close** (Alt+F4, Cmd+Q, window × button) — also asks for the
      quit password via ``closeEvent``.
    * **Quit URL** — when the browser signals ``quit_url_reached`` the window
      closes immediately with no password required.
    """

    def __init__(self, config: ExamConfig, quit_handler: QuitHandler) -> None:
        super().__init__()
        self.config = config
        self.quit_handler = quit_handler
        self._force_close = False

        self.browser = SecureBrowser(config, quit_handler)
        self.setCentralWidget(self.browser)

        self._setup_window()
        self._build_toolbar()
        self._connect_signals()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle(self.config.window_title)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.showFullScreen()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Exam Controls")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setStyleSheet(_TOOLBAR_STYLE)
        self.addToolBar(toolbar)

        quit_action = QAction("Quit Exam", self)
        quit_action.triggered.connect(self._on_quit_action)
        toolbar.addAction(quit_action)

    def _connect_signals(self) -> None:
        self.browser.quit_url_reached.connect(self._on_quit_url_reached)

    # ------------------------------------------------------------------
    # Quit handlers
    # ------------------------------------------------------------------

    def _on_quit_url_reached(self) -> None:
        """Called when the exam platform redirects to the quit URL."""
        self._force_close = True
        self.close()

    def _on_quit_action(self) -> None:
        """Called when the student clicks the toolbar Quit button."""
        if self.quit_handler.check_password(self):
            self._force_close = True
            self.close()

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._force_close:
            event.accept()
            return
        # Any other close attempt (Alt+F4, Cmd+Q, etc.) needs the password
        if self.quit_handler.check_password(self):
            event.accept()
        else:
            event.ignore()
