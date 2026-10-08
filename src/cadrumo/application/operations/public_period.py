"""Strict operation projection of the canonical filing-period value."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period, PeriodError


class PublicPeriod(BaseModel):
    """Year and code without domain coercion hooks in a public operation schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    filing_year: int
    code: str

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        """Refuse malformed coordinates while parsing the public request."""
        try:
            self.to_period()
        except PeriodError:
            raise ValueError("invalid filing period") from None
        return self

    @classmethod
    def from_period(cls, period: Period) -> Self:
        """Copy a canonical domain period without changing its spelling."""
        return cls(filing_year=period.filing_year, code=period.registry_token)

    def to_period(self) -> Period:
        """Resolve the canonical domain value, refusing a noncanonical spelling."""
        period = Period.from_year_and_code(self.filing_year, self.code)
        if period.registry_token != self.code:
            raise ValueError("period code must use its canonical spelling")
        return period
