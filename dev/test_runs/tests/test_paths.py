from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..paths import (
    SCRATCH_BASE_ENV,
    SCRATCH_PATH_BUDGET,
    SCRATCH_SEPARATOR,
    allocate_run_directory,
    allocate_scratch_directory,
    run_log_bases,
    run_log_families,
    run_log_roots,
    scratch_base,
    scratch_environment,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_run_directory_is_date_partitioned_unique_and_repository_local(tmp_path: Path) -> None:
    instant = datetime(2026, 9, 8, 12, 34, 56, 123456, tzinfo=UTC)

    first = allocate_run_directory(tmp_path, family="audit-runs", label="audit-code", now=instant)
    second = allocate_run_directory(tmp_path, family="audit-runs", label="audit-code", now=instant)

    assert first.parent == tmp_path / ".logs" / "audit-runs" / "2026-09-08"
    assert first.name.startswith("20260908T123456.123456Z-audit-code-")
    assert first != second


def test_every_base_a_run_can_land_under_is_enumerated() -> None:
    """The reaper's population is defined here, and it must cover both writers.

    Repository tooling passes its checkout; a pytest controller does not --
    ``conftest.py`` roots its run under the OS temp directory to keep collection
    storage outside the checkout. Enumerating only the checkout is what left the
    busier base unreaped, so the parity with ``conftest.py`` is asserted against
    that file rather than restated as a second constant.
    """
    bases = run_log_bases()

    assert REPO_ROOT in bases, "repository run families would be left unreaped"
    assert Path(tempfile.gettempdir()) in bases, "pytest controller runs would be left unreaped"
    conftest = (REPO_ROOT / "conftest.py").read_text(encoding="utf-8")
    assert "prepare_environment(Path(tempfile.gettempdir()))" in conftest, (
        "conftest.py no longer roots its run under the OS temp directory; run_log_bases must"
        " be updated to match wherever it roots now, or that base goes unreaped"
    )


def test_a_family_root_is_reported_only_where_it_exists(tmp_path: Path) -> None:
    """``run_log_roots`` filters to real directories, so a missing base is not a failure."""
    present = tmp_path / ".logs" / "test-runs"
    present.mkdir(parents=True)

    assert run_log_roots("test-runs", bases=(tmp_path, tmp_path / "absent")) == (present,)
    assert run_log_roots("never-written", bases=(tmp_path,)) == ()


def test_every_run_family_is_discovered_rather_than_named(tmp_path: Path) -> None:
    """A family nobody enumerated is still found, which is the whole point.

    The reaper judged one family by name and left the rest to be deleted by name
    alone, with no owner check. Discovery is what makes the next family safe
    without anyone remembering to add it: it is found because it exists, across
    every base, and a loose file beside the families is not mistaken for one.
    """
    other = tmp_path / "second-base"
    for family in ("audit-runs", "lane-runs", "test-runs"):
        (tmp_path / ".logs" / family).mkdir(parents=True)
    (other / ".logs" / "test-runs").mkdir(parents=True)
    (other / ".logs" / "unfinished-capture.err").write_text("captured", encoding="utf-8")

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
        assert len(str(scratch)) <= SCRATCH_PATH_BUDGET
    finally:
        scratch.rmdir()
        sibling.rmdir()


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


def test_a_base_too_deep_for_the_temp_budget_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deep = tmp_path / ("d" * SCRATCH_PATH_BUDGET)
    monkeypatch.setenv(SCRATCH_BASE_ENV, str(deep))

    with pytest.raises(RuntimeError, match="TEMP budget"):
        allocate_scratch_directory()

    assert not deep.exists()
