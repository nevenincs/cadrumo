"""Authorization at real supervisor entry/effect boundaries over durable synthetic stores."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.operations.capabilities import OperationReplayPolicy
from cadrumo.application.operations.composition import OperationSubmissionService
from cadrumo.application.operations.models import OperationIdentity, OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.projection_services import OperationResponseAuthorityBroker
from cadrumo.application.operations.registry import OperationReconciliationPolicy
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.operations import (
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
)

from .supervision_support import run_to_settlement
from .test_supervisor import (
    _NOW,
    ResumableReviewExecutor,
    _capabilities,
    _registry,
    _repositories,
    _request,
    _supervisor,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


class Authorization:
    """Explicit authority fault port; supervisor and durable journal remain real."""

    def __init__(self) -> None:
        self.denied: AccessAction | None = None
        self.calls: list[AccessAction | str] = []
        self.guard_attempts = 0
        self.deny_executor_entry = False

    async def require[Payload: BaseModel](
        self, *, identity: OperationIdentity, request: OperationRequest[Payload], action: AccessAction
    ) -> None:
        assert identity.definition_id == request.definition_id
        self.calls.append(action)
        if action is self.denied or (
            self.deny_executor_entry and action is AccessAction.START and self.calls.count(AccessAction.START) > 1
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)

    @asynccontextmanager
    async def commit_guard(self, identity: OperationIdentity) -> AsyncGenerator[None]:
        assert identity.operation_id
        self.guard_attempts += 1
        if self.denied is AccessAction.COMMIT:
            raise ProfileAccessRefusedError(AccessDenialCode.SESSION_INACTIVE)
        self.calls.append("guard_enter")
        try:
            yield
        finally:
            self.calls.append("guard_leave")


class Executor:
    def __init__(self) -> None:
        self.entered, self.proceed = asyncio.Event(), asyncio.Event()
        self.effects: list[str] = []

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        del request
        self.entered.set()
        await self.proceed.wait()
        async with context.cancellation.irreversible_section(), context.cancellation.irreversible_section():
            self.effects.append("effect body")
        return "result:synthetic-effect"


@pytest.mark.parametrize("boundary", [AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT, None])
def test_refusal_prevents_the_corresponding_supervisor_boundary(tmp_path: Path, boundary: AccessAction | None) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "operations", profile_objects=profile.repository
        )
        executor, authority = Executor(), Authorization()
        supervisor = _supervisor(
            registry=_registry(executor_type=Executor, build=lambda: executor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            execution_authority=authority,
        )

        async def exercise() -> None:
            if boundary is AccessAction.SUBMIT:
                authority.denied = boundary
                with pytest.raises(ProfileAccessRefusedError):
                    await supervisor.submit(_request(), operation_id="3" * 64)
                assert not executor.entered.is_set()
                return
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            if boundary is AccessAction.START:
                authority.denied = boundary
                with pytest.raises(ProfileAccessRefusedError):
                    await supervisor.start(operation_id)
                assert (await journal.load(operation_id)).lifecycle is OperationLifecycle.CREATED
                assert not executor.entered.is_set()
                return
            await supervisor.start(operation_id)
            await asyncio.wait_for(executor.entered.wait(), timeout=3)
            authority.denied = boundary
            executor.proceed.set()
            settled = await supervisor.settled(operation_id)
            if boundary is AccessAction.COMMIT:
                assert settled.terminal_condition is OperationTerminalCondition.REFUSED
                assert executor.effects == []
            else:
                assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert executor.effects == ["effect body"]
                assert authority.calls.count("guard_enter") == authority.calls.count("guard_leave") == 1
            await supervisor.shutdown()

        asyncio.run(exercise())


def test_a_refused_frontend_start_settles_and_frees_its_subject(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "operations", profile_objects=profile.repository
        )
        executor, authority = Executor(), Authorization()
        supervisor = _supervisor(
            registry=_registry(executor_type=Executor, build=lambda: executor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            execution_authority=authority,
        )
        service = OperationSubmissionService(supervisor, OperationResponseAuthorityBroker())

        async def exercise() -> None:
            operation_id = await supervisor.submit(_request(), operation_id="3" * 64)
            authority.denied = AccessAction.START
            with pytest.raises(ProfileAccessRefusedError):
                await service.start(operation_id)
            refused = await journal.load(operation_id)
            assert refused.lifecycle is OperationLifecycle.TERMINAL
            assert refused.terminal_condition is OperationTerminalCondition.REFUSED
            assert refused.effect is OperationEffect.NONE
            assert not executor.entered.is_set()
            authority.denied = None
            # Left CREATED, the refused start would hold the subject and refuse this submission.
            assert await supervisor.submit(_request(), operation_id="4" * 64) == "4" * 64
            await supervisor.shutdown()

        asyncio.run(exercise())


def test_revocation_after_start_admission_prevents_actual_executor_entry(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "operations", profile_objects=profile.repository
        )
        executor, authority = Executor(), Authorization()
        authority.deny_executor_entry = True
        supervisor = _supervisor(
            registry=_registry(executor_type=Executor, build=lambda: executor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            execution_authority=authority,
        )

        async def exercise() -> None:
            operation_id = await supervisor.submit(_request())
            await supervisor.start(operation_id)
            settled = await supervisor.settled(operation_id)
            assert settled.terminal_condition is OperationTerminalCondition.REFUSED
            assert not executor.entered.is_set() and not executor.effects
            await supervisor.shutdown()

        asyncio.run(exercise())


class ConcurrentExecutor:
    def __init__(self, authority: Authorization) -> None:
        self.authority = authority
        self.effects: list[str] = []

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        del request
        first_inside, second_attempting, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def first() -> None:
            async with context.cancellation.irreversible_section():
                first_inside.set()
                await release.wait()
                self.effects.append("first")
                self.authority.denied = AccessAction.COMMIT

        async def second() -> None:
            second_attempting.set()
            async with context.cancellation.irreversible_section():
                self.effects.append("second")

        one = asyncio.create_task(first())
        await first_inside.wait()
        two = asyncio.create_task(second())
        await second_attempting.wait()
        release.set()
        results = await asyncio.gather(one, two, return_exceptions=True)
        assert results[0] is None and isinstance(results[1], ProfileAccessRefusedError)
        return "result:concurrent-sections"


def test_concurrent_sections_do_not_inherit_another_tasks_guard(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "operations", profile_objects=profile.repository
        )
        authority = Authorization()
        executor = ConcurrentExecutor(authority)
        supervisor = _supervisor(
            registry=_registry(executor_type=ConcurrentExecutor, build=lambda: executor),
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            execution_authority=authority,
        )

        async def exercise() -> None:
            operation_id = await supervisor.submit(_request())
            await supervisor.start(operation_id)
            settled = await asyncio.wait_for(supervisor.settled(operation_id), timeout=5)
            assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert executor.effects == ["first"] and authority.guard_attempts == 2
            await supervisor.shutdown()

        asyncio.run(exercise())


def test_denied_checkpoint_resume_preserves_the_recoverable_record(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "operations", profile_objects=profile.repository
        )
        entered, release = asyncio.Event(), asyncio.Event()
        registry = _registry(
            executor_type=ResumableReviewExecutor,
            build=lambda: ResumableReviewExecutor(
                result_ref="result:resumed", resume_entered=entered, release_resume=release
            ),
            capabilities=_capabilities(
                durability=OperationDurability.RESUMABLE, replay=OperationReplayPolicy.RESUMABLE
            ),
            interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
            reconciliation_policy=OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT,
        )
        owner = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            lease_duration=timedelta(minutes=1),
        )
        operation_id = asyncio.run(owner.submit(_request()))
        before = asyncio.run(run_to_settlement(owner, operation_id))
        authority = Authorization()
        authority.denied = AccessAction.RESUME
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="3" * 64,
            token="4" * 64,
            clock=lambda: _NOW + timedelta(minutes=2),
            execution_authority=authority,
        )
        with pytest.raises(ProfileAccessRefusedError):
            asyncio.run(recovery.continue_operation(operation_id))
        assert asyncio.run(journal.load(operation_id)) == before
        assert authority.calls == [AccessAction.RESUME]
        assert not entered.is_set()


@pytest.mark.parametrize("expired", [False, True])
def test_continuation_respects_exact_owner_then_rechecks_executor_authority(tmp_path: Path, expired: bool) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal, leases, operands = _repositories(
            storage_root=tmp_path / "operations", profile_objects=profile.repository
        )
        executor, authority = Executor(), Authorization()
        registry = _registry(executor_type=Executor, build=lambda: executor)
        original = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            token="2" * 64,
            lease_duration=timedelta(minutes=1),
        )
        recovery = _supervisor(
            registry=registry,
            journal=journal,
            leases=leases,
            operands=operands,
            owner_id="3" * 64,
            token="4" * 64,
            clock=lambda: _NOW + timedelta(seconds=120 if expired else 1),
            execution_authority=authority,
        )

        async def exercise() -> None:
            operation_id = await original.submit(_request())
            before = await journal.load(operation_id)
            stored = await recovery.stored_invocation(operation_id, require_idle=True)
            assert stored.identity == before.identity
            assert stored.request.payload == _request().payload
            if not expired:
                with pytest.raises(ValueError, match="not owned"):
                    await recovery.continue_operation(operation_id)
                assert await journal.load(operation_id) == before
                assert not executor.entered.is_set()
                return
            authority.denied = AccessAction.START
            with pytest.raises(ProfileAccessRefusedError):
                await recovery.continue_operation(operation_id)
            assert not executor.entered.is_set()
            authority.denied = None
            await recovery.continue_operation(operation_id)
            await asyncio.wait_for(executor.entered.wait(), 3)
            with pytest.raises(ValueError, match="live local"):
                await recovery.stored_invocation(operation_id, require_idle=True)
            with pytest.raises(ValueError, match="live local"):
                await recovery.continue_operation(operation_id)
            executor.proceed.set()
            settled = await recovery.settled(operation_id)
            assert settled.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert await recovery.continue_operation(operation_id) == settled
            assert executor.effects == ["effect body"]
            await recovery.shutdown()

        asyncio.run(exercise())
