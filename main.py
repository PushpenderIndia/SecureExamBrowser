import sys
from pathlib import Path

from core import ExamApp, ExamConfig, load_seb_file
from core.file_association import ensure_registered

# sha256("admin123") — used as both admin and quit password when no .seb is loaded
_ADMIN123_HASH = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"

_DEFAULT_CONFIG = ExamConfig(
    start_url="https://www.codechef.com/",
    quit_url="https://www.codechef.com/ide",
    window_title="Secure Exam Browser",
    duration_minutes=75,
    hashed_quit_password=_ADMIN123_HASH,
)


def _resolve_config() -> ExamConfig:
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.suffix.lower() == ".sebexam" and p.is_file():
            return load_seb_file(p)
    return _DEFAULT_CONFIG


def main() -> None:
    ensure_registered()
    ExamApp(_resolve_config()).run()


if __name__ == "__main__":
    main()
