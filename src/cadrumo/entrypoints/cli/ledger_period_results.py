"""Typed ``--json`` payload of the filing periods ``aeat app ledger entry-options`` reports.

The application serves the periods; this module only gives them the strict
output shapes the CLI contract requires: sequences as lists and days as
``YYYY-MM-DD`` text.
"""

from __future__ import annotations

from typing import Literal

from ...application.ledger.models import IsoDateText
from ...core.json_contract import OutputSchema


class LedgerPeriodRefPayload(OutputSchema):
    """One period as a filing year and its code."""

    filing_year: int
    code: str


class LedgerPeriodPayload(OutputSchema):
    """One selectable period: its cadence, days, neighbours and words."""

    period: LedgerPeriodRefPayload
    kind: Literal["annual", "quarterly", "monthly"]
    first_day: IsoDateText
    last_day: IsoDateText
    previous: LedgerPeriodRefPayload | None
    next: LedgerPeriodRefPayload | None
    name_words: str
    name_words_language: str
    label_words: str
    label_words_language: str


class LedgerDayPeriodsPayload(OutputSchema):
    """The year, the quarter and the month that hold one day."""

    day: IsoDateText
    annual: LedgerPeriodRefPayload
    quarterly: LedgerPeriodRefPayload
    monthly: LedgerPeriodRefPayload


class LedgerPeriodCoveringPayload(OutputSchema):
    """The shortest period holding a span, or none where the span crosses a year end."""

    first_day: IsoDateText
    last_day: IsoDateText
    period: LedgerPeriodRefPayload | None


class LedgerPeriodsPayload(OutputSchema):
    """The periods of one year, the periods of the reference day, and what else was asked."""

    year: int
    annual_code: str
    periods: list[LedgerPeriodPayload]
    containing: LedgerDayPeriodsPayload
    covering: LedgerPeriodCoveringPayload | None = None
    days: list[LedgerDayPeriodsPayload] = []


__all__ = [
    "LedgerDayPeriodsPayload",
    "LedgerPeriodCoveringPayload",
    "LedgerPeriodPayload",
    "LedgerPeriodRefPayload",
    "LedgerPeriodsPayload",
]
