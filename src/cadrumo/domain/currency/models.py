"""Currency normalization value models.

Defines :class:`MonetaryAmount`, :class:`NormalizedAmount`,
:class:`CurrencyNormalizationStatus` and the typed :class:`EurRateLookup` a rate
provider answers with, for the EUR conversion results produced by
:class:`CurrencyNormalizationService`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.errors.hierarchy import CoreValidationError, pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.parsing.codes import IsoCurrencyCode, normalise_iso_4217_currency


class CurrencyNormalizationStatus(StrEnum):
    """Status of currency normalization."""

    NATIVE_EUR = "native_eur"
    NORMALIZED = "normalized"
    MISSING_RATE = "missing_rate"
    UNSUPPORTED_CURRENCY = "unsupported_currency"


class EurRateLookupStatus(StrEnum):
    """What a rate provider found for one currency and date."""

    FOUND = "found"
    MISSING_RATE = "missing_rate"
    """The series exists but has no usable observation in the look-back window."""
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    """The rate authority publishes no series for the currency at all."""


class EurRateLookup(BaseModel):
    """A rate provider's answer for one currency on one requested date.

    A found rate carries the date of the observation actually used, which is the
    requested date or the most recent publication before it when that date is
    not a publication day. The two dates differ on every weekend and holiday, so
    a stored conversion that kept only the requested date could not be re-derived
    from the published series.
    """

    model_config = STRICT_FROZEN_CONFIG

    status: EurRateLookupStatus
    rate_date: date
    source: str = Field(min_length=1)
    rate: Decimal | None = None
    observation_date: date | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _found_carries_its_observation(self) -> EurRateLookup:
        if self.status is EurRateLookupStatus.FOUND:
            if self.rate is None or self.observation_date is None:
                raise CoreValidationError("a found rate carries its rate and observation date")
            if not self.rate.is_finite() or self.rate <= 0:
                raise CoreValidationError("a found rate is finite and strictly positive")
            if self.observation_date > self.rate_date:
                raise CoreValidationError("a rate observation cannot postdate the requested date")
        elif self.rate is not None or self.observation_date is not None:
            raise CoreValidationError("only a found rate carries a rate or observation date")
        return self


class MonetaryAmount(BaseModel):
    """A monetary amount with its currency."""

    model_config = STRICT_FROZEN_CONFIG

    amount: Decimal
    currency: IsoCurrencyCode

    @field_validator("currency", mode="before")
    @classmethod
    @pydantic_validation_boundary
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
    eur_amount: Decimal | None
    """``None`` when no rate converted the amount: a missing rate is never a zero."""
    status: CurrencyNormalizationStatus
    rate: Decimal | None = None
    rate_source: str | None = None
    rate_date: date | None = None
    rate_observation_date: date | None = None


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
    observation_date: date | None = None
    """The publication the rate came from; ``None`` only on stamps recorded before it was kept."""
