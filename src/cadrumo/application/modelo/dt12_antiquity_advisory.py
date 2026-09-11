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

__all__ = ["dt12_antiquity_advisory_finding"]


# fact-relocation: selected DT12 antiquity declarations are consumed through RegistryQueryService and the dated mapping fact
def _registry_dt12_antiquity_declaration(
    revision: object,
    *,
    modelo: str,
    effective_date: date,
) -> ResolvedMappingFact:
    """Resolve the selected model declaration and the dated DT12 mapping fact."""
    model_report = RegistryQueryService(bundled_authority()).describe_modelo(modelo)
    resolved = bundled_authority().resolve_governed_fact(
        MappingFactQuery(
            fact_id="lirpf-dt12-antiquity-verification-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("selected DT12 declaration must resolve as a mapping fact")
    del revision, model_report
    return resolved


def dt12_antiquity_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    modelo: str,
) -> ModeloVerificationFinding | None:
    """Delegate DT12 antiquity verification declarations to the registry."""
    del casilla_values
    effective_date = getattr(revision, "valid_to", None) or date.today()
    _registry_dt12_antiquity_declaration(revision, modelo=modelo, effective_date=effective_date)
    raise NotImplementedError("registry-selected DT12 verification consumer is not yet implemented")
