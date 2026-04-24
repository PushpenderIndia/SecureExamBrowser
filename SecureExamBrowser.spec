# PyInstaller spec — macOS only.
# Windows and Linux use CLI flags directly in the GitHub workflow.
#
# Build:
#   pyinstaller SecureExamBrowser.spec
#
# The resulting bundle is at dist/SecureExamBrowser.app

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=[("config.example.toml", "."), ("assets", "assets")],
    hiddenimports=[
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebChannel",
        "PySide6.QtNetwork",
        "CoreWLAN",
        "CoreLocation",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SecureExamBrowser",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name="SecureExamBrowser",
)

app = BUNDLE(
    coll,
    name="SecureExamBrowser.app",
    icon=None,
    bundle_identifier="com.secureexambrowser.app",
    info_plist={
        # ── Required for WiFi SSID scanning ──────────────────────────────
        "NSLocationWhenInUseUsageDescription": (
            "WiFi network names are visible only with Location Services enabled."
        ),
        "NSLocationAlwaysAndWhenInUseUsageDescription": (
            "WiFi network names are visible only with Location Services enabled."
        ),
        # ── General app metadata ─────────────────────────────────────────
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
        "LSBackgroundOnly": False,
    },
)
