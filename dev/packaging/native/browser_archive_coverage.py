"""Refuse a product package whose browser archive pins do not cover its own Playwright driver.

The packaged browser setup downloads only archives the product's pin table
authenticates, and refuses to set the browser up when the table does not pin
the bundled driver's Chromium builds for the computer it runs on. Assembly
therefore reads both from the staged package itself, not from the build
environment, and stops when the package could never set its browser up.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.application.browser_archive_pins import BROWSER_ARCHIVE_PINS_RESOURCE, load_browser_archive_pins

from cadrumo.application.browser_location import required_browser_builds
from dev.packaging.playwright_driver import installed_playwright_driver_version

__all__ = ["BROWSER_PLATFORM_BY_TARGET", "BrowserArchiveCoverage", "verify_browser_archive_coverage"]

#: The browser item's platform key for each native package target.
BROWSER_PLATFORM_BY_TARGET: Final = {
    "windows-x86-64": "win-x64",
    "linux-x86-64": "linux-x64",
    "linux-aarch64": "linux-arm64",
    "macos-arm64": "mac-arm64",
}


@dataclass(frozen=True, slots=True)
class BrowserArchiveCoverage:
    """What a package's pins cover: its driver, its browser platform and how many archives."""

    playwright_driver: str
    browser_platform: str
    archives: int


def verify_browser_archive_coverage(packages: Path, target: str) -> BrowserArchiveCoverage | None:
    """Return what the staged pins cover for ``target``, or ``None`` when the package carries no Playwright.

    Raises:
        ValueError: When the package carries Playwright but its pin table is
            missing, malformed, for another driver, or pins no archive for one
            of the driver's Chromium builds on ``target``.
    """
    manifest = packages / "playwright" / "driver" / "package" / "browsers.json"
    if not manifest.is_file():
        return None
    platform = BROWSER_PLATFORM_BY_TARGET.get(target)
    if platform is None:
        raise ValueError(f"No browser platform is declared for the package target {target}")
    table = packages.joinpath("cadrumo", "_data", *BROWSER_ARCHIVE_PINS_RESOURCE)
    if not table.is_file():
        raise ValueError("The package carries Playwright but no browser archive pins")
    pins = load_browser_archive_pins(table.read_text(encoding="utf-8"))
    driver = installed_playwright_driver_version(manifest)
    builds = required_browser_builds(manifest)
    if pins is None or driver is None or builds is None:
        raise ValueError("The packaged Playwright driver or its browser pins are unreadable")
    covered = pins.covering(platform, driver, [build.directory_name for build in builds])
    if covered is None:
        raise ValueError(
            f"The browser archive pins ({pins.playwright_driver}) do not cover the packaged Playwright driver "
            f"{driver} on {platform}; run 'just pin-browser-archives'"
        )
    return BrowserArchiveCoverage(playwright_driver=driver, browser_platform=platform, archives=len(covered))
