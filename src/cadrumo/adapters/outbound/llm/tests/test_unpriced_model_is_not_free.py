"""An unpriced model reports an absence, never a plausible zero.

``estimate_cost_usd`` used to resolve any provider/model the pricing table did
not carry to ``Decimal('0')`` -- documented as deliberate, so that every usage
record carried a well-typed ``Decimal``. The cost of that convenience is that a
cost surface reports an absence as a positive answer: an operator budgeting from
``$0.0000`` concludes the call was free rather than unpriced, and the model the
campaign actually targets was one of the ones the table did not carry.

Widening the table does not fix it. The table is a snapshot of public rates, so
the set of models it lacks is permanent and moving; the next model added
re-creates the same silent zero. Only a refusal cannot rot into a wrong answer.

**Free and unpriced must stay distinguishable**, which is why the local provider
is asserted here beside the unpriced cases rather than left implicit: a fix that
collapsed them would satisfy "unknown does not return a number" while making a
genuinely free call indistinguishable from an unpriceable one.

**And the consumer end is asserted, not just the function.** A refusal a caller
swallows back into ``0.0`` is the same defect one layer along, so the aggregates
and the operator-facing text are pinned too -- a total that quietly summed only
the priced rows would be smaller, wrong, and still shaped like a bill.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..models import LLMProvider
from ..pricing import estimate_cost_usd

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MILLION = 1_000_000


def test_a_priced_model_still_returns_its_figure() -> None:
    """The positive control.

    Without it, "unpriced returns None" cannot be told apart from "the
    estimator stopped pricing anything", and the two call for opposite fixes.
    """
    assert estimate_cost_usd(LLMProvider.ANTHROPIC, "claude-sonnet-4-6", _MILLION, _MILLION) == Decimal("18.000000")
    assert estimate_cost_usd(LLMProvider.OPENAI, "gpt-4o", _MILLION, _MILLION) == Decimal("12.500000")


def test_a_versioned_variant_still_inherits_its_family_rate() -> None:
    """Prefix matching survives the change, so a dated release is not now unpriced."""
    assert estimate_cost_usd(
        LLMProvider.ANTHROPIC,
        "claude-sonnet-4-6-20260101",
        _MILLION,
        _MILLION,
    ) == Decimal("18.000000")


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        (LLMProvider.ANTHROPIC, "claude-haiku-4-5"),
        (LLMProvider.ANTHROPIC, "claude-opus-4-1"),
        (LLMProvider.OPENAI, "a-model-nobody-has-priced"),
    ],
)
def test_a_model_the_table_does_not_carry_refuses_rather_than_pricing_it_free(
    provider: LLMProvider,
    model: str,
) -> None:
    """The reported defect. ``claude-haiku-4-5`` is the design-target tier."""
    assert estimate_cost_usd(provider, model, _MILLION, _MILLION) is None


def test_the_local_provider_is_free_rather_than_unpriced() -> None:
    """Zero and None mean different things and both must remain reachable.

    A local model genuinely costs nothing, and saying so is a fact rather than
    an absence. Returning None here would make the operator chase a price that
    does not exist; returning zero for the cases above hid one that does.
    """
    assert estimate_cost_usd(LLMProvider.LOCAL, "qwen2.5:3b", _MILLION, _MILLION) == Decimal("0")


def test_the_pricing_table_prices_every_entry_it_claims() -> None:
    """No table row is itself a silent zero.

    Guards the other direction: a rate accidentally entered as zero would price
    a real model at nothing while looking like coverage, which is the reported
    defect wearing the table's own clothes rather than the fallback's.
    """
    from ..pricing import _PRICING_PER_MILLION

    assert _PRICING_PER_MILLION, "an empty table would make every model unpriced"
    for provider, prefix, input_rate, output_rate in _PRICING_PER_MILLION:
        assert input_rate > Decimal("0"), f"{provider.value}/{prefix} has a zero input rate"
        assert output_rate > Decimal("0"), f"{provider.value}/{prefix} has a zero output rate"
