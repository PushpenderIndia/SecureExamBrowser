from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ExamConfig:
    start_url: str
    quit_url: str = ""
    window_title: str = "Secure Exam Browser"
    duration_minutes: int | None = None
    hashed_quit_password: str = ""

    @property
    def allowed_host(self) -> str:
        return urlparse(self.start_url).netloc
