"""Generic verification mechanics for registry-selected Art.20 declarations."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.modelos.modelo_fact_context import ModeloFactResolutionContext
from ...domain.modelos.verification_report import ModeloVerificationFinding

__all__ = ["art20_reduccion_advisory_finding"]


# fact-relocation: selected Art.20 verification declarations are consumed through RegistryQueryService and the dated mapping fact
def _registry_art20_declaration(
    revision: object,
    *,
    context: ModeloFactResolutionContext,
) -> ResolvedMappingFact:
    """Resolve the selected M100 surface and dated Art.20 mapping fact."""
    authority = context.authority
    model_report = RegistryQueryService(authority).describe_modelo("100")
    effective_date = context.filing_period
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="lirpf-art-20-reduction-verification-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("selected Art.20 declaration must resolve as a mapping fact")
    del revision, model_report
    return resolved


def art20_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    context: ModeloFactResolutionContext,
) -> ModeloVerificationFinding | None:
    """Delegate Art.20 reduction verification declarations to the registry."""
    del casilla_values
    _registry_art20_declaration(revision, context=context)
    return None
