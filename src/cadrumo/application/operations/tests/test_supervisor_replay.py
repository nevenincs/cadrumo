"""Production-supervisor replay proofs over real durable operation storage."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from ....adapters.persistence.operations import (
    OperationJournalRepository,
    OperationLeaseFilesystemRepository,
    operation_secure_reference_repository,
)
from ....core import STRICT_FROZEN_CONFIG
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    OperationBaselinePolicy,
    OperationCancellation,
    OperationCapabilities,
    OperationClosePolicy,
    OperationConflictScope,
    OperationDeadline,
    OperationDefinition,
    OperationDurability,
    OperationEffect,
    OperationExecutorContext,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationReplayPolicy,
    OperationReplayStatus,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationSecureReferenceStore,
    OperationSensitiveInputPolicy,
    OperationSupervisor,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 14, 17, tzinfo=UTC)
_DEFINITION_ID = "operation.supervisor.replay"


class ReplayRequest(BaseModel):
    """Concrete encrypted operation input for the supervisor replay proof."""

    model_config = STRICT_FROZEN_CONFIG

    value: str = Field(min_length=1)


class ReplayNoticeExecutor:
    """Concrete executor that commits two independently replayable events."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> None:
        del request
        await context.events.notice("operation.replay.notice-one")
        await context.events.notice("operation.replay.notice-two")


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
    return OperationRegistry(
        definitions=(
            OperationDefinition(
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
            ),
        )
    )


def _supervisor(
    *,
    journal: OperationJournalRepository,
    leases: OperationLeaseFilesystemRepository,
    operands: OperationSecureReferenceStore,
) -> OperationSupervisor:
    """Construct the public replay surface over the real adapters."""
    return OperationSupervisor(
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
        asyncio.run(supervisor.start(operation_id))
        observer = _supervisor(
            journal=OperationJournalRepository(storage_root=tmp_path / "durable-state"),
            leases=OperationLeaseFilesystemRepository(storage_root=tmp_path / "durable-state"),
            operands=operands,
        )

        unknown = asyncio.run(observer.replay("4" * 64, 0, limit=2))
        first_page = asyncio.run(observer.replay(operation_id, 0, limit=2))
        repeated_first_page = asyncio.run(observer.replay(operation_id, 0, limit=2))
        second_page = asyncio.run(observer.replay(operation_id, first_page.next_cursor, limit=1))
        caught_up = asyncio.run(observer.replay(operation_id, second_page.next_cursor, limit=2))

        assert unknown.status is OperationReplayStatus.UNKNOWN_OPERATION
        assert unknown.events == ()
        assert unknown.next_cursor == 0
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
