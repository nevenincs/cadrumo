from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _force_english_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin CLI output to English so test assertions stay readable.

    The production default is ``es``; this fixture only affects test
    output, not runtime behaviour.
    """
    monkeypatch.setenv("AEAT_OUTPUT_LANGUAGE", "en")


@pytest.fixture(autouse=True)
def _isolated_aeat_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point `Settings.aeat_local_storage_root` at the test's `tmp_path`."""
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path))

