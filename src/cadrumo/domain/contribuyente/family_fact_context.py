"""Typed governed-fact resolution context for family calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..calculations.registry.authority import ValidatedRegistryAuthority
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
from ..calculations.registry.schema_base import DateAxis

_FAMILY_FACT_DATE_AXES: dict[str, DateAxis] = {
    "lirpf-art-58-descendant-ordinary-maximum-age": DateAxis.FILING_PERIOD,
    "lirpf-art-58-under-three-maximum-age": DateAxis.FILING_PERIOD,
    "lirpf-art-61-shared-custody-proration-factor": DateAxis.FILING_PERIOD,
    "lirpf-art-81-adoption-entry-window-years": DateAxis.FILING_PERIOD,
    "lirpf-art-81-contribution-ceiling-retired-effective-year": DateAxis.FILING_PERIOD,
    "lirpf-art-81-maternity-post-birth-enrollment-effective-year": DateAxis.FILING_PERIOD,
    "madrid-birth-adoption-following-periods": DateAxis.FILING_PERIOD,
}


@dataclass(frozen=True, slots=True)
class FamilyFactResolutionContext:
    """Authority and explicit filing/devengo coordinates for family facts."""

    authority: ValidatedRegistryAuthority
    filing_period: date
    devengo_date: date

    def integer(self, fact_id: str) -> int:
        """Resolve an integer-valued family governed fact."""
        value = self._scalar(fact_id)
        if type(value) is not int:
            raise RegistryValidationError(f"family fact {fact_id!r} must resolve to an integer")
        return value

    def decimal(self, fact_id: str) -> Decimal:
        """Resolve a Decimal-valued family governed fact."""
        value = self._scalar(fact_id)
        if not isinstance(value, Decimal):
            raise RegistryValidationError(f"family fact {fact_id!r} must resolve to a Decimal")
        return value

    def resolved_scalar(self, fact_id: str) -> ResolvedScalarFact:
        """Resolve a family fact on its declared temporal coordinate.

        The mapping is deliberately closed: consumers cannot accidentally use
        the filing coordinate for a fact whose declaration moves to devengo.
        """
        try:
            date_axis = _FAMILY_FACT_DATE_AXES[fact_id]
        except KeyError as exc:
            raise RegistryValidationError(f"unregistered family governed fact {fact_id!r}") from exc
        effective_date = self.filing_period if date_axis is DateAxis.FILING_PERIOD else self.devengo_date
        resolved = self.authority.resolve_governed_fact(
            ScalarFactQuery(fact_id=fact_id, date_axis=date_axis, effective_date=effective_date)
        )
        if not isinstance(resolved, ResolvedScalarFact):
            raise RegistryValidationError(f"family fact {fact_id!r} must resolve to a scalar")
        return resolved

    def _scalar(self, fact_id: str) -> int | Decimal:
        resolved = self.resolved_scalar(fact_id)
        if type(resolved.payload.value) is not int and not isinstance(resolved.payload.value, Decimal):
            raise RegistryValidationError(f"family fact {fact_id!r} must resolve to an integer or Decimal")
        return resolved.payload.value
