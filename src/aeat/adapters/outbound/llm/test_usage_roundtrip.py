"""Strict roundtrip across the encrypted ``UsageRecorder`` boundary.

``UsageRecorder`` persists :class:`UsageRecord` rows under the
``aeat.outbound.llm.usage`` namespace at
``SensitivityClass.DIAGNOSTIC``. Flagged as untested in the persistence-
boundary identity audit.

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

from ...persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from ...persistence.storage.sql import SecureObjectRepository
from ...persistence.storage.sql._orm import Base
from ...persistence.storage.sql.engine import create_engine_from_settings
from ....core.config import Settings
from ._models import LLMProvider, UsageRecord
from ._usage import UsageRecorder

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two UsageRecord rows survive the encrypted append-only sink with date filtering."""

    provider = EphemeralMasterKeyProvider()
    override_master_key_provider(provider)
    db_path = tmp_path / "llm-usage-roundtrip.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    try:
        SecureObjectRepository(engine=engine)

        recorder = UsageRecorder(root_dir=tmp_path / "llm-usage")
        today = datetime.now(UTC).replace(microsecond=0)
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
        assert set(all_loaded) == {record_today, record_yesterday}

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
    finally:
        engine.dispose()
        override_master_key_provider(None)
