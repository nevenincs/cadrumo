"""Stand-in browser builds for tests that need the launch guard to find a browser.

The guard finds a browser by the completion marker Playwright writes into each
build's folder, so a test whose launch is captured, expected to fail or only
needs to pass the guard places the folders and markers and no executables.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from ......application.browser_location import required_browser_builds
from ......core.config import override_settings

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

__all__ = ["place_installed_builds", "with_installed_browser"]


def place_installed_builds(browsers_root: Path) -> None:
    """Create each build folder the installed driver names, with its completion marker."""
    builds = required_browser_builds()
    assert builds is not None
    for build in builds:
        folder = browsers_root / build.directory_name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "INSTALLATION_COMPLETE").write_bytes(b"")


@contextmanager
def with_installed_browser(browsers_root: Path) -> Generator[None]:
    """Hand Playwright ``browsers_root``, holding the builds the installed driver launches."""
    place_installed_builds(browsers_root)
    with override_settings(cadrumo_playwright_browsers_dir=browsers_root):
        yield
