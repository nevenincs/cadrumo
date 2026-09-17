"""Generic verification mechanics for registry-selected DT12 declarations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...core.time.clock import today_madrid
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .semantic_role_resolution import AmbiguousSemanticRoleCasillaError, casilla_id_for_unique_revision_semantic_role

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = ["dt12_antiquity_advisory_finding"]


_DT12_TRABAJO_REDUCCION_ROLE = "irpf_rendimiento_trabajo_reduccion"


# Registry authority: selected DT12 antiquity declarations are consumed through
# the pinned operation and dated mapping fact.
def _registry_dt12_antiquity_declaration(
    revision: object,
    *,
    operation: PinnedAuthorityOperation,
    modelo: str,
    effective_date: date,
) -> ResolvedMappingFact:
    """Resolve the selected model declaration and the dated DT12 mapping fact."""
    del modelo
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="lirpf-dt12-antiquity-verification-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("selected DT12 declaration must resolve as a mapping fact")
    del revision
    return resolved


def dt12_antiquity_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    operation: PinnedAuthorityOperation,
    modelo: str,
) -> ModeloVerificationFinding | None:
    """Warn to confirm the DT 12ª antiquity condition when reduction applies."""
    try:
        reduccion_id = casilla_id_for_unique_revision_semantic_role(
            revision,
            _DT12_TRABAJO_REDUCCION_ROLE,
            modelo_id=modelo,
        )
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc

    if reduccion_id is None:
        return None

    reduccion_value = casilla_values.get(reduccion_id, Decimal(0))
    if reduccion_value <= Decimal(0):
        return None

    effective_date = getattr(revision, "valid_to", None) or today_madrid()
    declaration = _registry_dt12_antiquity_declaration(
        revision,
        operation=operation,
        modelo=modelo,
        effective_date=effective_date,
    )
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        casilla_id=reduccion_id,
        message_locale_key="application.modelo.findings.dt12a_reduccion_antiquity_possible",
        message_facts={
            "reduccion_id": reduccion_id,
            "reduccion_value": reduccion_value,
        },
        legal_refs=declaration.legal_refs,
        source_refs=declaration.source_refs,
    )
