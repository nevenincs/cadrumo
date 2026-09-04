"""Provider pricing helpers for cost estimation.

Holds the public per-million-token pricing table for each supported
:class:`llm.LLMProvider` and exposes
:func:`estimate_cost_usd` so :class:`llm.LLMClient`
can stamp every :class:`llm.LLMResponse` with a
deterministic USD cost estimate. The local provider always reports zero.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from ..core.decimal.constants import ZERO
from .models import LLMProvider

_PRICING_PER_MILLION: tuple[tuple[LLMProvider, str, Decimal, Decimal], ...] = (
    (LLMProvider.ANTHROPIC, "claude-opus-4-6", Decimal("5.00"), Decimal("25.00")),
    (LLMProvider.ANTHROPIC, "claude-sonnet-4-6", Decimal("3.00"), Decimal("15.00")),
    (LLMProvider.ANTHROPIC, "claude-opus-4-5", Decimal("5.00"), Decimal("25.00")),
    (LLMProvider.ANTHROPIC, "claude-sonnet-4-5", Decimal("3.00"), Decimal("15.00")),
    (LLMProvider.OPENAI, "gpt-4.1", Decimal("2.00"), Decimal("8.00")),
    (LLMProvider.OPENAI, "gpt-4o", Decimal("2.50"), Decimal("10.00")),
    (LLMProvider.GEMINI, "gemini-2.5-pro", Decimal("1.25"), Decimal("10.00")),
    (LLMProvider.GEMINI, "gemini-2.5-flash", Decimal("0.30"), Decimal("2.50")),
)
_TOKEN_SCALE = Decimal("1000000")
_QUANTIZE = Decimal("0.000001")


def estimate_cost_usd(provider: LLMProvider, model: str, input_tokens: int, output_tokens: int) -> Decimal | None:
    """Estimate request cost in USD from known public pricing, or refuse.

    Looks up the first pricing entry whose ``model`` field is a prefix of
    the lowercased ``model`` argument so model variants (versioned
    suffixes, dated minor releases) inherit their family's rates.

    **A model this table does not price returns ``None``, never zero.**
    It used to return zero so every usage record carried a well-typed
    ``Decimal``, and that is exactly how a cost surface reports an absence
    as a positive answer: a caller budgeting from ``$0.0000`` concludes the
    call was free rather than unpriced. The table is a snapshot of public
    rates and goes stale by construction, so the models it does not carry
    are a permanent, moving population -- widening it cannot fix this and
    re-introduces the silent zero for whatever is added next.

    **Free and unpriceable stay distinct.** The local provider genuinely
    costs nothing and keeps returning ``Decimal('0')``. Collapsing the two
    would put the defect back under a different name.

    Args:
        provider: The :class:`llm.LLMProvider`
            that produced the response.
        model: Provider-resolved model identifier (e.g.
            ``"claude-sonnet-4-6-20260101"``).
        input_tokens: Prompt-side token count.
        output_tokens: Completion-side token count.

    Returns:
        Estimated cost in USD, quantised to 6 decimal places with
        :data:`decimal.ROUND_HALF_UP` -- half away from zero, matching how
        this tree rounds money everywhere else, and distinct from banker's
        rounding (:data:`decimal.ROUND_HALF_EVEN`), which resolves a tie to
        the even digit instead;
        :data:`decimal.Decimal('0')` for the local provider, which is free
        rather than unpriced; and ``None`` when no table entry prices this
        provider and model.
    """
    if provider is LLMProvider.LOCAL:
        return ZERO
    normalized_model = model.lower()
    for known_provider, prefix, input_rate, output_rate in _PRICING_PER_MILLION:
        if provider is known_provider and normalized_model.startswith(prefix):
            input_cost = (Decimal(input_tokens) / _TOKEN_SCALE) * input_rate
            output_cost = (Decimal(output_tokens) / _TOKEN_SCALE) * output_rate
            return (input_cost + output_cost).quantize(_QUANTIZE, rounding=ROUND_HALF_UP)
    return None
