"""Typed governed-fact resolution context for modelo reduction calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..calculations.registry.authority import ValidatedRegistryAuthority
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
from ..calculations.registry.schema_base import DateAxis

_MODELO_FACT_DATE_AXES: dict[str, DateAxis] = {
    "lirpf-art-20-trabajo-reduccion-rnt-ceiling": DateAxis.FILING_PERIOD,
    "lirpf-art-52-individual-contribution-sublimit": DateAxis.FILING_PERIOD,
    "lirpf-dt12-rescate-reduction-rate": DateAxis.FILING_PERIOD,
    "lirpf-dt12-general-window-following-years": DateAxis.FILING_PERIOD,
    "lirpf-dt12-transitional-contingency-first-year": DateAxis.FILING_PERIOD,
    "lirpf-dt12-transitional-contingency-last-year": DateAxis.FILING_PERIOD,
    "lirpf-dt12-transitional-window-following-years": DateAxis.FILING_PERIOD,
    "lirpf-dt12-cliff-last-year": DateAxis.FILING_PERIOD,
    "sal-special-reserve-allocation-rate": DateAxis.FILING_PERIOD,
    "sal-special-reserve-capital-multiple": DateAxis.FILING_PERIOD,
}


@dataclass(frozen=True, slots=True)
class ModeloFactResolutionContext:
    """Authority and explicit filing/devengo coordinates for modelo facts."""

    authority: ValidatedRegistryAuthority
    filing_period: date
    devengo_date: date

    def integer(self, fact_id: str) -> int:
        """Resolve an integer-valued modelo governed fact."""
        value = self._scalar(fact_id)
        if type(value) is not int:
            raise RegistryValidationError(f"modelo fact {fact_id!r} must resolve to an integer")
        return value

    def decimal(self, fact_id: str) -> Decimal:
        """Resolve a Decimal-valued modelo governed fact."""
        value = self._scalar(fact_id)
        if not isinstance(value, Decimal):
            raise RegistryValidationError(f"modelo fact {fact_id!r} must resolve to a Decimal")
        return value

    def resolved_scalar(self, fact_id: str) -> ResolvedScalarFact:
        """Resolve a modelo fact on its declared temporal coordinate."""
        try:
            date_axis = _MODELO_FACT_DATE_AXES[fact_id]
        except KeyError as exc:
            raise RegistryValidationError(f"unregistered modelo governed fact {fact_id!r}") from exc
        effective_date = self.filing_period if date_axis is DateAxis.FILING_PERIOD else self.devengo_date
        resolved = self.authority.resolve_governed_fact(
            ScalarFactQuery(fact_id=fact_id, date_axis=date_axis, effective_date=effective_date)
        )
        if not isinstance(resolved, ResolvedScalarFact):
            raise RegistryValidationError(f"modelo fact {fact_id!r} must resolve to a scalar")
        return resolved

    def _scalar(self, fact_id: str) -> int | Decimal:
        resolved = self.resolved_scalar(fact_id)
        value = resolved.payload.value
        if type(value) is not int and not isinstance(value, Decimal):
            raise RegistryValidationError(f"modelo fact {fact_id!r} must resolve to an integer or Decimal")
        return value
