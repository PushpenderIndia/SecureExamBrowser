from __future__ import annotations

import gzip
import plistlib

from .config_builder import SEBConfig


class SEBFileGenerator:
    """Serialises a SEBConfig to a gzip-compressed Apple plist (.seb) file."""

    def __init__(self, config: SEBConfig) -> None:
        self.config = config

    def generate_xml(self) -> bytes:
        return plistlib.dumps(
            self.config.build_plist_dict(),
            fmt=plistlib.FMT_XML,
            sort_keys=True,
        )

    def write(self, output_path: str) -> None:
        xml_bytes = self.generate_xml()
        with gzip.open(output_path, "wb") as gz:
            gz.write(xml_bytes)
        print(f"Written: {output_path}")
        self._verify(output_path)

    def _verify(self, path: str) -> None:
        with gzip.open(path, "rb") as gz:
            data = plistlib.load(gz)
        print(f"  Top-level keys  : {len(data)}")
        print(f"  Prohibited procs: {len(data.get('prohibitedProcesses', []))}")
        print(f"  Start URL       : {data.get('startURL', '')}")
