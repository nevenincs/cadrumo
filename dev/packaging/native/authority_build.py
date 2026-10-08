"""Ensure a published authority exists, with explicit republication on request."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dev._paths import REPO_ROOT

from ..authority_staging import selected_published_authority
from ..command_execution import run_command
from .action_cache import action_lock


def publish(build: Path, *, rebuild: bool = False) -> None:
    """Compile missing publications; source or compiler edits require explicit rebuild."""
    with action_lock(build, "authority-publication"):
        if not rebuild:
            try:
                descriptor, _database = selected_published_authority(REPO_ROOT)
            except FileNotFoundError:
                pass
            else:
                print(f"Reusing published authority: {descriptor}; request registry_authority_rebuild to recompile")
                return
        command = [sys.executable, "-B", "-m", "dev.registry.pipeline", "publish-authority"]
        result = run_command(command, cwd=REPO_ROOT)
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode:
            raise SystemExit(result.returncode)
        selected_published_authority(REPO_ROOT)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--rebuild", action="store_true", help="Recompile and publish even when authority exists")
    args = parser.parse_args()
    publish(args.build, rebuild=args.rebuild)
