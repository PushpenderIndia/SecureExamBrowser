from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QUrl, Qt, Signal, QSize, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QFrame, QStackedWidget, QVBoxLayout, QWidget

from ..resources import resource_path
from .intro import IntroWidget


class ProctorPage(QWebEnginePage):
    """Local web page that auto-grants camera and microphone access."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.featurePermissionRequested.connect(self._grant_feature_permission)

    def _grant_feature_permission(self, security_origin, feature) -> None:
        allowed_features = {
            QWebEnginePage.Feature.MediaAudioCapture,
            QWebEnginePage.Feature.MediaVideoCapture,
            QWebEnginePage.Feature.MediaAudioVideoCapture,
        }
        policy = (
            QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
            if feature in allowed_features
            else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
        )
        self.setFeaturePermission(security_origin, feature, policy)


class ProctorWebView(QWebEngineView):
    """Hosts the local proctoring client."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._configure_page()
        self.setContextMenuPolicy(Qt.NoContextMenu)

    def _configure_page(self) -> None:
        page = ProctorPage(self)
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, False)
        self.setPage(page)

    def load_proctor_client(self) -> None:
        self.setUrl(QUrl.fromLocalFile(str(resource_path("assets", "proctor", "index.html"))))


class ProctorBridge(QObject):
    """Bridge events from the embedded proctor page into Qt."""

    sessionStarted = Signal()
    quitRequested = Signal()
    dragStarted = Signal(int, int)
    dragMoved = Signal(int, int)
    dragEnded = Signal()

    @Slot()
    def startSession(self) -> None:
        self.sessionStarted.emit()

    @Slot()
    def quitApp(self) -> None:
        self.quitRequested.emit()

    @Slot(int, int)
    def startDrag(self, screen_x: int, screen_y: int) -> None:
        self.dragStarted.emit(screen_x, screen_y)

    @Slot(int, int)
    def dragTo(self, screen_x: int, screen_y: int) -> None:
        self.dragMoved.emit(screen_x, screen_y)

    @Slot()
    def endDrag(self) -> None:
        self.dragEnded.emit()


class ProctorOverlay(QFrame):
    """Movable overlay window shown above the exam browser."""

    session_started = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_offset: QPoint | None = None
        self._compact_size = QSize(400, 225)
        self._compact_mode = False
        self._bridge = ProctorBridge(self)
        self._build_ui()
        self._configure_bridge()
        self._apply_styles()
        self.enter_onboarding_mode()

    def _build_ui(self) -> None:
        self.setObjectName("proctorOverlay")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget(self)

        # Page 0 – native intro widget (appears instantly, no WebEngine needed)
        self._intro = IntroWidget(self)
        self._intro.quit_requested.connect(self.quit_requested)
        self._intro.continue_requested.connect(self._on_intro_continue)

        # Page 1 – proctoring WebView (starts loading index.html immediately
        #           in the background so models are warm by the time the user
        #           finishes the intro)
        self.web_view = ProctorWebView(self)
        self.web_view.load_proctor_client()

        self._stack.addWidget(self._intro)    # index 0
        self._stack.addWidget(self.web_view)  # index 1
        self._stack.setCurrentIndex(0)

        layout.addWidget(self._stack, 1)

    def _configure_bridge(self) -> None:
        channel = QWebChannel(self.web_view.page())
        channel.registerObject("proctorBridge", self._bridge)
        self.web_view.page().setWebChannel(channel)
        self._bridge.sessionStarted.connect(self.session_started)
        self._bridge.quitRequested.connect(self.quit_requested)
        self._bridge.dragStarted.connect(self._start_drag)
        self._bridge.dragMoved.connect(self._drag_to)
        self._bridge.dragEnded.connect(self._end_drag)

    @Slot()
    def _on_intro_continue(self) -> None:
        """Switch from the native intro to the proctoring WebView."""
        self._stack.setCurrentIndex(1)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QFrame#proctorOverlay {
                background: #0b1220;
            }
            QFrame#proctorOverlay[compactMode="true"] {
                border: 1px solid #243145;
                border-radius: 14px;
            }
            QFrame#proctorOverlay[compactMode="false"] {
                border: 0;
                border-radius: 0;
            }
            """
        )

    def _refresh_style(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _content_rect(self):
        parent = self.parentWidget()
        if parent is None:
            return self.rect()
        central_widget = getattr(parent, "centralWidget", lambda: None)()
        if central_widget is None:
            return parent.rect()
        return central_widget.geometry()

    def enter_onboarding_mode(self) -> None:
        self._compact_mode = False
        self.setProperty("compactMode", False)
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.setGeometry(self._content_rect())
        self._refresh_style()

    def enter_compact_mode(self) -> None:
        self._compact_mode = True
        self.setProperty("compactMode", True)
        self.setFixedSize(self._compact_size)
        self._refresh_style()
        self.move_to_default_position()

    def move_to_default_position(self) -> None:
        if not self._compact_mode:
            return
        content_rect = self._content_rect()
        x = max(content_rect.left() + 16, content_rect.right() - self.width() - 24)
        y = content_rect.top() + 16
        self.move(x, y)

    def keep_in_bounds(self) -> None:
        content_rect = self._content_rect()
        if not self._compact_mode:
            self.setGeometry(content_rect)
            return
        min_x = content_rect.left() + 8
        min_y = content_rect.top() + 8
        max_x = max(min_x, content_rect.right() - self.width() - 8)
        max_y = max(min_y, content_rect.bottom() - self.height() - 8)
        self.move(min(max(self.x(), min_x), max_x), min(max(self.y(), min_y), max_y))

    @Slot(int, int)
    def _start_drag(self, screen_x: int, screen_y: int) -> None:
        self._drag_offset = QPoint(screen_x, screen_y) - self.frameGeometry().topLeft()

    @Slot(int, int)
    def _drag_to(self, screen_x: int, screen_y: int) -> None:
        if self._drag_offset is None:
            return
        self.move(QPoint(screen_x, screen_y) - self._drag_offset)
        self.keep_in_bounds()

    @Slot()
    def _end_drag(self) -> None:
        self._drag_offset = None
