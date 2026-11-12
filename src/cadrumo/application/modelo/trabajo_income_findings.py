"""Verification findings for the work-income boxes that no payer certificate fills.

The payer records fill the gross, in-kind, reduction and expense boxes of the work income
(:mod:`cadrumo.application.aggregation.retencion_soportada_source`). Four income boxes are in no
certificate (the employer's contributions and the protected-estate contribution), so only the
filer can state them, and leaving one out could lower the tax: each is a blocking finding while the
return rests on a work-income record and the box has neither a figure nor the statement of none.
The deductions only the filer can evidence are a served limitation, because leaving them out can
only raise the tax, unless a stored fact shows one applies (a stated disability) or the stated
figure passes its legal limit.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from ...core.casilla_id import CasillaId
from ...core.retencion_soportada import RetencionSoportadaClase
from ...domain.calculations.registry.formula_runtime_ops import resolve_parameter
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ..aggregation.retencion_soportada_source import recorded_income_classes
from .semantic_role_resolution import casilla_id_for_unique_revision_semantic_role

if TYPE_CHECKING:
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.modelos.calculation_revision import CalculationRevision

__all__ = [
    "TRABAJO_INCOME_STATEMENT_ROLES",
    "trabajo_income_findings",
    "trabajo_recorded",
]

_FINDINGS_KEY: Final[str] = "application.modelo.findings"
_ROLE_PREFIX: Final[str] = "irpf_rendimiento_trabajo_"

TRABAJO_INCOME_STATEMENT_ROLES: Final[Mapping[str, str]] = {
    f"{_ROLE_PREFIX}contribucion_empresarial_prevision": "prevision",
    f"{_ROLE_PREFIX}contribucion_empresarial_seguro_dependencia": "dependencia",
    f"{_ROLE_PREFIX}aportacion_patrimonio_protegido": "patrimonio_protegido",
    f"{_ROLE_PREFIX}aportacion_empresa_decision_trabajador": "decision_trabajador",
}
"""The income roles no payer certificate states, with the suffix of the words that name each."""

_TOTAL_INGRESOS_ROLE: Final[str] = f"{_ROLE_PREFIX}total_ingresos_integros"
_DISABILITY_INCREASE_ROLE: Final[str] = f"{_ROLE_PREFIX}incremento_discapacitado_activo"
_DISABILITY_PROFILE_PATH: Final[str] = "renta_taxpayer.disability_grade"
_EXPENSE_LIMITS: Final[tuple[tuple[str, str, str, str], ...]] = (
    # (casilla role, words suffix, limit parameter, legal reference)
    (
        f"{_ROLE_PREFIX}gasto_colegio_profesional",
        "colegio_profesional",
        "renta-trabajo-colegio-profesional-limite",
        "rd-439-2007:art-10",
    ),
    (
        f"{_ROLE_PREFIX}gasto_defensa_juridica",
        "defensa_juridica",
        "renta-trabajo-defensa-juridica-limite",
        "ley-35-2006:art-19",
    ),
)


def trabajo_recorded(target: CalculationRevision) -> bool:
    """Return whether the calculation rests on a payer record of work income, not on an attestation or absence."""
    return RetencionSoportadaClase.TRABAJO in recorded_income_classes(
        ref.source_ref for ref in target.source_provenance
    )


def _casilla(revision: ModeloRevision, role: str) -> CasillaId | None:
    return casilla_id_for_unique_revision_semantic_role(revision, role)


def _unstated_findings(revision: ModeloRevision, target: CalculationRevision) -> list[ModeloVerificationFinding]:
    bindings = {casilla.id: casilla.binding for casilla in revision.casillas}
    findings: list[ModeloVerificationFinding] = []
    for role, suffix in TRABAJO_INCOME_STATEMENT_ROLES.items():
        casilla_id = _casilla(revision, role)
        if casilla_id is None:
            continue
        binding = bindings.get(casilla_id)
        stated = (binding is not None and binding in target.binding_overrides) or casilla_id in (
            target.input_values_by_casilla_id
        )
        if not stated:
            findings.append(
                ModeloVerificationFinding(
                    kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                    severity=ModeloVerificationFindingSeverity.BLOCKING,
                    casilla_id=casilla_id,
                    message_locale_key=f"{_FINDINGS_KEY}.trabajo_income_unstated.{suffix}",
                    message_facts={"casilla_id": casilla_id},
                    legal_refs=("ley-35-2006:art-17",),
                ),
            )
    return findings


def _disability_finding(
    revision: ModeloRevision, target: CalculationRevision, profile_values: Mapping[str, str]
) -> ModeloVerificationFinding | None:
    if not (profile_values.get(_DISABILITY_PROFILE_PATH) or "").strip():
        return None
    casilla_id = _casilla(revision, _DISABILITY_INCREASE_ROLE)
    if casilla_id is None or casilla_id in target.input_values_by_casilla_id:
        return None
    return ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=casilla_id,
        message_locale_key=f"{_FINDINGS_KEY}.trabajo_disability_unstated",
        message_facts={"casilla_id": casilla_id},
        legal_refs=("ley-35-2006:art-19",),
    )


def _limit_findings(
    revision: ModeloRevision, target: CalculationRevision, effective_date: date
) -> list[ModeloVerificationFinding]:
    parameters = {parameter.id: parameter for parameter in revision.parameters}
    findings: list[ModeloVerificationFinding] = []
    for role, suffix, parameter_id, legal_ref in _EXPENSE_LIMITS:
        casilla_id = _casilla(revision, role)
        parameter = parameters.get(parameter_id)
        if casilla_id is None or parameter is None:
            continue
        limit = resolve_parameter(parameter, {"filing_period": effective_date})
        stated = target.casilla_values.get(casilla_id, Decimal(0))
        if stated > limit:
            findings.append(
                ModeloVerificationFinding(
                    kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                    severity=ModeloVerificationFindingSeverity.BLOCKING,
                    casilla_id=casilla_id,
                    message_locale_key=f"{_FINDINGS_KEY}.trabajo_expense_above_limit.{suffix}",
                    message_facts={"casilla_id": casilla_id, "stated": stated, "limit": limit},
                    legal_refs=(legal_ref,),
                ),
            )
    return findings


def trabajo_income_findings(
    revision: ModeloRevision,
    target: CalculationRevision,
    *,
    profile_values: Mapping[str, str],
    effective_date: date,
) -> tuple[ModeloVerificationFinding, ...]:
    """Return the work-income findings of ``target`` against the registry ``revision`` it was calculated on.

    ``profile_values`` are the path-keyed profile facts in force at the end of the ejercicio.
    A revision that declares none of the roles earns nothing here.
    """
    findings: list[ModeloVerificationFinding] = []
    recorded = trabajo_recorded(target)
    if recorded:
        findings.extend(_unstated_findings(revision, target))
    total_id = _casilla(revision, _TOTAL_INGRESOS_ROLE)
    has_work_income = recorded or (total_id is not None and target.casilla_values.get(total_id, Decimal(0)) > 0)
    if has_work_income and total_id is not None:
        findings.append(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.ADVISORY,
                severity=ModeloVerificationFindingSeverity.WARNING,
                casilla_id=total_id,
                message_locale_key=f"{_FINDINGS_KEY}.trabajo_deduction_not_computed",
                legal_refs=("ley-35-2006:art-19",),
            ),
        )
        disability = _disability_finding(revision, target, profile_values)
        if disability is not None:
            findings.append(disability)
        findings.extend(_limit_findings(revision, target, effective_date))
    return tuple(findings)
