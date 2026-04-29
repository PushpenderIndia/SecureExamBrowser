"""Virtual Machine detection for the Secure Exam Browser.

Detection strategy
------------------
Six independent checks are run; each fires one or more :class:`VMEvidence`
records carrying a *weight* (0–1) that represents its individual reliability.

Final result
------------
* ``is_vm``      — True when the highest single-evidence weight ≥
                   :data:`VM_CONFIDENCE_THRESHOLD` (0.5)
* ``confidence`` — highest weight seen across all evidence
* ``hypervisor`` — vendor string from that highest-weight check

Checks (in order)
-----------------
1. :class:`CpuidHypervisorCheck`   — OS hypervisor flag (sysctl / procfs / WMI)
2. :class:`HardwareVendorCheck`    — manufacturer/model strings from DMI / WMI
3. :class:`VMProcessCheck`         — running VM guest-agent processes
4. :class:`VMFileCheck`            — well-known VM guest-tools file paths
5. :class:`MacAddressCheck`        — virtual NIC OUI prefixes
6. :class:`WindowsRegistryCheck`   — VM guest-tools registry keys (Windows-only)
"""

from __future__ import annotations

import abc
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import ClassVar

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

VM_CONFIDENCE_THRESHOLD = 0.5

# ---------------------------------------------------------------------------
# Static lookup tables
# ---------------------------------------------------------------------------

_KNOWN_VM_VENDOR_SUBSTRINGS: frozenset[str] = frozenset({
    "vmware",
    "virtualbox",
    "vbox",
    "qemu",
    "kvm",
    "xen",
    "parallels",
    "innotek",       # VirtualBox legacy vendor
    "bochs",
    "bhyve",
    "hyper-v",
    "virtual machine",
    "amazon ec2",
    "google compute engine",
})

_VM_PROCESSES: dict[str, str] = {
    "vmtoolsd":        "VMware",
    "vmwaretray":      "VMware",
    "vmwareuser":      "VMware",
    "vmware-tray":     "VMware",
    "vmware-user":     "VMware",
    "vboxservice":     "VirtualBox",
    "vboxtray":        "VirtualBox",
    "vboxclient":      "VirtualBox",
    "prl_tools":       "Parallels",
    "prl_cc":          "Parallels",
    "prl_disp":        "Parallels",
    "qemu-ga":         "QEMU",
    "xe-daemon":       "Xen",
    "xenstore":        "Xen",
    "hv_kvp_daemon":   "Hyper-V",
    "hv_vss_daemon":   "Hyper-V",
}

_VM_FILES_LINUX: dict[str, str] = {
    "/sys/bus/pci/drivers/vmxnet3":              "VMware",
    "/sys/bus/pci/drivers/prl_tg":               "Parallels",
    "/sys/bus/pci/drivers/vboxguest":            "VirtualBox",
    "/usr/bin/VBoxClient":                       "VirtualBox",
    "/usr/sbin/vboxadd-service":                 "VirtualBox",
    "/usr/sbin/vmware-guestproxycerttool":       "VMware",
    "/usr/bin/vmware-user":                      "VMware",
}

_VM_FILES_WINDOWS: dict[str, str] = {
    r"C:\Windows\System32\Drivers\vmmouse.sys":              "VMware",
    r"C:\Windows\System32\Drivers\vmhgfs.sys":               "VMware",
    r"C:\Windows\System32\Drivers\VBoxMouse.sys":            "VirtualBox",
    r"C:\Windows\System32\Drivers\VBoxGuest.sys":            "VirtualBox",
    r"C:\Program Files\VMware\VMware Tools":                 "VMware",
    r"C:\Program Files\Oracle\VirtualBox Guest Additions":   "VirtualBox",
}

_VM_MAC_OUI_TO_VENDOR: dict[str, str] = {
    "00:50:56": "VMware",
    "00:0c:29": "VMware",
    "00:05:69": "VMware",
    "08:00:27": "VirtualBox",
    "52:54:00": "QEMU/KVM",
    "00:16:3e": "Xen",
    "00:1c:42": "Parallels",
    "00:15:5d": "Hyper-V",
}

_VM_MAC_PREFIXES: frozenset[str] = frozenset(_VM_MAC_OUI_TO_VENDOR)

