"""The public verdict snapshot keeps every offered door and the bytes of a verdict that offers one."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import BaseModel, ConfigDict

from ....core.identifier_grammar import NamespacedId
from ....core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ..models import (
    ActionArgumentBinding,
    ActionReference,
    AlternativeRecoveryAction,
    ConditionEvidence,
    PreconditionVerdict,
)
from ..projection import ActionArgumentSnapshot, ConditionEvidenceSnapshot, PreconditionVerdictSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _evidence() -> ConditionEvidence:
    return ConditionEvidence(
        condition_id="modelo.work.verify.cross_period_dependency.clean",
        evidence_id="modelo.work.verify.cross_period_dependency",
        provenance=ActionEvidenceProvenance.DOMAIN_EVALUATION,
        values={"source_modelo": "100", "year": 7},
    )


def _create_verdict(*alternatives: AlternativeRecoveryAction) -> PreconditionVerdict:
    return PreconditionVerdict(
        failed_condition_id="modelo.work.verify.cross_period_dependency.clean",
        evidence=(_evidence(),),
        action=ActionReference(action_id="operator.modelo.work.create"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="modelo",
                status=ActionArgumentStatus.RESOLVED,
                value="100",
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="modelo",
            ),
        ),
        conditionality=ActionConditionality.IMMEDIATE,
        alternative_actions=alternatives,
    )


def _statement() -> AlternativeRecoveryAction:
    return AlternativeRecoveryAction(
        action=ActionReference(action_id="operator.modelo.work.attest_prior_value"),
        argument_bindings=(
            ActionArgumentBinding(
                argument_name="binding_id",
                status=ActionArgumentStatus.RESOLVED,
                value="irpf.previous_year_economic_activity_net_income",
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="binding_id",
            ),
            ActionArgumentBinding(
                argument_name="ceiling",
                status=ActionArgumentStatus.RESOLVED,
                value=Decimal("12.50"),
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="ceiling",
            ),
            ActionArgumentBinding(argument_name="value", status=ActionArgumentStatus.MISSING),
        ),
        missing_argument_names=("value",),
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )


def test_the_snapshot_restores_every_alternative_in_order_through_its_json() -> None:
    capture = AlternativeRecoveryAction(
        action=ActionReference(action_id="operator.live.filed.pull"),
        conditionality=ActionConditionality.IMMEDIATE,
    )
    verdict = _create_verdict(_statement(), capture)

    snapshot = PreconditionVerdictSnapshot.from_verdict(verdict)
    restored = PreconditionVerdictSnapshot.model_validate_json(snapshot.model_dump_json())

    assert restored == snapshot
    assert restored.to_verdict() == verdict
    assert [item.action_id for item in restored.alternative_actions] == [
        "operator.modelo.work.attest_prior_value",
        "operator.live.filed.pull",
    ]
    ceiling = restored.to_verdict().alternative_actions[0].argument_bindings[1]
    assert ceiling.argument_name == "ceiling"
    assert ceiling.value == Decimal("12.50")
    assert type(ceiling.value) is Decimal


class _SnapshotBeforeAlternatives(BaseModel):
    """The snapshot exactly as workflow history stored it before alternatives existed."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    failed_condition_id: NamespacedId
    evidence: tuple[ConditionEvidenceSnapshot, ...]
    action_id: NamespacedId | None = None
    argument_bindings: tuple[ActionArgumentSnapshot, ...] = ()
    missing_argument_names: tuple[str, ...] = ()
    conditionality: ActionConditionality
    no_recovery_outcome: NoRecoveryOutcome | None = None


def test_a_snapshot_without_alternatives_keeps_the_bytes_stored_before_the_list() -> None:
    verdict = _create_verdict()
    snapshot = PreconditionVerdictSnapshot.from_verdict(verdict)
    stored = _SnapshotBeforeAlternatives(
        failed_condition_id=verdict.failed_condition_id,
        evidence=tuple(ConditionEvidenceSnapshot.from_evidence(item) for item in verdict.evidence),
        action_id="operator.modelo.work.create",
        argument_bindings=tuple(ActionArgumentSnapshot.from_argument(item) for item in verdict.argument_bindings),
        conditionality=ActionConditionality.IMMEDIATE,
    ).model_dump_json()

    assert snapshot.model_dump_json() == stored
    assert set(json.loads(snapshot.model_dump_json())) == {
        "failed_condition_id",
        "evidence",
        "action_id",
        "argument_bindings",
        "missing_argument_names",
        "conditionality",
        "no_recovery_outcome",
    }
    restored = PreconditionVerdictSnapshot.model_validate_json(stored)
    assert restored == snapshot
    assert restored.model_dump_json() == stored
    assert restored.to_verdict() == verdict
