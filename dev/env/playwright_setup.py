"""Converge browser binaries and Linux libraries for full worktree initialization."""

from __future__ import annotations

import os
import shutil
import sys

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command

from .playwright_doctor import managed_browsers_root, run_doctor


def _install(*arguments: str, system: bool = False) -> int:
    """Run Playwright's installer without CI forcing an installed system channel to reinstall."""
    environment = dict(os.environ)
    environment.pop("CI", None)
    environment["PLAYWRIGHT_BROWSERS_PATH"] = str(managed_browsers_root())
    command = [sys.executable, "-m", "playwright", *arguments]
    if system and sys.platform == "linux" and os.geteuid() != 0:
        sudo = shutil.which("sudo")
        if sudo is None:
            print("browser-setup: missing system resources require root or passwordless sudo.", file=sys.stderr)
            return 1
        command = [sudo, "-n", *command]
    result = run_command(command, cwd=REPO_ROOT, environment=environment, timeout_seconds=600, errors="replace")
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    return result.returncode


def provision_browsers() -> int:
    """Reuse launchable bundled Chromium and repair missing binaries or Linux libraries."""
    if run_doctor() == 0:
        print("browser-setup: reusing provisioned chromium")
        return 0
    result = _install("install", "chromium")
    if result:
        return result
    if run_doctor() == 0:
        return 0
    if sys.platform != "linux":
        return 1
    result = _install("install-deps", "chromium", system=True)
    return result if result else run_doctor()


def main() -> int:
    """Provision and verify the browsers required by the development environment."""
    return provision_browsers()


if __name__ == "__main__":
    sys.exit(main())
