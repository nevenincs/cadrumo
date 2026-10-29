from __future__ import annotations

import json
import os
import shutil
import stat
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dev import _paths
from dev._paths import REPO_ROOT, TEMP_ROOT

from .. import paths
from ..paths import (
    SCRATCH_PREFIX,
    SCRATCH_SEPARATOR,
    ScratchAllocation,
    ScratchOwnershipError,
    allocate_run_directory,
    allocate_scratch_directory,
    remove_scratch_directory,
    run_log_bases,
    run_log_families,
    run_log_roots,
    scratch_base,
    scratch_environment,
)
from ..paths import (
    test_log_root as configured_test_log_root,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_run_directory_is_date_partitioned_unique_and_repository_local(tmp_path: Path) -> None:
    instant = datetime(2026, 9, 8, 12, 34, 56, 123456, tzinfo=UTC)

    first = allocate_run_directory(tmp_path, family="audit-runs", label="audit-code", now=instant)
    second = allocate_run_directory(tmp_path, family="audit-runs", label="audit-code", now=instant)

    assert first.parent == tmp_path / "logs" / "audit-runs" / "2026-09-08"
    assert first.name.startswith("20260908T123456.123456Z-audit-code-")
    assert first != second


@pytest.mark.parametrize("family,label", [("../outside", "run"), ("safe", "../outside"), ("C:\\outside", "run")])
def test_run_directory_rejects_traversal(tmp_path: Path, family: str, label: str) -> None:
    with pytest.raises(ValueError, match="one path component"):
        allocate_run_directory(tmp_path, family=family, label=label)
    assert not (tmp_path / "logs").exists()


def test_every_base_a_run_can_land_under_is_enumerated() -> None:
    """The reaper's population is defined here, and it must cover both writers.

    New output follows the configured storage root. The checkout and OS temp
    bases remain enumerable for old runs that predate storage-root routing.
    """
    bases = run_log_bases()

    assert configured_test_log_root() in bases, "configured run families would be left unreaped"
    assert REPO_ROOT in bases, "legacy repository run families would be left unreaped"
    assert configured_test_log_root() == TEMP_ROOT
    conftest = (REPO_ROOT / "conftest.py").read_text(encoding="utf-8")
    assert "prepare_environment(" in conftest


def test_a_family_root_is_reported_only_where_it_exists(tmp_path: Path) -> None:
    """``run_log_roots`` filters to real directories, so a missing base is not a failure."""
    present = tmp_path / "logs" / "test-runs"
    present.mkdir(parents=True)

    assert run_log_roots("test-runs", bases=(tmp_path, tmp_path / "absent")) == (present,)
    assert run_log_roots("never-written", bases=(tmp_path,)) == ()


def test_legacy_log_roots_remain_discoverable(tmp_path: Path) -> None:
    legacy = tmp_path / ".logs" / "audit-runs"
    legacy.mkdir(parents=True)
    assert run_log_roots("audit-runs", bases=(tmp_path,)) == (legacy,)
    assert run_log_families(bases=(tmp_path,)) == ("audit-runs",)


@pytest.mark.parametrize("stem", ["logs", ".logs"])
def test_discovery_never_follows_linked_log_containers_or_families(tmp_path: Path, stem: str) -> None:
    outside = tmp_path / "outside"
    (outside / "audit-runs").mkdir(parents=True)
    base = tmp_path / "base"
    base.mkdir()
    link = base / stem
    link.symlink_to(outside, target_is_directory=True)
    assert run_log_families(bases=(base,)) == ()
    assert run_log_roots("audit-runs", bases=(base,)) == ()
    link.unlink()
    link.mkdir()
    (link / "audit-runs").symlink_to(outside / "audit-runs", target_is_directory=True)
    assert run_log_families(bases=(base,)) == ()
    assert run_log_roots("audit-runs", bases=(base,)) == ()


def test_allocator_refuses_linked_log_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "checkout"
    temp = root / ".tmp"
    temp.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (temp / "logs").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(_paths, "REPO_ROOT", root)
    monkeypatch.setattr(_paths, "TEMP_ROOT", temp)
    monkeypatch.setattr(paths, "REPO_ROOT", root)
    monkeypatch.setenv("CADRUMO_TEST_LOG_ROOT", str(temp))
    with pytest.raises(ValueError, match="link"):
        allocate_run_directory(root, family="audit-runs", label="probe")
    assert list(outside.iterdir()) == []


def test_every_run_family_is_discovered_rather_than_named(tmp_path: Path) -> None:
    """A family nobody enumerated is still found, which is the whole point.

    The reaper judged one family by name and left the rest to be deleted by name
    alone, with no owner check. Discovery is what makes the next family safe
    without anyone remembering to add it: it is found because it exists, across
    every base, and a loose file beside the families is not mistaken for one.
    """
    other = tmp_path / "second-base"
    for family in ("audit-runs", "lane-runs", "test-runs"):
        (tmp_path / "logs" / family).mkdir(parents=True)
    (other / "logs" / "test-runs").mkdir(parents=True)
    (other / "logs" / "unfinished-capture.err").write_text("captured", encoding="utf-8")

    assert run_log_families(bases=(tmp_path, other)) == ("audit-runs", "lane-runs", "test-runs")
    assert run_log_families(bases=(tmp_path / "absent",)) == ()


def test_run_scratch_is_short_owned_and_beside_the_pinned_base() -> None:
    base = scratch_base()
    scratch = allocate_scratch_directory()
    sibling = allocate_scratch_directory()
    try:
        assert scratch.is_dir()
        assert scratch.parent == base
        assert scratch.name.split(SCRATCH_SEPARATOR)[1] == str(os.getpid())
        assert sibling != scratch
    finally:
        scratch.rmdir()
        sibling.rmdir()


def test_external_scratch_override_does_not_escape_the_worktree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CADRUMO_SCRATCH_BASE", str(tmp_path.anchor))
    assert scratch_base() == TEMP_ROOT


def test_real_worktree_run_logs_are_confined_to_temporary_root() -> None:
    run = allocate_run_directory(REPO_ROOT, family="audit-runs", label="probe")
    assert run.is_relative_to(TEMP_ROOT / "logs")


def test_run_bases_validate_and_discover_declared_native_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "checkout"
    build = root / "build" / "preset"
    build.mkdir(parents=True)
    (root / "CMakePresets.json").write_text(json.dumps({"configurePresets": [{"name": "preset"}]}), encoding="utf-8")
    distribution = root / "native" / "cmake" / "distribution"
    distribution.mkdir(parents=True)
    (distribution / "CMakePresets.json").write_text(json.dumps({"configurePresets": []}), encoding="utf-8")
    (build / "build-paths.json").write_text(
        json.dumps({"source": str(root), "paths": {"testing": "testing"}}), encoding="utf-8"
    )
    monkeypatch.setattr(_paths, "REPO_ROOT", root)
    monkeypatch.setattr(_paths, "TEMP_ROOT", root / ".tmp")
    monkeypatch.setattr(paths, "REPO_ROOT", root)
    monkeypatch.setenv("CADRUMO_TEST_LOG_ROOT", str(build / "testing" / "run-logs"))
    monkeypatch.setenv("CADRUMO_SCRATCH_BASE", str(build / "testing" / "scratch"))
    assert configured_test_log_root() == build / "testing" / "run-logs"
    assert scratch_base() == build / "testing" / "scratch"
    run = allocate_run_directory(root, family="audit-runs", label="probe")
    run.mkdir(parents=True)
    assert run_log_roots("audit-runs") == (run.parents[1],)


def test_run_bases_reject_traversal_before_allocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "checkout"
    root.mkdir()
    monkeypatch.setattr(_paths, "REPO_ROOT", root)
    monkeypatch.setattr(_paths, "TEMP_ROOT", root / ".tmp")
    monkeypatch.setenv("CADRUMO_SCRATCH_BASE", str(root / ".tmp" / ".." / "escape"))
    with pytest.raises(ValueError, match="traversal"):
        allocate_scratch_directory()
    assert not (root / "escape").exists()


def test_nested_runs_allocate_beside_the_first_rather_than_inside_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """A child run inherits the parent's TEMP; its scratch must not nest inside it."""
    outer = allocate_scratch_directory()
    try:
        for name, value in scratch_environment(outer).items():
            monkeypatch.setenv(name, value)
        inner = allocate_scratch_directory()
        inner.rmdir()
    finally:
        outer.rmdir()

    assert inner.parent == outer.parent


@pytest.fixture
def scratch() -> Iterator[Path]:
    """Allocate a real scratch beside this run's, and remove whatever a refusal left of it."""
    allocated = allocate_scratch_directory()
    try:
        yield allocated
    finally:
        if allocated.is_symlink() or allocated.is_junction():
            allocated.unlink()
        elif allocated.exists():
            shutil.rmtree(allocated)


def test_a_scratch_is_removed_whole_without_following_a_link_out_of_it(scratch: Path, tmp_path: Path) -> None:
    """Everything inside goes, a read-only member included; what a link inside points at stays."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "kept.txt").write_text("not the scratch's to remove", encoding="utf-8")
    nested = scratch / "pytest" / "gw0" / "test_case0"
    nested.mkdir(parents=True)
    (nested / "payload.bin").write_bytes(b"\0" * 4096)
    read_only = scratch / "read-only.txt"
    read_only.write_text("read-only member", encoding="utf-8")
    read_only.chmod(stat.S_IREAD)
    # Unguarded: a host that cannot create a directory symlink reports a red
    # naming the OS refusal, rather than a skip that retires this proof.
    (scratch / "link-out").symlink_to(outside, target_is_directory=True)
    allocation = ScratchAllocation.record(scratch)

    remove_scratch_directory(allocation)

    assert not scratch.exists()
    assert (outside / "kept.txt").read_text(encoding="utf-8") == "not the scratch's to remove"


def test_a_scratch_another_process_allocated_is_refused_and_left_intact(scratch: Path, tmp_path: Path) -> None:
    """An xdist worker or nested pytest inherits its controller's scratch; it may never remove it."""
    foreign = tmp_path / SCRATCH_SEPARATOR.join((SCRATCH_PREFIX, str(os.getpid() + 1), "abc123"))
    foreign.mkdir()
    with pytest.raises(ScratchOwnershipError, match="not a scratch directory named for process"):
        ScratchAllocation.record(foreign)
    status = foreign.stat()
    as_seen_by_another_owner = ScratchAllocation(foreign, os.getpid(), (status.st_dev, status.st_ino))
    with pytest.raises(ScratchOwnershipError, match="not named as the scratch of process"):
        remove_scratch_directory(as_seen_by_another_owner)
    assert foreign.is_dir()

    recorded = ScratchAllocation.record(scratch)
    with pytest.raises(ScratchOwnershipError, match="belongs to process"):
        remove_scratch_directory(ScratchAllocation(scratch, os.getpid() + 1, recorded.identity))
    assert scratch.is_dir()


def test_a_path_outside_the_allocation_is_refused_and_left_intact(tmp_path: Path) -> None:
    unrelated = tmp_path / "not-a-scratch"
    unrelated.mkdir()
    (unrelated / "precious.txt").write_text("keep", encoding="utf-8")
    status = unrelated.stat()

    with pytest.raises(ScratchOwnershipError, match="not named as the scratch"):
        remove_scratch_directory(ScratchAllocation(unrelated, os.getpid(), (status.st_dev, status.st_ino)))

    assert (unrelated / "precious.txt").read_text(encoding="utf-8") == "keep"


def test_a_directory_replacing_the_allocation_under_its_name_is_refused(scratch: Path) -> None:
    allocation = ScratchAllocation.record(scratch)
    scratch.rmdir()
    scratch.mkdir()
    (scratch / "someone-elses.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ScratchOwnershipError, match="no longer the directory this run allocated"):
        remove_scratch_directory(allocation)

    assert (scratch / "someone-elses.txt").read_text(encoding="utf-8") == "keep"


def test_a_link_standing_in_for_the_scratch_is_refused_and_its_target_left_intact(
    scratch: Path, tmp_path: Path
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "precious.txt").write_text("keep", encoding="utf-8")
    allocation = ScratchAllocation.record(scratch)
    scratch.rmdir()
    scratch.symlink_to(target, target_is_directory=True)

    with pytest.raises(ScratchOwnershipError, match="is a link"):
        remove_scratch_directory(allocation)

    assert (target / "precious.txt").read_text(encoding="utf-8") == "keep"
