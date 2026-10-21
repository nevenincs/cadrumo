"""Gate: the committed browser archive pins match what the locked Playwright driver downloads.

The listings come from the real driver's dry run for every supported platform,
so a Playwright upgrade without regenerated pins fails here. The defect cases
mutate a copy of the committed table and must each be reported.
"""

from __future__ import annotations

import pytest

from cadrumo.application.browser_archive_pins import BrowserArchivePins, load_browser_archive_pins

from ..browser_archive_pins import (
    PINS_PATH,
    ListedArchive,
    check_pins,
    listed_archives,
    locked_driver_version,
    parse_listing,
    render_pins,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def committed() -> BrowserArchivePins:
    pins = load_browser_archive_pins()
    assert pins is not None
    return pins


@pytest.fixture(scope="module")
def listed() -> list[ListedArchive]:
    return listed_archives()


def test_the_committed_pins_match_the_locked_driver(committed: BrowserArchivePins, listed: list[ListedArchive]) -> None:
    assert check_pins(committed, listed, locked_driver_version()) == []


def test_the_committed_table_is_exactly_what_the_generator_renders(committed: BrowserArchivePins) -> None:
    assert PINS_PATH.read_text(encoding="utf-8") == render_pins(committed)


def test_a_missing_pin_is_reported(committed: BrowserArchivePins, listed: list[ListedArchive]) -> None:
    pins = committed.model_copy(update={"archives": committed.archives[1:]})

    assert check_pins(pins, listed, locked_driver_version())


def test_pins_for_another_driver_are_reported(committed: BrowserArchivePins, listed: list[ListedArchive]) -> None:
    pins = committed.model_copy(update={"playwright_driver": "0.0.0"})

    assert check_pins(pins, listed, locked_driver_version())


def test_a_pin_at_another_path_or_from_an_undeclared_host_is_reported(
    committed: BrowserArchivePins, listed: list[ListedArchive]
) -> None:
    first = committed.archives[0]
    moved = first.model_copy(update={"urls": (*first.urls, f"https://mirror.example/{first.path}")})

    pins = committed.model_copy(update={"archives": (moved, *committed.archives[1:])})
    problems = check_pins(pins, listed, locked_driver_version())

    assert any("undeclared source" in problem for problem in problems)
    assert any("other sources" in problem for problem in problems)


def test_the_listing_parser_reads_sources_in_the_drivers_order() -> None:
    listing = """Chrome for Testing 1 (playwright chromium v1248)
  Install location:    C:\\pw\\chromium-1248
  Download url:        https://cdn.playwright.dev/builds/cft/1/win64/chrome-win64.zip

FFmpeg (playwright ffmpeg v1013)
  Install location:    /pw/ffmpeg-1013
  Download url:        https://cdn.playwright.dev/dbazure/download/playwright/builds/ffmpeg/1013/f.zip
  Download fallback 1: https://playwright.download.prss.microsoft.com/dbazure/download/playwright/builds/ffmpeg/1013/f.zip

Winldd (playwright winldd v1007)
  Install location:    /pw/winldd-1007
"""

    assert parse_listing(listing) == {
        "chromium-1248": ("https://cdn.playwright.dev/builds/cft/1/win64/chrome-win64.zip",),
        "ffmpeg-1013": (
            "https://cdn.playwright.dev/dbazure/download/playwright/builds/ffmpeg/1013/f.zip",
            "https://playwright.download.prss.microsoft.com/dbazure/download/playwright/builds/ffmpeg/1013/f.zip",
        ),
    }
