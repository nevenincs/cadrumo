"""Cost estimation for LLM responses.

:class:`llm.LLMClient` stamps every :class:`llm.LLMResponse` with the result
of :func:`estimate_cost_usd`. On-host inference costs nothing. A run on the
agent service is billed by whichever lane the person selected, at rates
Cadrumo does not see, so it is unpriced rather than free.
"""

from __future__ import annotations

from decimal import Decimal

from ....core.config_support import LLMProvider
from ....core.decimal.constants import ZERO


def estimate_cost_usd(provider: LLMProvider, model: str, input_tokens: int, output_tokens: int) -> Decimal | None:
    """Return the call's cost in USD, or ``None`` when it cannot be priced.

    **Unpriced is ``None``, never zero.** A caller budgeting from ``$0.0000``
    would conclude the call was free rather than unpriced. The local provider
    genuinely costs nothing and returns ``Decimal('0')``.

    Args:
        provider: The :class:`llm.LLMProvider` that produced the response.
        model: The model that served it.
        input_tokens: Prompt-side token count.
        output_tokens: Completion-side token count.

    Returns:
        ``Decimal('0')`` for on-host inference, ``None`` otherwise.
    """
    del model, input_tokens, output_tokens
    if provider is LLMProvider.LOCAL:
        return ZERO
    return None
