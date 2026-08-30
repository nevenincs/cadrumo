"""Currency normalization value models.

Defines :class:`MonetaryAmount`, :class:`NormalizedAmount`, and
:class:`CurrencyNormalizationStatus` for the EUR conversion results produced by
:class:`CurrencyNormalizationService`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.parsing import IsoCurrencyCode, normalise_iso_4217_currency


class CurrencyNormalizationStatus(StrEnum):
    """Status of currency normalization."""

    NATIVE_EUR = "native_eur"
    NORMALIZED = "normalized"
    MISSING_RATE = "missing_rate"
    UNSUPPORTED_CURRENCY = "unsupported_currency"


class MonetaryAmount(BaseModel):
    """A monetary amount with its currency."""

    model_config = STRICT_FROZEN_CONFIG

    amount: Decimal
    currency: IsoCurrencyCode

    @field_validator("currency", mode="before")
    @classmethod
    def _normalise_currency(cls, v: object) -> object:
        """Normalise through the canonical ISO-4217 owner.

        Runs ``mode="before"`` because the field's own length constraint
        would otherwise fire on a padded token (``" eur "``) before the
        normaliser ever runs, and because
        :meth:`CurrencyNormalizationService.normalize` compares
        ``currency`` against :data:`~core.external_constants.DEFAULT_CURRENCY`
        by raw equality: a lowercase or padded native-EUR amount must
        already be canonical ``"EUR"`` by the time that comparison runs,
        or it silently misclassifies as a foreign currency with a missing
        rate instead of the native-EUR identity conversion.
        """
        return normalise_iso_4217_currency(v)


class NormalizedAmount(BaseModel):
    """A EUR-normalized monetary amount with provenance."""

    model_config = STRICT_FROZEN_CONFIG

    original: MonetaryAmount
    eur_amount: Decimal
    status: CurrencyNormalizationStatus
    rate: Decimal | None = None
    rate_source: str | None = None
    rate_date: date | None = None


class FxConversionStamp(BaseModel):
    """The euro-conversion stamp a foreign-currency record carries.

    Three fields rather than the ``(rate, date)`` pair this replaced, because a
    stored euro figure that cannot say WHO quoted the rate is a number with no
    authority behind it. The rate and the date say what was applied; *source*
    says which rate authority stated it, which is what makes the conversion
    auditable years later against the same published series.
    """

    model_config = STRICT_FROZEN_CONFIG

    rate: Decimal = Field(gt=Decimal("0"))
    rate_date: date
    source: str = Field(min_length=1)
