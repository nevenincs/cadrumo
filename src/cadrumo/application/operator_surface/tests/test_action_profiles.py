"""Contract tests for declarative manifest action profiles."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.operator_action_enums import NoRecoveryOutcome
from ...operator_actions import ActionReference
from ..models import ManifestActionProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_profile_preserves_one_condition_scenario_to_action_association() -> None:
    missing_profile = ManifestActionProfile(
        subject_leaf_key="modelo.work.verify",
        condition_id="profile.active",
        scenario_id="profile.no_active_profile",
        action=ActionReference(action_id="operator.profile.create"),
    )
    missing_revision = ManifestActionProfile(
        subject_leaf_key="modelo.work.verify",
        condition_id="workflow.calculation_revision.exists",
        scenario_id="workflow.calculation_revision.unknown",
        action=ActionReference(action_id="operator.modelo.work.calculate"),
    )

    associations = {
        profile.identity: profile.action.action_id
        for profile in (missing_profile, missing_revision)
        if profile.action is not None
    }

    assert associations == {
        (
            "modelo.work.verify",
            "profile.active",
            "profile.no_active_profile",
        ): "operator.profile.create",
        (
            "modelo.work.verify",
            "workflow.calculation_revision.exists",
            "workflow.calculation_revision.unknown",
        ): "operator.modelo.work.calculate",
    }


def test_profile_requires_an_action_or_explicit_terminal_outcome() -> None:
    terminal = ManifestActionProfile(
        subject_leaf_key="modelo.work.file",
        condition_id="filing.live_submission.disabled",
        scenario_id="filing.live_submission.requested",
        no_recovery_outcome=NoRecoveryOutcome.SAFETY,
    )

    assert terminal.action is None
    assert terminal.no_recovery_outcome is NoRecoveryOutcome.SAFETY

    with pytest.raises(ValidationError, match="exactly one action reference"):
        ManifestActionProfile(
            subject_leaf_key="modelo.work.file",
            condition_id="filing.live_submission.disabled",
            scenario_id="filing.live_submission.requested",
        )

    with pytest.raises(ValidationError, match="exactly one action reference"):
        ManifestActionProfile(
            subject_leaf_key="modelo.work.file",
            condition_id="filing.live_submission.disabled",
            scenario_id="filing.live_submission.requested",
            action=ActionReference(action_id="operator.overview.status"),
            no_recovery_outcome=NoRecoveryOutcome.SAFETY,
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_identity"),
    (
        ("subject_leaf_key", "aeat app modelo work verify"),
        ("condition_id", "Profile is missing"),
        ("scenario_id", "missing_profile"),
    ),
)
def test_profile_rejects_command_prose_and_non_namespaced_identities(
    field_name: str,
    invalid_identity: str,
) -> None:
    values = {
        "subject_leaf_key": "modelo.work.verify",
        "condition_id": "profile.active",
        "scenario_id": "profile.no_active_profile",
        "action": ActionReference(action_id="operator.profile.create"),
    }
    values[field_name] = invalid_identity

    with pytest.raises(ValidationError, match=field_name):
        ManifestActionProfile.model_validate(values)


@pytest.mark.parametrize(
    "undeclared_field",
    ("predicate", "message", "command", "argument_values"),
)
def test_profile_refuses_policy_presentation_and_runtime_value_fields(
    undeclared_field: str,
) -> None:
    values = {
        "subject_leaf_key": "modelo.work.verify",
        "condition_id": "profile.active",
        "scenario_id": "profile.no_active_profile",
        "action": {"action_id": "operator.profile.create"},
        undeclared_field: "not part of the declarative contract",
    }

    with pytest.raises(ValidationError, match="extra_forbidden"):
        ManifestActionProfile.model_validate(values)


def test_profile_is_strict_frozen_and_serializes_only_declarative_identities() -> None:
    profile = ManifestActionProfile(
        subject_leaf_key="modelo.work.verify",
        condition_id="profile.active",
        scenario_id="profile.no_active_profile",
        action=ActionReference(action_id="operator.profile.create"),
    )

    assert profile.model_dump(mode="json") == {
        "subject_leaf_key": "modelo.work.verify",
        "condition_id": "profile.active",
        "scenario_id": "profile.no_active_profile",
        "action": {"action_id": "operator.profile.create"},
        "no_recovery_outcome": None,
    }
    with pytest.raises(ValidationError, match="frozen_instance"):
        profile.__setattr__("condition_id", "profile.other")
