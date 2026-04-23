from __future__ import annotations

import logging
import socket
import time

from PySide6.QtCore import QObject, QTimer

from .policy import DEFAULT_REMOTE_ACCESS_POLICY, RemoteAccessPolicy
from .process_utils import (
    build_process_search_blob,
    extract_remote_endpoint,
    matches_any_token,
)

try:
    import psutil
except ImportError:  # pragma: no cover - handled gracefully at runtime
    psutil = None


logger = logging.getLogger(__name__)


class RemoteAccessMonitor(QObject):
    """Best-effort monitor for banned remote-access software and endpoints."""

    def __init__(
        self,
        policy: RemoteAccessPolicy = DEFAULT_REMOTE_ACCESS_POLICY,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._policy = policy
        self._timer = QTimer(self)
        self._timer.setInterval(policy.scan_interval_ms)
        self._timer.timeout.connect(self._scan_once)
        self._domain_ips: set[str] = set()
        self._last_domain_refresh: float = 0.0
        self._action_cooldowns: dict[int, float] = {}
        self._current_pid: int | None = None

    def start(self) -> None:
        if psutil is None:
            logger.warning("psutil is not installed; remote-access monitor disabled")
            return

        self._current_pid = psutil.Process().pid
        self._refresh_domain_ips(force=True)
        self._scan_once()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self._action_cooldowns.clear()

    def _scan_once(self) -> None:
        if psutil is None:
            return

        self._refresh_domain_ips()
        self._terminate_banned_processes()
        self._terminate_banned_connections()
        self._prune_cooldowns()

    def _refresh_domain_ips(self, force: bool = False) -> None:
        now = time.monotonic()
        age_ms = (now - self._last_domain_refresh) * 1000
        if not force and age_ms < self._policy.dns_refresh_interval_ms:
            return

        resolved_ips: set[str] = set()
        for domain in self._policy.domains:
            try:
                infos = socket.getaddrinfo(domain, None, proto=socket.IPPROTO_TCP)
            except OSError:
                continue

            for info in infos:
                sockaddr = info[4]
                if sockaddr:
                    resolved_ips.add(str(sockaddr[0]))

        self._domain_ips = resolved_ips
        self._last_domain_refresh = now

    def _terminate_banned_processes(self) -> None:
        assert psutil is not None

        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            try:
                if proc.pid == self._current_pid:
                    continue

                searchable = build_process_search_blob(
                    proc.info.get("name"),
                    proc.info.get("exe"),
                    proc.info.get("cmdline"),
                )
                if not searchable:
                    continue

                if matches_any_token(searchable, self._policy.process_tokens):
                    self._terminate_process(proc, "matched deny-listed process name")
                elif matches_any_token(searchable, self._policy.domains):
                    self._terminate_process(proc, "matched deny-listed remote domain")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def _terminate_banned_connections(self) -> None:
        assert psutil is not None

        try:
            connections = psutil.net_connections(kind="inet")
        except (psutil.AccessDenied, psutil.Error):
            return

        for connection in connections:
            endpoint = extract_remote_endpoint(getattr(connection, "raddr", None))
            if endpoint is None or connection.pid is None:
                continue

            remote_ip, remote_port = endpoint
            if (
                remote_port in self._policy.ports
                or remote_ip in self._domain_ips
            ):
                try:
                    proc = psutil.Process(connection.pid)
                    self._terminate_process(
                        proc,
                        f"connected to deny-listed endpoint {remote_ip}:{remote_port}",
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

    def _terminate_process(self, proc: "psutil.Process", reason: str) -> None:
        assert psutil is not None

        if not self._should_act(proc.pid):
            return

        name = proc.info.get("name") if hasattr(proc, "info") else proc.name()
        logger.warning(
            "Terminating process pid=%s name=%s reason=%s",
            proc.pid,
            name,
            reason,
        )
        self._action_cooldowns[proc.pid] = time.monotonic()

        try:
            proc.terminate()
            proc.wait(timeout=2)
        except psutil.TimeoutExpired:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def _should_act(self, pid: int) -> bool:
        last_action = self._action_cooldowns.get(pid, 0.0)
        return (time.monotonic() - last_action) >= 5.0

    def _prune_cooldowns(self) -> None:
        now = time.monotonic()
        stale_pids = [
            pid for pid, ts in self._action_cooldowns.items()
            if (now - ts) >= 60.0
        ]
        for pid in stale_pids:
            self._action_cooldowns.pop(pid, None)
