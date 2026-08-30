"""Retention-window pruning for :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`.

``prune`` bounds the run-telemetry store's growth in two stages: an age
cutoff (``retention_days``) and a record-count cap (``max_records``). Both
default to the centralized :class:`~core.config.Settings` fields, and
both accept an explicit per-call override.

Ages are anchored to real wall-clock time (``datetime.now(UTC)``) rather than
:func:`~core.time.frozen_clock`: freezing the clock would also freeze the
storage runtime's idle-session-expiry check (which reads the same clock seam),
and an arbitrary frozen instant unrelated to the session's real
``opened_at + idle_window`` deadline spuriously expires the test's active
bucket session.

Anti-tautology: every assertion checks *which* records survive pruning by
``run_id`` identity, not merely a post-prune count -- a broken cutoff or an
inverted oldest/newest ordering would flip which records are removed and
fail these tests even if the raw counts happened to coincide.

See Also:
    :class:`~adapters.outbound.llm.LLMRunTelemetryRecorder`
        Local-only recorder whose ``prune`` method enforces age and count
        bounds.
    :class:`~adapters.outbound.llm.LLMRunRecord`
        Diagnostic metadata record used to assert survivor identity.
    :class:`~adapters.outbound.llm.LLMCache`
        Cache store whose list-then-delete prune shape is mirrored by run
        telemetry.
    :data:`~adapters.persistence.storage.LLM_RUN_TELEMETRY_NAMESPACE`
        Secure-object namespace that keeps run telemetry local and diagnostic.
    :class:`~core.config.Settings`
        Central source for the default telemetry retention window and cap.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from .....adapters.persistence.storage import secure_object_repository_for_active_bucket
from .....core.classification import SensitivityClass
from .....core.config import override_settings
from .....core.hashing import canonical_json_bytes
from .....llm.errors import LLMCacheError
from .._run_telemetry import (
    _RUN_TELEMETRY_NAMESPACE,
    _RUN_TELEMETRY_VERSION,
    LLMRunRecord,
    LLMRunTelemetryRecorder,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _record(days_ago: int, *, run_id: str, anchor: datetime) -> LLMRunRecord:
    return LLMRunRecord(
        run_id=run_id,
        caller="cadrumo.application.ledger.llm_classification",
        provider="claude",
        model="claude-opus-4-7",
        duration_ms=1000,
        succeeded=True,
        started_at=anchor - timedelta(days=days_ago),
    )


def test_prune_removes_records_older_than_retention_window(tmp_path: Path) -> None:
    """A record older than the retention window is pruned; a fresher one survives."""
    anchor = datetime.now(UTC)
    recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "llm-run-telemetry")
    fresh = _record(1, run_id="fresh", anchor=anchor)
    stale = _record(45, run_id="stale", anchor=anchor)
    recorder.record(fresh)
    recorder.record(stale)

    removed = recorder.prune(retention_days=30, max_records=1000)

    assert removed == 1
    remaining_ids = {item.run_id for item in recorder.load_records()}
    assert remaining_ids == {"fresh"}


def test_prune_keeps_records_inside_the_window(tmp_path: Path) -> None:
    """Nothing is removed when every record is inside both bounds."""
    anchor = datetime.now(UTC)
    recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "llm-run-telemetry")
    recorder.record(_record(1, run_id="a", anchor=anchor))
    recorder.record(_record(2, run_id="b", anchor=anchor))

    removed = recorder.prune(retention_days=30, max_records=1000)

    assert removed == 0
    assert {item.run_id for item in recorder.load_records()} == {"a", "b"}


def test_prune_enforces_max_records_cap_evicting_oldest_first(tmp_path: Path) -> None:
    """When the count cap is exceeded, the oldest surviving records are evicted first."""
    anchor = datetime.now(UTC)
    recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "llm-run-telemetry")
    # Five records, all inside the age window, ages 5..1 days ago (5 oldest, 1 newest).
    for age in range(5, 0, -1):
        recorder.record(_record(age, run_id=f"run-{age}", anchor=anchor))

    removed = recorder.prune(retention_days=30, max_records=3)

    assert removed == 2
    remaining_records = recorder.load_records()
    assert all(item.started_at.utcoffset() == timedelta(0) for item in remaining_records)
    remaining_ids = {item.run_id for item in remaining_records}
    # The three most-recent (smallest age) records survive; the two oldest are gone.
    assert remaining_ids == {"run-1", "run-2", "run-3"}


def test_prune_defaults_come_from_centralized_settings(tmp_path: Path) -> None:
    """With no explicit args, ``prune`` reads the centralized retention settings."""
    anchor = datetime.now(UTC)
    recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "llm-run-telemetry")
    recorder.record(_record(1, run_id="fresh", anchor=anchor))
    recorder.record(_record(400, run_id="ancient", anchor=anchor))

    with override_settings(
        cadrumo_llm_run_telemetry_retention_days=30,
        cadrumo_llm_run_telemetry_max_records=1000,
    ):
        removed = recorder.prune()

    assert removed == 1
    assert {item.run_id for item in recorder.load_records()} == {"fresh"}


def test_prune_is_idempotent_on_an_already_pruned_store(tmp_path: Path) -> None:
    """Running prune twice in a row removes nothing the second time."""
    anchor = datetime.now(UTC)
    recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "llm-run-telemetry")
    recorder.record(_record(1, run_id="fresh", anchor=anchor))
    recorder.record(_record(45, run_id="stale", anchor=anchor))

    first_pass = recorder.prune(retention_days=30, max_records=1000)
    second_pass = recorder.prune(retention_days=30, max_records=1000)

    assert first_pass == 1
    assert second_pass == 0
    assert {item.run_id for item in recorder.load_records()} == {"fresh"}


def test_load_records_raises_on_a_payload_missing_its_object_key_uuid(tmp_path: Path) -> None:
    """Anti-tautology proof: a corrupted payload with no ``object_key_uuid`` raises loudly.

    This is not a legacy-migration tolerance branch (``no-legacy-compatibility``):
    every record written by :meth:`~adapters.outbound.llm.LLMRunTelemetryRecorder.record` always carries
    ``object_key_uuid``, so a payload missing it can only be storage corruption or
    a malformed direct write, and the loader must refuse rather than silently
    reconstruct a malformed delete key.
    """
    root_dir = tmp_path / "llm-run-telemetry"
    recorder = LLMRunTelemetryRecorder(root_dir=root_dir)
    good = _record(1, run_id="good", anchor=datetime.now(UTC))
    recorder.record(good)

    # Directly inject a malformed sibling payload lacking ``object_key_uuid``,
    # bypassing ``record`` to simulate storage corruption rather than the
    # recorder's own (always-well-formed) write path.
    corrupted = _record(2, run_id="corrupted", anchor=datetime.now(UTC))
    malformed_payload = {
        "logical_root": root_dir.resolve().as_posix(),
        "record": corrupted.model_dump(mode="json"),
    }
    secure_object_repository_for_active_bucket().save(
        namespace=_RUN_TELEMETRY_NAMESPACE,
        object_key="|".join((root_dir.resolve().as_posix(), corrupted.started_at.isoformat(), "corrupted", "no-uuid")),
        classification=SensitivityClass.DIAGNOSTIC,
        schema_version=_RUN_TELEMETRY_VERSION,
        written_at=corrupted.started_at,
        payload=canonical_json_bytes(malformed_payload),
    )

    with pytest.raises(LLMCacheError, match="object_key_uuid"):
        recorder.load_records()


def test_client_construction_sweeps_the_run_telemetry_store(tmp_path: Path) -> None:
    """Building an LLMClient fires the retention sweep over its run-telemetry recorder.

    Records persist through ``record`` (which does not prune); constructing an
    ``LLMClient`` around the recorder then prunes stale records via the
    once-per-client retention sweep - proving the retention R3 promises fires in
    production rather than depending on a manual prune() call.
    """
    from .....llm.client import LLMClient

    anchor = datetime.now(UTC)
    recorder = LLMRunTelemetryRecorder(root_dir=tmp_path / "llm-run-telemetry")
    recorder.record(_record(1, run_id="fresh", anchor=anchor))
    recorder.record(_record(45, run_id="stale", anchor=anchor))

    LLMClient(run_telemetry_recorder=recorder)

    assert {item.run_id for item in recorder.load_records()} == {"fresh"}
