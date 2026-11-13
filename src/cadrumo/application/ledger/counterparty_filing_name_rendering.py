"""The width-scoped rendering a person states for a counterparty's filing name.

Kept apart from the counterparty operation because the CLI option contract
resolves this type at command resolution, and the operation module reaches the
pinned registry catalogues that resolving a command must not load.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

LEDGER_COUNTERPARTY_FILING_NAME_PART_MAX = 256
"""The longest stated name part a filing-name statement takes; the field width is the layout's."""


class CounterpartyFilingNameRendering(BaseModel):
    """A shorter rendering the person states for a field of one width."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    width: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=LEDGER_COUNTERPARTY_FILING_NAME_PART_MAX)


__all__ = ["LEDGER_COUNTERPARTY_FILING_NAME_PART_MAX", "CounterpartyFilingNameRendering"]
