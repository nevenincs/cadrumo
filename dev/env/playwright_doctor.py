"""Probe whether the workstation's managed browser passes the product's own full check.

This is the ``just doctor-browser`` recipe. It runs the ``browser`` setup item's
full check, exactly as ``dependencies.verify`` does: the required builds and
their completion markers, the executables against the install receipt when
there is one, and one headless launch whose reported version must match the
bundled Playwright's manifest. A developer check and the product therefore
agree on what "the browser works" means.

The item is built with the same real adapters the setup registry binds; the
check is read-only and downloads nothing. It runs as a standalone process, so a
hung launch surfaces as a timeout here rather than inside a CLI session.

Exit codes:

* 0 -- the browser is present and launched with the expected version.
* 1 -- it is not; stderr names what the full check found and the remediation.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from cadrumo.adapters.outbound.browser_runtime.installer import (
    remove_browser_builds,
    run_browser_install,
)
from cadrumo.adapters.outbound.browser_runtime.launch_check import launch_headless_browser
from cadrumo.application.dependency_contracts import DependencyCheckMode, DependencyProbeOutcome, DependencyProbeReading
from cadrumo.application.dependency_receipts import DependencyReceiptStore, dependency_receipts_root
from cadrumo.application.provisioning_browser import PlaywrightBrowserItem, playwright_browsers_root

REMEDIATION = "run 'playwright install chromium' (or 'just setup-browser') to install the browser binary"


def managed_browsers_root() -> Path:
    """Return the browser directory the product launches from.

    Playwright's own default is a per-user cache the product never reads, so a
    probe or install against it would report a browser the product cannot use.
    """
    return playwright_browsers_root()


def browser_full_check() -> DependencyProbeReading:
    """Run the browser item's full check with the real adapters and return its reading."""
    item = PlaywrightBrowserItem(
        install=run_browser_install,
        launch=launch_headless_browser,
        remove_builds=remove_browser_builds,
        receipts=DependencyReceiptStore(dependency_receipts_root()),
    )
    return asyncio.run(item.check(DependencyCheckMode.FULL))


def run_doctor() -> int:
    """Run the full check; return the process exit code."""
    reading = browser_full_check()
    if reading.outcome is DependencyProbeOutcome.PRESENT and reading.facts.get("launched") is True:
        print(f"playwright-doctor: the browser launches successfully ({reading.facts.get('launched_version')}).")
        return 0
    found = reading.failure_category or reading.blocked_reason or reading.stale_reason
    detail = reading.outcome.value if found is None else f"{reading.outcome.value}: {found.value}"
    print(
        f"playwright-doctor: the managed browser at {managed_browsers_root()} is not launchable ({detail}) "
        f"-- {REMEDIATION}",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    """Run :func:`run_doctor` against the managed browser."""
    return run_doctor()


if __name__ == "__main__":
    sys.exit(main())
