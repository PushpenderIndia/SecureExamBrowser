from __future__ import annotations

import hashlib
import platform
import subprocess

_cached_uid: str | None = None


def get_device_uid() -> str:
    """Return a stable 12-char UID derived from a hardware identifier.

    Source per platform:
      macOS   — IOPlatformUUID via ioreg (board-level, survives OS upgrades)
      Windows — MachineGuid from registry (set at Windows install)
      Linux   — /etc/machine-id (set at OS install, survives upgrades)

    The raw value is SHA-256-hashed so hardware IDs are never exposed.
    Result is cached for the lifetime of the process.
    """
    global _cached_uid
    if _cached_uid is None:
        raw    = _raw_id()
        digest = hashlib.sha256(raw.encode()).hexdigest().upper()
        _cached_uid = f"{digest[0:4]}-{digest[4:8]}-{digest[8:12]}"
    return _cached_uid


# ------------------------------------------------------------------
# Platform helpers
# ------------------------------------------------------------------

def _raw_id() -> str:
    system = platform.system()
    if system == "Darwin":
        return _macos_id()
    if system == "Windows":
        return _windows_id()
    return _linux_id()


def _macos_id() -> str:
    try:
        out = subprocess.check_output(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).decode()
        for line in out.splitlines():
            if "IOPlatformUUID" in line:
                parts = line.split('"')
                if len(parts) >= 4:
                    return parts[-2]
    except Exception:
        pass
    return _fallback()


def _windows_id() -> str:
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
        )
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return str(value)
    except Exception:
        pass
    return _fallback()


def _linux_id() -> str:
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(path) as f:
                value = f.read().strip()
            if value:
                return value
        except OSError:
            pass
    return _fallback()


def _fallback() -> str:
    import socket
    return socket.gethostname()
