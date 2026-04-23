"""Internet connectivity monitor.

Primary:  ``QNetworkInformation`` — OS-level reachability events (no polling).
Fallback: Periodic HTTP HEAD probe when no backend is available.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkInformation,
    QNetworkReply,
    QNetworkRequest,
)

# Lightweight connectivity-check endpoint (returns HTTP 204, no body)
_PROBE_URL = "http://clients3.google.com/generate_204"
_POLL_INTERVAL_MS = 5_000


class NetworkMonitor(QObject):
    """Emits :attr:`connectivity_changed` whenever the internet status flips.

    Signals
    -------
    connectivity_changed(bool)
        ``True``  → just came online.
        ``False`` → just went offline.
    """

    connectivity_changed = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._online: bool = True
        self._nam: QNetworkAccessManager | None = None

        if QNetworkInformation.loadDefaultBackend():
            info = QNetworkInformation.instance()
            self._online = (
                info.reachability() == QNetworkInformation.Reachability.Online
            )
            info.reachabilityChanged.connect(self._on_reachability_changed)
        else:
            self._start_polling()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def is_online(self) -> bool:
        return self._online

    # ------------------------------------------------------------------
    # QNetworkInformation path
    # ------------------------------------------------------------------

    def _on_reachability_changed(
        self, reachability: QNetworkInformation.Reachability
    ) -> None:
        self._emit_if_changed(
            reachability == QNetworkInformation.Reachability.Online
        )

    # ------------------------------------------------------------------
    # Polling fallback path
    # ------------------------------------------------------------------

    def _start_polling(self) -> None:
        self._nam = QNetworkAccessManager(self)
        timer = QTimer(self)
        timer.setInterval(_POLL_INTERVAL_MS)
        timer.timeout.connect(self._probe)
        timer.start()
        self._probe()  # immediate first check

    def _probe(self) -> None:
        assert self._nam is not None
        request = QNetworkRequest(QUrl(_PROBE_URL))
        # Never serve from cache — we need a live round-trip
        request.setAttribute(
            QNetworkRequest.Attribute.CacheLoadControlAttribute,
            QNetworkRequest.CacheLoadControl.AlwaysNetwork,
        )
        reply = self._nam.head(request)
        reply.finished.connect(lambda: self._on_probe_finished(reply))

    def _on_probe_finished(self, reply: QNetworkReply) -> None:
        online = reply.error() == QNetworkReply.NetworkError.NoError
        reply.deleteLater()
        self._emit_if_changed(online)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit_if_changed(self, online: bool) -> None:
        if online != self._online:
            self._online = online
            self.connectivity_changed.emit(online)
