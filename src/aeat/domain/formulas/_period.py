"""Fiscal-period primitives for the :mod:`aeat.domain.formulas` engine.

A :class:`FiscalPeriod` is a closed, strict pydantic v2 model identifying
either a calendar year or a specific quarter within a year. The
engine uses the period's ``start``/``end`` date span to resolve the
active ruleset in :class:`aeat.domain.formulas.RulesetRegistry`.
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field

from ._codes import Quarter

_MIN_YEAR = 1990
_MAX_YEAR = 2100

_QUARTER_MONTH_RANGE: dict[Quarter, tuple[int, int]] = {
    Quarter.Q1: (1, 3),
    Quarter.Q2: (4, 6),
    Quarter.Q3: (7, 9),
    Quarter.Q4: (10, 12),
}


class FiscalPeriod(BaseModel):
    """A fiscal period keyed by year and optional quarter."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    year: Annotated[int, Field(ge=_MIN_YEAR, le=_MAX_YEAR)]
    quarter: Quarter | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def start(self) -> date:
        """Return the first day of the period."""
        if self.quarter is None:
            return date(self.year, 1, 1)
        month, _ = _QUARTER_MONTH_RANGE[self.quarter]
        return date(self.year, month, 1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def end(self) -> date:
        """Return the last day of the period."""
        if self.quarter is None:
            return date(self.year, 12, 31)
        _, month = _QUARTER_MONTH_RANGE[self.quarter]
        last_day = calendar.monthrange(self.year, month)[1]
        return date(self.year, month, last_day)

    def contains(self, other: date) -> bool:
        """Return ``True`` when ``other`` falls within this period."""
        return self.start <= other <= self.end
