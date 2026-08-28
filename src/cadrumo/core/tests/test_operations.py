"""Contract tests for the frontend-neutral operation axes."""

from __future__ import annotations

from enum import StrEnum

import pytest

from ..operations import (
    LIFECYCLES_BEFORE_EXECUTOR_ENTRY,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationEventKind,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_EXPECTED_MEMBERS = {
    OperationLifecycle: (
        "created",
        "queued",
        "running",
        "waiting_for_interaction",
        "waiting_for_external",
        "cancellation_requested",
        "settling",
        "terminal",
    ),
    OperationTerminalCondition: (
        "succeeded",
        "refused",
        "failed",
        "cancelled",
        "timed_out",
        "interrupted",
    ),
    OperationEffect: ("none", "updated", "partial", "unknown"),
    OperationDurability: ("ephemeral", "recorded", "resumable"),
    OperationCancellation: ("unsupported", "cooperative", "contained"),
    OperationDeadline: ("absent", "cooperative", "enforced"),
    OperationClosePolicy: ("detach_allowed", "request_cancel", "block_until_settled"),
    OperationEventKind: (
        "phase",
        "progress",
        "log",
        "effect",
        "notice",
        "reconciliation",
        "diagnostic",
        "interaction",
        "terminal",
    ),
    OperationInteractionKind: ("input", "choice", "review", "apply", "reject"),
}


@pytest.mark.parametrize(("axis", "expected"), _EXPECTED_MEMBERS.items())
def test_operation_axis_is_closed_and_serialisation_transparent(axis: type[StrEnum], expected: tuple[str, ...]) -> None:
    """Every accepted architecture token hydrates exactly and serialises unchanged."""
    assert tuple(member.value for member in axis) == expected
    assert tuple(axis(token) for token in expected) == tuple(axis)
    assert all(isinstance(member, str) for member in axis)


@pytest.mark.parametrize("axis", _EXPECTED_MEMBERS)
def test_operation_axis_refuses_an_unknown_token(axis: type[StrEnum]) -> None:
    """Unknown generic state meanings cannot enter through a free-form token."""
    with pytest.raises(ValueError, match="is not a valid"):
        axis("frontend_owned_state")
def test_the_pre_entry_lifecycles_are_exactly_created_and_queued() -> None:
    """Pin the membership every consumer of this set relies on.

    Three call sites -- the persisted-snapshot consistency check, the
    cancellation precondition and the settlement stop-proof -- now read this
    one set. A lifecycle stage added before execution begins must be enrolled
    here or all three silently stop covering it, and each would fail
    differently: a snapshot inconsistency would go unnoticed, a cancellation
    would be accepted too early, and a settlement would demand stop proof from
    an executor that never ran.
    """
    assert {OperationLifecycle.CREATED, OperationLifecycle.QUEUED} == LIFECYCLES_BEFORE_EXECUTOR_ENTRY


def test_the_pre_entry_set_excludes_every_stage_an_executor_can_have_entered() -> None:
    """The complement is the load-bearing half.

    ``RUNNING`` onwards must stay OUT: were any of them enrolled, the
    cancellation precondition would refuse to cancel a genuinely running
    operation, which is the failure the operator would feel first.
    """
    for stage in (
        OperationLifecycle.RUNNING,
        OperationLifecycle.WAITING_FOR_INTERACTION,
        OperationLifecycle.WAITING_FOR_EXTERNAL,
        OperationLifecycle.CANCELLATION_REQUESTED,
        OperationLifecycle.SETTLING,
        OperationLifecycle.TERMINAL,
    ):
        assert stage not in LIFECYCLES_BEFORE_EXECUTOR_ENTRY


def test_every_lifecycle_is_ruled_on_by_the_pre_entry_set() -> None:
    """No stage may be left unclassified when the enum grows.

    Membership is stated, not derived, so a new stage would default to "an
    executor could already have entered". This makes that default impossible to
    take silently.
    """
    classified = LIFECYCLES_BEFORE_EXECUTOR_ENTRY | {
        stage for stage in OperationLifecycle if stage not in LIFECYCLES_BEFORE_EXECUTOR_ENTRY
    }
    assert classified == set(OperationLifecycle)
    assert {stage.name for stage in OperationLifecycle} == {
        "CREATED",
        "QUEUED",
        "RUNNING",
        "WAITING_FOR_INTERACTION",
        "WAITING_FOR_EXTERNAL",
        "CANCELLATION_REQUESTED",
        "SETTLING",
        "TERMINAL",
    }
