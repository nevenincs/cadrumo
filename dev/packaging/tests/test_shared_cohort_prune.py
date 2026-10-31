"""The cohort cache retains recent entries and removes orphaned locks."""

import os
import time
from pathlib import Path

import pytest

from .. import shared_cohort as cohort_module
from ..build_scratch_reclaim import SHARED_COHORT_WORK_FAMILY, reclaimable_scratch, var_scratch_name
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


def test_cohort_work_with_dead_parent_is_spared_even_by_age_reclaim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from .. import build_scratch_reclaim

    work = tmp_path / var_scratch_name(SHARED_COHORT_WORK_FAMILY, "snapshot")
    work.mkdir()
    old = time.time() - 30 * 24 * 60 * 60
    os.utime(work, (old, old))
    monkeypatch.setattr(build_scratch_reclaim, "process_is_live", lambda _pid: False)

    reclaimable, spared = reclaimable_scratch(tmp_path, reclaim_by_age=True)

    assert reclaimable == ()
    assert spared == (work,)


@pytest.mark.parametrize("fail", [False, True])
def test_cohort_retains_failed_work_and_preserves_other_builds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail: bool
) -> None:
    key = "a" * 64
    peer = tmp_path / var_scratch_name(SHARED_COHORT_WORK_FAMILY, f"{key}-peer")
    peer.mkdir()
    legacy = tmp_path / f".{key}.legacy.work"
    legacy.mkdir()
    created: list[Path] = []
    result = cohort_module.SharedCohort(key, tmp_path, (tmp_path, tmp_path, tmp_path), tmp_path, tmp_path)

    def snapshot(_root: Path, work: Path) -> Path:
        created.append(work)
        work.mkdir()
        return work

    def build(_root: Path, _work: Path, _repo: Path, _staged: Path, _key: str) -> None:
        if fail:
            raise RuntimeError("build refused")

    monkeypatch.setattr(cohort_module, "dev_cache_dir", lambda _name: tmp_path)
    monkeypatch.setattr(cohort_module, "cohort_key", lambda *_args, **_kwargs: key)
    monkeypatch.setattr(cohort_module, "_verified_entry", lambda *_args: None)
    monkeypatch.setattr(cohort_module, "build_root_snapshot", snapshot)
    monkeypatch.setattr(cohort_module, "_build_from", build)
    monkeypatch.setattr(cohort_module, "_publish", lambda *_args: result)
    monkeypatch.setattr(cohort_module, "_prune", lambda *_args: None)
    cohort_module.shared_cohort.cache_clear()
    try:
        if fail:
            with pytest.raises(RuntimeError, match="build refused") as raised:
                cohort_module.shared_cohort(tmp_path)
            assert str(created[0]) in " ".join(raised.value.__notes__)
        else:
            assert cohort_module.shared_cohort(tmp_path) is result
    finally:
        cohort_module.shared_cohort.cache_clear()

    assert len(created) == 1 and created[0].exists() is fail
    assert peer.is_dir() and legacy.is_dir()
