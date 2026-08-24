"""Real filesystem and restart proofs for credential-free secret-wait operations."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from .....application.operations import (
    CredentialFreeOperationRequest,
    EphemeralSecretSubmission,
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationDefinition,
    OperationEffect,
    OperationEphemeralSecretDeclaration,
    OperationExecutorContext,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationLifecycle,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationReplayPolicy,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationSecretRequirement,
    OperationSensitiveInputPolicy,
    OperationSupervisor,
    OperationTerminalCondition,
    OperationTerminalReceipt,
)
from .....core import (
    STRICT_FROZEN_CONFIG,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
)
from ...storage import RepositoryError
from .. import OperationJournalRepository, OperationLeaseFilesystemRepository

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2026, 8, 24, 12, tzinfo=UTC)
_SECRET = b"s114-runtime-canary-4b9f1a"
_INPUT_KIND = "profile.unlock_input"
_PROFILE_ID = UUID("8bca3f7c-ec82-4f74-862d-c4ae3a548579")


class SafeUnlockRequest(CredentialFreeOperationRequest):
    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    purpose_code: str


class PasswordBearingRequest(CredentialFreeOperationRequest):
    model_config = STRICT_FROZEN_CONFIG

    password: str


class BinaryBearingRequest(CredentialFreeOperationRequest):
    model_config = STRICT_FROZEN_CONFIG

    payload: bytes


class UnmarkedRequest(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID


class ConsumingExecutor:
    def __init__(self) -> None:
        self.calls = 0
        self.second_consume_refused = False
        self.backing_zeroized = False

    async def execute(
        self,
        request: OperationRequest[SafeUnlockRequest],
        context: OperationExecutorContext,
    ) -> str:
        assert request.payload.profile_id == _PROFILE_ID
        self.calls += 1
        backing: bytearray | None = None
        async with context.ephemeral_secret.consume() as secret:
            assert secret.tobytes() == _SECRET
            backing = secret.obj
        assert backing is not None
        self.backing_zeroized = all(value == 0 for value in backing)
        try:
            async with context.ephemeral_secret.consume():
                raise AssertionError("a consumed secret was yielded twice")
        except ValueError:
            self.second_consume_refused = True
        return "secret-operation:complete"


class BlockingExecutor:
    def __init__(self, entered: asyncio.Event, release: asyncio.Event) -> None:
        self.entered = entered
        self.release = release
        self.calls = 0
        self.active_buffer_zeroized = False

    async def execute(
        self,
        request: OperationRequest[SafeUnlockRequest],
        context: OperationExecutorContext,
    ) -> str:
        del request
        self.calls += 1
        async with context.ephemeral_secret.consume() as secret:
            assert secret.tobytes() == _SECRET
            self.entered.set()
            await self.release.wait()
            self.active_buffer_zeroized = not any(secret)
        return "secret-operation:complete"


def _capabilities() -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.REQUEST_BOUND,
        request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
        sensitive_input=OperationSensitiveInputPolicy.NONE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def _definition(executor: ConsumingExecutor | BlockingExecutor) -> OperationDefinition:
    return OperationDefinition(
        definition_id="profile.unlock.ephemeral",
        request_type=SafeUnlockRequest,
        result_type=None,
        executor_factory=OperationExecutorFactory(
            request_type=SafeUnlockRequest,
            executor_type=type(executor),
            build=lambda: executor,
        ),
        phase_codes=("profile.unlock",),
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        ephemeral_secret=OperationEphemeralSecretDeclaration(
            secret_kind=_INPUT_KIND,
            lifetime=timedelta(seconds=30),
        ),
    )


def _request() -> OperationRequest[SafeUnlockRequest]:
    return OperationRequest[SafeUnlockRequest](
        definition_id="profile.unlock.ephemeral",
        subject_ref=f"profile:{_PROFILE_ID}",
        payload=SafeUnlockRequest(profile_id=_PROFILE_ID, purpose_code="unlock"),
    )


def _supervisor(
    *,
    root: Path,
    registry: OperationRegistry,
    owner: str,
    token: str,
    clock: list[datetime],
) -> OperationSupervisor:
    journal = OperationJournalRepository(storage_root=root)
    return OperationSupervisor(
        registry=registry,
        journal=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=None,
        owner_id=owner,
        lease_token_factory=lambda: token,
        clock=lambda: clock[0],
        lease_duration=timedelta(minutes=1),
    )


def _mutated_requirements(requirement: OperationSecretRequirement) -> tuple[OperationSecretRequirement, ...]:
    return (
        requirement.model_copy(
            update={"identity": requirement.identity.model_copy(update={"definition_id": "profile.unlock.other"})}
        ),
        requirement.model_copy(
            update={"identity": requirement.identity.model_copy(update={"subject_ref": "profile:other"})}
        ),
        requirement.model_copy(update={"interaction_id": "f" * 64}),
        requirement.model_copy(update={"revision": requirement.revision + 1}),
    )


def _assert_no_secret_or_derivative(root: Path) -> None:
    derivative = hashlib.sha256(_SECRET).hexdigest().encode("ascii")
    for path in root.rglob("*"):
        if path.is_file():
            raw = path.read_bytes()
            assert _SECRET not in raw, path
            assert derivative not in raw, path


def test_registry_refuses_unmarked_credential_secret_binary_and_invalid_secret_capability() -> None:
    executor = ConsumingExecutor()
    accepted = _definition(executor)
    assert OperationRegistry(definitions=(accepted,)).lookup(accepted.definition_id) is accepted

    for request_type, message in (
        (UnmarkedRequest, "explicitly inherit"),
        (PasswordBearingRequest, "forbidden security meaning"),
        (BinaryBearingRequest, "secret-capable format"),
    ):
        payload = accepted.model_dump()
        payload["request_type"] = request_type
        payload["executor_factory"] = OperationExecutorFactory(
            request_type=request_type,
            executor_type=ConsumingExecutor,
            build=ConsumingExecutor,
        )
        with pytest.raises(ValidationError, match=message):
            OperationDefinition.model_validate(payload)

    for mutation, message in (
        ({"request_storage": OperationRequestStoragePolicy.SECURE_REFERENCE}, "credential-free"),
        ({"durability": OperationDurability.RESUMABLE, "replay": OperationReplayPolicy.RESUMABLE}, "recorded"),
    ):
        payload = accepted.model_dump()
        payload["capabilities"] = {**payload["capabilities"], **mutation}
        with pytest.raises(ValidationError, match=message):
            OperationDefinition.model_validate(payload)


def test_exact_one_shot_submission_executes_once_and_never_reaches_filesystem(tmp_path: Path) -> None:
    executor = ConsumingExecutor()
    registry = OperationRegistry(definitions=(_definition(executor),))
    clock = [_NOW]
    supervisor = _supervisor(root=tmp_path, registry=registry, owner="1" * 64, token="2" * 64, clock=clock)
    assert isinstance(supervisor, EphemeralSecretSubmission)
    operation_id = asyncio.run(supervisor.submit(_request(), operation_id="3" * 64))
    created = asyncio.run(supervisor.inspect(operation_id))
    requirement = created.secret_requirement
    assert requirement is not None
    journal_path = tmp_path / "operation-journals" / f"{operation_id}.json"
    initial_document = json.loads(journal_path.read_text(encoding="utf-8"))
    assert initial_document["snapshot"]["credential_free_request_json"] == _request().payload.model_dump_json()
    assert initial_document["snapshot"]["request_storage"] == "credential_free_journal"

    for mismatch in _mutated_requirements(requirement):
        submitted = bytearray(_SECRET)
        with pytest.raises(ValueError, match="does not match"):
            asyncio.run(supervisor.submit_ephemeral_secret(mismatch, submitted))
        assert submitted == bytearray(len(_SECRET))

    wrong_operation = requirement.model_copy(
        update={"identity": requirement.identity.model_copy(update={"operation_id": "4" * 64})}
    )
    wrong_operation_buffer = bytearray(_SECRET)
    with pytest.raises(RepositoryError):
        asyncio.run(supervisor.submit_ephemeral_secret(wrong_operation, wrong_operation_buffer))
    assert wrong_operation_buffer == bytearray(len(_SECRET))

    submitted = bytearray(_SECRET)
    asyncio.run(supervisor.submit_ephemeral_secret(requirement, submitted))
    assert submitted == bytearray(len(_SECRET))
    duplicate = bytearray(_SECRET)
    with pytest.raises(ValueError, match="already has a submission"):
        asyncio.run(supervisor.submit_ephemeral_secret(requirement, duplicate))
    assert duplicate == bytearray(len(_SECRET))

    terminal = asyncio.run(supervisor.start(operation_id))
    assert terminal.lifecycle is OperationLifecycle.TERMINAL
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.executor_entered_at == _NOW
    assert executor.calls == 1
    assert executor.second_consume_refused
    assert executor.backing_zeroized
    after_terminal = bytearray(_SECRET)
    with pytest.raises(ValueError, match="no longer awaiting"):
        asyncio.run(supervisor.submit_ephemeral_secret(requirement, after_terminal))
    assert after_terminal == bytearray(len(_SECRET))
    _assert_no_secret_or_derivative(tmp_path)


def test_expiry_cancellation_and_shutdown_clear_pre_entry_secret_waits(tmp_path: Path) -> None:
    executor = ConsumingExecutor()
    registry = OperationRegistry(definitions=(_definition(executor),))
    clock = [_NOW]
    supervisor = _supervisor(root=tmp_path, registry=registry, owner="4" * 64, token="5" * 64, clock=clock)

    expiry_id = asyncio.run(supervisor.submit(_request(), operation_id="6" * 64))
    expiry_requirement = asyncio.run(supervisor.inspect(expiry_id)).secret_requirement
    assert expiry_requirement is not None
    expiry_buffer = bytearray(_SECRET)
    asyncio.run(supervisor.submit_ephemeral_secret(expiry_requirement, expiry_buffer))
    clock[0] = expiry_requirement.expires_at
    expired = asyncio.run(supervisor.start(expiry_id))
    assert expired.terminal_condition is OperationTerminalCondition.INTERRUPTED
    assert expired.effect is OperationEffect.NONE
    assert expired.executor_entered_at is None

    clock[0] = _NOW + timedelta(minutes=10)
    cancel_id = asyncio.run(supervisor.submit(_request(), operation_id="7" * 64))
    cancel_requirement = asyncio.run(supervisor.inspect(cancel_id)).secret_requirement
    assert cancel_requirement is not None
    cancel_buffer = bytearray(_SECRET)
    asyncio.run(supervisor.submit_ephemeral_secret(cancel_requirement, cancel_buffer))
    cancelled = asyncio.run(supervisor.request_cancel(cancel_id))
    assert cancelled.terminal_condition is OperationTerminalCondition.CANCELLED
    assert cancelled.effect is OperationEffect.NONE
    assert executor.calls == 0

    shutdown_id = asyncio.run(supervisor.submit(_request(), operation_id="8" * 64))
    shutdown_requirement = asyncio.run(supervisor.inspect(shutdown_id)).secret_requirement
    assert shutdown_requirement is not None
    shutdown_buffer = bytearray(_SECRET)
    asyncio.run(supervisor.submit_ephemeral_secret(shutdown_requirement, shutdown_buffer))
    asyncio.run(supervisor.shutdown())
    post_shutdown_buffer = bytearray(_SECRET)
    with pytest.raises(ValueError, match="submission channel is closed"):
        asyncio.run(supervisor.submit_ephemeral_secret(shutdown_requirement, post_shutdown_buffer))
    assert post_shutdown_buffer == bytearray(len(_SECRET))
    with pytest.raises(ValueError, match="no exact live submission"):
        asyncio.run(supervisor.start(shutdown_id))
    _assert_no_secret_or_derivative(tmp_path)


def test_submission_and_cancellation_share_one_operation_boundary(tmp_path: Path) -> None:
    async def scenario() -> None:
        executor = ConsumingExecutor()
        registry = OperationRegistry(definitions=(_definition(executor),))
        clock = [_NOW]
        supervisor = _supervisor(root=tmp_path, registry=registry, owner="1" * 64, token="2" * 64, clock=clock)
        operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
        requirement = (await supervisor.inspect(operation_id)).secret_requirement
        assert requirement is not None
        submitted = bytearray(_SECRET)

        async with supervisor._lease_lock(operation_id):
            submission = asyncio.create_task(supervisor.submit_ephemeral_secret(requirement, submitted))
            await asyncio.sleep(0)
            assert not submission.done()
            cancellation = asyncio.create_task(supervisor.request_cancel(operation_id))
            await asyncio.sleep(0)
            assert not cancellation.done()

        await submission
        terminal = await cancellation
        assert terminal.terminal_condition is OperationTerminalCondition.CANCELLED
        assert submitted == bytearray(len(_SECRET))
        retry = bytearray(_SECRET)
        with pytest.raises(ValueError, match="no longer awaiting"):
            await supervisor.submit_ephemeral_secret(requirement, retry)
        assert retry == bytearray(len(_SECRET))
        assert not supervisor._ephemeral_secrets.has_exact(requirement, observed_at=clock[0])
        assert executor.calls == 0
        _assert_no_secret_or_derivative(tmp_path)

    asyncio.run(scenario())


def test_submission_and_terminal_settlement_share_one_operation_boundary(tmp_path: Path) -> None:
    async def scenario() -> None:
        executor = ConsumingExecutor()
        registry = OperationRegistry(definitions=(_definition(executor),))
        clock = [_NOW]
        supervisor = _supervisor(root=tmp_path, registry=registry, owner="7" * 64, token="8" * 64, clock=clock)
        operation_id = await supervisor.submit(_request(), operation_id="9" * 64)
        snapshot = await supervisor.inspect(operation_id)
        requirement = snapshot.secret_requirement
        assert requirement is not None
        submitted = bytearray(_SECRET)
        receipt = OperationTerminalReceipt(
            identity=snapshot.identity,
            revision=snapshot.revision + 1,
            condition=OperationTerminalCondition.INTERRUPTED,
            effect=OperationEffect.NONE,
            settled_at=clock[0],
        )

        async with supervisor._lease_lock(operation_id):
            submission = asyncio.create_task(supervisor.submit_ephemeral_secret(requirement, submitted))
            await asyncio.sleep(0)
            assert not submission.done()
            settlement = asyncio.create_task(supervisor.settle(operation_id, receipt))
            await asyncio.sleep(0)
            assert not settlement.done()

        await submission
        terminal = await settlement
        assert terminal.terminal_condition is OperationTerminalCondition.INTERRUPTED
        assert submitted == bytearray(len(_SECRET))
        assert not supervisor._ephemeral_secrets.has_exact(requirement, observed_at=clock[0])
        assert executor.calls == 0
        _assert_no_secret_or_derivative(tmp_path)

    asyncio.run(scenario())


def test_shutdown_zeroizes_secret_during_active_consumption(tmp_path: Path) -> None:
    async def scenario() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()
        executor = BlockingExecutor(entered, release)
        registry = OperationRegistry(definitions=(_definition(executor),))
        clock = [_NOW]
        supervisor = _supervisor(root=tmp_path, registry=registry, owner="4" * 64, token="5" * 64, clock=clock)
        operation_id = await supervisor.submit(_request(), operation_id="6" * 64)
        requirement = (await supervisor.inspect(operation_id)).secret_requirement
        assert requirement is not None
        submitted = bytearray(_SECRET)
        await supervisor.submit_ephemeral_secret(requirement, submitted)
        execution = asyncio.create_task(supervisor.start(operation_id))
        await entered.wait()

        await supervisor.shutdown()
        release.set()
        terminal = await execution

        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert executor.active_buffer_zeroized
        assert submitted == bytearray(len(_SECRET))
        _assert_no_secret_or_derivative(tmp_path)

    asyncio.run(scenario())


def test_restart_before_entry_is_none_and_after_entry_is_unknown_without_reexecution(tmp_path: Path) -> None:
    async def scenario() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()
        executor = BlockingExecutor(entered, release)
        registry = OperationRegistry(definitions=(_definition(executor),))
        clock = [_NOW]
        owner = _supervisor(root=tmp_path, registry=registry, owner="9" * 64, token="a" * 64, clock=clock)

        before_id = await owner.submit(_request(), operation_id="b" * 64)
        await owner.shutdown()
        clock[0] = _NOW + timedelta(minutes=2)
        replacement = _supervisor(root=tmp_path, registry=registry, owner="c" * 64, token="d" * 64, clock=clock)
        before = await replacement.reconcile(before_id)
        assert before.terminal_condition is OperationTerminalCondition.INTERRUPTED
        assert before.effect is OperationEffect.NONE
        assert before.executor_entered_at is None
        assert executor.calls == 0

        clock[0] = _NOW + timedelta(minutes=3)
        after_id = await replacement.submit(_request(), operation_id="e" * 64)
        requirement = (await replacement.inspect(after_id)).secret_requirement
        assert requirement is not None
        await replacement.submit_ephemeral_secret(requirement, bytearray(_SECRET))
        start_task = asyncio.create_task(replacement.start(after_id))
        await entered.wait()
        running = await replacement.inspect(after_id)
        assert running.lifecycle is OperationLifecycle.RUNNING
        assert running.executor_entered_at == clock[0]
        start_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await start_task
        await replacement.shutdown()

        clock[0] = _NOW + timedelta(minutes=5)
        final_owner = _supervisor(root=tmp_path, registry=registry, owner="f" * 64, token="0" * 64, clock=clock)
        after = await final_owner.reconcile(after_id)
        assert after.terminal_condition is OperationTerminalCondition.INTERRUPTED
        assert after.effect is OperationEffect.UNKNOWN
        assert executor.calls == 1

    asyncio.run(scenario())
    _assert_no_secret_or_derivative(tmp_path)
