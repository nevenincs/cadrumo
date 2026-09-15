"""Generic verification mechanics for registry-selected Art.52 declarations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = ["art52_reduccion_advisory_finding"]


_ART52_REDUCCION_TOTAL_ROLE = "irpf_reduccion_prevision_social_total"
_ART52_APORTACIONES_TRABAJADOR_CON_CONTRIBUCION_EMPRESARIAL_ROLE = (
    "irpf_red_prevision_social_aportaciones_trabajador_con_contribucion_empresarial"
)
_ART52_CONTRIBUCIONES_EMPRESARIALES_ROLE = "irpf_red_prevision_social_contribuciones_empresariales_excepto_scd"
_ART52_APORTACIONES_AUTONOMOS_EMPRESARIOS_ROLE = "irpf_red_prevision_social_aportaciones_autonomos_empresarios"
_ART52_INDIVIDUAL_SUBLIMIT_FACT_ID = "lirpf-art-52-individual-contribution-sublimit"


# Registry authority: selected Art.52 declarations are consumed through the pinned operation and dated mapping fact
def _registry_art52_declaration(
    revision: object,
    *,
    operation: PinnedAuthorityOperation,
    modelo: str,
    effective_date: date,
) -> ResolvedMappingFact:
    """Resolve selected model context and the dated Art.52 mapping fact."""
    del modelo
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id="lirpf-art-52-reduction-verification-mapping",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("selected Art.52 declaration must resolve as a mapping fact")
    del revision
    return resolved


def art52_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    operation: PinnedAuthorityOperation,
    modelo: str,
) -> ModeloVerificationFinding | None:
    """Warn when individual previdencia-social reduction exceeds its sub-limit."""
    try:
        reduccion_id = casilla_id_for_unique_revision_semantic_role(
            revision,
            _ART52_REDUCCION_TOTAL_ROLE,
            modelo_id=modelo,
        )
        trabajador_con_contribucion_id = casilla_id_for_unique_revision_semantic_role(
            revision,
            _ART52_APORTACIONES_TRABAJADOR_CON_CONTRIBUCION_EMPRESARIAL_ROLE,
            modelo_id=modelo,
        )
        empresarial_id = casilla_id_for_unique_revision_semantic_role(
            revision,
            _ART52_CONTRIBUCIONES_EMPRESARIALES_ROLE,
            modelo_id=modelo,
        )
        autonomos_empresarios_id = casilla_id_for_unique_revision_semantic_role(
            revision,
            _ART52_APORTACIONES_AUTONOMOS_EMPRESARIOS_ROLE,
            modelo_id=modelo,
        )
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc

    if (
        reduccion_id is None
        or trabajador_con_contribucion_id is None
        or empresarial_id is None
        or autonomos_empresarios_id is None
    ):
        return None

    reduccion_value = casilla_values.get(reduccion_id, Decimal(0))
    trabajador_con_contribucion_value = casilla_values.get(trabajador_con_contribucion_id, Decimal(0))
    empresarial_value = casilla_values.get(empresarial_id, Decimal(0))
    autonomos_empresarios_value = casilla_values.get(autonomos_empresarios_id, Decimal(0))
    effective_date = getattr(revision, "valid_to", None) or date.today()
    _registry_art52_declaration(
        revision,
        operation=operation,
        modelo=modelo,
        effective_date=effective_date,
    )
    context = ModeloFactResolutionContext(
        authority=operation,
        filing_period=effective_date,
        devengo_date=effective_date,
    )
    resolved_sublimit = context.resolved_decimal(_ART52_INDIVIDUAL_SUBLIMIT_FACT_ID)
    sublimit = resolved_sublimit.payload.value
    if not isinstance(sublimit, Decimal):
        raise ModeloError("Art. 52 individual sublimit fact must resolve to a Decimal")
    if (
        reduccion_value > sublimit
        and trabajador_con_contribucion_value == Decimal(0)
        and empresarial_value == Decimal(0)
        and autonomos_empresarios_value == Decimal(0)
    ):
        return ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.ADVISORY,
            severity=ModeloVerificationFindingSeverity.WARNING,
            casilla_id=reduccion_id,
            message_locale_key="application.modelo.findings.art52_reduccion_individual_sublimit_possible",
            message_facts={
                "reduccion_id": reduccion_id,
                "reduccion_value": reduccion_value,
                "sublimit": sublimit,
            },
            legal_refs=resolved_sublimit.legal_refs,
            source_refs=resolved_sublimit.source_refs,
        )
    return None
