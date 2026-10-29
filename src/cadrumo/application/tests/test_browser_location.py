"""Browser location: the managed browsers folder Playwright is handed."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...core.config import Settings
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


def test_browsers_root_defaults_under_the_configured_storage_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", raising=False)
    settings = Settings(cadrumo_local_storage_root=tmp_path)

    assert playwright_browsers_root(settings=settings) == (tmp_path / "components" / "playwright").resolve()


def test_cadrumo_browser_root_override_wins_over_vendor_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("CADRUMO_STORAGE_ROOT", str(storage_root))
    monkeypatch.delenv("CADRUMO_LOCAL_STORAGE_ROOT", raising=False)
    monkeypatch.setenv("CADRUMO_PLAYWRIGHT_BROWSERS_DIR", "browser-cache")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "vendor-cache"))

    assert playwright_browsers_root() == (storage_root / "browser-cache").resolve()
