"""Self-register the .sebexam file association on first run.

macOS  — handled automatically by CFBundleDocumentTypes in Info.plist.
Windows — writes to HKCU\Software\Classes (no admin required).
Linux   — writes a .desktop file and calls xdg-mime.
"""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_registered() -> None:
    """Register .sebexam → this executable if not already set up."""
    if sys.platform == "win32":
        _register_windows()
    elif sys.platform.startswith("linux"):
        _register_linux()
    # macOS: Info.plist + argv_emulation handles it — nothing to do at runtime.


# ── Windows ──────────────────────────────────────────────────────────────────

def _register_windows() -> None:
    import winreg

    exe = _exe_path()
    command = f'"{exe}" "%1"'

    # Check if already registered to this exe
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Classes\SecureExamBrowserConfig\shell\open\command",
        ) as key:
            existing, _ = winreg.QueryValueEx(key, "")
            if existing == command:
                return  # already up to date
    except FileNotFoundError:
        pass  # not registered yet

    root = winreg.HKEY_CURRENT_USER

    def _set(path: str, value: str) -> None:
        with winreg.CreateKey(root, path) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, value)

    _set(r"Software\Classes\.sebexam",                                   "SecureExamBrowserConfig")
    _set(r"Software\Classes\SecureExamBrowserConfig",                    "Secure Exam Browser Config")
    _set(r"Software\Classes\SecureExamBrowserConfig\DefaultIcon",        f'"{exe}",0')
    _set(r"Software\Classes\SecureExamBrowserConfig\shell\open\command", command)

    # Notify the shell so the icon refreshes without a reboot
    try:
        from ctypes import windll
        windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:
        pass


# ── Linux ─────────────────────────────────────────────────────────────────────

def _register_linux() -> None:
    import subprocess

    exe = _exe_path()
    desktop_dir = Path.home() / ".local" / "share" / "applications"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    desktop_file = desktop_dir / "secureexambrowser.desktop"

    content = (
        "[Desktop Entry]\n"
        "Name=Secure Exam Browser\n"
        "Type=Application\n"
        f"Exec={exe} %f\n"
        "MimeType=application/x-sebexam;\n"
        "NoDisplay=true\n"
    )

    if desktop_file.exists() and desktop_file.read_text() == content:
        return  # already up to date

    desktop_file.write_text(content)

    try:
        subprocess.run(
            ["xdg-mime", "default", "secureexambrowser.desktop", "application/x-sebexam"],
            check=True, capture_output=True,
        )
    except Exception:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _exe_path() -> str:
    """Return the running executable path (works for both PyInstaller and source)."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return str(Path(sys.argv[0]).resolve())
