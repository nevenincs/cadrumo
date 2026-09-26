"""Production-supervisor replay proofs over real durable operation storage."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.owner import OperationExecutorContext
from cadrumo.application.operations.persistence.journal import OperationSecureReferenceStore
from cadrumo.application.operations.persistence.replay import OperationReplayPage, OperationReplayStatus
from cadrumo.application.operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.operations.tests.authority_test_support import unread_authority_operation
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)

from .supervision_support import run_to_settlement

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 14, 17, tzinfo=UTC)
_DEFINITION_ID = "operation.supervisor.replay"


class ReplayRequest(BaseModel):
    """Concrete encrypted operation input for the supervisor replay proof."""

    model_config = STRICT_FROZEN_CONFIG

    value: str = Field(min_length=1)


class ReplayNoticeExecutor:
    """Concrete executor that commits two independently replayable events, then stays live.

    Staying live keeps the replayed stream free of a terminal event; the test
    closes the host once the replay proof is read.
    """

    notices_committed: asyncio.Event
    release: asyncio.Event

    @classmethod
    def reset(cls) -> None:
        cls.notices_committed = asyncio.Event()
        cls.release = asyncio.Event()

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> None:
        del request
        await context.events.notice("operation.replay.notice-one")
        await context.events.notice("operation.replay.notice-two")
        type(self).notices_committed.set()
        await type(self).release.wait()


def _capabilities() -> OperationCapabilities:
    """Declare the exact durable operation behavior exercised in this proof."""
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def _registry() -> OperationRegistry:
    """Build the concrete registered operation that emits durable notice events."""
    definition = OperationDefinition(
        definition_id=_DEFINITION_ID,
        request_type=ReplayRequest,
        result_type=None,
        executor_factory=OperationExecutorFactory(
            request_type=ReplayRequest,
            executor_type=ReplayNoticeExecutor,
            build=ReplayNoticeExecutor,
        ),
        phase_codes=("operation.replay.phase",),
        interaction_kinds=frozenset(),
        capabilities=_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operation.supervisor.replay.request",
            schema_version=1,
            model_type=ReplayRequest,
        ),
    )
    return OperationRegistry(
        definitions=(definition,),
        public_registrations=(registration,),
    )


def _supervisor(
    *,
    journal: OperationJournalRepository,
    leases: OperationLeaseFilesystemRepository,
    operands: OperationSecureReferenceStore,
) -> OperationSupervisor:
    """Construct the public replay surface over the real adapters."""
    return OperationSupervisor(
        authority_operation=unread_authority_operation(),
        registry=_registry(),
        journal=journal,
        event_stream=journal,
        leases=leases,
        operands=operands,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: _NOW,
        lease_duration=timedelta(minutes=10),
    )


def test_supervisor_replay_reads_idempotent_bounded_pages_from_the_durable_event_stream(tmp_path: Path) -> None:
    """Real encrypted-SQL and filesystem adapters preserve authoritative cursor replay."""
    ReplayNoticeExecutor.reset()
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        journal = OperationJournalRepository(storage_root=tmp_path / "durable-state")
        leases = OperationLeaseFilesystemRepository(storage_root=tmp_path / "durable-state")
        operands = operation_secure_reference_repository(objects=profile.repository)
        supervisor = _supervisor(journal=journal, leases=leases, operands=operands)
        operation_id = asyncio.run(
            supervisor.submit(
                OperationRequest[BaseModel](
                    definition_id=_DEFINITION_ID,
                    subject_ref="subject:supervisor-replay",
                    payload=ReplayRequest(value="encrypted-operation-input"),
                    idempotency_key=None,
                ),
                operation_id="3" * 64,
            )
        )
        observer = _supervisor(
            journal=OperationJournalRepository(storage_root=tmp_path / "durable-state"),
            leases=OperationLeaseFilesystemRepository(storage_root=tmp_path / "durable-state"),
            operands=operands,
        )

        async def replay_live_operation() -> tuple[
            OperationReplayPage, OperationReplayPage, OperationReplayPage, OperationReplayPage
        ]:
            waiter = asyncio.create_task(run_to_settlement(supervisor, operation_id))
            await ReplayNoticeExecutor.notices_committed.wait()
            first_page = await observer.replay(operation_id, 0, limit=2)
            repeated_first_page = await observer.replay(operation_id, 0, limit=2)
            second_page = await observer.replay(operation_id, first_page.next_cursor, limit=1)
            caught_up = await observer.replay(operation_id, second_page.next_cursor, limit=2)
            waiter.cancel()
            with suppress(asyncio.CancelledError):
                await waiter
            await supervisor.shutdown()
            return first_page, repeated_first_page, second_page, caught_up

        first_page, repeated_first_page, second_page, caught_up = asyncio.run(replay_live_operation())

        assert first_page.status is OperationReplayStatus.PAGE
        assert tuple(event.sequence for event in first_page.events) == (1, 2)
        assert first_page.next_cursor == 2
        assert repeated_first_page == first_page
        assert second_page.status is OperationReplayStatus.PAGE
        assert tuple(event.sequence for event in second_page.events) == (3,)
        assert second_page.next_cursor == 3
        assert caught_up.status is OperationReplayStatus.CAUGHT_UP
        assert caught_up.events == ()
        assert caught_up.next_cursor == second_page.next_cursor
