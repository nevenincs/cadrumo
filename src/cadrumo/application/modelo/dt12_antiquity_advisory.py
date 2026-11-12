"""Advise confirming the DT 12ª antiquity condition when its reduction is applied."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.casilla_id import CasillaId
from ...core.casilla_value_absence import AbsentCasillaReading
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .calculation_input_refusal_doors import semantic_role_ambiguous_verdict
from .dt12_advisory import DT12_TRABAJO_REDUCCION_ROLE, resolve_dt12_verification_mapping
from .semantic_role_resolution import AmbiguousSemanticRoleCasillaError, casilla_id_for_unique_revision_semantic_role

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = ["dt12_antiquity_advisory_finding"]


def dt12_antiquity_advisory_finding(
    revision: object,
    casilla_values: Mapping[CasillaId, Decimal],
    *,
    operation: PinnedAuthorityOperation,
    modelo: str,
    effective_date: date,
) -> ModeloVerificationFinding | None:
    """Warn to confirm the DT 12ª antiquity condition when reduction applies."""
    try:
        reduccion_id = casilla_id_for_unique_revision_semantic_role(
            revision,
            DT12_TRABAJO_REDUCCION_ROLE,
            modelo_id=modelo,
        )
    except AmbiguousSemanticRoleCasillaError as exc:
        raise ModeloError(
            str(exc),
            context=exc.ambiguity.context(),
            precondition_verdict=semantic_role_ambiguous_verdict(exc.ambiguity.semantic_role),
        ) from exc

    if reduccion_id is None:
        return None

    reduccion_value = AbsentCasillaReading.ADVISORY_TRIGGER_OPERAND.read(casilla_values, reduccion_id)
    if reduccion_value <= Decimal(0):
        return None

    declaration = resolve_dt12_verification_mapping(
        revision,
        operation=operation,
        fact_id="lirpf-dt12-antiquity-verification-mapping",
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
