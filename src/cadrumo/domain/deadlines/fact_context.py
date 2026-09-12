"""Typed governed-fact resolution context for deadline consequences.

The deadline domain receives authority and both temporal coordinates from its
application composition boundary.  It does not open the bundled registry on a
domain-method call: the caller must state the filing and submission dates that
select each fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import (
    MappingFactQuery,
    ResolvedMappingFact,
    ResolvedScalarFact,
    ScalarFactQuery,
)
from ..calculations.registry.schema_base import DateAxis

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority

_DEADLINE_FACT_DATE_AXIS_MAPPING_FACT_ID = "deadline-fact-date-axis-mapping"


@dataclass(frozen=True, slots=True)
class DeadlineFactResolutionContext:
    """Authority and explicit filing/submission coordinates for deadline facts."""

    authority: ValidatedRegistryAuthority
    filing_period: date
    submission_date: date

    def decimal(self, fact_id: str) -> Decimal:
        """Resolve a Decimal-valued deadline scalar while retaining provenance."""
        resolved = self.resolved_scalar(fact_id)
        if not isinstance(resolved.payload.value, Decimal):
            raise RegistryValidationError(f"deadline fact {fact_id!r} must resolve to a Decimal")
        return resolved.payload.value

    def integer(self, fact_id: str) -> int:
        """Resolve an integer-valued deadline scalar while retaining provenance."""
        resolved = self.resolved_scalar(fact_id)
        if type(resolved.payload.value) is not int:
            raise RegistryValidationError(f"deadline fact {fact_id!r} must resolve to an integer")
        return resolved.payload.value

    def mapping_decimal(self, fact_id: str, key: int) -> Decimal:
        """Resolve one exact Decimal entry from a governed mapping fact.

        A missing key is an unpublished legal coordinate, not permission to
        substitute the most recent value.
        """
        resolved = self.resolved_mapping(fact_id)
        for entry in resolved.payload.entries:
            if entry.key == key:
                if not isinstance(entry.value, Decimal):
                    raise RegistryValidationError(f"deadline mapping {fact_id!r} entry {key!r} must be Decimal")
                return entry.value
        raise RegistryValidationError(f"deadline mapping {fact_id!r} has no entry for {key!r}")

    def resolved_scalar(self, fact_id: str) -> ResolvedScalarFact:
        """Resolve a scalar on the fact's declared temporal axis."""
        axis = self._date_axis(fact_id)
        resolved = self.authority.resolve_governed_fact(
            ScalarFactQuery(fact_id=fact_id, date_axis=axis, effective_date=self._coordinate(axis))
        )
        if not isinstance(resolved, ResolvedScalarFact):
            raise RegistryValidationError(f"deadline fact {fact_id!r} must resolve to a scalar")
        return resolved

    def resolved_mapping(self, fact_id: str) -> ResolvedMappingFact:
        """Resolve a mapping on the fact's declared temporal axis."""
        axis = self._date_axis(fact_id)
        resolved = self.authority.resolve_governed_fact(
            MappingFactQuery(fact_id=fact_id, date_axis=axis, effective_date=self._coordinate(axis))
        )
        if not isinstance(resolved, ResolvedMappingFact):
            raise RegistryValidationError(f"deadline fact {fact_id!r} must resolve to a mapping")
        return resolved

    def _date_axis(self, fact_id: str) -> DateAxis:
        resolved = self.authority.resolve_governed_fact(
            MappingFactQuery(
                fact_id=_DEADLINE_FACT_DATE_AXIS_MAPPING_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=self.filing_period,
            ),
        )
        if not isinstance(resolved, ResolvedMappingFact):
            raise RegistryValidationError(
                f"deadline fact {_DEADLINE_FACT_DATE_AXIS_MAPPING_FACT_ID!r} must resolve to a mapping",
            )
        for entry in resolved.payload.entries:
            if entry.key != fact_id:
                continue
            if not isinstance(entry.value, str):
                raise RegistryValidationError(
                    f"deadline fact {fact_id!r} date axis must be a string",
                )
            try:
                return DateAxis(entry.value)
            except ValueError as exc:
                raise RegistryValidationError(
                    f"deadline fact {fact_id!r} has unknown date axis {entry.value!r}",
                ) from exc
        raise RegistryValidationError(f"unregistered deadline governed fact {fact_id!r}")

    def _coordinate(self, axis: DateAxis) -> date:
        if axis is DateAxis.FILING_PERIOD:
            return self.filing_period
        if axis is DateAxis.SUBMISSION_DATE:
            return self.submission_date
        raise RegistryValidationError(f"deadline fact axis {axis.value!r} has no configured coordinate")
