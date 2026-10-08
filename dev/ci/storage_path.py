"""Resolve CI evidence directories through the shared storage authority."""

from __future__ import annotations

import argparse

from dev._paths import REPO_ROOT


def main() -> None:
    """Print the selected storage directory for workflow environment transport."""
    from cadrumo.core.storage_environment import storage_directory

    parser = argparse.ArgumentParser(description=__doc__, epilog=f"Checkout: {REPO_ROOT}")
    parser.add_argument("channel", choices=("homebrew", "scoop"))
    channel = parser.parse_args().channel
    root = storage_directory(f"CADRUMO_{channel.upper()}_ROOT", f"development/releases/{channel}")
    root.mkdir(parents=True, exist_ok=True)
    print(root)


if __name__ == "__main__":
    main()
