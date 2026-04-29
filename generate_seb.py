#!/usr/bin/env python3
"""
Interactive .seb config file generator.

Run:
    python3 generate_seb.py
"""

import hashlib
import sys

from core.seb import SEBConfig, SEBFileGenerator

# sha256("admin123")
_DEFAULT_ADMIN_HASH = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"


def _prompt(label: str, default: str = "", required: bool = False) -> str:
    hint = f" [{default}]" if default else ""
    while True:
        value = input(f"  {label}{hint}: ").strip()
        if not value and default:
            return default
        if value:
            return value
        if required:
            print("    ! This field is required.")


def _prompt_password(label: str, default_hash: str = "") -> str:
    """Prompt for a plain-text password and return its SHA-256 hex digest.
    Press Enter to keep the default hash unchanged."""
    hint = " [keep current]" if default_hash else " [leave empty = no password]"
    value = input(f"  {label}{hint}: ").strip()
    if not value:
        return default_hash
    return hashlib.sha256(value.encode()).hexdigest()


def main() -> None:
    print("=" * 60)
    print("  Secure Exam Browser — .seb Config Generator")
    print("=" * 60)
    print()

    # ── Output path ──────────────────────────────────────────────
    print("Output")
    output_path = _prompt("Output file", default="exam.sebexam")
    if not output_path.endswith(".sebexam"):
        output_path += ".sebexam"
    print()

    # ── URLs ─────────────────────────────────────────────────────
    print("Exam URLs")
    config = SEBConfig()
    config.start_url = _prompt("Start URL", default=config.start_url, required=True)
    config.quit_url  = _prompt("End exam URL (auto-exit when browser lands here)", default=config.quit_url)
    print()

    # ── Passwords ────────────────────────────────────────────────
    print("Passwords  (plain text — will be stored as SHA-256)")
    config.hashed_admin_password = _prompt_password(
        "Admin password", default_hash=_DEFAULT_ADMIN_HASH
    )
    same = input("  Use same password for Quit? [Y/n]: ").strip().lower()
    if same in ("", "y", "yes"):
        config.hashed_quit_password = config.hashed_admin_password
    else:
        config.hashed_quit_password = _prompt_password(
            "Quit password", default_hash=config.hashed_admin_password
        )
    print()

    # ── Duration ─────────────────────────────────────────────────
    print("Exam Duration")
    raw = _prompt("Duration in minutes (0 = no limit)", default="0")
    config.duration_minutes = int(raw) if raw.isdigit() and int(raw) > 0 else None
    print()

    # ── Originator tag ───────────────────────────────────────────
    print("Metadata")
    config.originator_version = _prompt(
        "Originator version tag", default=config.originator_version
    )
    print()

    # ── Generate ─────────────────────────────────────────────────
    print(f"Generating '{output_path}' …")
    SEBFileGenerator(config).write(output_path)
    print()
    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