_WIN_VM_REGISTRY_KEYS: list[tuple[str, str]] = [
    (r"SOFTWARE\Oracle\VirtualBox Guest Additions",  "VirtualBox"),
    (r"SOFTWARE\VMware, Inc.\VMware Tools",           "VMware"),
    (r"SOFTWARE\Parallels\Parallels Tools",           "Parallels"),
    (r"SYSTEM\ControlSet001\Services\VBoxGuest",      "VirtualBox"),
    (r"SYSTEM\ControlSet001\Services\vmhgfs",         "VMware"),
    (r"SYSTEM\ControlSet001\Services\vmci",           "VMware"),
    (r"SYSTEM\ControlSet001\Services\VBoxSF",         "VirtualBox"),
]

_MAC_RE = re.compile(r"^([0-9a-f]{2}[:\-]){5}[0-9a-f]{2}$", re.I)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VMEvidence:
    """One piece of VM detection evidence produced by a single check."""
    check_name: str
    description: str
    hypervisor: str
    weight: float       # 0.0–1.0; reliability of this single indicator


@dataclass
class VMDetectionResult:
    """Aggregated output of :class:`VMDetector.scan`."""
    is_vm: bool
    confidence: float           # highest single-evidence weight; 0.0 if clean
    hypervisor: str | None      # vendor from the highest-weight check
    evidence: list[VMEvidence] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if not self.is_vm:
            return "No VM indicators detected"
        hyp = self.hypervisor or "unknown hypervisor"
        return f"VM detected ({hyp}, confidence={self.confidence:.0%})"


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class _VMCheck(abc.ABC):
    """Interface for a single VM detection strategy."""

    name: ClassVar[str]

    @abc.abstractmethod
    def run(self) -> list[VMEvidence]:
        """Return zero or more evidence items.  Must never raise."""


# ---------------------------------------------------------------------------
# Check 1 — OS-level hypervisor flag
# ---------------------------------------------------------------------------

class CpuidHypervisorCheck(_VMCheck):
    """Asks the OS whether a hardware hypervisor is present.

    * macOS  — ``sysctl -n kern.hv_vmm_present``
    * Linux  — ``/proc/cpuinfo`` hypervisor flag; ``systemd-detect-virt``
    * Windows — ``wmic computersystem get HypervisorPresent``
    """

    name = "cpuid_hypervisor"

    def run(self) -> list[VMEvidence]:
        if sys.platform == "darwin":
            return self._check_macos()
        if sys.platform == "win32":
            return self._check_windows()
        return self._check_linux()

    # ------------------------------------------------------------------ macOS

    def _check_macos(self) -> list[VMEvidence]:
        try:
            result = subprocess.run(
                ["sysctl", "-n", "kern.hv_vmm_present"],
                capture_output=True, text=True, timeout=3,
            )
            if result.stdout.strip() == "1":
                return [VMEvidence(
                    check_name=self.name,
                    description="sysctl kern.hv_vmm_present=1",
                    hypervisor="hypervisor",
                    weight=0.90,
                )]
        except Exception:
            pass
        return []

    # ------------------------------------------------------------------ Linux

    def _check_linux(self) -> list[VMEvidence]:
        evidence: list[VMEvidence] = []

        try:
            with open("/proc/cpuinfo") as fh:
                if "hypervisor" in fh.read():
                    evidence.append(VMEvidence(
                        check_name=self.name,
                        description="/proc/cpuinfo contains 'hypervisor' CPU flag",
                        hypervisor="hypervisor",
                        weight=0.85,
                    ))
        except OSError:
            pass

        try:
            result = subprocess.run(
                ["systemd-detect-virt", "--vm"],
                capture_output=True, text=True, timeout=3,
            )
            virt = result.stdout.strip()
            if result.returncode == 0 and virt and virt != "none":
                evidence.append(VMEvidence(
                    check_name=self.name,
                    description=f"systemd-detect-virt reports '{virt}'",
                    hypervisor=virt.title(),
                    weight=0.95,
                ))
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

        return evidence

    # ---------------------------------------------------------------- Windows

    def _check_windows(self) -> list[VMEvidence]:
        try:
            result = subprocess.run(
                ["wmic", "computersystem", "get", "HypervisorPresent", "/value"],
                capture_output=True, text=True, timeout=5,
            )
            if "TRUE" in result.stdout.upper():
                return [VMEvidence(
                    check_name=self.name,
                    description="WMI Win32_ComputerSystem.HypervisorPresent=True",
                    hypervisor="hypervisor",
                    weight=0.90,
                )]
        except Exception:
            pass
        return []


