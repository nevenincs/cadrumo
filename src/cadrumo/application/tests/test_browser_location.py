"""Browser location: the managed browsers folder Playwright is handed."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...core.config import Settings, override_settings
from ...core.storage_taxonomy import StorageCategory
from ...core.storage_taxonomy_locations import storage_location
from ..browser_location import playwright_browsers_root

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_browsers_root_ignores_uncontrolled_vendor_override(tmp_path: Path) -> None:
    storage_root = tmp_path / "configured-storage"
    vendor_root = tmp_path / "vendor-playwright-cache"

    assert (
        playwright_browsers_root(
            env={"CADRUMO_STORAGE_ROOT": str(storage_root), "PLAYWRIGHT_BROWSERS_PATH": str(vendor_root)}
        )
        == (storage_root / "components/playwright").resolve()
    )
    assert playwright_browsers_root(tmp_path, env={"PLAYWRIGHT_BROWSERS_PATH": str(vendor_root)}) == tmp_path


def test_browsers_root_defaults_under_the_configured_storage_root(tmp_path: Path) -> None:
    settings = Settings(cadrumo_storage_root=tmp_path)

    assert playwright_browsers_root(settings=settings) == (tmp_path / "components" / "playwright").resolve()


def test_ambient_vendor_override_does_not_move_the_browsers_root_off_the_storage_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "vendor-cache"))

    with override_settings(cadrumo_storage_root=storage_root):
        browsers_root = playwright_browsers_root()

    assert (
        browsers_root
        == (storage_root / storage_location(StorageCategory.PLAYWRIGHT_BROWSERS).relative_path()).resolve()
    )
