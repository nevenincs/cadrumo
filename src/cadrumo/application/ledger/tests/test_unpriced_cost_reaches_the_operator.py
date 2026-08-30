"""An unpriced call stays visible all the way to the surface an operator reads.

Refusing to price an unknown model is only half the fix. Every layer above the
estimator sums costs, and a sum that skipped the unpriced rows would return a
smaller number still shaped like a bill -- the same defect one layer along, and
harder to see because the total looks complete.

So the aggregate poisons rather than skips: one unpriced record makes the whole
total unavailable, and a count travels beside it so the absence is attributable
instead of merely total.

The per-provider fold is exercised through the real
:func:`~application.ledger.llm_diagnostics.build_llm_diagnostics_report` shapes rather than by
asserting the helper in isolation, because the defect being guarded lives in the
FOLD -- an implementation that dropped ``None`` rows on the way in would satisfy
any assertion made about the estimator alone.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....llm.models import LLMProvider, UsageRecord
from ..llm_diagnostics import _aggregate_usage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _record(cost: Decimal | None, *, provider: LLMProvider = LLMProvider.ANTHROPIC) -> UsageRecord:
    return UsageRecord(
        prompt_id="p",
        caller="test",
        text="",
        provider=provider,
        model="claude-haiku-4-5" if cost is None else "claude-sonnet-4-6",
        input_tokens=1000,
        output_tokens=1000,
        cost_estimate_usd=cost,
        cache_hit=False,
        created_at=datetime(2026, 8, 8, tzinfo=UTC),
        request_id="r" * 8,
    )


def test_a_provider_with_only_priced_calls_reports_their_sum() -> None:
    """The positive control: the fold still totals when everything is priced."""
    rows = _aggregate_usage([_record(Decimal("1.50")), _record(Decimal("2.25"))])

    assert len(rows) == 1
    assert rows[0].cost_estimate_usd == Decimal("3.75")
    assert rows[0].unpriced_calls == 0


def test_one_unpriced_call_makes_the_provider_total_unavailable() -> None:
    """The sum is withheld rather than quietly computed over the priced subset.

    ``1.50`` would be a defensible-looking answer and a wrong one: it is the
    cost of some of the calls, presented as the cost of all of them.
    """
    rows = _aggregate_usage([_record(Decimal("1.50")), _record(None)])

    assert len(rows) == 1
    assert rows[0].cost_estimate_usd is None
    assert rows[0].unpriced_calls == 1
    # The rest of the row is still reported: an unpriceable cost must not
    # suppress the token counts an operator can still act on.
    assert rows[0].calls == 2
    assert rows[0].total_tokens == 4000


def test_an_unpriced_provider_does_not_hide_a_priced_one() -> None:
    """Poisoning is per provider, so one unpriceable model does not blank the rest."""
    rows = {
        row.provider: row
        for row in _aggregate_usage(
            [
                _record(Decimal("1.50"), provider=LLMProvider.ANTHROPIC),
                _record(None, provider=LLMProvider.ANTHROPIC),
                _record(Decimal("4.00"), provider=LLMProvider.OPENAI),
            ],
        )
    }

    assert rows[LLMProvider.ANTHROPIC.value].cost_estimate_usd is None
    assert rows[LLMProvider.OPENAI.value].cost_estimate_usd == Decimal("4.00")
    assert rows[LLMProvider.OPENAI.value].unpriced_calls == 0
