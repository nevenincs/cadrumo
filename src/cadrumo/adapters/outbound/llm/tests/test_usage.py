"""Unit tests for usage recording.

Verifies that :class:`cadrumo.adapters.outbound.llm.UsageRecorder` round-trips
records through encrypted secure-object storage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....core.config import override_settings
from .....core.config_support import LLMProvider
from ....persistence.llm.usage import UsageRecorder
from ..models import LLMResponse

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_CREATED_AT = datetime(2026, 5, 28, 12, 35, 0, tzinfo=UTC)


def test_usage_recorder_round_trip(tmp_path: Path) -> None:
    """Usage records preserve accounting fields through encrypted storage."""

    recorder = UsageRecorder(root_dir=tmp_path)
    response = LLMResponse(
        text="ok",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        input_tokens=15,
        output_tokens=6,
        cost_estimate_usd=Decimal("0.000135"),
        cache_hit=False,
        created_at=_CREATED_AT,
        request_id="request-id",
    )
    record = recorder.build_record(response, prompt_id="translation_v1", caller="test-suite")
    path = recorder.record(record)
    assert not path.exists()
    assert recorder.load_records() == (record,)
    loaded = recorder.load_records()[0]
    assert loaded.input_tokens == 15
    assert loaded.output_tokens == 6
    assert loaded.cost_estimate_usd == Decimal("0.000135")


def test_usage_default_root_uses_central_settings(tmp_path: Path) -> None:
    """Direct usage-recorder construction must honor the centralized usage directory."""

    configured_root = tmp_path / "configured-usage"
    with override_settings(cadrumo_llm_usage_dir=configured_root):
        recorder = UsageRecorder()

    response = LLMResponse(
        text="ok",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        input_tokens=15,
        output_tokens=6,
        cost_estimate_usd=Decimal("0.000135"),
        cache_hit=False,
        created_at=_CREATED_AT,
        request_id="request-id",
    )
    record = recorder.build_record(response, prompt_id="translation_v1", caller="test-suite")
    path = recorder.record(record)

    assert recorder.root_dir == configured_root
    assert path.parent == configured_root
    assert not configured_root.exists()
    assert recorder.load_records() == (record,)
