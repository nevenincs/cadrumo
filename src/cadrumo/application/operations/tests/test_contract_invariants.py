"""Cross-contract invariants exercised through canonical defining modules."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict

import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from ....core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ..capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..interactions import OperationApplyResponse
from ..models import (
    OperationIdentity,
    OperationRequest,
    OperationSnapshot,
    OperationTerminalReceipt,
)
from ..persistence.events import OperationDiagnosticEvent

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 13, 20, 0, tzinfo=UTC)
_IDENTITY = OperationIdentity(operation_id="a" * 64, definition_id="profile.sync", subject_ref="profile:active")


class _ApplyResponseValues(TypedDict):
    """Typed common fields for the apply-response constructor boundary."""

    interaction_id: str
    operation_id: str
    revision: int
    response_token: str
    continuation_digest: str
    reviewed_proposal_digest: str
    actor_ref: str
    responded_at: datetime
    baseline_digest: str
    proposed_effect_digest: str


class _Payload(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")
    value: int


@pytest.mark.parametrize(
    "lifecycle", tuple(member for member in OperationLifecycle if member is not OperationLifecycle.TERMINAL)
)
@pytest.mark.parametrize("effect", tuple(OperationEffect))
def test_nonterminal_lifecycle_and_effect_axes_remain_independently_representable(
    lifecycle: OperationLifecycle, effect: OperationEffect
) -> None:
    request = OperationRequest[_Payload](
        definition_id=_IDENTITY.definition_id,
        subject_ref=_IDENTITY.subject_ref,
        payload=_Payload(value=1),
    )
    snapshot = OperationSnapshot[_Payload](
        identity=_IDENTITY,
        request=request,
        revision=2,
        lifecycle=lifecycle,
        effect=effect,
        updated_at=_NOW,
    )
    assert snapshot.lifecycle is lifecycle
    assert snapshot.effect is effect


def _capabilities() -> dict[str, object]:
    return {
        "durability": OperationDurability.RECORDED,
        "cancellation": OperationCancellation.COOPERATIVE,
        "deadline": OperationDeadline.COOPERATIVE,
        "replay": OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        "baseline": OperationBaselinePolicy.NONE,
        "request_storage": OperationRequestStoragePolicy.SECURE_REFERENCE,
        "sensitive_input": OperationSensitiveInputPolicy.NONE,
        "conflict_scope": OperationConflictScope.DEFINITION_SUBJECT,
        "owned_resources": frozenset(),
        "permitted_effects": frozenset({OperationEffect.NONE}),
        "close_policy": OperationClosePolicy.REQUEST_CANCEL,
    }


def _ephemeral_capabilities() -> dict[str, object]:
    return {
        **_capabilities(),
        "durability": OperationDurability.EPHEMERAL,
        "cancellation": OperationCancellation.UNSUPPORTED,
        "deadline": OperationDeadline.ABSENT,
        "replay": OperationReplayPolicy.NONE,
        "conflict_scope": OperationConflictScope.NONE,
        "close_policy": OperationClosePolicy.DETACH_ALLOWED,
    }


@pytest.mark.parametrize(
    ("base", "mutation"),
    (
        (_ephemeral_capabilities(), {"replay": OperationReplayPolicy.IDEMPOTENT_SUBMIT}),
        (_ephemeral_capabilities(), {"conflict_scope": OperationConflictScope.DEFINITION_SUBJECT}),
        (_ephemeral_capabilities(), {"permitted_effects": frozenset({OperationEffect.UPDATED})}),
        (_capabilities(), {"permitted_effects": frozenset()}),
        (_capabilities(), {"durability": OperationDurability.RESUMABLE}),
        (_capabilities(), {"replay": OperationReplayPolicy.RESUMABLE}),
        (_capabilities(), {"conflict_scope": OperationConflictScope.NONE}),
        (
            {
                **_capabilities(),
                "deadline": OperationDeadline.ABSENT,
                "close_policy": OperationClosePolicy.DETACH_ALLOWED,
            },
            {"cancellation": OperationCancellation.CONTAINED},
        ),
        (
            {
                **_capabilities(),
                "cancellation": OperationCancellation.UNSUPPORTED,
                "deadline": OperationDeadline.ABSENT,
                "close_policy": OperationClosePolicy.DETACH_ALLOWED,
            },
            {"deadline": OperationDeadline.COOPERATIVE},
        ),
        (
            {
                **_capabilities(),
                "cancellation": OperationCancellation.UNSUPPORTED,
                "deadline": OperationDeadline.ABSENT,
                "close_policy": OperationClosePolicy.DETACH_ALLOWED,
            },
            {"close_policy": OperationClosePolicy.REQUEST_CANCEL},
        ),
        (
            {
                **_capabilities(),
                "cancellation": OperationCancellation.COOPERATIVE,
                "deadline": OperationDeadline.ABSENT,
                "close_policy": OperationClosePolicy.REQUEST_CANCEL,
            },
            {"deadline": OperationDeadline.ENFORCED},
        ),
    ),
)
def test_each_forbidden_capability_branch_refuses_one_field_mutation(
    base: dict[str, object], mutation: dict[str, object]
) -> None:
    TypeAdapter(OperationCapabilities).validate_python(base)
    with pytest.raises(ValidationError):
        TypeAdapter(OperationCapabilities).validate_python({**base, **mutation})


@pytest.mark.parametrize("effect", tuple(OperationEffect))
@pytest.mark.parametrize(
    ("condition", "references"),
    (
        (OperationTerminalCondition.SUCCEEDED, {"result_ref": "result:one"}),
        (OperationTerminalCondition.REFUSED, {"refusal_ref": "refusal:one"}),
        (OperationTerminalCondition.FAILED, {}),
        (OperationTerminalCondition.CANCELLED, {}),
        (OperationTerminalCondition.TIMED_OUT, {}),
        (OperationTerminalCondition.INTERRUPTED, {}),
    ),
)
def test_every_terminal_condition_is_independent_of_effect(
    condition: OperationTerminalCondition, references: dict[str, str], effect: OperationEffect
) -> None:
    request = OperationRequest[_Payload](
        definition_id=_IDENTITY.definition_id, subject_ref=_IDENTITY.subject_ref, payload=_Payload(value=1)
    )
    receipt = OperationTerminalReceipt(
        identity=_IDENTITY,
        revision=2,
        condition=condition,
        effect=effect,
        settled_at=_NOW,
        **references,
    )
    snapshot = OperationSnapshot[_Payload](
        identity=_IDENTITY,
        request=request,
        revision=2,
        lifecycle=OperationLifecycle.TERMINAL,
        terminal_condition=condition,
        effect=effect,
        updated_at=_NOW,
        terminal_receipt=receipt,
    )
    assert snapshot.effect is effect


def test_snapshot_refuses_invalid_terminal_axis_correlations() -> None:
    request = OperationRequest[_Payload](
        definition_id=_IDENTITY.definition_id, subject_ref=_IDENTITY.subject_ref, payload=_Payload(value=1)
    )
    receipt = OperationTerminalReceipt(
        identity=_IDENTITY,
        revision=2,
        condition=OperationTerminalCondition.FAILED,
        effect=OperationEffect.NONE,
        settled_at=_NOW,
    )
    with pytest.raises(ValidationError):
        OperationSnapshot[_Payload](
            identity=_IDENTITY,
            request=request,
            revision=2,
            lifecycle=OperationLifecycle.RUNNING,
            terminal_condition=OperationTerminalCondition.FAILED,
            updated_at=_NOW,
            terminal_receipt=receipt,
        )
    with pytest.raises(ValidationError, match="effect does not match"):
        OperationSnapshot[_Payload](
            identity=_IDENTITY,
            request=request,
            revision=2,
            lifecycle=OperationLifecycle.TERMINAL,
            terminal_condition=OperationTerminalCondition.FAILED,
            effect=OperationEffect.UPDATED,
            updated_at=_NOW,
            terminal_receipt=receipt,
        )


def test_public_apply_response_preserves_the_exact_binding_tuple() -> None:
    values: _ApplyResponseValues = {
        "interaction_id": "b" * 64,
        "operation_id": _IDENTITY.operation_id,
        "revision": 4,
        "response_token": "c" * 64,
        "continuation_digest": "d" * 64,
        "reviewed_proposal_digest": "e" * 64,
        "actor_ref": "operator:local",
        "responded_at": _NOW,
        "baseline_digest": "f" * 64,
        "proposed_effect_digest": "1" * 64,
    }
    accepted = OperationApplyResponse(**values)
    assert accepted.model_dump() == {**values, "intent": "apply"}


@pytest.mark.parametrize(
    "unsafe",
    ("12345678Z", "Bearer secret-token", "https://aeat.example/path?token=secret", "TimeoutError: secret"),
)
def test_public_event_boundary_refuses_sensitive_diagnostic_material(unsafe: str) -> None:
    with pytest.raises(ValidationError):
        OperationDiagnosticEvent(
            identity=_IDENTITY,
            revision=2,
            sequence=1,
            timestamp=_NOW,
            code="profile.sync.diagnostic",
            diagnostic_ref=unsafe,
        )
