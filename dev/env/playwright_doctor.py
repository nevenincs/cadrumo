"""Probe whether the workstation satisfies the CONFIGURED Playwright browser channel.

This is the ``just playwright-doctor`` recipe: the health check the anti-bot
channel pinning decision requires but the justfile never built. AEAT browser
automation is pinned to ``channel: "chrome"`` in New Headless mode for anti-bot
fingerprint reasons; bundled Chromium is the explicit fallback only if system
Chrome breaks. This probe reads the ACTUAL configured
channel (``cadrumo.core.config.Settings.cadrumo_browser_channel``) rather than
hardcoding ``"chrome"``, so it stays correct when an operator overrides the channel
via ``CADRUMO_BROWSER_CHANNEL``.

Unlike ``cadrumo.application.provisioning.probe_playwright_browser`` (a fast
filesystem-cache check used inside the interactive CLI process, where the
Playwright sync driver can hang), this script performs a REAL headless launch and
immediate close of the configured channel: it is a standalone dev/CI process, so a
hang surfaces as a ``just playwright-doctor`` timeout rather than a hung CLI
session.

Exit codes:

* 0 — the configured channel launches successfully.
* 1 — the channel is not launchable; stderr names the exact remediation.
"""

from __future__ import annotations

import asyncio
import sys

from cadrumo.core.optional_extras import BROWSER_EXTRA, MissingOptionalExtraError, require_optional_extra
from cadrumo.core.config import load_settings


def remediation_for_channel(channel: str) -> str:
    """Return the exact, actionable remediation command for a channel launch failure.

    The ``chrome`` channel is the mandated default; Playwright does not
    download a private Chrome copy for it, it installs/detects the SYSTEM Google
    Chrome (via the OS package manager on Linux, which typically needs root/apt
    access), so its remediation spells that constraint out. Every other channel
    (``chromium``, ``msedge``, ...) is a normal Playwright-managed download.
    """
    if channel == "chrome":
        return (
            "run 'playwright install chrome' (this installs/detects the SYSTEM "
            "Google Chrome, not a bundled download; on Linux it shells out to the "
            "OS package manager and typically needs root/apt access — pre-install "
            "'google-chrome-stable' yourself first if 'playwright install chrome' "
            "cannot elevate) or run 'just env-playwright' to provision both channels"
        )
    return f"run 'playwright install {channel}' (or 'just env-playwright') to install the browser binary"


async def _probe_channel(channel: str, *, headless: bool) -> None:
    """Launch and immediately close ``channel``; raise on any failure."""
    require_optional_extra(BROWSER_EXTRA)
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=channel, headless=headless)
        await browser.close()


def run_doctor(*, channel: str | None = None, headless: bool = True) -> int:
    """Probe the configured (or explicitly supplied) channel; return the process exit code.

    ``channel`` overrides the settings-resolved channel for callers (tests) that
    want to probe a deliberately broken or deliberately real channel without
    mutating process environment; production callers (the CLI recipe) leave it
    ``None`` and get the live ``cadrumo_browser_channel`` setting.
    """
    resolved_channel = channel if channel is not None else load_settings().cadrumo_browser_channel
    try:
        asyncio.run(_probe_channel(resolved_channel, headless=headless))
    except MissingOptionalExtraError as exc:
        print(
            f"playwright-doctor: optional extra {exc.extra.extra!r} is not installed "
            f"(import name {exc.extra.import_name!r})",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # Playwright's launch-failure exception surface is undocumented
        print(
            f"playwright-doctor: configured channel {resolved_channel!r} is not launchable "
            f"({type(exc).__name__}: {exc}) — {remediation_for_channel(resolved_channel)}",
            file=sys.stderr,
        )
        return 1
    print(f"playwright-doctor: configured channel {resolved_channel!r} launches successfully.")
    return 0


def main() -> int:
    """Run :func:`run_doctor` against the live configured channel."""
    return run_doctor()


if __name__ == "__main__":
    sys.exit(main())
