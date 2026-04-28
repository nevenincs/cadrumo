"""Cumulation helpers for Modelo 180 annual summary fixtures."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class Modelo180QuarterlyRetention(BaseModel):
    """One quarterly Modelo 115-style rental withholding source."""

    model_config = _STRICT_FROZEN

    recipients: Decimal = Field(ge=Decimal("0"))
    recipient_ids: tuple[str, ...]
    base_retencion: Decimal = Field(ge=Decimal("0"))
    retenciones: Decimal = Field(ge=Decimal("0"))
    ingresos_especie: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def _recipient_count_matches_ids(self) -> Modelo180QuarterlyRetention:
        if len(set(self.recipient_ids)) != len(self.recipient_ids):
            raise ValueError("quarterly Modelo 180 source recipient ids must be unique")
        if self.recipients != Decimal(len(self.recipient_ids)):
            raise ValueError("quarterly Modelo 180 source recipient count must match recipient ids")
        return self

    @classmethod
    def from_m115_casillas(
        cls,
        casillas: Mapping[str, Decimal],
        *,
        recipient_ids: tuple[str, ...],
    ) -> Modelo180QuarterlyRetention:
        """Build a quarterly source from the Modelo 115 casilla subset feeding M180."""
        return cls(
            recipients=casillas["01"],
            recipient_ids=recipient_ids,
            base_retencion=casillas["02"],
            retenciones=casillas["03"],
            ingresos_especie=casillas["04"],
        )


class Modelo180AnnualSummary(BaseModel):
    """Modelo 180 four-casilla annual summary derived from quarterlies."""

    model_config = _STRICT_FROZEN

    recipients: Decimal = Field(ge=Decimal("0"))
    recipient_ids: tuple[str, ...]
    base_retencion: Decimal = Field(ge=Decimal("0"))
    retenciones: Decimal = Field(ge=Decimal("0"))
    ingresos_especie: Decimal = Field(ge=Decimal("0"))

    def as_casillas(self) -> dict[str, Decimal]:
        """Return the annual summary in Modelo 180 casilla-id form."""
        return {
            "01": self.recipients,
            "02": self.base_retencion,
            "03": self.retenciones,
            "04": self.ingresos_especie,
        }


def aggregate_modelo_180_from_quarters(quarters: Iterable[Modelo180QuarterlyRetention]) -> Modelo180AnnualSummary:
    """Aggregate exactly four Modelo 115 quarter summaries into Modelo 180.

    Modelo 180 verifies casilla 03 from the annual base rather than by
    summing rounded quarterly retenciones. That keeps cumulation aligned
    with the annual ruleset's terminal two-decimal calculation.
    """
    quarter_list = tuple(quarters)
    if len(quarter_list) != 4:
        raise ValueError(f"Modelo 180 annual cumulation requires exactly 4 quarters; got {len(quarter_list)}")

    annual_base = sum((q.base_retencion for q in quarter_list), start=Decimal("0"))
    annual_recipient_ids = tuple(sorted({recipient_id for q in quarter_list for recipient_id in q.recipient_ids}))
    return Modelo180AnnualSummary(
        recipients=Decimal(len(annual_recipient_ids)),
        recipient_ids=annual_recipient_ids,
        base_retencion=annual_base,
        retenciones=(annual_base * Decimal("0.19")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        ingresos_especie=sum((q.ingresos_especie for q in quarter_list), start=Decimal("0")),
    )
