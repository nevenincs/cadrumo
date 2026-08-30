"""Real validation proofs for operation capability declarations."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)
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
