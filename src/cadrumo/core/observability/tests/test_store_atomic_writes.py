"""Atomic-replacement contract for persisted run artifacts.

:func:`~core.observability.save_trace` and
:func:`~core.observability.save_envelope` are durable run evidence that a
later diagnostics read back, so neither may overwrite its
destination in place: a crash, kill, or raise part-way through the write
would leave a torn artifact behind a name that a reader trusts.

Both writers therefore route through the canonical standard-tier atomic
text owner, which stages a sibling tempfile and swaps it in with
:func:`os.replace`. These tests pin that routing by observation rather
than by inspection. A second hard link to the pre-existing destination
holds a durable handle on the original inode: an in-place write is
visible through that handle, an atomic stage-and-replace is not. The
failure tests induce a REAL :func:`os.replace` refusal -- a directory
occupying the destination path -- rather than patching any part of the
write sequence, matching the real-behaviour discipline in
``core/tests/test_atomic_write.py``.

See Also:
    :func:`~core.observability.save_trace`
        Redacts, then persists the run trace through the atomic owner.
    :func:`~core.observability.save_envelope`
        Persists the emitted envelope document through the same owner.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....tests.storage_scope import storage_overrides
from ...config import override_settings
from ...directory_scan import scan_directory
from ...storage_taxonomy import StorageCategory
from ..errors import RunTracePersistenceError
from ..models import RunOutcome, RunTrace
from ..store import ENVELOPE_FILENAME, TRACE_FILENAME, runs_dir, save_envelope, save_trace

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RUN_ID = "0123456789abcdef"
_STARTED_AT = datetime(2026, 4, 14, tzinfo=UTC)
_FINISHED_AT = datetime(2026, 4, 14, 0, 0, 1, tzinfo=UTC)
_STALE_ARTIFACT = "STALE-BUT-COMPLETE-PRIOR-ARTIFACT"


def _trace(run_id: str = _RUN_ID) -> RunTrace:
    return RunTrace(
        run_id=run_id,
        started_at=_STARTED_AT,
        finished_at=_FINISHED_AT,
        entrypoint="cadrumo hello",
        arguments=(),
        corpus_sha256="b" * 64,
        db_sha256="c" * 64,
        cert_fingerprint="",
        outcome=RunOutcome.OK,
    )


def _seed_prior_artifact(target: Path) -> Path:
    """Create ``target`` with prior content and return a same-inode witness."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_STALE_ARTIFACT, encoding="utf-8")
    witness = target.with_name(f"{target.stem}-witness{target.suffix}")
    os.link(target, witness)
    assert target.stat().st_ino == witness.stat().st_ino
    return witness


class TestSaveTraceReplacesAtomically:
    """`save_trace` swaps in a staged artifact instead of writing in place."""

    def test_prior_trace_inode_never_receives_the_new_artifact(self, tmp_path: Path) -> None:
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            target = runs_dir() / _RUN_ID / TRACE_FILENAME
            witness = _seed_prior_artifact(target)

            save_trace(_trace())

            assert '"run_id"' in target.read_text(encoding="utf-8")
            assert witness.read_text(encoding="utf-8") == _STALE_ARTIFACT
            assert target.stat().st_ino != witness.stat().st_ino
            assert scan_directory(target.parent, pattern="*.tmp") == ()

    def test_real_replace_failure_leaves_no_temporary_file(self, tmp_path: Path) -> None:
        """A directory occupying ``trace.json`` is a real ``os.replace`` refusal."""
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            target = runs_dir() / _RUN_ID / TRACE_FILENAME
            target.mkdir(parents=True, exist_ok=True)
            (target / "marker.txt").write_text("still a directory", encoding="utf-8")

            with pytest.raises(RunTracePersistenceError):
                save_trace(_trace())

            assert target.is_dir()
            assert (target / "marker.txt").read_text(encoding="utf-8") == "still a directory"
            assert scan_directory(target.parent, pattern="*.tmp") == ()


class TestSaveEnvelopeReplacesAtomically:
    """`save_envelope` swaps in a staged artifact instead of writing in place."""

    def test_prior_envelope_inode_never_receives_the_new_artifact(self, tmp_path: Path) -> None:
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            target = runs_dir() / _RUN_ID / ENVELOPE_FILENAME
            witness = _seed_prior_artifact(target)

            save_envelope(_RUN_ID, {"schema_version": 2, "status": "success"})

            assert '"status"' in target.read_text(encoding="utf-8")
            assert witness.read_text(encoding="utf-8") == _STALE_ARTIFACT
            assert target.stat().st_ino != witness.stat().st_ino
            assert scan_directory(target.parent, pattern="*.tmp") == ()

    def test_real_replace_failure_leaves_no_temporary_file(self, tmp_path: Path) -> None:
        """A directory occupying ``envelope.json`` is a real ``os.replace`` refusal."""
        with override_settings(**storage_overrides(tmp_path, StorageCategory.RUNS)):
            target = runs_dir() / _RUN_ID / ENVELOPE_FILENAME
            target.mkdir(parents=True, exist_ok=True)
            (target / "marker.txt").write_text("still a directory", encoding="utf-8")

            with pytest.raises(RunTracePersistenceError):
                save_envelope(_RUN_ID, {"schema_version": 2, "status": "success"})

            assert target.is_dir()
            assert (target / "marker.txt").read_text(encoding="utf-8") == "still a directory"
            assert scan_directory(target.parent, pattern="*.tmp") == ()


__all__: list[str] = []