# ---------------------------------------------------------------------------
# Check 2 — Hardware vendor / model strings
# ---------------------------------------------------------------------------

class HardwareVendorCheck(_VMCheck):
    """Inspects hardware manufacturer and model strings for VM signatures.

    * macOS  — ``system_profiler SPHardwareDataType``
    * Linux  — ``/sys/class/dmi/id/`` entries
    * Windows — ``wmic computersystem get Manufacturer,Model``
    """

    name = "hardware_vendor"

    def run(self) -> list[VMEvidence]:
        if sys.platform == "darwin":
            return self._check_macos()
        if sys.platform == "win32":
            return self._check_windows()
        return self._check_linux()

    def _match_vendor(self, text: str) -> str | None:
        lower = text.lower()
        for substr in _KNOWN_VM_VENDOR_SUBSTRINGS:
            if substr in lower:
                return substr.title()
        return None

    # ------------------------------------------------------------------ macOS

    def _check_macos(self) -> list[VMEvidence]:
        try:
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType"],
                capture_output=True, text=True, timeout=10,
            )
            vm_vendor = self._match_vendor(result.stdout)
            if vm_vendor:
                return [VMEvidence(
                    check_name=self.name,
                    description=f"system_profiler hardware matches VM vendor: {vm_vendor}",
                    hypervisor=vm_vendor,
                    weight=0.85,
                )]
        except Exception:
            pass
        return []

    # ------------------------------------------------------------------ Linux

    def _check_linux(self) -> list[VMEvidence]:
        dmi_fields = {
            "/sys/class/dmi/id/sys_vendor":   "system vendor",
            "/sys/class/dmi/id/board_vendor":  "board vendor",
            "/sys/class/dmi/id/product_name":  "product name",
            "/sys/class/dmi/id/bios_vendor":   "BIOS vendor",
        }
        for path, label in dmi_fields.items():
            try:
                content = open(path).read().strip()
                vm_vendor = self._match_vendor(content)
                if vm_vendor:
                    return [VMEvidence(
                        check_name=self.name,
                        description=f"DMI {label}='{content}' matches VM vendor",
                        hypervisor=vm_vendor,
                        weight=0.85,
                    )]
            except OSError:
                continue
        return []

    # ---------------------------------------------------------------- Windows

    def _check_windows(self) -> list[VMEvidence]:
        try:
            result = subprocess.run(
                ["wmic", "computersystem", "get", "Manufacturer,Model", "/value"],
                capture_output=True, text=True, timeout=5,
            )
            vm_vendor = self._match_vendor(result.stdout)
            if vm_vendor:
                return [VMEvidence(
                    check_name=self.name,
                    description=f"WMI Manufacturer/Model matches VM vendor: {vm_vendor}",
                    hypervisor=vm_vendor,
                    weight=0.85,
                )]
        except Exception:
            pass
        return []


# ---------------------------------------------------------------------------
# Check 3 — VM guest-agent processes
# ---------------------------------------------------------------------------

class VMProcessCheck(_VMCheck):
    """Scans running processes for known VM guest-agent executables."""

    name = "vm_process"

    def run(self) -> list[VMEvidence]:
        if psutil is None:
            return []

        found: list[VMEvidence] = []
        try:
            for proc in psutil.process_iter(["name", "exe"]):
                try:
                    proc_name = (proc.info.get("name") or "").lower()
                    proc_exe  = (proc.info.get("exe")  or "").lower()
                    search_str = f"{proc_name} {proc_exe}"
                    for token, hypervisor in _VM_PROCESSES.items():
                        if token in search_str:
                            found.append(VMEvidence(
                                check_name=self.name,
                                description=f"VM guest process running: {proc.info.get('name')}",
                                hypervisor=hypervisor,
                                weight=0.75,
                            ))
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return found


# ---------------------------------------------------------------------------
# Check 4 — VM-specific file paths
# ---------------------------------------------------------------------------

