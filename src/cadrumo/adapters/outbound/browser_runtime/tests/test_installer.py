"""Real installer delegation preserves controlled browser and temporary storage roots."""

from pathlib import Path

import pytest

from .....core.config import override_settings
from .. import installer

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_installer_passes_configured_storage_and_temp_roots_to_playwright(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage_root = tmp_path / "storage"
    expected_root = storage_root / "browser-cache"
    expected_temp = storage_root / "tmp"
    captured: dict[str, object] = {}

    def fake_run(_arguments: list[str], **kwargs: object) -> object:
        captured.update(kwargs)
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr(installer.subprocess, "run", fake_run)

    with override_settings(
        cadrumo_local_storage_root=storage_root,
        cadrumo_playwright_browsers_dir=expected_root,
        cadrumo_temp_dir=expected_temp,
    ):
        assert installer.run_browser_installer(1.0) == 0
    environment = captured["env"]
    assert isinstance(environment, dict)
    assert environment["PLAYWRIGHT_BROWSERS_PATH"] == str(expected_root.resolve())
    assert environment["TEMP"] == str(expected_temp.resolve())
    assert environment["TMP"] == str(expected_temp.resolve())
    assert environment["TMPDIR"] == str(expected_temp.resolve())
