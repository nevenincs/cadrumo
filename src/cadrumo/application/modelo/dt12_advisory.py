"""Generic verification mechanics for registry-selected DT12 declarations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.modelos.verification_report import ModeloVerificationFinding

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


# fact-relocation: selected DT12 declarations are consumed through the pinned operation and dated mapping fact
def _registry_dt12_declaration(
    revision: object,
    *,
    operation: PinnedAuthorityOperation,
) -> ResolvedMappingFact:
    """Resolve selected Modelo 100 context and the dated DT12 mapping fact."""
    effective_date = getattr(revision, "valid_to", None) or date.today()
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="lirpf-dt12-reduction-verification-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("selected DT12 declaration must resolve as a mapping fact")
    return resolved


def dt12_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    operation: PinnedAuthorityOperation,
) -> ModeloVerificationFinding | None:
    """Delegate DT12 verification declarations to the selected registry."""
    del casilla_values
    _registry_dt12_declaration(revision, operation=operation)
    return None


__all__ = ["dt12_reduccion_advisory_finding"]
