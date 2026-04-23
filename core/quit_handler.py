from urllib.parse import urlparse

from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox

from .config import ExamConfig


class QuitHandler:
    """Owns all quit-authorization logic.

    Two ways to authorize a quit:
      1. Password prompt  — used when the user clicks Quit or presses a close
                           shortcut.
      2. Quit URL         — when the browser lands on ``config.quit_url`` the
                           app exits silently (no password required).  This lets
                           the exam platform redirect the student to a known
                           "submission confirmed" page to end the session.
    """

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
        if ok and password == self.config.quit_password:
            return True
        if ok:
            QMessageBox.warning(parent, "Access Denied", "Incorrect password.")
        return False

    def is_quit_url(self, url_string: str) -> bool:
        """Return True if *url_string* matches the configured quit URL."""
        if not self.config.quit_url:
            return False
        current = urlparse(url_string)
        target = urlparse(self.config.quit_url)
        return current.netloc == target.netloc and current.path == target.path
