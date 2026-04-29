import hashlib
from urllib.parse import urlparse

from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox

from .config import ExamConfig


class QuitHandler:

    def __init__(self, config: ExamConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_password(self, parent) -> bool:
        """Show a password dialog.  Returns True only on correct input."""
        password, ok = QInputDialog.getText(
            parent,
            "Exit Exam",
            "Enter quit password:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return False

        entered_hash = hashlib.sha256(password.encode()).hexdigest()
        if entered_hash == self.config.hashed_quit_password:
            return True
        QMessageBox.warning(parent, "Access Denied", "Incorrect password.")
        return False

    def is_quit_url(self, url_string: str) -> bool:
        """Return True if *url_string* matches the configured quit URL."""
        if not self.config.quit_url:
            return False
        current = urlparse(url_string)
        target = urlparse(self.config.quit_url)
        return current.netloc == target.netloc and current.path == target.path
