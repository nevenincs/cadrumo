"""Probe whether the workstation's managed browser launches through the bundled Playwright.

This is the ``just doctor-browser`` recipe. It launches the headless build in
the managed browser directory once, through the bundled Playwright driver, and
compares the version the browser reports with the driver's own manifest. The
product's browser item is checked by the native component engine; this probe
only tells a developer whether the browsers the test lanes share are usable.

The probe is read-only and downloads nothing. It runs as a standalone process,
so a hung launch surfaces here rather than inside a CLI session.

Exit codes:

* 0 -- the browser launched and reported the version the driver expects.
* 1 -- it did not; stderr names what was found and the remediation.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from cadrumo.application.provisioning_browser import playwright_browsers_root, required_browser_builds

REMEDIATION = "run 'playwright install chromium' (or 'just setup-browser') to install the browser binary"

_DRIVER_BROWSERS_VARIABLE = "PLAYWRIGHT_BROWSERS_PATH"
_HEADLESS_BUILD = "chromium-headless-shell"


def managed_browsers_root() -> Path:
    """Return the browser directory the product launches from.

    Playwright's own default is a per-user cache the product never reads, so a
    probe or install against it would report a browser the product cannot use.
    """
    return playwright_browsers_root()


@contextmanager
def _driver_browsers(root: Path) -> Generator[None]:
    """Point the driver this process starts at ``root``, restoring the variable afterwards."""
    previous = os.environ.get(_DRIVER_BROWSERS_VARIABLE)
    os.environ[_DRIVER_BROWSERS_VARIABLE] = str(root)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(_DRIVER_BROWSERS_VARIABLE, None)
        else:
            os.environ[_DRIVER_BROWSERS_VARIABLE] = previous


def launch_problem() -> str | None:
    """Launch the managed headless browser once; return what went wrong, or ``None`` when it matched."""
    builds = required_browser_builds()
    if builds is None:
        return "the bundled Playwright driver's browser manifest is unreadable"
    expected = next((build.browser_version for build in builds if build.name == _HEADLESS_BUILD), None)
    with _driver_browsers(managed_browsers_root()), sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError as error:
            first = str(error).strip().splitlines()
            return f"launch failed: {first[0] if first else type(error).__name__}"
        try:
            version = browser.version
        finally:
            browser.close()
    if expected is not None and version != expected:
        return f"it reports version {version}, the driver expects {expected}"
    return None


def run_doctor() -> int:
    """Launch the managed browser; return the process exit code."""
    problem = launch_problem()
    if problem is None:
        print("playwright-doctor: the browser launches successfully.")
        return 0
    print(
        f"playwright-doctor: the managed browser at {managed_browsers_root()} is not launchable ({problem}) "
        f"-- {REMEDIATION}",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    """Run :func:`run_doctor` against the managed browser."""
    return run_doctor()


if __name__ == "__main__":
    sys.exit(main())
