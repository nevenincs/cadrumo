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
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.retencion_soportada import RetencionSoportadaClase
from ...domain.calculations.registry.trabajo_expense_limits import TrabajoExpenseLimits, trabajo_expense_limits
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ..aggregation.retencion_soportada_source import recorded_income_classes
from .precondition_action_bindings import AlternativeActionArguments
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario
from .semantic_role_resolution import casilla_id_for_unique_revision_semantic_role

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.ids import BindingId
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.modelos.calculation_revision import CalculationRevision

__all__ = [
    "TRABAJO_INCOME_STATEMENT_ROLES",
    "TrabajoIncomeFinding",
    "trabajo_income_findings",
    "trabajo_recorded",
]

_ROLE_PREFIX: Final[str] = "irpf_rendimiento_trabajo_"

TRABAJO_INCOME_STATEMENT_ROLES: Final[Mapping[str, str]] = {
    f"{_ROLE_PREFIX}contribucion_empresarial_prevision": "prevision",
    f"{_ROLE_PREFIX}contribucion_empresarial_seguro_dependencia": "dependencia",
    f"{_ROLE_PREFIX}aportacion_patrimonio_protegido": "patrimonio_protegido",
    f"{_ROLE_PREFIX}aportacion_empresa_decision_trabajador": "decision_trabajador",
}
"""The income roles no payer certificate states, with the suffix of the words that name each."""

_UNSTATED_SCENARIO: Final[str] = "unstated"
_TOTAL_INGRESOS_ROLE: Final[str] = f"{_ROLE_PREFIX}total_ingresos_integros"
_DISABILITY_INCREASE_ROLE: Final[str] = f"{_ROLE_PREFIX}incremento_discapacitado_activo"
_DISABILITY_PROFILE_PATH: Final[str] = "renta_taxpayer.disability_grade"
_EXPENSE_LIMITS: Final[tuple[tuple[str, str, str], ...]] = (
    # (casilla role, words suffix, legal reference)
    (f"{_ROLE_PREFIX}gasto_colegio_profesional", "colegio_profesional", "rd-439-2007:art-10"),
    (f"{_ROLE_PREFIX}gasto_defensa_juridica", "defensa_juridica", "ley-35-2006:art-19"),
)


def trabajo_recorded(target: CalculationRevision) -> bool:
    """Return whether the calculation rests on a payer record of work income, not on an attestation or absence."""
    return RetencionSoportadaClase.TRABAJO in recorded_income_classes(
        ref.source_ref for ref in target.source_provenance
    )


def _casilla(revision: ModeloRevision, role: str) -> CasillaId | None:
    return casilla_id_for_unique_revision_semantic_role(revision, role)


TrabajoIncomeFinding = tuple[ModeloVerificationFinding, ModeloPreconditionFailure | None]
"""One work-income finding with the verify verdict a blocking one carries; a warning carries none."""


def _blocking(
    finding: ModeloVerificationFinding,
    target: CalculationRevision,
    *,
    scenario: str,
    binding_id: str | None,
) -> TrabajoIncomeFinding:
    """Pair a blocking finding with the door that states its box.

    A box read from a binding is stated by the override bound to it, any other
    box by its own value. The verdict knows the declaration and the box; the
    filer supplies the figure. An unstated income box is first served the one
    statement that the boxes no payer certificate fills hold nothing, and the
    box's own door stays beside it as an alternative.
    """
    casilla_id = finding.casilla_id
    if casilla_id is None:
        raise ValueError("a work-income finding names its box")
    income_unstated = scenario == _UNSTATED_SCENARIO
    door_arguments: dict[str, str] = {"work_unit_id": target.work_unit_id}
    if binding_id is not None:
        scenario = f"{scenario}_source"
        door_arguments["binding_id"] = binding_id
    else:
        door_arguments["casilla_id"] = str(casilla_id)
    primary_arguments: dict[str, str] = door_arguments
    missing_arguments: tuple[str, ...] = ("value",)
    alternative_actions: tuple[AlternativeActionArguments, ...] = ()
    box_door = "operator.modelo.work.set_value" if binding_id is None else "operator.modelo.work.override"
    if income_unstated:
        primary_arguments = {"work_unit_id": target.work_unit_id}
        missing_arguments = ()
        alternative_actions = (
            AlternativeActionArguments(
                action_id=box_door,
                action_argument_values=door_arguments,
                missing_action_arguments=("value",),
            ),
        )
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.work.verify",
        scenario_id=f"modelo.work.verify.trabajo_income.{scenario}",
        evidence_id="modelo.work.verify.trabajo_income",
        evidence_values={
            "calculation_revision_id": target.calculation_revision_id,
            "work_unit_id": target.work_unit_id,
            "casilla_id": str(casilla_id),
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values=primary_arguments,
        missing_action_arguments=missing_arguments,
        alternative_actions=alternative_actions,
    )
    return (finding, failure)


def _stated(target: CalculationRevision, casilla_id: CasillaId, binding: BindingId | None) -> bool:
    if binding is not None and binding in target.binding_overrides:
        return True
    return casilla_id in target.input_values_by_casilla_id


