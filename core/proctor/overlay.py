from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QUrl, Qt, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from ..resources import resource_path


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
    dragStarted = Signal(int, int)
    dragMoved = Signal(int, int)
    dragEnded = Signal()

    @Slot()
    def startSession(self) -> None:
        self.sessionStarted.emit()

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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._drag_offset: QPoint | None = None
        self._bridge = ProctorBridge(self)
        self._build_ui()
        self._configure_bridge()
        self._apply_styles()

    def _build_ui(self) -> None:
        self.setObjectName("proctorOverlay")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(400, 225)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.web_view = ProctorWebView(self)
        self.web_view.load_proctor_client()

        layout.addWidget(self.web_view, 1)

    def _configure_bridge(self) -> None:
        channel = QWebChannel(self.web_view.page())
        channel.registerObject("proctorBridge", self._bridge)
        self.web_view.page().setWebChannel(channel)
        self._bridge.sessionStarted.connect(self.session_started)
        self._bridge.dragStarted.connect(self._start_drag)
        self._bridge.dragMoved.connect(self._drag_to)
        self._bridge.dragEnded.connect(self._end_drag)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QFrame#proctorOverlay {
                background: #0b1220;
                border: 1px solid #243145;
                border-radius: 14px;
            }
            """
        )

    def move_to_default_position(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = max(16, parent.width() - self.width() - 24)
        y = 72
        self.move(x, y)

    def keep_in_bounds(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        max_x = max(0, parent.width() - self.width() - 8)
        max_y = max(0, parent.height() - self.height() - 8)
        self.move(min(max(self.x(), 8), max_x), min(max(self.y(), 72), max_y))

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
