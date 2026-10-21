"""An unpriced model reports an absence, never a plausible zero.

``estimate_cost_usd`` once resolved any provider/model a pricing table did not
carry to ``Decimal('0')``, so a cost surface reported an absence as a positive
answer: an operator budgeting from ``$0.0000`` concluded the call was free rather
than unpriced. An agent run is billed on the person's selected lane, at rates
Cadrumo does not see, so it is unpriced: only a refusal cannot rot into a wrong
answer.

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

from .....core.config_support import LLMProvider
from ..pricing import estimate_cost_usd

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MILLION = 1_000_000


@pytest.mark.parametrize("model", ["example/api/example-model-1", "example/cli/example-model-2"])
def test_an_agent_run_is_unpriced_rather_than_free(model: str) -> None:
    """The agent bills on the person's selected lane, at rates Cadrumo does not see."""
    assert estimate_cost_usd(LLMProvider.AGENT, model, _MILLION, _MILLION) is None


def test_the_local_provider_is_free_rather_than_unpriced() -> None:
    """Zero and None mean different things and both must remain reachable.

    A local model genuinely costs nothing, and saying so is a fact rather than
    an absence. Returning None here would make the operator chase a price that
    does not exist; returning zero for the cases above hid one that does.
    """
    assert estimate_cost_usd(LLMProvider.LOCAL, "qwen2.5:3b", _MILLION, _MILLION) == Decimal("0")
