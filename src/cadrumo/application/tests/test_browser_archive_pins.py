"""The browser archive pin table: what it admits, what it refuses, and when it covers an install."""

from __future__ import annotations

from pathlib import Path

import playwright
import pytest
from pydantic import ValidationError

from ..browser_archive_pins import BrowserArchivePins, load_browser_archive_pins
from ..dependency_network import dependency_hosts
from ..provisioning_browser import installed_playwright_driver_version

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SHA = "ab" * 32
_PATH = "builds/cft/156.0.8078.4/win64/chrome-win64.zip"


def _table(*archives: str, driver: str = "1.64.0") -> str:
    return f'playwright_driver = "{driver}"\n' + "".join(archives)


def _archive(
    *,
    platform: str = "win-x64",
    directory: str = "chromium-1248",
    path: str = _PATH,
    urls: tuple[str, ...] = (f"https://cdn.playwright.dev/{_PATH}",),
    size: int = 10,
    sha: str = _SHA,
) -> str:
    sources = ", ".join(f'"{url}"' for url in urls)
    return (
        f'\n[[archives]]\nplatform = "{platform}"\ndirectory_name = "{directory}"\npath = "{path}"\n'
        f'urls = [{sources}]\ndownload_bytes = {size}\nsha256 = "{sha}"\n'
    )


def test_a_well_formed_table_loads_and_selects_by_platform() -> None:
    pins = load_browser_archive_pins(
        _table(
            _archive(),
            _archive(
                directory="ffmpeg-1013",
                path="builds/ffmpeg/1013/ffmpeg-win64.zip",
                urls=(
                    "https://cdn.playwright.dev/dbazure/download/playwright/builds/ffmpeg/1013/ffmpeg-win64.zip",
                    "https://cdn.playwright.dev/builds/ffmpeg/1013/ffmpeg-win64.zip",
                ),
            ),
            _archive(
                platform="linux-x64",
                path="builds/cft/156.0.8078.4/linux64/chrome-linux64.zip",
                urls=("https://cdn.playwright.dev/builds/cft/156.0.8078.4/linux64/chrome-linux64.zip",),
            ),
        )
    )

    assert pins is not None
    assert [pin.directory_name for pin in pins.for_platform("win-x64")] == ["chromium-1248", "ffmpeg-1013"]
    assert [pin.platform for pin in pins.for_platform("linux-x64")] == ["linux-x64"]
    assert pins.for_platform("mac-arm64") == ()


@pytest.mark.parametrize(
    "archive",
    (
        _archive(path="builds/../../escape.zip", urls=("https://cdn.playwright.dev/builds/../../escape.zip",)),
        _archive(urls=("https://cdn.playwright.dev/builds/other.zip",)),
        _archive(urls=(f"http://cdn.playwright.dev/{_PATH}",)),
        _archive(urls=(f"https://cdn.playwright.dev/{_PATH}", f"https://cdn.playwright.dev/{_PATH}")),
        _archive(sha="AB" * 32),
        _archive(size=0),
        _archive(platform="win-arm64"),
    ),
)
def test_a_pin_that_could_admit_other_bytes_or_sources_is_refused(archive: str) -> None:
    with pytest.raises(ValidationError):
        load_browser_archive_pins(_table(archive))


def test_a_platform_pins_each_build_once() -> None:
    with pytest.raises(ValidationError):
        load_browser_archive_pins(_table(_archive(), _archive(sha="cd" * 32)))


def _pins() -> BrowserArchivePins:
    pins = load_browser_archive_pins(
        _table(
            _archive(),
            _archive(
                directory="chromium_headless_shell-1248",
                path=("builds/cft/156.0.8078.4/win64/chrome-headless-shell-win64.zip"),
                urls=("https://cdn.playwright.dev/builds/cft/156.0.8078.4/win64/chrome-headless-shell-win64.zip",),
            ),
        )
    )
    assert pins is not None
    return pins


def test_pins_cover_an_install_only_for_their_driver_and_every_required_build() -> None:
    pins = _pins()
    builds = ("chromium-1248", "chromium_headless_shell-1248")

    assert pins.covering("win-x64", "1.64.0", builds) == pins.for_platform("win-x64")
    assert pins.covering("win-x64", "1.65.0", builds) is None
    assert pins.covering("win-x64", None, builds) is None
    assert pins.covering("win-x64", "1.64.0", (*builds, "chromium-1300")) is None
    assert pins.covering("linux-x64", "1.64.0", builds) is None


def test_the_bundled_table_pins_the_installed_driver_from_declared_hosts_only() -> None:
    pins = load_browser_archive_pins()
    manifest = Path(playwright.__file__).parent / "driver" / "package" / "browsers.json"

    assert pins is not None
    assert pins.playwright_driver == installed_playwright_driver_version(manifest)
    declared = set(dependency_hosts("browser"))
    for pin in pins.archives:
        assert all(url.split("/")[2] in declared for url in pin.urls)
