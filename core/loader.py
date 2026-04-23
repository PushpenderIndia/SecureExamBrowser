"""Load ExamConfig from a TOML file.

Uses the standard-library ``tomllib`` (Python 3.11+).

Config file resolution order
-----------------------------
1. Explicit *path* argument passed to :func:`load_config`.
2. ``<exe dir>/config.toml`` when running as a PyInstaller bundle
   (next to the ``.exe`` / binary on Windows & Linux, or next to the
   ``.app`` bundle on macOS).
3. ``<project root>/config.toml`` when running from source.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from .config import ExamConfig


def _default_config_path() -> Path:
    """Return the expected location of ``config.toml``."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        # macOS .app bundle layout:  Foo.app/Contents/MacOS/<binary>
        # Place config.toml next to the .app bundle, not inside it.
        if sys.platform == "darwin" and exe.parent.name == "MacOS":
            return exe.parent.parent.parent.parent / "config.toml"
        # Windows / Linux --onefile: binary sits at the install root.
        return exe.parent / "config.toml"

    # Running from source: project root is one level above core/
    return Path(__file__).parent.parent / "config.toml"


def load_config(path: Path | str | None = None) -> ExamConfig:
    """Parse *path* (defaults to ``config.toml`` next to the executable /
    project root) and return an :class:`ExamConfig`.

    Raises
    ------
    FileNotFoundError
        When the config file does not exist.
    KeyError
        When a required key is missing from the ``[exam]`` table.
    """
    config_path = Path(path) if path else _default_config_path()

    if not config_path.is_file():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            "Copy config.example.toml → config.toml and fill in your values."
        )

    with config_path.open("rb") as fh:
        data = tomllib.load(fh)

    try:
        exam = data["exam"]
    except KeyError:
        raise KeyError("config.toml must contain an [exam] table.")

    try:
        return ExamConfig(
            start_url=exam["start_url"],
            quit_password=exam["quit_password"],
            quit_url=exam.get("quit_url", ""),
            window_title=exam.get("window_title", "Secure Exam Browser"),
        )
    except KeyError as exc:
        raise KeyError(f"Missing required key in [exam]: {exc}") from exc
