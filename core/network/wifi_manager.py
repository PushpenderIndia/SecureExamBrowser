"""WiFi scanner and connector.

Backend selection
-----------------
macOS          : CoreWLAN (scan/connect) + CoreLocation (permission)
                 via  pyobjc-framework-CoreWLAN / pyobjc-framework-CoreLocation
Windows/Linux  : pywifi

All blocking OS calls run inside QThread workers so the UI never freezes.

macOS location-services note
-----------------------------
macOS 10.15+ hides WiFi SSIDs unless the app holds Location Services
permission (kCLAuthorizationStatusAuthorizedAlways / WhenInUse).

* Production app bundle  : add NSLocationWhenInUseUsageDescription and
  NSLocationAlwaysAndWhenInUseUsageDescription to Info.plist, then call
  WiFiManager.request_location_auth() once on startup.
* Development (Terminal) : System Settings → Privacy & Security →
  Location Services → Terminal → enable.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class WiFiNetwork:
    ssid:      str
    signal:    int    # 0 – 100
    secured:   bool
    connected: bool = False


def signal_bars(signal: int) -> str:
    """Return a 4-char signal indicator e.g. ``●●●○``."""
    filled = max(0, min(4, round(signal / 25)))
    return "●" * filled + "○" * (4 - filled)


def _dbm_to_pct(dbm: int) -> int:
    """Convert dBm (e.g. -65) to 0-100 %. Clamps to [0, 100]."""
    return max(0, min(100, 2 * (dbm + 100)))


# ── macOS backend ─────────────────────────────────────────────────────────────

def _macos_location_status() -> int:
    """Return CoreLocation authorization status (0–4)."""
    import CoreLocation                                         # noqa: PLC0415
    return CoreLocation.CLLocationManager.authorizationStatus()


def _macos_location_granted() -> bool:
    return _macos_location_status() in (3, 4)


def _macos_request_location(manager_holder: list) -> None:
    """Request Always authorization.  Keeps the manager alive via holder."""
    import CoreLocation                                         # noqa: PLC0415
    mgr = CoreLocation.CLLocationManager.alloc().init()
    manager_holder.append(mgr)          # prevent GC
    mgr.requestAlwaysAuthorization()


def _macos_location_error_msg() -> str:
    status = _macos_location_status()
    if status in (1, 2):
        return (
            "Location Services access denied.\n"
            "Go to  System Settings → Privacy & Security → Location Services\n"
            "and enable this app (or Terminal during development)."
        )
    # status == 0 (not determined) or anything else
    return (
        "Location Services permission is required to see WiFi network names.\n"
        "\n"
        "A permission dialog should appear — please click Allow.\n"
        "If no dialog appears, go to:\n"
        "  System Settings → Privacy & Security → Location Services\n"
        "and enable this app (or Terminal during development),\n"
        "then click Refresh."
    )


def _scan_macos() -> list[WiFiNetwork]:
    import CoreWLAN                                             # noqa: PLC0415
    client = CoreWLAN.CWWiFiClient.sharedWiFiClient()
    iface  = client.interface()
    if iface is None:
        return []

    current_ssid          = iface.ssid()
    network_set, error    = iface.scanForNetworksWithName_error_(None, None)
    if error or not network_set:
        return []

    result: list[WiFiNetwork] = []
    seen:   set[str]          = set()
    for n in network_set:
        ssid = n.ssid()
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        result.append(WiFiNetwork(
            ssid      = ssid,
            signal    = _dbm_to_pct(int(n.rssiValue())),
            secured   = not bool(n.isOpen()),
            connected = ssid == current_ssid,
        ))

    result.sort(key=lambda n: n.signal, reverse=True)
    return result


def _connect_macos(ssid: str, password: str) -> tuple[bool, str]:
    import CoreWLAN                                             # noqa: PLC0415
    client = CoreWLAN.CWWiFiClient.sharedWiFiClient()
    iface  = client.interface()
    if iface is None:
        return False, "No WiFi interface found."

    network_set, _ = iface.scanForNetworksWithName_error_(ssid, None)
    if not network_set:
        return False, f'Network "{ssid}" not found in scan.'

    # Pick closest (strongest RSSI) match
    target = max(network_set, key=lambda n: int(n.rssiValue()))

    ok, err = iface.associateToNetwork_password_error_(
        target, password if password else None, None
    )
    if ok:
        return True, f'Connected to "{ssid}".'
    return False, str(err) if err else f'Could not connect to "{ssid}".'


# ── pywifi backend  (Windows / Linux) ─────────────────────────────────────────

def _pywifi_iface():
    import pywifi                                               # noqa: PLC0415
    ifaces = pywifi.PyWiFi().interfaces()
    return ifaces[0] if ifaces else None


def _scan_pywifi() -> list[WiFiNetwork]:
    from pywifi import const                                    # noqa: PLC0415
    iface = _pywifi_iface()
    if iface is None:
        return []

    iface.scan()
    time.sleep(3)                     # wait for OS scan to complete
    raw = iface.scan_results()

    result: list[WiFiNetwork] = []
    seen:   set[str]          = set()
    for r in raw:
        ssid = (r.ssid or "").strip()
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        secured = bool(r.akm) and r.akm[0] != const.AKM_TYPE_NONE
        result.append(WiFiNetwork(
            ssid    = ssid,
            signal  = _dbm_to_pct(r.signal),
            secured = secured,
        ))

    result.sort(key=lambda n: n.signal, reverse=True)
    return result


def _connect_pywifi(ssid: str, password: str) -> tuple[bool, str]:
    import pywifi                                               # noqa: PLC0415
    from pywifi import const                                    # noqa: PLC0415

    iface = _pywifi_iface()
    if iface is None:
        return False, "No WiFi interface found."

    profile       = pywifi.Profile()
    profile.ssid  = ssid
    profile.auth  = const.AUTH_ALG_OPEN
    if password:
        profile.akm.append(const.AKM_TYPE_WPA2PSK)
        profile.cipher = const.CIPHER_TYPE_CCMP
        profile.key    = password
    else:
        profile.akm.append(const.AKM_TYPE_NONE)
        profile.cipher = const.CIPHER_TYPE_NONE

    iface.remove_all_network_profiles()
    tmp = iface.add_network_profile(profile)
    iface.connect(tmp)

    for _ in range(15):
        time.sleep(1)
        if iface.status() == const.IFACE_CONNECTED:
            return True, f'Connected to "{ssid}".'

    return False, f'Timed out waiting to connect to "{ssid}".'


# ── QThread workers ───────────────────────────────────────────────────────────

class _ScanWorker(QThread):
    done  = Signal(list)   # list[WiFiNetwork]
    error = Signal(str)

    def run(self) -> None:
        try:
            self.done.emit(
                _scan_macos() if sys.platform == "darwin" else _scan_pywifi()
            )
        except Exception as exc:
            self.error.emit(str(exc))
            self.done.emit([])


class _ConnectWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, ssid: str, password: str) -> None:
        super().__init__()
        self._ssid     = ssid
        self._password = password

    def run(self) -> None:
        try:
            fn  = _connect_macos if sys.platform == "darwin" else _connect_pywifi
            ok, msg = fn(self._ssid, self._password)
            self.done.emit(ok, msg)
        except Exception as exc:
            self.done.emit(False, str(exc))


# ── Public class ──────────────────────────────────────────────────────────────

class WiFiManager(QObject):
    """Non-blocking WiFi scanner and connector.

    Signals
    -------
    scan_complete(list[WiFiNetwork])
        Emitted when a scan finishes (list may be empty).
    scan_error(str)
        Emitted instead of scan_complete when a pre-scan check fails
        (e.g. missing location permission on macOS).
    connect_result(bool, str)
        Emitted when a connection attempt finishes.
    """

    scan_complete  = Signal(list)
    scan_error     = Signal(str)
    connect_result = Signal(bool, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._scan_worker:    _ScanWorker    | None = None
        self._connect_worker: _ConnectWorker | None = None
        # Holds the CLLocationManager alive on macOS after requesting auth
        self._loc_mgr_holder: list = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request_location_auth(self) -> None:
        """macOS only: show the system permission dialog.

        Must be called from the main thread.  Has no effect on other platforms
        or when permission is already granted.
        """
        if sys.platform != "darwin":
            return
        if not _macos_location_granted():
            _macos_request_location(self._loc_mgr_holder)

    def scan(self) -> None:
        """Start an async WiFi scan.  Results arrive via scan_complete or
        scan_error."""
        if self._scan_worker and self._scan_worker.isRunning():
            return

        worker = _ScanWorker(self)
        worker.done.connect(self.scan_complete)
        worker.error.connect(self.scan_error)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda: setattr(self, '_scan_worker', None))
        self._scan_worker = worker
        worker.start()

    def connect(self, ssid: str, password: str = "") -> None:
        """Connect to *ssid* asynchronously.  Result arrives via
        connect_result."""
        if self._connect_worker and self._connect_worker.isRunning():
            return

        worker = _ConnectWorker(ssid, password)
        worker.done.connect(self.connect_result)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda: setattr(self, '_connect_worker', None))
        self._connect_worker = worker
        worker.start()
