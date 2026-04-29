"""Single-instance guard: prevents more than one copy of the exam browser.

Strategy
--------
The first process that calls :meth:`SingleInstanceGuard.acquire` starts a
``QLocalServer`` bound to a fixed name.  Any subsequent process that calls
``acquire`` finds the server already listening, detects the existing instance
via ``QLocalSocket``, and returns ``False``.

On Unix the server lives as an abstract socket (no file left behind).
On Windows it becomes a named pipe.  Either way, ``QLocalServer.removeServer``
cleans up a stale socket left by a previous crash before a new server starts.

Requires ``QApplication`` to exist before instantiation.
"""

from __future__ import annotations

import logging

from PySide6.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger(__name__)

_SERVER_NAME = "SecureExamBrowser_SingleInstance_v1"
_CONNECT_TIMEOUT_MS = 300


class SingleInstanceGuard:
    """Acquire / release a cross-platform single-instance lock.

    Typical usage in ExamApp::

        guard = SingleInstanceGuard()
        if not guard.acquire():
            # show dialog, sys.exit(1)
        app.aboutToQuit.connect(guard.release)
    """

    def __init__(self) -> None:
        self._server: QLocalServer | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def acquire(self) -> bool:
        """Attempt to become the sole running instance.

        Returns ``True``  — this process owns the lock (first instance).
        Returns ``False`` — another instance is already running.
        """
        if self._is_already_running():
            logger.warning(
                "SingleInstanceGuard: duplicate instance detected on '%s'",
                _SERVER_NAME,
            )
            return False

        self._server = QLocalServer()
        # Allow any local user to connect (needed on some Linux/macOS configs)
        self._server.setSocketOptions(QLocalServer.SocketOption.WorldAccessOption)

        # Remove a stale socket left by a previous hard-crash
        QLocalServer.removeServer(_SERVER_NAME)

        if not self._server.listen(_SERVER_NAME):
            logger.error(
                "SingleInstanceGuard: failed to start server: %s",
                self._server.errorString(),
            )
            # Fail open — a listen failure is not a duplicate instance; let the
            # app proceed rather than falsely blocking a legitimate launch.
            self._server = None
            return True

        logger.debug("SingleInstanceGuard: lock acquired on '%s'", _SERVER_NAME)
        return True

    def release(self) -> None:
        """Release the lock.  Safe to call more than once.

        Connect this to ``QApplication.aboutToQuit`` so the socket is always
        removed even when the app exits normally.
        """
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(_SERVER_NAME)
            self._server = None
            logger.debug("SingleInstanceGuard: lock released")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _is_already_running(self) -> bool:
        """Return ``True`` if a live server is already listening on the name."""
        sock = QLocalSocket()
        sock.connectToServer(_SERVER_NAME)
        alive = sock.waitForConnected(_CONNECT_TIMEOUT_MS)
        if alive:
            sock.disconnectFromServer()
        sock.deleteLater()
        return alive
