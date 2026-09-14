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
from typing import TYPE_CHECKING

from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_base import DateAxis
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from ..calculations.observations_repository import CalculationObservationRepositoryProtocol

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = [
    "collect_prior_payment_minoracion_not_captured_diagnostics",
    "collect_prior_payment_not_deducted_diagnostics",
]


def _selected_registry_declaration(
    revision: ModeloRevision,
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    operation: PinnedAuthorityOperation | None = None,
) -> ResolvedMappingFact | None:
    """Resolve the dated declaration when it applies to the selected work scope."""
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return _selected_registry_declaration(
                revision,
                modelo=modelo,
                period_token=period_token,
                filing_year=filing_year,
                operation=indexed_operation,
            )
    effective_date = date(filing_year, 12, 31)
    resolved = operation.resolve_governed_fact(
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
    if selected_modelo != modelo:
        return None
    selected_revision = declarations.get("revision")
    if not selected_revision:
        raise ValueError("selected prior-payment declaration lacks a revision coordinate")
    if selected_revision != str(revision.id):
        return None
    operation.revision_for_context(
        selected_modelo,
        filing_year=filing_year,
        period=period_token,
        on=effective_date,
    )
    return resolved


def collect_prior_payment_not_deducted_diagnostics(
    revision: ModeloRevision,
    casilla_values: Mapping[str, Decimal],
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    observation_repository: CalculationObservationRepositoryProtocol,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Resolve the selected declaration before the generic diagnostic seam."""
    del casilla_values, observation_repository
    _selected_registry_declaration(
        revision,
        modelo=modelo,
        period_token=period_token,
        filing_year=filing_year,
    )
    return ()


def collect_prior_payment_minoracion_not_captured_diagnostics(
    revision: ModeloRevision,
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    observation_repository: CalculationObservationRepositoryProtocol,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Resolve the selected declaration before the generic diagnostic seam."""
    del observation_repository
    _selected_registry_declaration(
        revision,
        modelo=modelo,
        period_token=period_token,
        filing_year=filing_year,
    )
    return ()
