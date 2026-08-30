"""Strict roundtrip across the encrypted ``UsageRecorder`` boundary.

``UsageRecorder`` persists :class:`UsageRecord` rows under the
``cadrumo.outbound.llm.usage`` namespace at
``SensitivityClass.DIAGNOSTIC``.

Anti-tautology: writes two distinct records on different dates with
non-default caller and prompt_id values; asserts both records round-trip
and that the date-range filter on ``load_records`` returns only the
expected entry, witnessing both identity preservation and the date-axis
boundary.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from .....llm.models import LLMProvider, UsageRecord
from .._usage import UsageRecorder

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TODAY = datetime(2026, 5, 28, 12, 40, 0, tzinfo=UTC)


def _record(when: datetime, *, caller: str, prompt_id: str, request_id: str) -> UsageRecord:
    return UsageRecord(
        prompt_id=prompt_id,
        caller=caller,
        text="Casilla 03 records cumulative net revenue for the period.",
        provider=LLMProvider.ANTHROPIC,
        model="claude-opus-4-7",
        input_tokens=137,
        output_tokens=64,
        cost_estimate_usd=Decimal("0.0145"),
        cache_hit=False,
        created_at=when,
        request_id=request_id,
    )


def test_llm_usage_records_survive_encrypted_storage_roundtrip(
    tmp_path: Path,
) -> None:
    """Two UsageRecord rows survive the encrypted append-only sink with date filtering."""

    recorder = UsageRecorder(root_dir=tmp_path / "llm-usage")
    today = _TODAY
    yesterday = today - timedelta(days=1)
    record_today = _record(
        today,
        caller="aeat.cli.modelo.calc",
        prompt_id="casilla_extract_v1",
        request_id="b" * 64,
    )
    record_yesterday = _record(
        yesterday,
        caller="aeat.cli.translation",
        prompt_id="translation_v1",
        request_id="c" * 64,
    )
    recorder.record(record_today)
    recorder.record(record_yesterday)

    all_loaded = recorder.load_records()
    assert len(all_loaded) == 2
    # Identity preserved across the encrypted append-only sink:
    # both records sit in the loaded tuple bit-for-bit.
    assert frozenset(all_loaded) == frozenset([record_today, record_yesterday])

    # Date-axis filter must yield exactly the today-side record.
    only_today = recorder.load_records(since=today.date(), until=today.date())
    assert only_today == (record_today,)

    # Yesterday's record alone via an exclusive lower bound.
    only_yesterday = recorder.load_records(
        since=yesterday.date(),
        until=yesterday.date(),
    )
    assert only_yesterday == (record_yesterday,)

    summary = recorder.summarize(since=date(2000, 1, 1))
    assert summary.entries == 2
    assert summary.total_input_tokens == 274
    assert summary.total_output_tokens == 128
    assert summary.total_cost_estimate_usd == Decimal("0.0290")
