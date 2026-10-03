"""Real validation proofs for operation capability declarations."""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from ....core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)
from .. import capabilities as capabilities_module
from ..capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _recorded_capabilities() -> dict[str, object]:
    return {
        "durability": OperationDurability.RECORDED,
        "cancellation": OperationCancellation.UNSUPPORTED,
        "deadline": OperationDeadline.ABSENT,
        "replay": OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        "baseline": OperationBaselinePolicy.REQUEST_BOUND,
        "request_storage": OperationRequestStoragePolicy.SECURE_REFERENCE,
        "sensitive_input": OperationSensitiveInputPolicy.SECURE_REFERENCE,
        "conflict_scope": OperationConflictScope.DEFINITION_SUBJECT,
        "owned_resources": frozenset(),
        "permitted_effects": frozenset({OperationEffect.NONE, OperationEffect.UPDATED}),
        "close_policy": OperationClosePolicy.DETACH_ALLOWED,
    }


def test_all_capability_dimensions_are_required() -> None:
    complete = _recorded_capabilities()

    for field_name in complete:
        incomplete = complete.copy()
        del incomplete[field_name]
        with pytest.raises(ValidationError) as caught:
            OperationCapabilities.model_validate(incomplete)
        assert field_name in str(caught.value)


def test_complete_declarations_are_strict_frozen_and_closed() -> None:
    capabilities = OperationCapabilities.model_validate(_recorded_capabilities())

    assert capabilities.replay is OperationReplayPolicy.IDEMPOTENT_SUBMIT
    with pytest.raises(ValidationError):
        OperationCapabilities.model_validate({**_recorded_capabilities(), "unexpected": True})
    with pytest.raises(ValidationError):
        capabilities.deadline = OperationDeadline.ENFORCED


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {"durability": OperationDurability.EPHEMERAL, "conflict_scope": OperationConflictScope.NONE},
            "ephemeral operations may permit only the none effect",
        ),
        (
            {
                "durability": OperationDurability.EPHEMERAL,
                "conflict_scope": OperationConflictScope.NONE,
                "permitted_effects": frozenset({OperationEffect.NONE}),
            },
            "ephemeral operations cannot promise durable replay",
        ),
        ({"conflict_scope": OperationConflictScope.NONE}, "require a conflict scope"),
        ({"durability": OperationDurability.RESUMABLE}, "must be declared together"),
        ({"replay": OperationReplayPolicy.RESUMABLE}, "must be declared together"),
        ({"permitted_effects": frozenset()}, "at least one permitted effect"),
        (
            {"cancellation": OperationCancellation.CONTAINED},
            "contained cancellation requires a supervisor-owned resource",
        ),
        (
            {"deadline": OperationDeadline.COOPERATIVE},
            "cooperative deadlines require a cancellable executor",
        ),
        ({"deadline": OperationDeadline.ENFORCED}, "enforced deadlines require contained cancellation"),
        ({"close_policy": OperationClosePolicy.REQUEST_CANCEL}, "requires a cancellable executor"),
    ],
)
def test_forbidden_capability_combinations_fail_closed(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        OperationCapabilities.model_validate({**_recorded_capabilities(), **changes})


def test_resumable_contained_operation_declares_exact_resources_and_policies() -> None:
    capabilities = OperationCapabilities(
        durability=OperationDurability.RESUMABLE,
        cancellation=OperationCancellation.CONTAINED,
        deadline=OperationDeadline.ENFORCED,
        replay=OperationReplayPolicy.RESUMABLE,
        baseline=OperationBaselinePolicy.EXACT_APPROVAL,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset({OperationOwnedResource.ASYNC_TASK, OperationOwnedResource.PROCESS}),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.REQUEST_CANCEL,
    )

    assert capabilities.owned_resources == frozenset(
        {OperationOwnedResource.ASYNC_TASK, OperationOwnedResource.PROCESS}
    )
    assert capabilities.baseline is OperationBaselinePolicy.EXACT_APPROVAL


_PROFILE_NAMES = tuple(name for name in capabilities_module.__all__ if name.endswith("_CAPABILITIES"))
_PROFILE_NAME_GRAMMAR = re.compile(
    r"RECORDED_(?P<cooperative>COOPERATIVE_)?(?P<replay>NON_IDEMPOTENT|IDEMPOTENT)_(?P<bound>REQUEST_BOUND_)?"
    r"(?P<custody>JOURNALED|SECURE_INPUT|SECURE_STORED)_(?P<effects>READ|UPDATE|PARTIAL_UPDATE|REQUIRED_UPDATE)_CAPABILITIES"
)


def _capabilities_named_by(profile_name: str) -> OperationCapabilities:
    """Rebuild the policy a profile name promises, independently of its definition."""
    parsed = _PROFILE_NAME_GRAMMAR.fullmatch(profile_name)
    if parsed is None:
        raise ValueError(f"profile name does not spell a capability policy: {profile_name}")
    cooperative = parsed["cooperative"] is not None
    custody = {
        "JOURNALED": (OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL, OperationSensitiveInputPolicy.NONE),
        "SECURE_INPUT": (
            OperationRequestStoragePolicy.SECURE_REFERENCE,
            OperationSensitiveInputPolicy.SECURE_REFERENCE,
        ),
        "SECURE_STORED": (OperationRequestStoragePolicy.SECURE_REFERENCE, OperationSensitiveInputPolicy.NONE),
    }[parsed["custody"]]
    effects = {
        "READ": frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
        "UPDATE": frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
        "PARTIAL_UPDATE": frozenset(
            {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.PARTIAL, OperationEffect.UNKNOWN}
        ),
        "REQUIRED_UPDATE": frozenset({OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
    }[parsed["effects"]]
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.COOPERATIVE if cooperative else OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.COOPERATIVE if cooperative else OperationDeadline.ABSENT,
        replay=(
            OperationReplayPolicy.IDEMPOTENT_SUBMIT if parsed["replay"] == "IDEMPOTENT" else OperationReplayPolicy.NONE
        ),
        baseline=OperationBaselinePolicy.REQUEST_BOUND if parsed["bound"] else OperationBaselinePolicy.NONE,
        request_storage=custody[0],
        sensitive_input=custody[1],
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=effects,
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def test_named_capability_profiles_are_published() -> None:
    assert "RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES" in _PROFILE_NAMES
    assert all(isinstance(getattr(capabilities_module, name), OperationCapabilities) for name in _PROFILE_NAMES)


@pytest.mark.parametrize("profile_name", _PROFILE_NAMES)
def test_every_named_profile_declares_exactly_the_policy_its_name_spells(profile_name: str) -> None:
    assert getattr(capabilities_module, profile_name) == _capabilities_named_by(profile_name)


def test_named_profiles_are_pairwise_distinct() -> None:
    profiles = [getattr(capabilities_module, name) for name in _PROFILE_NAMES]

    for index, profile in enumerate(profiles):
        assert profile not in profiles[index + 1 :], _PROFILE_NAMES[index]


def test_profile_name_check_rejects_a_mislabelled_or_unspelled_profile() -> None:
    journaled_read = capabilities_module.RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES

    assert journaled_read != _capabilities_named_by("RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES")
    assert journaled_read != _capabilities_named_by("RECORDED_NON_IDEMPOTENT_JOURNALED_READ_CAPABILITIES")
    assert journaled_read != _capabilities_named_by("RECORDED_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES")
    with pytest.raises(ValueError, match="does not spell"):
        _capabilities_named_by("RECORDED_DEFAULT_CAPABILITIES")
