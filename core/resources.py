from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Resolve project assets both from source and PyInstaller bundles."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent.parent
    return base_path.joinpath(*parts)
