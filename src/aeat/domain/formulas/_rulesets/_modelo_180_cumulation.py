"""Cumulation helpers for Modelo 180 annual summary fixtures.

Aggregates four quarterly :class:`Modelo180QuarterlyRetention` records
(typically derived from Modelo 115 casillas) into the four-casilla annual
:class:`Modelo180AnnualSummary` that Modelo 180 expects, applying the 19 %
retención rate to the annual base rather than summing rounded quarterly
amounts.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class Modelo180QuarterlyRetention(BaseModel):
    """One quarterly Modelo 115-style rental-withholding source.

    Attributes:
        recipients: Number of distinct landlords; must equal
            ``len(recipient_ids)``.
        recipient_ids: Tuple of unique landlord NIFs / NIEs.
        base_retencion: Rental base subject to retención for the
            quarter.
        retenciones: Retenciones declared for the quarter.
        ingresos_especie: In-kind income reported for the quarter.
    """

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
        """Build a quarterly source from the Modelo 115 casilla subset feeding M180.

        Args:
            casillas: Modelo 115 casilla mapping; required keys are
                ``"01"`` (recipients), ``"02"`` (base), ``"03"``
                (retenciones), and ``"04"`` (ingresos en especie).
            recipient_ids: Unique landlord identifiers backing the
                recipient count.

        Returns:
            A populated :class:`Modelo180QuarterlyRetention`.
        """
        return cls(
            recipients=casillas["01"],
            recipient_ids=recipient_ids,
            base_retencion=casillas["02"],
            retenciones=casillas["03"],
            ingresos_especie=casillas["04"],
        )


class Modelo180AnnualSummary(BaseModel):
    """Modelo 180 four-casilla annual summary derived from quarterlies.

    Attributes:
        recipients: Distinct-landlord count across the year.
        recipient_ids: Sorted tuple of unique landlord NIFs / NIEs.
        base_retencion: Annual base subject to retención.
        retenciones: Annual retenciones (computed from the annual base
            at the 19 % rate, not by summing quarterly amounts).
        ingresos_especie: Annual in-kind income (sum of quarters).
    """

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

    Args:
        quarters: Four :class:`Modelo180QuarterlyRetention` records, one
            per fiscal quarter.

    Returns:
        A :class:`Modelo180AnnualSummary` ready for the Modelo 180
        casilla map.

    Raises:
        ValueError: When ``quarters`` does not contain exactly four
            entries.
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
