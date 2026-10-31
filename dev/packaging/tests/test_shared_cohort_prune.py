"""The cohort cache retains recent entries and removes orphaned locks."""

import os
from pathlib import Path

import pytest

from ..shared_cohort import _prune

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_prune_keeps_current_and_recent_entries_and_live_locks(tmp_path: Path) -> None:
    for index in range(5):
        entry = tmp_path / str(index)
        entry.mkdir()
        manifest = entry / "cohort.json"
        manifest.write_text("{}", encoding="utf-8")
        os.utime(manifest, (1_700_000_000 + index, 1_700_000_000 + index))
        (tmp_path / f".{index}.lock").touch()
    (tmp_path / ".orphan.lock").touch()

    _prune(tmp_path, "0")

    assert {path.name for path in tmp_path.iterdir() if path.is_dir()} == {"0", "2", "3", "4"}
    assert (tmp_path / ".0.lock").exists()
    assert not (tmp_path / ".1.lock").exists()
    assert not (tmp_path / ".orphan.lock").exists()
