"""Contract tests for the frontend-neutral operation axes."""

from __future__ import annotations

from enum import StrEnum

import pytest

from ..operations import (
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
