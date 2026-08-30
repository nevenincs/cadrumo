"""Retention-window pruning for :class:`~adapters.outbound.llm.UsageRecorder`.

``prune`` bounds the usage store's growth in two stages mirroring
:meth:`~adapters.outbound.llm.LLMRunTelemetryRecorder.prune`: an age cutoff
(``retention_days``) then a record-count cap (``max_records``). Ages are
anchored to real wall-clock time via each record's own ``created_at`` (not a
frozen clock, which would also freeze the storage runtime's idle-session-expiry
check and spuriously expire the active bucket session). Assertions check which
records survive by ``request_id`` identity, not merely a post-prune count.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from .....adapters.persistence.storage import secure_object_repository_for_active_bucket
from .....core.classification import SensitivityClass
from .....core.hashing import canonical_json_bytes
from .....core.redaction import default_rules_for_class, redact_structured
from .....llm.errors import LLMCacheError
from .....llm.models import LLMProvider, UsageRecord
from .._usage import _USAGE_NAMESPACE, _USAGE_VERSION, UsageRecorder

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _inject_corrupt_usage_record(recorder: UsageRecorder, *, request_id: str, anchor: datetime) -> None:
    """Persist a malformed payload that lacks the required ``object_key_uuid``."""
    record = _record(1, request_id=request_id, anchor=anchor)
    redacted = redact_structured(
        record.model_dump(mode="json"),
        rules=default_rules_for_class(SensitivityClass.DIAGNOSTIC),
    )
    payload = {"logical_root": recorder._logical_root(), "record": redacted}
    secure_object_repository_for_active_bucket().save(
        namespace=_USAGE_NAMESPACE,
        object_key=f"{recorder._logical_root()}|{record.created_at.isoformat()}|{request_id}|corrupt",
        classification=SensitivityClass.DIAGNOSTIC,
        schema_version=_USAGE_VERSION,
        written_at=record.created_at,
        payload=canonical_json_bytes(payload),
    )


def _record(days_ago: int, *, request_id: str, anchor: datetime) -> UsageRecord:
    return UsageRecord(
        prompt_id="translation_v1",
        caller="cadrumo.application.ledger.llm_classification",
        text="usage probe",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        input_tokens=10,
        output_tokens=2,
        cost_estimate_usd=Decimal("0.000060"),
        cache_hit=False,
        created_at=anchor - timedelta(days=days_ago),
        request_id=request_id,
    )


def test_prune_removes_records_older_than_retention_window(tmp_path: Path) -> None:
    anchor = datetime.now(UTC)
    recorder = UsageRecorder(root_dir=tmp_path / "llm-usage")
    recorder.record(_record(1, request_id="fresh", anchor=anchor))
    recorder.record(_record(45, request_id="stale", anchor=anchor))

    removed = recorder.prune(retention_days=30, max_records=1000)

    assert removed == 1
    assert {item.request_id for item in recorder.load_records()} == {"fresh"}


def test_prune_keeps_records_inside_both_bounds(tmp_path: Path) -> None:
    anchor = datetime.now(UTC)
    recorder = UsageRecorder(root_dir=tmp_path / "llm-usage")
    recorder.record(_record(1, request_id="a", anchor=anchor))
    recorder.record(_record(2, request_id="b", anchor=anchor))

    removed = recorder.prune(retention_days=30, max_records=1000)

    assert removed == 0
    assert {item.request_id for item in recorder.load_records()} == {"a", "b"}


def test_prune_enforces_max_records_cap_evicting_oldest_first(tmp_path: Path) -> None:
    anchor = datetime.now(UTC)
    recorder = UsageRecorder(root_dir=tmp_path / "llm-usage")
    for age in range(5, 0, -1):
        recorder.record(_record(age, request_id=f"req-{age}", anchor=anchor))

    removed = recorder.prune(retention_days=3650, max_records=3)

    assert removed == 2
    remaining = {item.request_id for item in recorder.load_records()}
    # The three most-recent (smallest age) survive; the two oldest are evicted.
    assert remaining == {"req-1", "req-2", "req-3"}


def test_prune_defaults_to_central_settings(tmp_path: Path) -> None:
    anchor = datetime.now(UTC)
    recorder = UsageRecorder(root_dir=tmp_path / "llm-usage")
    recorder.record(_record(1, request_id="fresh", anchor=anchor))
    recorder.record(_record(400, request_id="ancient", anchor=anchor))

    # No explicit args: retention_days defaults to cadrumo_llm_usage_retention_days (30).
    removed = recorder.prune()

    assert removed == 1
    assert {item.request_id for item in recorder.load_records()} == {"fresh"}


def test_client_construction_sweeps_the_usage_store(tmp_path: Path) -> None:
    """Building an LLMClient fires the retention sweep over its usage recorder.

    Records persist through ``record`` (which does not prune); constructing an
    ``LLMClient`` around the recorder then prunes stale records via the
    once-per-client retention sweep - proving retention fires in production
    rather than relying on a manual prune() call.
    """
    from .....llm.client import LLMClient

    anchor = datetime.now(UTC)
    recorder = UsageRecorder(root_dir=tmp_path / "llm-usage")
    recorder.record(_record(1, request_id="fresh", anchor=anchor))
    recorder.record(_record(400, request_id="stale", anchor=anchor))

    LLMClient(usage_recorder=recorder)

    assert {item.request_id for item in recorder.load_records()} == {"fresh"}


def test_read_path_refuses_record_missing_object_key_uuid(tmp_path: Path) -> None:
    """The normal read path treats a missing writer-owned UUID as corruption."""
    anchor = datetime.now(UTC)
    recorder = UsageRecorder(root_dir=tmp_path / "llm-usage")
    _inject_corrupt_usage_record(recorder, request_id="corrupt", anchor=anchor)

    with pytest.raises(LLMCacheError, match="object_key_uuid"):
        recorder.load_records()


def test_prune_hard_refuses_a_record_missing_object_key_uuid(tmp_path: Path) -> None:
    """prune cannot reconstruct a uuid-less record's key, so it refuses loudly."""
    anchor = datetime.now(UTC)
    recorder = UsageRecorder(root_dir=tmp_path / "llm-usage")
    _inject_corrupt_usage_record(recorder, request_id="corrupt", anchor=anchor)

    with pytest.raises(LLMCacheError, match="object_key_uuid"):
        recorder.prune(retention_days=30, max_records=1000)
