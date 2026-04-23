import sys

from PySide6.QtWidgets import QApplication

from .config import ExamConfig
from .network import NetworkMonitor, WiFiManager
from .quit_handler import QuitHandler
from .system import SystemGuard
from .window import ExamWindow


class ExamApp:
    """Wires together every top-level service and the main window.

    Service lifecycle
    -----------------
    SystemGuard  : activated just before the event loop starts; deactivated
                   via QApplication.aboutToQuit so the OS is always restored.
    NetworkMonitor / WiFiManager : live for the full session.
    QuitHandler  : stateless helper, lives with this object.
    """

    def __init__(self, config: ExamConfig) -> None:
        self.qt_app         = QApplication(sys.argv)
        self.quit_handler   = QuitHandler(config)
        self.network_monitor = NetworkMonitor()
        self.wifi_manager   = WiFiManager()
        self.system_guard   = SystemGuard()
        self.window = ExamWindow(
            config,
            self.quit_handler,
            self.network_monitor,
            self.wifi_manager,
        )

    def run(self) -> None:
        self.system_guard.activate()
        self.qt_app.aboutToQuit.connect(self.system_guard.deactivate)
        self.window.show()
        sys.exit(self.qt_app.exec())
