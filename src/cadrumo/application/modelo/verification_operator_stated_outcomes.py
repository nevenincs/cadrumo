"""A calculated box the registry leaves open for the operator to state, and what verification makes of it.

A formula may leave its target without a value and name the box the operator
states in its place. Until that box is stated the verification is blocked, with
the door that states it. Once stated, the operator's figure stands for the
missing value in the registry checks that bound it, so typing the box admits
the declaration.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Final

from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.calculations.registry.formula_runtime_ops import (
    OPERATOR_BOX_CONTEXT_KEY,
    RegistryUnresolvedOutcomeReason,
)
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from .preconditions import build_modelo_precondition_failure

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ...domain.calculations.registry.formula_runtime import RegistryCalculationUnresolvedOutcome
    from ...domain.modelos.calculation_revision import CalculationRevision
    from .preconditions import ModeloPreconditionFailure

__all__ = [
    "STATED_BOX_ACTION_ID",
    "append_operator_stated_outcome_findings",
    "values_with_operator_stated_figures",
]

STATED_BOX_ACTION_ID = "operator.modelo.work.set_value"
"""The catalogue action by which the operator states the value of one box of a work unit."""

_EXTINCION_ENTIDAD_MESSAGE_KEY: Final = (
    "application.modelo.projection_words.casilla_reason.m200_extincion_entidad_unsupported"
)
_OTHER_REASON_MESSAGE_KEY: Final = "application.modelo.projection_words.casilla_reason.other"


def _operator_box(outcome: RegistryCalculationUnresolvedOutcome) -> CasillaId | None:
    named = outcome.context.get(OPERATOR_BOX_CONTEXT_KEY)
    return None if named is None else validated_casilla_id(named, surface="unresolved outcome operator box")


def _stated_figure(target: CalculationRevision, box: CasillaId) -> Decimal | None:
    raw = target.input_values_by_casilla_id.get(box)
    if raw is None:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def values_with_operator_stated_figures(target: CalculationRevision) -> Mapping[CasillaId, Decimal]:
    """The calculated values, the figure the operator stated standing for each box the registry left open.

    A box left open names the box the operator states; the figure stated there
    is the value the checks bounding the open box read, since it is the
    operator's to give and nothing else can bound it. A box not yet stated
    keeps no value.
    """
    values = dict(target.casilla_values)
    for outcome in target.unresolved_outcomes:
        box = _operator_box(outcome)
        if box is None:
            continue
        stated = _stated_figure(target, box)
        if stated is not None:
            values[outcome.casilla_id] = stated
    return values


def append_operator_stated_outcome_findings(
    *,
    target: CalculationRevision,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    """Block the verification for each open box whose operator box is not stated, with the door that states it."""
    for outcome in target.unresolved_outcomes:
        box = _operator_box(outcome)
        if box is None or _stated_figure(target, box) is not None:
            continue
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            casilla_id=box,
            message_locale_key=(
                _EXTINCION_ENTIDAD_MESSAGE_KEY
                if outcome.reason is RegistryUnresolvedOutcomeReason.M200_EXTINCION_ENTIDAD_UNSUPPORTED
                else _OTHER_REASON_MESSAGE_KEY
            ),
            message_facts={"reason": outcome.reason.value, "casilla_id": box, "open_casilla_id": outcome.casilla_id},
            legal_refs=outcome.legal_refs,
            source_refs=outcome.source_refs,
        )
        findings.append(finding)
        failures_by_finding_id[id(finding)] = build_modelo_precondition_failure(
            subject_leaf_key="modelo.work.verify",
            condition_id="modelo.work.verify.operator_box.stated",
            scenario_id="modelo.work.verify.operator_box.unstated",
            evidence_id="modelo.work.verify.operator_box",
            evidence_values={"reason_code": outcome.reason.value, "casilla_id": box},
            provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
            action_id=STATED_BOX_ACTION_ID,
            action_argument_values={"casilla_id": box, "work_unit_id": target.work_unit_id},
            missing_action_arguments=("value",),
        )
