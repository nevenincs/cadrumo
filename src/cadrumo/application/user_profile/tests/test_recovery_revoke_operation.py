"""The recovery revocation's projector and its one-shot frame, without any custody behind them."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.user_profile.recovery_custody import ProfileRecoveryEnrollmentOutcome, ProfileRecoveryError
from cadrumo.application.user_profile.recovery_revoke_operation import (
    RECOVERY_REVOKE_OPERATION_DEFINITION_ID,
    RecoveryRevokeExecutor,
    RecoveryRevokeRequest,
    RecoveryRevokeResult,
    project_recovery_revoke_result,
)
from cadrumo.core.config import override_settings
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _receipt(profile_id: UUID, *, effect: OperationEffect) -> OperationTerminalReceipt:
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64,
            definition_id=RECOVERY_REVOKE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
        ),
        revision=3,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        settled_at=datetime(2026, 9, 27, 12, tzinfo=UTC),
        result_ref="b" * 64,
    )


def test_the_projector_releases_the_outcome_only_against_its_own_receipt_and_effect() -> None:
    profile_id = uuid4()
    removed = RecoveryRevokeResult(profile_id=profile_id, changed=True)
    unchanged = RecoveryRevokeResult(profile_id=profile_id, changed=False)

    released = project_recovery_revoke_result(removed, _receipt(profile_id, effect=OperationEffect.UPDATED))
    idle = project_recovery_revoke_result(unchanged, _receipt(profile_id, effect=OperationEffect.NONE))

    assert (released.enrolled, released.changed) == (False, True)
    assert (idle.enrolled, idle.changed) == (False, False)
    for result, receipt in (
        (removed, _receipt(profile_id, effect=OperationEffect.NONE)),
        (unchanged, _receipt(profile_id, effect=OperationEffect.UPDATED)),
        (removed, _receipt(uuid4(), effect=OperationEffect.UPDATED)),
    ):
        with pytest.raises(ValueError, match="contradicts its terminal receipt"):
            project_recovery_revoke_result(result, receipt)


class _Frame:
    """The one-shot frame of one invocation, wiped when it is released."""

    def __init__(self, payload: bytes) -> None:
        self.buffer = bytearray(payload)

    @asynccontextmanager
    async def consume(self) -> AsyncGenerator[memoryview]:
        view = memoryview(self.buffer)
        try:
            yield view
        finally:
            view.release()
            self.buffer[:] = bytes(len(self.buffer))


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, phase: str) -> None:
        del phase

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


@pytest.mark.parametrize("payload", [b"", b"\xff\xfe not text"])
def test_a_frame_that_cannot_be_a_passphrase_is_refused_before_custody_is_asked(payload: bytes) -> None:
    profile_id = uuid4()
    subject = profile_operation_subject(str(profile_id))
    frame, events = _Frame(payload), _Events()
    asked: list[object] = []

    def revoke(**kwargs: object) -> ProfileRecoveryEnrollmentOutcome:
        asked.append(kwargs)
        return ProfileRecoveryEnrollmentOutcome(profile_id=str(profile_id), enrolled=False, changed=True)

    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="c" * 64, definition_id=RECOVERY_REVOKE_OPERATION_DEFINITION_ID, subject_ref=subject
            ),
            ephemeral_secret=frame,
            events=events,
        ),
    )
    request = OperationRequest[RecoveryRevokeRequest](
        definition_id=RECOVERY_REVOKE_OPERATION_DEFINITION_ID,
        subject_ref=subject,
        payload=RecoveryRevokeRequest(profile_id=profile_id),
    )

    with override_settings(cadrumo_active_profile=str(profile_id)), pytest.raises(ProfileRecoveryError) as refused:
        asyncio.run(RecoveryRevokeExecutor(revoke=revoke).execute(request, context))

    assert refused.value.translated_message == "application.user_profile.errors.passphrase_current_rejected"
    assert refused.value.__cause__ is None and refused.value.__context__ is None
    assert asked == []
    assert events.effects == []
    assert not any(frame.buffer)
