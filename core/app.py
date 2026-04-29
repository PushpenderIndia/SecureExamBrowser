import logging
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from .config import ExamConfig
from .network import NetworkMonitor, WiFiManager
from .quit_handler import QuitHandler
from .single_instance import SingleInstanceGuard
from .system import RemoteAccessMonitor, SystemGuard, VMDetector
from .window import ExamWindow

logger = logging.getLogger(__name__)


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
        self.qt_app              = QApplication(sys.argv)
        self.single_instance     = SingleInstanceGuard()
        self.quit_handler        = QuitHandler(config)
        self.network_monitor     = NetworkMonitor()
        self.wifi_manager        = WiFiManager()
        self.system_guard        = SystemGuard()
        self.remote_access_monitor = RemoteAccessMonitor()
        self.window = ExamWindow(
            config,
            self.quit_handler,
            self.network_monitor,
            self.wifi_manager,
        )

    def run(self) -> None:
        self._block_if_duplicate()
        self._block_if_vm()
        self.qt_app.aboutToQuit.connect(self.single_instance.release)
        self.system_guard.activate()
        self.qt_app.aboutToQuit.connect(self.system_guard.deactivate)
        self.remote_access_monitor.start()
        self.qt_app.aboutToQuit.connect(self.remote_access_monitor.stop)
        self.window.show()
        QTimer.singleShot(0, self.system_guard.activate_kiosk)
        sys.exit(self.qt_app.exec())

    # ------------------------------------------------------------------
    # Duplicate-instance guard
    # ------------------------------------------------------------------

    def _block_if_duplicate(self) -> None:
        if self.single_instance.acquire():
            return

        logger.warning("Duplicate instance detected — blocking second launch")
        QMessageBox.warning(
            None,
            "Already Running",
            "Secure Exam Browser is already open.\n\n"
            "Only one instance is allowed at a time.\n"
            "Please use the existing window to continue your exam.",
        )
        sys.exit(1)

    # ------------------------------------------------------------------
    # VM guard
    # ------------------------------------------------------------------

    def _block_if_vm(self) -> None:
        result = VMDetector().scan()
        if not result.is_vm:
            return

        logger.warning("VM detected — blocking exam start. %s", result.summary)
        QMessageBox.critical(
            None,
            "Virtual Machine Detected",
            f"This exam cannot be taken inside a virtual machine.\n\n"
            f"Detected: {result.summary}\n\n"
            "Please use a physical device and restart the exam browser.",
        )
        sys.exit(1)
