"""Generic verification mechanics for registry-selected DT12 declarations."""

from __future__ import annotations

from collections.abc import Mapping
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


_DT12_TRABAJO_INGRESO_ROLE = "irpf_rendimiento_trabajo_importe_integro_dinerario"
_DT12_TRABAJO_REDUCCION_ROLE = "irpf_rendimiento_trabajo_reduccion"
_DT12_LARGE_TRABAJO_THRESHOLD = Decimal("20000")


# Registry authority: selected DT12 declarations are consumed through the pinned operation and dated mapping fact
def _registry_dt12_declaration(
    revision: object,
    *,
    operation: PinnedAuthorityOperation,
) -> ResolvedMappingFact:
    """Resolve selected Modelo 100 context and the dated DT12 mapping fact."""
    effective_date = getattr(revision, "valid_to", None) or today_madrid()
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
    """Warn when large trabajo income has no DT 12ª reduction declaration.

    The threshold and semantic roles are the established DT 12ª verification
    predicate.  The mapping is still resolved through the caller-owned
    operation so the advisory is grounded in the same authority generation as
    the selected workflow.
    """
    try:
        ingreso_id = casilla_id_for_unique_revision_semantic_role(
            revision,
            _DT12_TRABAJO_INGRESO_ROLE,
        )
        reduccion_id = casilla_id_for_unique_revision_semantic_role(
            revision,
            _DT12_TRABAJO_REDUCCION_ROLE,
        )
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc

    if ingreso_id is None or reduccion_id is None:
        return None

    ingreso_value = casilla_values.get(ingreso_id, Decimal(0))
    reduccion_value = casilla_values.get(reduccion_id, Decimal(0))
    if ingreso_value <= _DT12_LARGE_TRABAJO_THRESHOLD or reduccion_value != Decimal(0):
        return None

    declaration = _registry_dt12_declaration(revision, operation=operation)
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.WARNING,
        casilla_id=reduccion_id,
        message_locale_key="application.modelo.findings.dt12a_reduccion_possible",
        message_facts={
            "ingreso_id": ingreso_id,
            "ingreso_value": ingreso_value,
            "reduccion_id": reduccion_id,
        },
        legal_refs=declaration.legal_refs,
        source_refs=declaration.source_refs,
    )


__all__ = ["dt12_reduccion_advisory_finding"]
