"""Operating-system process control for installing the Playwright Chromium build.

:func:`run_browser_installer` runs the installed Playwright package's own
installer under the current interpreter over a fixed argv, so the downloaded
revisions are exactly the ones that package launches.
"""

from __future__ import annotations

import os
import subprocess
import sys

from ....application.provisioning_browser import playwright_browsers_root
from ....core.child_console import child_console_creation_flags
from ....core.config import load_settings
from ....core.storage_taxonomy import StorageCategory
from ....core.storage_taxonomy_locations import storage_path

__all__ = ["run_browser_installer"]


def run_browser_installer(timeout_s: float) -> int:
    """Run ``playwright install chromium`` and return its exit code.

    Raises:
        TimeoutError: When the install does not finish within ``timeout_s``.
    """
    try:
        settings = load_settings()
        browser_root = playwright_browsers_root(settings=settings)
        temporary_root = storage_path(StorageCategory.TEMPORARY_FILES, settings=settings)
        browser_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        environment = dict(os.environ)
        environment["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_root)
        for variable in ("TEMP", "TMP", "TMPDIR"):
            environment[variable] = str(temporary_root)
        completed = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_s,
            check=False,
            env=environment,
            creationflags=child_console_creation_flags(),
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"browser install exceeded {timeout_s:.0f}s") from exc
    return int(completed.returncode)
