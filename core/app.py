import sys

from PySide6.QtWidgets import QApplication

from .config import ExamConfig
from .quit_handler import QuitHandler
from .window import ExamWindow


class ExamApp:
    """Wires together the Qt application, the quit handler, and the window."""

    def __init__(self, config: ExamConfig) -> None:
        self.qt_app = QApplication(sys.argv)
        self.quit_handler = QuitHandler(config)
        self.window = ExamWindow(config, self.quit_handler)

    def run(self) -> None:
        self.window.show()
        sys.exit(self.qt_app.exec())
