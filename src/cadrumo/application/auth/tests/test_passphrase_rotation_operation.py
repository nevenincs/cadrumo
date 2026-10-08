"""Registered passphrase rotation preserves one truthful commit boundary."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.application.auth.operation_definitions import (
    PROFILE_ROTATION_OPERATION_DEFINITION_ID,
    ProfilePassphraseRotationOperationExecutor,
    ProfilePassphraseRotationOperationRequest,
)
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.user_profile.passphrase_rotation import (
    ProfilePassphraseRotationError,
    ProfilePassphraseRotationOutcome,
)
from cadrumo.core.operations import OperationEffect

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RESULT_REF = "sha256:" + "a" * 64
_INPUT = {
    "current_passphrase": "current-private-sentinel",
    "new_passphrase": "replacement-private-sentinel",
    "new_passphrase_confirmation": "replacement-private-sentinel",
}


class _Secret:
    def __init__(self, payload: bytes) -> None:
        self.buffer = bytearray(payload)

    @asynccontextmanager
    async def consume(self) -> AsyncGenerator[memoryview]:
        view = memoryview(self.buffer)
        try:
            yield view
        finally:
            view.release()
            self.buffer[:] = b"\x00" * len(self.buffer)


class _Events:
    def __init__(self, trace: list[tuple[str, object]]) -> None:
        self.trace = trace
        self.effects: list[OperationEffect] = []

    async def phase(self, phase: str) -> None:
        self.trace.append(("phase", phase))

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)
        self.trace.append(("effect", effect))


class _Commit:
    def __init__(self, trace: list[tuple[str, object]]) -> None:
        self.trace = trace
        self.active = False
        self.owner: asyncio.Task[object] | None = None

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        assert not self.active
        self.active = True
        self.owner = asyncio.current_task()
        self.trace.append(("commit", "enter"))
        try:
            yield
        finally:
            self.active = False
            self.trace.append(("commit", "exit"))


class _Operands:
    def __init__(self, commit: _Commit, trace: list[tuple[str, object]], *, fail: bool = False) -> None:
        self.commit = commit
        self.trace = trace
        self.fail = fail
        self.written: BaseModel | None = None

    async def put(self, operand: BaseModel, *, written_at: object) -> str:
        assert self.commit.active
        assert asyncio.current_task() is self.commit.owner
        assert written_at is not None
        self.trace.append(("operand", "put"))
        if self.fail:
            raise OSError("encrypted operand write failed")
        self.written = operand
        return _RESULT_REF


def _scenario(
    *, payload: bytes | None = None, operand_failure: bool = False
) -> tuple[
    OperationRequest[ProfilePassphraseRotationOperationRequest],
    OperationExecutorContext,
    _Secret,
    _Events,
    _Commit,
    _Operands,
    list[tuple[str, object]],
]:
    profile_id = uuid4()
    request = OperationRequest[ProfilePassphraseRotationOperationRequest](
        definition_id=PROFILE_ROTATION_OPERATION_DEFINITION_ID,
        subject_ref=f"profile:{profile_id}",
        payload=ProfilePassphraseRotationOperationRequest(profile_id=profile_id),
    )
    trace: list[tuple[str, object]] = []
    secret = _Secret(payload if payload is not None else json.dumps(_INPUT).encode())
    events = _Events(trace)
    commit = _Commit(trace)
    operands = _Operands(commit, trace, fail=operand_failure)
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="b" * 64,
                definition_id=PROFILE_ROTATION_OPERATION_DEFINITION_ID,
                subject_ref=f"profile:{profile_id}",
            ),
            ephemeral_secret=secret,
            events=events,
            cancellation=commit,
            operands=operands,
            authority_operation=SimpleNamespace(profile_decode_context=lambda: object()),
        ),
    )
    return request, context, secret, events, commit, operands, trace


def _outcome(profile_id: UUID) -> ProfilePassphraseRotationOutcome:
    return ProfilePassphraseRotationOutcome(
        profile_id=str(profile_id),
        password_generation=2,
        dek_epoch_preserved=True,
        recovery_enrollment_retained=False,
    )


def test_rotation_persists_typed_result_and_finalizes_in_same_commit_task() -> None:
    request, context, secret, events, commit, operands, trace = _scenario()
    event_loop_thread = threading.get_ident()

    def rotate(**kwargs: object) -> ProfilePassphraseRotationOutcome:
        assert threading.get_ident() != event_loop_thread
        assert kwargs["current_passphrase"] == _INPUT["current_passphrase"]
        assert kwargs["new_passphrase"] == _INPUT["new_passphrase"]
        return _outcome(request.payload.profile_id)

    async def finalize(identity: OperationIdentity, result: ProfilePassphraseRotationOutcome) -> None:
        assert identity == context.identity
        assert commit.active and asyncio.current_task() is commit.owner
        assert operands.written is result
        trace.append(("finalizer", result.password_generation))

    async def run() -> str:
        return await ProfilePassphraseRotationOperationExecutor(
            rotate_passphrase=rotate,
            finalize_rotation=finalize,
        ).execute(request, context)

    assert asyncio.run(run()) == _RESULT_REF
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert trace.index(("operand", "put")) < trace.index(("finalizer", 2)) < trace.index(("commit", "exit"))
    assert operands.written == _outcome(request.payload.profile_id)
    assert not commit.active
    assert not any(secret.buffer)


@pytest.mark.parametrize(
    "payload",
    [
        b"\xffprivate-sentinel",
        b'{"current_passphrase":"private-sentinel","current_passphrase":"other"}',
        json.dumps({**_INPUT, "unexpected": "private-sentinel"}).encode(),
        json.dumps({**_INPUT, "current_passphrase": 7}).encode(),
        b'{"current_passphrase":NaN}',
        b"[private-sentinel",
    ],
)
def test_malformed_protected_frame_refuses_without_input_or_write(payload: bytes) -> None:
    request, context, secret, events, commit, operands, _trace = _scenario(payload=payload)

    def unexpected_rotate(**kwargs: object) -> ProfilePassphraseRotationOutcome:
        del kwargs
        raise AssertionError("malformed input reached the writer")

    async def run() -> None:
        await ProfilePassphraseRotationOperationExecutor(rotate_passphrase=unexpected_rotate).execute(request, context)

    with pytest.raises(ProfilePassphraseRotationError) as caught:
        asyncio.run(run())
    assert "private-sentinel" not in str(caught.value)
    assert "current_passphrase" not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert events.effects == []
    assert operands.written is None
    assert not commit.active
    assert not any(secret.buffer)


@pytest.mark.parametrize(
    ("failure", "expected_effects"),
    [
        (ProfilePassphraseRotationError("Current password refused"), [OperationEffect.UNKNOWN, OperationEffect.NONE]),
        (RuntimeError("writer failed after uncertain publication"), [OperationEffect.UNKNOWN]),
    ],
)
def test_writer_refusal_and_unknown_fault_keep_distinct_effects(
    failure: Exception, expected_effects: list[OperationEffect]
) -> None:
    request, context, secret, events, commit, operands, _trace = _scenario()

    def rotate(**kwargs: object) -> ProfilePassphraseRotationOutcome:
        del kwargs
        raise failure

    async def run() -> None:
        await ProfilePassphraseRotationOperationExecutor(rotate_passphrase=rotate).execute(request, context)

    with pytest.raises(type(failure)):
        asyncio.run(run())
    assert events.effects == expected_effects
    assert operands.written is None
    assert not commit.active
    assert not any(secret.buffer)


def test_committed_rotation_remains_updated_when_operand_write_fails() -> None:
    request, context, secret, events, commit, operands, _trace = _scenario(operand_failure=True)

    def rotate(**kwargs: object) -> ProfilePassphraseRotationOutcome:
        del kwargs
        return _outcome(request.payload.profile_id)

    async def run() -> None:
        await ProfilePassphraseRotationOperationExecutor(rotate_passphrase=rotate).execute(request, context)

    with pytest.raises(OSError, match="encrypted operand write failed"):
        asyncio.run(run())
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert operands.written is None
    assert not commit.active
    assert not any(secret.buffer)


def test_wrong_profile_outcome_cannot_be_persisted_as_a_success() -> None:
    request, context, secret, events, commit, operands, _trace = _scenario()

    def rotate(**kwargs: object) -> ProfilePassphraseRotationOutcome:
        del kwargs
        return _outcome(uuid4())

    async def run() -> None:
        await ProfilePassphraseRotationOperationExecutor(rotate_passphrase=rotate).execute(request, context)

    with pytest.raises(ValueError, match="invalid profile outcome"):
        asyncio.run(run())
    assert events.effects == [OperationEffect.UNKNOWN]
    assert operands.written is None
    assert not commit.active
    assert not any(secret.buffer)


def test_constructed_invalid_outcome_stays_unknown_and_unstored() -> None:
    request, context, secret, events, commit, operands, _trace = _scenario()

    def rotate(**kwargs: object) -> ProfilePassphraseRotationOutcome:
        del kwargs
        return ProfilePassphraseRotationOutcome.model_construct(
            profile_id=str(request.payload.profile_id),
            password_generation=True,
            dek_epoch_preserved="yes",
            recovery_enrollment_retained=False,
        )

    async def run() -> None:
        await ProfilePassphraseRotationOperationExecutor(rotate_passphrase=rotate).execute(request, context)

    with pytest.raises(ValueError, match="invalid profile outcome") as caught:
        asyncio.run(run())
    assert caught.value.__context__ is None
    assert events.effects == [OperationEffect.UNKNOWN]
    assert operands.written is None
    assert not commit.active
    assert not any(secret.buffer)


def test_cancellation_waits_for_blocking_write_result_and_finalizer() -> None:
    request, context, secret, events, commit, operands, trace = _scenario()
    started = threading.Event()
    release = threading.Event()

    def rotate(**kwargs: object) -> ProfilePassphraseRotationOutcome:
        del kwargs
        started.set()
        assert release.wait(3)
        return _outcome(request.payload.profile_id)

    async def finalize(_identity: OperationIdentity, _result: ProfilePassphraseRotationOutcome) -> None:
        assert commit.active and asyncio.current_task() is commit.owner
        trace.append(("finalizer", "done"))

    async def run() -> None:
        task = asyncio.create_task(
            ProfilePassphraseRotationOperationExecutor(
                rotate_passphrase=rotate,
                finalize_rotation=finalize,
            ).execute(request, context)
        )
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert commit.active
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    try:
        asyncio.run(run())
    finally:
        release.set()
    assert events.effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert operands.written == _outcome(request.payload.profile_id)
    assert trace.index(("finalizer", "done")) < trace.index(("commit", "exit"))
    assert not commit.active
    assert not any(secret.buffer)
