"""Converge browser binaries and Linux libraries for full worktree initialization."""

from __future__ import annotations

import os
import shutil
import sys

from cadrumo.core.config import Settings
from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command

from .playwright_doctor import run_doctor


def _install(*arguments: str, system: bool = False) -> int:
    """Run Playwright's installer without CI forcing an installed system channel to reinstall."""
    environment = dict(os.environ)
    environment.pop("CI", None)
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
    """Reuse launchable channels and repair missing binaries or Linux libraries.

    Bundled Chromium is the default AEAT channel and the browser tests launch
    directly. An operator who configures a system channel such as ``chrome``
    gets that channel checked as well. A real headless launch verifies both
    the executable and its shared libraries.
    """
    channels = dict.fromkeys(("chromium", Settings().cadrumo_browser_channel))
    for channel in channels:
        if run_doctor(channel=channel) == 0:
            print(f"browser-setup: reusing provisioned {channel}")
            continue
        result = _install("install", channel, system=channel in {"chrome", "msedge"})
        if result:
            return result
        if run_doctor(channel=channel) == 0:
            continue
        if sys.platform != "linux":
            return 1
        result = _install("install-deps", channel, system=True)
        if result:
            return result
        if run_doctor(channel=channel):
            return 1
    return 0


def main() -> int:
    """Provision and verify the browsers required by the development environment."""
    return provision_browsers()


if __name__ == "__main__":
    sys.exit(main())
