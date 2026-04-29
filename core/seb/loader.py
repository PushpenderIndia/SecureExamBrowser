"""Load ExamConfig from a .sebexam file (gzip-compressed Apple plist)."""

from __future__ import annotations

import gzip
import plistlib
from pathlib import Path

from ..config import ExamConfig


def load_seb_file(path: Path | str) -> ExamConfig:
    """Parse *path* (.seb) and return an ExamConfig.

    Password mapping
    ----------------
    .seb files store passwords as SHA-256 hashes.  If hashedQuitPassword is
    non-empty it is used directly; otherwise hashedAdminPassword is used so
    the admin password doubles as the quit credential.
    """
    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(f".seb file not found: {path}")

    try:
        with gzip.open(path, "rb") as gz:
            data = plistlib.load(gz)
    except Exception as exc:
        raise ValueError(f"Cannot parse .seb file '{path}': {exc}") from exc

    start_url: str = data.get("startURL", "")
    if not start_url:
        raise ValueError(f"'startURL' missing in {path.name}")

    quit_url: str = data.get("quitURL", "")

    # Prefer the explicit quit password; fall back to admin password.
    hashed_quit_password: str = (
        data.get("hashedQuitPassword") or data.get("hashedAdminPassword") or ""
    )

    return ExamConfig(
        start_url=start_url,
        quit_url=quit_url,
        window_title=path.stem,
        hashed_quit_password=hashed_quit_password,
    )
