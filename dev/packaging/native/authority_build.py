"""Ensure a published authority exists, with explicit republication on request."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dev._paths import REPO_ROOT

from ..authority_staging import selected_published_authority
from ..command_execution import run_command
from .action_cache import action_lock
from .build_log import BuildLog, command_line, display_path


def publish(build: Path, *, rebuild: bool = False) -> None:
    """Compile missing publications; source or compiler edits require explicit rebuild."""
    log = BuildLog("registry_authority")
    with action_lock(build, "authority-publication"):
        if not rebuild:
            try:
                descriptor, _database = selected_published_authority(REPO_ROOT)
            except FileNotFoundError:
                log.status("no published authority is selected; compiling and publishing it")
            else:
                log.status(
                    f"up to date, reusing {display_path(descriptor)}; build registry_authority_rebuild to recompile"
                )
                return
        else:
            log.status("recompiling and republishing the registry authority on request")
        command = [sys.executable, "-B", "-m", "dev.registry.pipeline", "publish-authority"]
        log.debug(f"command: {command_line(command)}")
        result = run_command(command, cwd=REPO_ROOT, inherit_output=True)
        if result.returncode:
            log.error(f"publication failed with exit status {result.returncode}; the existing publication is kept")
            raise SystemExit(result.returncode)
        descriptor, _database = selected_published_authority(REPO_ROOT)
        log.status(f"published {display_path(descriptor)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--rebuild", action="store_true", help="Recompile and publish even when authority exists")
    args = parser.parse_args()
    publish(args.build, rebuild=args.rebuild)
