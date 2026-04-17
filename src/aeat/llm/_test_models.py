"""Unit tests for public LLM models."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from . import LLMProvider, LLMRequest, LLMResponse, Translation


@pytest.mark.unit
def test_llm_request_round_trip() -> None:
    """LLMRequest should round-trip through JSON."""

    request = LLMRequest(
        prompt="Translate this",
        system="Be precise.",
        max_tokens=128,
        temperature=0.0,
        language="es",
        cache_key="translation_v1",
        provider_override=LLMProvider.ANTHROPIC,
        model_override="claude-sonnet-4-6",
    )
    assert LLMRequest.model_validate_json(request.model_dump_json()) == request


@pytest.mark.unit
def test_llm_response_round_trip() -> None:
    """LLMResponse should round-trip through JSON."""

    response = LLMResponse(
        text="Resumen",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        input_tokens=10,
        output_tokens=4,
        cost_estimate_usd=Decimal("0.000090"),
        cache_hit=False,
        created_at=datetime.now(UTC),
        request_id="abc123",
    )
    assert LLMResponse.model_validate_json(response.model_dump_json()) == response


@pytest.mark.unit
def test_translation_round_trip() -> None:
    """Translation should round-trip through JSON."""

    translation = Translation(
        text="Hola",
        source_lang="en",
        target_lang="es",
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-6",
        input_tokens=8,
        output_tokens=3,
        created_at=datetime.now(UTC),
    )
    assert Translation.model_validate_json(translation.model_dump_json()) == translation
