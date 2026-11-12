"""Generic verification mechanics for registry-selected Art.52 declarations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...core.casilla_value_absence import AbsentCasillaReading
from ...domain.calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...domain.calculations.registry.schema_base import DateAxis
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.modelo_fact_context import ModeloFactResolutionContext
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .calculation_input_refusal_doors import semantic_role_ambiguous_verdict
from .refusal_door_verdicts import registry_defect_verdict
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
_ART52_EXCESO_EJERCICIOS_ANTERIORES_ROLE = "irpf_red_prevision_social_exceso_ejercicios_anteriores"
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


@dataclass(frozen=True, slots=True)
class _Art52Casillas:
    """The revision's casillas the advisory reads, each found by its semantic role."""

    reduccion: CasillaId
    trabajador_con_contribucion: CasillaId
    empresarial: CasillaId
    autonomos_empresarios: CasillaId
    exceso_ejercicios_anteriores: CasillaId | None


def _art52_casillas(revision: object, *, modelo: str) -> _Art52Casillas | None:
    """Resolve the roles the advisory reads, or ``None`` when the revision lacks a required one.

    A revision without an earlier-year excess box has no excess to set aside.
    """
    roles = (
        _ART52_REDUCCION_TOTAL_ROLE,
        _ART52_APORTACIONES_TRABAJADOR_CON_CONTRIBUCION_EMPRESARIAL_ROLE,
        _ART52_CONTRIBUCIONES_EMPRESARIALES_ROLE,
        _ART52_APORTACIONES_AUTONOMOS_EMPRESARIOS_ROLE,
        _ART52_EXCESO_EJERCICIOS_ANTERIORES_ROLE,
    )
    try:
        ids = tuple(casilla_id_for_unique_revision_semantic_role(revision, role, modelo_id=modelo) for role in roles)
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(
            str(exc),
            translated_message="application.modelo.errors.semantic_role_ambiguous",
            context=exc.ambiguity.context(),
            precondition_verdict=semantic_role_ambiguous_verdict(exc.ambiguity.semantic_role),
        ) from exc
    reduccion, trabajador, empresarial, autonomos, exceso = ids
    if reduccion is None or trabajador is None or empresarial is None or autonomos is None:
        return None
    return _Art52Casillas(reduccion, trabajador, empresarial, autonomos, exceso)


def _individual_art52_sublimit_exceeded(
    casillas: _Art52Casillas,
    casilla_values: Mapping[CasillaId, Decimal],
    sublimit: Decimal,
) -> bool:
    """Whether the year's own amounts exceed the individual sublimit with no other contribution channel.

    The excesses of earlier ejercicios reduce first against the whole art. 52.1.b limit whatever
    their origin (RIRPF art. 51), so the part of the reduction they explain is not measured against
    the individual sublimit.
    """
    reduccion_value = AbsentCasillaReading.ADVISORY_TRIGGER_OPERAND.read(casilla_values, casillas.reduccion)
    exceso_id = casillas.exceso_ejercicios_anteriores
    exceso_value = (
        Decimal(0) if exceso_id is None else AbsentCasillaReading.ADVISORY_GAP_OPERAND.read(casilla_values, exceso_id)
    )
    channels = (casillas.trabajador_con_contribucion, casillas.empresarial, casillas.autonomos_empresarios)
    return reduccion_value - min(exceso_value, reduccion_value) > sublimit and all(
        AbsentCasillaReading.ADVISORY_GAP_OPERAND.read(casilla_values, channel) == Decimal(0) for channel in channels
    )


def art52_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    operation: PinnedAuthorityOperation,
    modelo: str,
    effective_date: date,
) -> ModeloVerificationFinding | None:
    """Warn when individual previdencia-social reduction exceeds its sub-limit.

    ``effective_date`` is the filing coordinate the caller resolves every other
    dated fact at, so the declaration follows the work's filing year.
    """
    casillas = _art52_casillas(revision, modelo=modelo)
    if casillas is None:
        return None
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
        raise ModeloError(
            "Art. 52 individual sublimit fact must resolve to a Decimal",
            translated_message="application.modelo.errors.advisory_limit_not_numeric",
            context={"fact": _ART52_INDIVIDUAL_SUBLIMIT_FACT_ID},
            precondition_verdict=registry_defect_verdict("art52_sublimit_fact"),
        )
    if _individual_art52_sublimit_exceeded(casillas, casilla_values, sublimit):
        reduccion_id = casillas.reduccion
        reduccion_value = AbsentCasillaReading.ADVISORY_TRIGGER_OPERAND.read(casilla_values, reduccion_id)
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
