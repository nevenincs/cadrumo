"""Generic verification mechanics for registry-selected Art.20 declarations."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.modelo_fact_context import ModeloFactResolutionContext
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .semantic_role_resolution import AmbiguousSemanticRoleCasillaError, casilla_id_for_unique_revision_semantic_role

__all__ = ["art20_reduccion_advisory_finding"]


_ART20_RNT_ROLE = "irpf_rendimiento_trabajo_rendimiento_neto"
_ART20_REDUCCION_ROLE = "irpf_rendimiento_trabajo_reduccion_gastos_generales"
_ART20_RNT_CEILING_FACT_ID = "lirpf-art-20-trabajo-reduccion-rnt-ceiling"


# fact-relocation: selected Art.20 verification declarations are consumed through the dated mapping fact
def _registry_art20_declaration(
    revision: object,
    *,
    context: ModeloFactResolutionContext,
) -> ResolvedMappingFact:
    """Resolve the selected M100 surface and dated Art.20 mapping fact."""
    authority = context.authority
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
    del revision
    return resolved


def art20_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    context: ModeloFactResolutionContext,
) -> ModeloVerificationFinding | None:
    """Warn when in-band trabajo income has no general reduction declaration."""
    try:
        rnt_id = casilla_id_for_unique_revision_semantic_role(revision, _ART20_RNT_ROLE)
        reduccion_id = casilla_id_for_unique_revision_semantic_role(revision, _ART20_REDUCCION_ROLE)
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc

    if rnt_id is None or reduccion_id is None:
        return None

    rnt_value = casilla_values.get(rnt_id, Decimal(0))
    reduccion_value = casilla_values.get(reduccion_id, Decimal(0))
    resolved_ceiling = context.resolved_decimal(_ART20_RNT_CEILING_FACT_ID)
    ceiling = resolved_ceiling.payload.value
    if not isinstance(ceiling, Decimal):
        raise ModeloError("Art. 20 RNT ceiling fact must resolve to a Decimal")
    if not (Decimal(0) < rnt_value < ceiling and reduccion_value == Decimal(0)):
        return None

    _registry_art20_declaration(revision, context=context)
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.ADVISORY,
        severity=ModeloVerificationFindingSeverity.WARNING,
        casilla_id=reduccion_id,
        message_locale_key="application.modelo.findings.art20_reduccion_possible",
        message_facts={
            "rnt_id": rnt_id,
            "rnt_value": rnt_value,
            "reduccion_id": reduccion_id,
        },
        legal_refs=resolved_ceiling.legal_refs,
        source_refs=resolved_ceiling.source_refs,
    )
