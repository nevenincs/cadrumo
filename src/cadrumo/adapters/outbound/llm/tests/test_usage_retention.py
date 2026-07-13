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

from .. import LLMProvider
from .._models import UsageRecord
from .._usage import UsageRecorder

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


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
