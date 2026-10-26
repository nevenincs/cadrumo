"""Real validation tests for the application-owned action outcome records."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from types import MappingProxyType

import pytest
from pydantic import BaseModel, ValidationError

from ....core.action_argument_resolution import ActionArgumentResolution
from ....core.json_contract import (
    ActionConditionEvidence,
    ResolvedActionArgument,
    ResolvedActionReference,
    ResolvedPreconditionAction,
)
from ....core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ....core.precondition_action_invariants import (
    PreconditionActionIdentity,
    PreconditionEvidence,
    PreconditionOutcomeInvariant,
)
from ..models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _ActionContractComposition(BaseModel):
    """Compose the application verdict and wire projection in one real schema."""

    application_binding: ActionArgumentBinding
    application_evidence: ConditionEvidence
    application_verdict: PreconditionVerdict
    wire_binding: ResolvedActionArgument
    wire_evidence: ActionConditionEvidence
    wire_verdict: ResolvedPreconditionAction


def _evidence() -> ConditionEvidence:
    return ConditionEvidence(
        condition_id="profile.active",
        evidence_id="profile.active.selection",
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        values={"bucket_count": 0, "is_selected": False, "profile_key": "operator"},
    )


def _resolved_argument() -> ActionArgumentBinding:
    return ActionArgumentBinding(
        argument_name="profile_key",
        status=ActionArgumentStatus.RESOLVED,
        value="operator",
        source=ActionArgumentSource.CONDITION_EVIDENCE,
        source_key="profile_key",
        source_evidence_id="profile.active.selection",
    )


def test_application_and_wire_action_models_share_the_core_enum_objects_and_schema_definitions() -> None:
    """One composed contract cannot grow parallel enum schema identities."""
    assert ConditionEvidence.model_fields["provenance"].annotation is ActionEvidenceProvenance
    assert ActionConditionEvidence.model_fields["provenance"].annotation is ActionEvidenceProvenance
    assert ActionArgumentBinding.model_fields["status"].annotation is ActionArgumentStatus
    assert ResolvedActionArgument.model_fields["status"].annotation is ActionArgumentStatus
    assert ActionArgumentBinding.model_fields["source"].annotation == ActionArgumentSource | None
    assert ResolvedActionArgument.model_fields["source"].annotation == ActionArgumentSource | None
    assert PreconditionVerdict.model_fields["conditionality"].annotation is ActionConditionality
    assert ResolvedPreconditionAction.model_fields["conditionality"].annotation is ActionConditionality
    assert PreconditionVerdict.model_fields["no_recovery_outcome"].annotation == NoRecoveryOutcome | None
    assert ResolvedPreconditionAction.model_fields["no_recovery_outcome"].annotation == NoRecoveryOutcome | None

    schema = _ActionContractComposition.model_json_schema()
    definitions = schema["$defs"]
    expected_definitions = {
        enum_type.__name__: tuple(member.value for member in enum_type)
        for enum_type in (
            ActionArgumentSource,
            ActionArgumentStatus,
            ActionConditionality,
            ActionEvidenceProvenance,
            NoRecoveryOutcome,
        )
    }
    actual_definitions = {
        title: tuple(definition["enum"])
        for definition in definitions.values()
        if (title := definition.get("title")) in expected_definitions
    }

    assert actual_definitions == expected_definitions
    assert {
        title: {name for name, definition in definitions.items() if definition.get("title") == title}
        for title in expected_definitions
    } == {title: {title} for title in expected_definitions}


def test_application_and_wire_action_argument_models_share_one_core_resolution_implementation() -> None:
    """Both layer DTOs inherit the sole core-owned resolution invariant."""
    assert ActionArgumentBinding.__bases__ == (ActionArgumentResolution,)
    assert ResolvedActionArgument.__bases__ == (ActionArgumentResolution,)
    assert "_validate_resolution" in ActionArgumentResolution.__dict__
    assert "_validate_resolution" not in ActionArgumentBinding.__dict__
    assert "_validate_resolution" not in ResolvedActionArgument.__dict__


def test_application_and_wire_precondition_models_have_one_core_invariant_owner() -> None:
    """Both projections inherit the only factual-evidence and outcome invariant."""
    assert ConditionEvidence.__bases__ == (PreconditionEvidence,)
    assert ActionConditionEvidence.__bases__ == (PreconditionEvidence,)
    assert ActionReference.__bases__ == (PreconditionActionIdentity,)
    assert ResolvedActionReference.__bases__ == (PreconditionActionIdentity,)
    assert PreconditionOutcomeInvariant in PreconditionVerdict.__mro__
    assert PreconditionOutcomeInvariant in ResolvedPreconditionAction.__mro__

    canonical_validators = {
        "_freeze_values",
        "_serialize_values",
        "_canonicalize_evidence",
        "_canonicalize_arguments",
        "_canonicalize_missing_names",
        "_validate_outcome",
        "_reject_arguments_their_evidence_does_not_support",
        "_reject_conditionality_the_outcome_contradicts",
    }
    assert canonical_validators <= set(PreconditionEvidence.__dict__) | set(PreconditionOutcomeInvariant.__dict__)
    assert not canonical_validators & set(ConditionEvidence.__dict__)
    assert not canonical_validators & set(ActionConditionEvidence.__dict__)
    assert not canonical_validators & set(PreconditionVerdict.__dict__)
    assert not canonical_validators & set(ResolvedPreconditionAction.__dict__)


def test_application_and_wire_precondition_models_pin_the_actionable_and_closed_refusal_schema() -> None:
    """The application verdict and wire record must keep one executable grammar."""
    expected_fields = (
        "failed_condition_id",
        "evidence",
        "action",
        "argument_bindings",
        "missing_argument_names",
        "conditionality",
        "no_recovery_outcome",
    )

    assert tuple(PreconditionVerdict.model_fields) == expected_fields
    assert tuple(ResolvedPreconditionAction.model_fields) == expected_fields
    assert tuple(member.value for member in ActionConditionality) == (
        "immediate",
        "requires_arguments",
        "not_applicable",
    )
    assert tuple(member.value for member in ActionArgumentStatus) == ("resolved", "missing")
    assert tuple(member.value for member in NoRecoveryOutcome) == (
        "terminal",
        "safety",
        "operator_decision",
    )


def test_application_and_wire_precondition_models_both_refuse_evidence_from_another_condition() -> None:
    """The shared outcome invariant rejects the same factual join defect in both projections."""
    with pytest.raises(ValidationError, match="condition evidence must identify the failed condition"):
        PreconditionVerdict(
            failed_condition_id="profile.other",
            evidence=(_evidence(),),
            conditionality=ActionConditionality.NOT_APPLICABLE,
            no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
        )

    with pytest.raises(ValidationError, match="condition evidence must identify the failed condition"):
        ResolvedPreconditionAction(
            failed_condition_id="profile.other",
            evidence=(
                ActionConditionEvidence(
                    condition_id="profile.active",
                    evidence_id="profile.active.selection",
                    provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                    values={"profile_key": "operator"},
                ),
            ),
            conditionality=ActionConditionality.NOT_APPLICABLE,
            no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
        )


def test_immediate_verdict_is_immutable_and_serializes_evidence_deterministically() -> None:
    verdict = PreconditionVerdict(
        failed_condition_id="profile.active",
        evidence=(_evidence(),),
        action=ActionReference(action_id="profile.create"),
        argument_bindings=(_resolved_argument(),),
        missing_argument_names=(),
        conditionality=ActionConditionality.IMMEDIATE,
    )

    assert verdict.evidence[0].values == {
        "bucket_count": 0,
        "is_selected": False,
        "profile_key": "operator",
    }
    assert list(verdict.evidence[0].values) == ["bucket_count", "is_selected", "profile_key"]
    assert verdict.model_dump(mode="json") == {
        "failed_condition_id": "profile.active",
        "evidence": [
            {
                "condition_id": "profile.active",
                "evidence_id": "profile.active.selection",
                "provenance": "application_state",
                "values": {"bucket_count": 0, "is_selected": False, "profile_key": "operator"},
            },
        ],
        "action": {"action_id": "profile.create"},
        "argument_bindings": [
            {
                "argument_name": "profile_key",
                "status": "resolved",
                "value": "operator",
                "source": "operator_action.condition_evidence",
                "source_key": "profile_key",
                "source_evidence_id": "profile.active.selection",
            },
        ],
        "missing_argument_names": [],
        "conditionality": "immediate",
        "no_recovery_outcome": None,
    }

    assert isinstance(verdict.evidence[0].values, MappingProxyType)
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        verdict.failed_condition_id = "profile.other"


@pytest.mark.parametrize(
    ("binding", "match"),
    (
        (
            {
                "argument_name": "profile_key",
                "status": ActionArgumentStatus.RESOLVED,
                "value": "operator",
                "source": None,
                "source_key": "profile.active.selection",
            },
            "resolved action arguments require value, source, and source_key",
        ),
        (
            {
                "argument_name": "profile_key",
                "status": ActionArgumentStatus.MISSING,
                "value": "operator",
                "source": ActionArgumentSource.REQUEST_CONTEXT,
                "source_key": "profile_key",
            },
            "missing action arguments cannot carry value or source",
        ),
    ),
)
def test_argument_resolution_states_are_not_ambiguous(binding: dict[str, object], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        ActionArgumentBinding.model_validate(binding)


def test_condition_evidence_binding_requires_a_declared_matching_fact() -> None:
    for binding, match in (
        (
            ActionArgumentBinding(
                argument_name="profile_key",
                status=ActionArgumentStatus.RESOLVED,
                value="operator",
                source=ActionArgumentSource.CONDITION_EVIDENCE,
                source_key="profile_key",
                source_evidence_id="profile.active.unknown",
            ),
            "reference declared evidence",
        ),
        (
            ActionArgumentBinding(
                argument_name="profile_key",
                status=ActionArgumentStatus.RESOLVED,
                value="operator",
                source=ActionArgumentSource.CONDITION_EVIDENCE,
                source_key="unknown_fact",
                source_evidence_id="profile.active.selection",
            ),
            "reference a declared evidence fact",
        ),
        (
            ActionArgumentBinding(
                argument_name="profile_key",
                status=ActionArgumentStatus.RESOLVED,
                value="different",
                source=ActionArgumentSource.CONDITION_EVIDENCE,
                source_key="profile_key",
                source_evidence_id="profile.active.selection",
            ),
            "exactly match its evidence fact",
        ),
    ):
        with pytest.raises(ValidationError, match=match):
            PreconditionVerdict(
                failed_condition_id="profile.active",
                evidence=(_evidence(),),
                action=ActionReference(action_id="profile.create"),
                argument_bindings=(binding,),
                conditionality=ActionConditionality.IMMEDIATE,
            )

    with pytest.raises(ValidationError, match="require source_evidence_id"):
        ActionArgumentBinding(
            argument_name="profile_key",
            status=ActionArgumentStatus.RESOLVED,
            value="operator",
            source=ActionArgumentSource.CONDITION_EVIDENCE,
            source_key="profile_key",
        )


@pytest.mark.parametrize(
    "values",
    (
        {"operator_message": "profile unavailable"},
        {"profile_key": "Run aeat config profile create operator"},
        {"profile_key": "`aeat config profile create operator`"},
    ),
)
def test_evidence_refuses_presentation_and_executable_command_prose(
    values: dict[str, str],
) -> None:
    with pytest.raises(ValidationError, match=r"presentation|raw aeat command prose"):
        ConditionEvidence(
            condition_id="profile.active",
            evidence_id="profile.active.selection",
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            values=values,
        )


def test_evidence_allows_stable_identifiers_revisions_and_paths() -> None:
    evidence = ConditionEvidence(
        condition_id="modelo.ready",
        evidence_id="modelo.ready.registry",
        provenance=ActionEvidenceProvenance.REGISTRY_RECORD,
        values={
            "registry_path": "aeat/registry/modelo_303/2024",
            "revision_id": "aeat.model.303.v2024",
            "source_path": r"C:\evidence\aeat\modelo_303\2024",
        },
    )

    assert evidence.model_dump(mode="json")["values"] == {
        "registry_path": "aeat/registry/modelo_303/2024",
        "revision_id": "aeat.model.303.v2024",
        "source_path": r"C:\evidence\aeat\modelo_303\2024",
    }


def test_missing_arguments_must_match_conditional_recovery_action() -> None:
    missing = ActionArgumentBinding(argument_name="profile_key", status=ActionArgumentStatus.MISSING)

    verdict = PreconditionVerdict(
        failed_condition_id="profile.active",
        evidence=(_evidence(),),
        action=ActionReference(action_id="profile.create"),
        argument_bindings=(missing,),
        missing_argument_names=("profile_key",),
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )
    assert verdict.missing_argument_names == ("profile_key",)

    with pytest.raises(ValidationError, match="missing_argument_names"):
        PreconditionVerdict(
            failed_condition_id="profile.active",
            evidence=(_evidence(),),
            action=ActionReference(action_id="profile.create"),
            argument_bindings=(missing,),
            missing_argument_names=(),
            conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
        )


def test_action_conditionality_requires_consistent_resolved_or_missing_bindings() -> None:
    missing = ActionArgumentBinding(argument_name="profile_key", status=ActionArgumentStatus.MISSING)

    with pytest.raises(ValidationError, match="missing action arguments require requires_arguments"):
        PreconditionVerdict(
            failed_condition_id="profile.active",
            evidence=(_evidence(),),
            action=ActionReference(action_id="operator.profile.create"),
            argument_bindings=(missing,),
            missing_argument_names=("profile_key",),
            conditionality=ActionConditionality.IMMEDIATE,
        )


@pytest.mark.parametrize(
    "invalid_verdict",
    (
        pytest.param(
            lambda: PreconditionVerdict(
                failed_condition_id="profile.active",
                evidence=(_evidence(), _evidence()),
                conditionality=ActionConditionality.NOT_APPLICABLE,
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
            ),
            id="duplicate-evidence-id",
        ),
        pytest.param(
            lambda: PreconditionVerdict(
                failed_condition_id="profile.active",
                evidence=(_evidence(),),
                action=ActionReference(action_id="operator.profile.create"),
                argument_bindings=(
                    ActionArgumentBinding(
                        argument_name="profile_key",
                        status=ActionArgumentStatus.MISSING,
                    ),
                    ActionArgumentBinding(
                        argument_name="profile_key",
                        status=ActionArgumentStatus.MISSING,
                    ),
                ),
                missing_argument_names=("profile_key",),
                conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
            ),
            id="duplicate-binding-argument-name",
        ),
        pytest.param(
            lambda: PreconditionVerdict(
                failed_condition_id="profile.active",
                evidence=(_evidence(),),
                action=ActionReference(action_id="operator.profile.create"),
                argument_bindings=(
                    ActionArgumentBinding(
                        argument_name="profile_key",
                        status=ActionArgumentStatus.MISSING,
                    ),
                ),
                missing_argument_names=("profile_key", "profile_key"),
                conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
            ),
            id="duplicate-missing-argument-name",
        ),
    ),
)
def test_verdict_rejects_duplicate_public_members(
    invalid_verdict: Callable[[], PreconditionVerdict],
) -> None:
    with pytest.raises(ValidationError):
        invalid_verdict()

    with pytest.raises(ValidationError, match="fully resolved recovery actions require immediate conditionality"):
        PreconditionVerdict(
            failed_condition_id="profile.active",
            evidence=(_evidence(),),
            action=ActionReference(action_id="operator.profile.create"),
            conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
        )


def test_equivalent_verdicts_canonicalize_evidence_bindings_and_missing_arguments() -> None:
    first_evidence = _evidence()
    second_evidence = ConditionEvidence(
        condition_id="profile.active",
        evidence_id="profile.active.runtime",
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        values={"tenant_id": "tenant-a"},
    )
    profile_binding = _resolved_argument()
    tenant_binding = ActionArgumentBinding(
        argument_name="tenant_id",
        status=ActionArgumentStatus.RESOLVED,
        value="tenant-a",
        source=ActionArgumentSource.CONDITION_EVIDENCE,
        source_key="tenant_id",
        source_evidence_id="profile.active.runtime",
    )

    canonical = PreconditionVerdict(
        failed_condition_id="profile.active",
        evidence=(first_evidence, second_evidence),
        action=ActionReference(action_id="profile.create"),
        argument_bindings=(profile_binding, tenant_binding),
        conditionality=ActionConditionality.IMMEDIATE,
    )
    reversed_input = PreconditionVerdict(
        failed_condition_id="profile.active",
        evidence=(second_evidence, first_evidence),
        action=ActionReference(action_id="profile.create"),
        argument_bindings=(tenant_binding, profile_binding),
        conditionality=ActionConditionality.IMMEDIATE,
    )
    missing = PreconditionVerdict(
        failed_condition_id="profile.active",
        evidence=(first_evidence,),
        action=ActionReference(action_id="profile.create"),
        argument_bindings=(
            ActionArgumentBinding(argument_name="tenant_id", status=ActionArgumentStatus.MISSING),
            ActionArgumentBinding(argument_name="profile_key", status=ActionArgumentStatus.MISSING),
        ),
        missing_argument_names=("tenant_id", "profile_key"),
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
    )

    assert canonical.model_dump(mode="json") == reversed_input.model_dump(mode="json")
    assert tuple(item.evidence_id for item in reversed_input.evidence) == (
        "profile.active.runtime",
        "profile.active.selection",
    )
    assert tuple(item.argument_name for item in reversed_input.argument_bindings) == ("profile_key", "tenant_id")
    assert missing.missing_argument_names == ("profile_key", "tenant_id")


@pytest.mark.parametrize(
    "outcome",
    (
        NoRecoveryOutcome.TERMINAL,
        NoRecoveryOutcome.SAFETY,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
)
def test_no_recovery_is_explicit_for_every_closed_outcome(outcome: NoRecoveryOutcome) -> None:
    verdict = PreconditionVerdict(
        failed_condition_id="profile.active",
        evidence=(_evidence(),),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=outcome,
    )
    assert verdict.no_recovery_outcome is outcome
    assert verdict.action is None


def test_verdict_requires_exactly_one_action_or_no_recovery_outcome() -> None:
    with pytest.raises(ValidationError, match="exactly one action or no_recovery_outcome"):
        PreconditionVerdict(
            failed_condition_id="profile.active",
            evidence=(_evidence(),),
            conditionality=ActionConditionality.NOT_APPLICABLE,
        )

    with pytest.raises(ValidationError, match="exactly one action or no_recovery_outcome"):
        PreconditionVerdict(
            failed_condition_id="profile.active",
            evidence=(_evidence(),),
            action=ActionReference(action_id="profile.create"),
            conditionality=ActionConditionality.IMMEDIATE,
            no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
        )


@pytest.mark.parametrize(
    "invalid_verdict",
    (
        pytest.param(
            lambda: PreconditionVerdict(
                failed_condition_id="profile.active",
                evidence=(_evidence(),),
                argument_bindings=(
                    ActionArgumentBinding(
                        argument_name="profile_key",
                        status=ActionArgumentStatus.MISSING,
                    ),
                ),
                missing_argument_names=("profile_key",),
                conditionality=ActionConditionality.NOT_APPLICABLE,
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
            ),
            id="no-recovery-with-arguments",
        ),
        pytest.param(
            lambda: PreconditionVerdict(
                failed_condition_id="profile.active",
                evidence=(_evidence(),),
                conditionality=ActionConditionality.IMMEDIATE,
                no_recovery_outcome=NoRecoveryOutcome.SAFETY,
            ),
            id="no-recovery-not-immediately-applicable",
        ),
        pytest.param(
            lambda: PreconditionVerdict(
                failed_condition_id="profile.active",
                evidence=(_evidence(),),
                action=ActionReference(action_id="operator.profile.create"),
                conditionality=ActionConditionality.NOT_APPLICABLE,
            ),
            id="action-not-applicable",
        ),
    ),
)
def test_verdict_rejects_invalid_action_and_no_recovery_conditionality(
    invalid_verdict: Callable[[], PreconditionVerdict],
) -> None:
    with pytest.raises(ValidationError):
        invalid_verdict()


def test_action_and_argument_ids_reject_noncanonical_or_raw_prose_forms() -> None:
    with pytest.raises(ValidationError, match="action_id"):
        ActionReference(action_id="Run aeat config profile create operator")

    with pytest.raises(ValidationError, match="argument_name"):
        ActionArgumentBinding(
            argument_name="profile key",
            status=ActionArgumentStatus.MISSING,
        )


@pytest.mark.parametrize(
    ("invalid_record", "match"),
    (
        pytest.param(
            lambda: PreconditionVerdict(
                failed_condition_id="profile active",
                evidence=(_evidence(),),
                conditionality=ActionConditionality.NOT_APPLICABLE,
                no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
            ),
            "failed_condition_id",
            id="failed-condition-id",
        ),
        pytest.param(
            lambda: ConditionEvidence(
                condition_id="profile.active",
                evidence_id="profile active selection",
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                values={"profile_key": "operator"},
            ),
            "evidence_id",
            id="evidence-id",
        ),
        pytest.param(
            lambda: ActionArgumentBinding(
                argument_name="profile_key",
                status=ActionArgumentStatus.RESOLVED,
                value="operator",
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key="profile key",
            ),
            "source_key",
            id="binding-source-key",
        ),
        pytest.param(
            lambda: ActionArgumentBinding(
                argument_name="profile_key",
                status=ActionArgumentStatus.RESOLVED,
                value="operator",
                source=ActionArgumentSource.CONDITION_EVIDENCE,
                source_key="profile_key",
                source_evidence_id="profile active selection",
            ),
            "source_evidence_id",
            id="binding-source-evidence-id",
        ),
    ),
)
def test_verdict_models_reject_noncanonical_identifier_fields(
    invalid_record: Callable[[], object],
    match: str,
) -> None:
    with pytest.raises(ValidationError, match=match):
        invalid_record()


def test_evidence_requires_stable_identity_and_typed_values() -> None:
    evidence = ConditionEvidence(
        condition_id="profile.active",
        evidence_id="profile.active.selection",
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        values={"amount": Decimal("12.50"), "count": 3},
    )
    assert evidence.model_dump(mode="json")["values"] == {"amount": "12.50", "count": 3}

    with pytest.raises(ValidationError, match="condition_id"):
        ConditionEvidence(
            condition_id="profile active",
            evidence_id="profile.active.selection",
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
            values={"count": 3},
        )


def test_verdict_rejects_evidence_for_a_different_condition() -> None:
    with pytest.raises(ValidationError, match="condition evidence must identify the failed condition"):
        PreconditionVerdict(
            failed_condition_id="profile.other",
            evidence=(_evidence(),),
            conditionality=ActionConditionality.NOT_APPLICABLE,
            no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
        )
