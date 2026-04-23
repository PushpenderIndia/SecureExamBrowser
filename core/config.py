from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class ExamConfig:
    # Required
    start_url: str
    quit_password: str

    # Optional — navigate to this URL to auto-quit without a password prompt
    quit_url: str = ""

    # UI
    window_title: str = "Secure Exam Browser"

    # Derived: host that the browser is allowed to stay on
    @property
    def allowed_host(self) -> str:
        return urlparse(self.start_url).netloc
