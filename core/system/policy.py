from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RemoteAccessPolicy:
    process_tokens: tuple[str, ...]
    domains: tuple[str, ...]
    ports: tuple[int, ...]
    scan_interval_ms: int = 3_000
    dns_refresh_interval_ms: int = 300_000


DEFAULT_REMOTE_ACCESS_POLICY = RemoteAccessPolicy(
    process_tokens=(
        "slack",
        "whatsapp",
        "teamviewer",
        "anydesk",
        "vscode",
        "rustdesk",
        "parsec",
        "splashtop",
        "logmein",
        "gotomypc",
        "connectwisecontrol",
        "screenconnect",
        "remmina",
        "nomachine",
        "realvnc",
        "tightvnc",
        "ultravnc",
        "tigervnc",
        "vncviewer",
        "x11vnc",
        "aeroadmin",
        "dwservice",
        "chrome-remote-desktop",
        "chromoting",
        "msteams remote control",
        "quickassist",
        "quick assist",
        "remote utilities",
        "radmin",
    ),
    domains=(
        "teamviewer.com",
        "anydesk.com",
        "rustdesk.com",
        "parsec.app",
        "parsecgaming.com",
        "splashtop.com",
        "logmein.com",
        "goto.com",
        "gotomypc.com",
        "connectwise.com",
        "screenconnect.com",
        "realvnc.com",
        "ultravnc.com",
        "tightvnc.com",
        "nomachine.com",
        "remmina.org",
        "chrome.remote.desktop.google.com",
        "remotedesktop.google.com",
        "chromoting.com",
        "dwservice.net",
        "aeroadmin.com",
        "radmin.com",
    ),
    ports=(
        5938,
        6568,
        7070,
        7071,
        21115,
        21116,
        21117,
        21118,
        21119,
        4899,
        5500,
        5900,
        5901,
        5902,
        3389,
    ),
)
