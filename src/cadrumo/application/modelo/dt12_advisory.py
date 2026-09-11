"""Generic verification mechanics for registry-selected DT12 declarations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.modelos.verification_report import ModeloVerificationFinding


# fact-relocation: selected DT12 declarations are consumed through RegistryQueryService and the dated mapping fact
def _registry_dt12_declaration(revision: object) -> ResolvedMappingFact:
    """Resolve selected Modelo 100 context and the dated DT12 mapping fact."""
    authority = bundled_authority()
    model_report = RegistryQueryService(authority).describe_modelo("100")
    effective_date = getattr(revision, "valid_to", None) or date.today()
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="lirpf-dt12-reduction-verification-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("selected DT12 declaration must resolve as a mapping fact")
    del model_report
    return resolved


def dt12_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
) -> ModeloVerificationFinding | None:
    """Delegate DT12 verification declarations to the selected registry."""
    del casilla_values
    _registry_dt12_declaration(revision)
    return None


__all__ = ["dt12_reduccion_advisory_finding"]
