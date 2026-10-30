"""Generic verification mechanics for registry-selected DT12 declarations."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...core.casilla_value_absence import AbsentCasillaReading
from ...core.time.clock import today_madrid
from ...domain.calculations.registry.errors import RegistryValidationError
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
DT12_TRABAJO_REDUCCION_ROLE = "irpf_rendimiento_trabajo_reduccion"
_DT12_THRESHOLD_KEY = "predicate.threshold"


# Registry authority: selected DT12 declarations are consumed through the pinned operation and dated mapping fact
def resolve_dt12_verification_mapping(
    revision: object,
    *,
    operation: PinnedAuthorityOperation,
    fact_id: str,
) -> ResolvedMappingFact:
    """Resolve one DT12 verification mapping fact dated at the selected revision's end."""
    effective_date = getattr(revision, "valid_to", None) or today_madrid()
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id=fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TypeError("selected DT12 declaration must resolve as a mapping fact")
    return resolved


def _declared_threshold(declaration: ResolvedMappingFact) -> Decimal:
    """Read the large-trabajo income threshold the mapping fact declares."""
    for entry in declaration.payload.entries:
        if entry.key == _DT12_THRESHOLD_KEY:
            try:
                threshold = Decimal(str(entry.value))
            except InvalidOperation as exc:
                raise RegistryValidationError(f"DT12 mapping {_DT12_THRESHOLD_KEY!r} is not a decimal") from exc
            if not threshold.is_finite():
                raise RegistryValidationError(f"DT12 mapping {_DT12_THRESHOLD_KEY!r} is not finite")
            return threshold
    raise RegistryValidationError(f"DT12 mapping is missing {_DT12_THRESHOLD_KEY!r}")


def dt12_reduccion_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    operation: PinnedAuthorityOperation,
) -> ModeloVerificationFinding | None:
    """Warn when large trabajo income has no DT 12ª reduction declaration.

    The income threshold comes from the registry mapping fact, resolved through
    the caller-owned operation so the advisory is grounded in the same authority
    generation as the selected workflow.
    """
    try:
        ingreso_id = casilla_id_for_unique_revision_semantic_role(
            revision,
            _DT12_TRABAJO_INGRESO_ROLE,
        )
        reduccion_id = casilla_id_for_unique_revision_semantic_role(
            revision,
            DT12_TRABAJO_REDUCCION_ROLE,
        )
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(str(exc), context=exc.ambiguity.context()) from exc

    if ingreso_id is None or reduccion_id is None:
        return None

    ingreso_value = AbsentCasillaReading.ADVISORY_TRIGGER_OPERAND.read(casilla_values, ingreso_id)
    reduccion_value = AbsentCasillaReading.ADVISORY_GAP_OPERAND.read(casilla_values, reduccion_id)
    declaration = resolve_dt12_verification_mapping(
        revision, operation=operation, fact_id="lirpf-dt12-reduction-verification-mapping"
    )
    if ingreso_value <= _declared_threshold(declaration) or reduccion_value != Decimal(0):
        return None

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


__all__ = ["DT12_TRABAJO_REDUCCION_ROLE", "dt12_reduccion_advisory_finding", "resolve_dt12_verification_mapping"]
