from __future__ import annotations

from collections.abc import Iterable


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(str(item) for item in value).lower()
    return str(value).lower()


def build_process_search_blob(name: object, exe: object, cmdline: object) -> str:
    return " ".join(
        part for part in (
            normalize_text(name),
            normalize_text(exe),
            normalize_text(cmdline),
        ) if part
    )


def matches_any_token(haystack: str, tokens: Iterable[str]) -> bool:
    return any(token in haystack for token in tokens)


def extract_remote_endpoint(raddr: object) -> tuple[str, int] | None:
    if not raddr:
        return None

    ip = getattr(raddr, "ip", None)
    port = getattr(raddr, "port", None)

    if ip is not None and port is not None:
        return str(ip), int(port)

    if isinstance(raddr, tuple) and len(raddr) >= 2:
        return str(raddr[0]), int(raddr[1])

    return None
