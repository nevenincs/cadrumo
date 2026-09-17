"""Operating-system process control for installing the Playwright Chromium build.

:func:`run_browser_installer` runs the installed Playwright package's own
installer under the current interpreter over a fixed argv, so the downloaded
revisions are exactly the ones that package launches.
"""

from __future__ import annotations

import subprocess
import sys

__all__ = ["run_browser_installer"]


def run_browser_installer(timeout_s: float) -> int:
    """Run ``playwright install chromium`` and return its exit code.

    Raises:
        TimeoutError: When the install does not finish within ``timeout_s``.
    """
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"browser install exceeded {timeout_s:.0f}s") from exc
    return int(completed.returncode)