class VMFileCheck(_VMCheck):
    """Checks for well-known VM guest-tools files and driver paths."""

    name = "vm_file"

    def run(self) -> list[VMEvidence]:
        if sys.platform == "linux":
            targets = _VM_FILES_LINUX
        elif sys.platform == "win32":
            targets = _VM_FILES_WINDOWS
        else:
            return []

        found: list[VMEvidence] = []
        for path, hypervisor in targets.items():
            if os.path.exists(path):
                found.append(VMEvidence(
                    check_name=self.name,
                    description=f"VM-specific path present: {path}",
                    hypervisor=hypervisor,
                    weight=0.70,
                ))
        return found


# ---------------------------------------------------------------------------
# Check 5 — Virtual NIC MAC address prefixes
# ---------------------------------------------------------------------------

class MacAddressCheck(_VMCheck):
    """Checks network interface MAC addresses against known VM OUI prefixes."""

    name = "mac_address"

    def run(self) -> list[VMEvidence]:
        if psutil is None:
            return []

        found: list[VMEvidence] = []
        try:
            for iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    mac = addr.address or ""
                    if not _MAC_RE.match(mac):
                        continue
                    normalized = mac.lower().replace("-", ":")
                    prefix = normalized[:8]
                    if prefix in _VM_MAC_PREFIXES:
                        vendor = _VM_MAC_OUI_TO_VENDOR.get(prefix, "VM")
                        found.append(VMEvidence(
                            check_name=self.name,
                            description=f"VM OUI {prefix} on interface '{iface}'",
                            hypervisor=vendor,
                            weight=0.50,
                        ))
        except Exception:
            pass
        return found


# ---------------------------------------------------------------------------
# Check 6 — Windows registry keys
# ---------------------------------------------------------------------------

class WindowsRegistryCheck(_VMCheck):
    """Inspects HKLM for VM guest-tools installation registry keys (Windows-only)."""

    name = "windows_registry"

    def run(self) -> list[VMEvidence]:
        if sys.platform != "win32":
            return []

        found: list[VMEvidence] = []
        try:
            import winreg
            for reg_path, hypervisor in _WIN_VM_REGISTRY_KEYS:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                    winreg.CloseKey(key)
                    found.append(VMEvidence(
                        check_name=self.name,
                        description=f"Registry key present: HKLM\\{reg_path}",
                        hypervisor=hypervisor,
                        weight=0.85,
                    ))
                except OSError:
                    continue
        except ImportError:
            pass
        return found


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

_ALL_CHECKS: tuple[type[_VMCheck], ...] = (
    CpuidHypervisorCheck,
    HardwareVendorCheck,
    VMProcessCheck,
    VMFileCheck,
    MacAddressCheck,
    WindowsRegistryCheck,
)


class VMDetector:
    """Runs all registered VM checks and aggregates a :class:`VMDetectionResult`.

    Usage::

        result = VMDetector().scan()
        if result.is_vm:
            print(result.summary)

    A custom check set can be injected for testing::

        result = VMDetector(checks=(CpuidHypervisorCheck,)).scan()
    """

    def __init__(self, checks: tuple[type[_VMCheck], ...] = _ALL_CHECKS) -> None:
        self._checks: list[_VMCheck] = [cls() for cls in checks]

    def scan(self) -> VMDetectionResult:
        """Run all checks synchronously and return the aggregated result."""
        all_evidence: list[VMEvidence] = []

        for check in self._checks:
            try:
                evidence = check.run()
                all_evidence.extend(evidence)
            except Exception:
                logger.debug(
                    "VM check '%s' raised unexpectedly", check.name, exc_info=True
                )

        if not all_evidence:
            logger.debug("VMDetector: no VM indicators found")
            return VMDetectionResult(is_vm=False, confidence=0.0, hypervisor=None)

        for ev in all_evidence:
            logger.info(
                "VM evidence [%s] weight=%.2f  %s", ev.check_name, ev.weight, ev.description
            )

        best = max(all_evidence, key=lambda e: e.weight)
        confidence = best.weight
        is_vm = confidence >= VM_CONFIDENCE_THRESHOLD

        return VMDetectionResult(
            is_vm=is_vm,
            confidence=confidence,
            hypervisor=best.hypervisor if is_vm else None,
            evidence=all_evidence,
        )
