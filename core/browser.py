from urllib.parse import urlparse

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView

from .config import ExamConfig
from .quit_handler import QuitHandler

# Keys that must not reach the web engine
_BLOCKED_KEYS = frozenset(
    {
        Qt.Key_F5,   # reload
        Qt.Key_F11,  # fullscreen toggle
        Qt.Key_F12,  # DevTools
    }
)

# Modifier+key combos that must be swallowed  (modifier_mask, key)
_BLOCKED_COMBOS = frozenset(
    {
        (Qt.ControlModifier, Qt.Key_R),   # Ctrl+R  reload
        (Qt.ControlModifier, Qt.Key_W),   # Ctrl+W  close tab
        (Qt.ControlModifier, Qt.Key_T),   # Ctrl+T  new tab
        (Qt.ControlModifier, Qt.Key_N),   # Ctrl+N  new window
        (Qt.ControlModifier, Qt.Key_L),   # Ctrl+L  focus address bar
        (Qt.ControlModifier | Qt.ShiftModifier, Qt.Key_I),  # DevTools
        (Qt.ControlModifier | Qt.ShiftModifier, Qt.Key_J),  # Console
    }
)


class SecurePage(QWebEnginePage):
    """Custom page that restricts navigation to the allowed host."""

    def __init__(self, config: ExamConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = config

    # ------------------------------------------------------------------
    # Navigation guard
    # ------------------------------------------------------------------

    def acceptNavigationRequest(
        self, url: QUrl, nav_type: QWebEnginePage.NavigationType, is_main_frame: bool
    ) -> bool:
        host = urlparse(url.toString()).netloc
        # Allow empty host (about:blank, data: URIs) and the exam host
        if not host or host == self.config.allowed_host:
            return True
        return False

    # Block new windows / tabs spawned by the page
    def createWindow(self, _type):
        return None


class SecureBrowser(QWebEngineView):
    """Locked-down web view.

    Emits ``quit_url_reached`` when the page navigates to the configured
    quit URL so the window can close without requiring a password.
    """

    quit_url_reached = Signal()

    def __init__(self, config: ExamConfig, quit_handler: QuitHandler) -> None:
        super().__init__()
        self.config = config
        self.quit_handler = quit_handler

        self._attach_secure_page()
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.urlChanged.connect(self._on_url_changed)
        self.setUrl(QUrl(self.config.start_url))

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _attach_secure_page(self) -> None:
        page = SecurePage(self.config, self)
        self.setPage(page)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_url_changed(self, url: QUrl) -> None:
        if self.quit_handler.is_quit_url(url.toString()):
            self.quit_url_reached.emit()

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def createWindow(self, _type):
        """Block popups / new-window requests at the view level too."""
        return None

    def keyPressEvent(self, event) -> None:
        key = event.key()
        mods = event.modifiers()

        if key in _BLOCKED_KEYS:
            event.accept()
            return

        if any(mods == m and key == k for m, k in _BLOCKED_COMBOS):
            event.accept()
            return

        super().keyPressEvent(event)
