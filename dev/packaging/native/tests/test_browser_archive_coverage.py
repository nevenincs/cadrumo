"""Assembly refuses a product package whose browser pins do not cover its own Playwright driver.

Each staged tree carries the real locked driver's ``package.json`` and
``browsers.json``, and a pins folder carries the real committed pin table, laid
out as the package stages them; the defect cases change one of them.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import playwright
import pytest

from dev._paths import COMPONENT_PINS_ROOT
from dev.env.browser_archive_pins import PINS_FILE

from ...runtime_wheelhouse_contract import SUPPORTED_TARGETS
from ..browser_archive_coverage import BROWSER_PLATFORM_BY_TARGET, verify_browser_archive_coverage

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DRIVER_PACKAGE = Path(playwright.__file__).parent / "driver" / "package"


def _stage(root: Path, *, pins: bool = True) -> Path:
    """Stage the locked driver under ``root`` and, unless refused, the committed pins in ``root/pins``."""
    driver = root / "playwright" / "driver" / "package"
    driver.mkdir(parents=True)
    for name in ("package.json", "browsers.json"):
        shutil.copy2(_DRIVER_PACKAGE / name, driver / name)
    (root / "pins").mkdir()
    if pins:
        shutil.copy2(COMPONENT_PINS_ROOT / PINS_FILE, root / "pins" / PINS_FILE)
    return driver


@pytest.mark.parametrize("target", sorted(BROWSER_PLATFORM_BY_TARGET))
def test_every_package_target_is_covered_by_the_committed_pins(tmp_path: Path, target: str) -> None:
    _stage(tmp_path)

    covered = verify_browser_archive_coverage(tmp_path, tmp_path / "pins", target)

    assert covered is not None
    assert covered.browser_platform == BROWSER_PLATFORM_BY_TARGET[target]
    assert covered.archives >= 3


def test_a_package_without_playwright_is_not_checked(tmp_path: Path) -> None:
    assert verify_browser_archive_coverage(tmp_path, tmp_path / "pins", "windows-x86-64") is None


def test_a_package_with_playwright_but_no_pins_is_refused(tmp_path: Path) -> None:
    _stage(tmp_path, pins=False)

    with pytest.raises(ValueError, match="no browser archive pins"):
        verify_browser_archive_coverage(tmp_path, tmp_path / "pins", "windows-x86-64")


def test_a_driver_the_pins_were_not_made_for_is_refused(tmp_path: Path) -> None:
    driver = _stage(tmp_path)
    document = json.loads((driver / "package.json").read_text(encoding="utf-8"))
    (driver / "package.json").write_text(json.dumps({**document, "version": "0.0.1"}), encoding="utf-8")

    with pytest.raises(ValueError, match="pin-browser-archives"):
        verify_browser_archive_coverage(tmp_path, tmp_path / "pins", "linux-x86-64")


def test_a_chromium_revision_the_pins_do_not_name_is_refused(tmp_path: Path) -> None:
    driver = _stage(tmp_path)
    document = json.loads((driver / "browsers.json").read_text(encoding="utf-8"))
    for entry in document["browsers"]:
        if entry["name"] == "chromium-headless-shell":
            entry["revision"] = "1"
    (driver / "browsers.json").write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match="do not cover"):
        verify_browser_archive_coverage(tmp_path, tmp_path / "pins", "macos-arm64")


def test_a_target_without_a_browser_platform_is_refused(tmp_path: Path) -> None:
    _stage(tmp_path)

    with pytest.raises(ValueError, match="No browser platform"):
        verify_browser_archive_coverage(tmp_path, tmp_path / "pins", "freebsd-x86-64")


def test_every_declared_package_target_has_a_browser_platform() -> None:
    assert {target.name for target in SUPPORTED_TARGETS} == set(BROWSER_PLATFORM_BY_TARGET)
