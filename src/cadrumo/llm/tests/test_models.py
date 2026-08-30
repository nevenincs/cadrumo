"""Unit tests for the public pydantic models exported by the LLM subpackage.

Verifies JSON round-trip fidelity for
:class:`cadrumo.llm.LLMRequest`,
:class:`cadrumo.llm.LLMResponse`, and
:class:`cadrumo.llm.Translation`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...core.operator_action_enums import NoRecoveryOutcome
from ..errors import LLMValidationError
from ..models import LLMProvider, LLMRequest, LLMResponse, PromptDefinition, Translation

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_CREATED_AT = datetime(2026, 5, 28, 12, 30, 0, tzinfo=UTC)


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


def test_blank_request_prompt_preserves_its_terminal_condition_through_pydantic() -> None:
    """The model validator keeps the exact refusal for the outer CLI boundary."""
    with pytest.raises(ValidationError) as raised:
        LLMRequest(prompt=" \t")

    nested = raised.value.errors(include_url=False)[0]["ctx"]["error"]
    assert isinstance(nested, LLMValidationError)
    verdict = nested.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "llm.request.prompt_nonempty"
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values == {"request_prompt_nonempty": False}


def test_invalid_prompt_definition_id_preserves_its_terminal_condition_through_pydantic() -> None:
    """Invalid authored prompt metadata cannot fall back to producer prose."""
    with pytest.raises(ValidationError) as raised:
        PromptDefinition(
            id="Not a canonical prompt id",
            version=1,
            template="{{ value }}",
            description="test prompt",
        )

    nested = raised.value.errors(include_url=False)[0]["ctx"]["error"]
    assert isinstance(nested, LLMValidationError)
    verdict = nested.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "llm.prompt_definition.id_valid"
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert verdict.evidence[0].values == {"prompt_definition_id_valid": False}


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
        created_at=_CREATED_AT,
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
        created_at=_CREATED_AT,
    )
    assert Translation.model_validate_json(translation.model_dump_json()) == translation
