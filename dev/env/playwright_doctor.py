"""Probe whether the workstation can launch Playwright's bundled Chromium.

This is the ``just doctor-browser`` recipe. AEAT browser automation launches
only Playwright's bundled Chromium, so this probe performs the same launch
without selecting any system browser.

Unlike ``cadrumo.application.provisioning_browser.probe_playwright_browser`` (a fast
filesystem-cache check used inside the interactive CLI process, where the
Playwright sync driver can hang), this script performs a REAL headless launch and
immediate close: it is a standalone dev/CI process, so a hang surfaces as a
``just doctor-browser`` timeout rather than a hung CLI session.

Exit codes:

* 0 — the bundled Chromium launches successfully.
* 1 — it is not launchable; stderr names the exact remediation.
"""

from __future__ import annotations

import asyncio
import sys

from cadrumo.core.optional_extras import BROWSER_EXTRA, MissingOptionalExtraError, require_optional_extra

REMEDIATION = "run 'playwright install chromium' (or 'just setup-browser') to install the browser binary"


async def _probe_bundled_chromium(*, headless: bool) -> None:
    """Launch and immediately close the bundled Chromium; raise on any failure."""
    require_optional_extra(BROWSER_EXTRA)
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        await browser.close()


def run_doctor(*, headless: bool = True) -> int:
    """Probe the bundled Chromium; return the process exit code."""
    try:
        asyncio.run(_probe_bundled_chromium(headless=headless))
    except MissingOptionalExtraError as exc:
        print(
            f"playwright-doctor: optional extra {exc.extra.extra!r} is not installed "
            f"(import name {exc.extra.import_name!r})",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # Playwright's launch-failure exception surface is undocumented
        print(
            f"playwright-doctor: bundled Chromium is not launchable ({type(exc).__name__}: {exc}) — {REMEDIATION}",
            file=sys.stderr,
        )
        return 1
    print("playwright-doctor: bundled Chromium launches successfully.")
    return 0


def main() -> int:
    """Run :func:`run_doctor` against the bundled Chromium."""
    return run_doctor()


if __name__ == "__main__":
    sys.exit(main())