def _unstated_findings(revision: ModeloRevision, target: CalculationRevision) -> list[TrabajoIncomeFinding]:
    bindings = {casilla.id: casilla.binding for casilla in revision.casillas}
    findings: list[TrabajoIncomeFinding] = []
    for role, suffix in TRABAJO_INCOME_STATEMENT_ROLES.items():
        casilla_id = _casilla(revision, role)
        if casilla_id is None:
            continue
        binding = bindings.get(casilla_id)
        if not _stated(target, casilla_id, binding):
            finding = ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                casilla_id=casilla_id,
                message_locale_key=(
                    "application.modelo.findings.trabajo_income_unstated.prevision"
                    if suffix == "prevision"
                    else "application.modelo.findings.trabajo_income_unstated.dependencia"
                    if suffix == "dependencia"
                    else "application.modelo.findings.trabajo_income_unstated.patrimonio_protegido"
                    if suffix == "patrimonio_protegido"
                    else "application.modelo.findings.trabajo_income_unstated.decision_trabajador"
                ),
                message_facts={"casilla_id": casilla_id},
                legal_refs=("ley-35-2006:art-17",),
            )
            findings.append(
                _blocking(finding, target, scenario="unstated", binding_id=None if binding is None else str(binding))
            )
    return findings


def _disability_finding(
    revision: ModeloRevision, target: CalculationRevision, profile_values: Mapping[str, str]
) -> TrabajoIncomeFinding | None:
    if not (profile_values.get(_DISABILITY_PROFILE_PATH) or "").strip():
        return None
    casilla_id = _casilla(revision, _DISABILITY_INCREASE_ROLE)
    if casilla_id is None or casilla_id in target.input_values_by_casilla_id:
        return None
    finding = ModeloVerificationFinding(
        kind=ModeloVerificationFindingKind.BLOCKING_RULE,
        severity=ModeloVerificationFindingSeverity.BLOCKING,
        casilla_id=casilla_id,
        message_locale_key="application.modelo.findings.trabajo_disability_unstated",
        message_facts={"casilla_id": casilla_id},
        legal_refs=("ley-35-2006:art-19",),
    )
    # Only the box's own typed value answers the increase, so that value is the door.
    return _blocking(finding, target, scenario="disability_increase_unstated", binding_id=None)


def _limit_findings(
    revision: ModeloRevision, target: CalculationRevision, limits: TrabajoExpenseLimits
) -> list[TrabajoIncomeFinding]:
    bindings = {casilla.id: casilla.binding for casilla in revision.casillas}
    findings: list[TrabajoIncomeFinding] = []
    for role, suffix, legal_ref in _EXPENSE_LIMITS:
        casilla_id = _casilla(revision, role)
        limit = limits.colegio_profesional if suffix == "colegio_profesional" else limits.defensa_juridica
        if casilla_id is None or limit is None:
            continue
        stated = target.casilla_values.get(casilla_id, Decimal(0))
        if stated > limit:
            binding = bindings.get(casilla_id)
            finding = ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                casilla_id=casilla_id,
                message_locale_key=(
                    "application.modelo.findings.trabajo_expense_above_limit.colegio_profesional"
                    if suffix == "colegio_profesional"
                    else "application.modelo.findings.trabajo_expense_above_limit.defensa_juridica"
                ),
                message_facts={"casilla_id": casilla_id, "stated": stated, "limit": limit},
                legal_refs=(legal_ref,),
            )
            findings.append(
                _blocking(
                    finding,
                    target,
                    scenario="expense_above_limit",
                    binding_id=None if binding is None else str(binding),
                )
            )
    return findings


def trabajo_income_findings(
    modelo_id: str,
    revision: ModeloRevision,
    target: CalculationRevision,
    *,
    profile_values: Mapping[str, str],
    effective_date: date,
    operation: PinnedAuthorityOperation,
) -> tuple[TrabajoIncomeFinding, ...]:
    """Return the work-income findings of ``target`` against the ``modelo_id`` registry ``revision`` it rests on.

    Each blocking finding is built with its verify verdict and the door that
    states its box; the served limitation is a warning and carries none.
    ``profile_values`` are the path-keyed profile facts in force at the end of the ejercicio.
    A revision that declares none of the roles earns nothing here.
    """
    findings: list[TrabajoIncomeFinding] = []
    recorded = trabajo_recorded(target)
    if recorded:
        findings.extend(_unstated_findings(revision, target))
    total_id = _casilla(revision, _TOTAL_INGRESOS_ROLE)
    has_work_income = recorded or (total_id is not None and target.casilla_values.get(total_id, Decimal(0)) > 0)
    if has_work_income and total_id is not None:
        findings.append(
            (
                ModeloVerificationFinding(
                    kind=ModeloVerificationFindingKind.ADVISORY,
                    severity=ModeloVerificationFindingSeverity.WARNING,
                    casilla_id=total_id,
                    message_locale_key="application.modelo.findings.trabajo_deduction_not_computed",
                    legal_refs=("ley-35-2006:art-19",),
                    disclosed_limitation=True,
                ),
                None,
            ),
        )
        disability = _disability_finding(revision, target, profile_values)
        if disability is not None:
            findings.append(disability)
        limits = trabajo_expense_limits(modelo_id, revision, operation=operation, effective_date=effective_date)
        findings.extend(_limit_findings(revision, target, limits))
    return tuple(findings)
