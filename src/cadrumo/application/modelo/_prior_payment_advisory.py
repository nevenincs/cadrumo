"""Generic mechanics for registry-selected prior-payment diagnostics.

The declaration identities, relation predicates, applicability, and evidence
provenance live in the selected registry mapping.  This module keeps only the
diagnostic boundary and resolves that mapping before handing control back to
the calculation path.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.queries import RegistryQueryService
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_base import DateAxis
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..calculations.observations_repository import CalculationObservationRepository

__all__ = [
    "collect_prior_payment_minoracion_not_captured_diagnostics",
    "collect_prior_payment_not_deducted_diagnostics",
]


def _selected_registry_declaration(revision: ModeloRevision) -> ResolvedMappingFact:
    """Resolve the dated declaration used by both diagnostic entry points."""
    authority = bundled_authority()
    effective_date = getattr(revision, "valid_from", None) or date.today()
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="m130-prior-payment-verification-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("selected prior-payment declaration must resolve as a mapping fact")
    declarations = {str(entry.key): str(entry.value) for entry in resolved.payload.entries}
    selected_modelo = declarations.get("modelo")
    if not selected_modelo:
        raise ValueError("selected prior-payment declaration lacks a model coordinate")
    RegistryQueryService(authority).describe_modelo(selected_modelo, as_of=effective_date)
    return resolved


def collect_prior_payment_not_deducted_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[str, Decimal],
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    observation_repository: CalculationObservationRepository,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Resolve the selected declaration before the generic diagnostic seam."""
    del casilla_values, modelo, period_token, filing_year, observation_repository
    _selected_registry_declaration(revision)
    return ()


def collect_prior_payment_minoracion_not_captured_diagnostics(
    revision: ModeloRevision,
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    observation_repository: CalculationObservationRepository,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Resolve the selected declaration before the generic diagnostic seam."""
    del modelo, period_token, filing_year, observation_repository
    _selected_registry_declaration(revision)
    return ()
