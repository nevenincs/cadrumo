from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..paths import allocate_run_directory, run_log_bases, run_log_roots

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
