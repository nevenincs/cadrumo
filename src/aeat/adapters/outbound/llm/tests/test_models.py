"""Unit tests for the public pydantic models exported by the LLM subpackage.

Verifies JSON round-trip fidelity for
:class:`aeat.adapters.outbound.llm.LLMRequest`,
:class:`aeat.adapters.outbound.llm.LLMResponse`, and
:class:`aeat.adapters.outbound.llm.Translation`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from .. import LLMProvider, LLMRequest, LLMResponse, Translation

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


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
