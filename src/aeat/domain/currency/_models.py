from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CurrencyNormalizationStatus(StrEnum):
    """Status of currency normalization."""

    NATIVE_EUR = "native_eur"
    NORMALIZED = "normalized"
    MISSING_RATE = "missing_rate"
    UNSUPPORTED_CURRENCY = "unsupported_currency"


class MonetaryAmount(BaseModel):
    """A monetary amount with its currency."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)


class NormalizedAmount(BaseModel):
    """A EUR-normalized monetary amount with provenance."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    original: MonetaryAmount
    eur_amount: Decimal
    status: CurrencyNormalizationStatus
    rate: Decimal | None = None
    rate_source: str | None = None
    rate_date: date | None = None
