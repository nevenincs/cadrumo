"""Real supervisor proof for the recorded filed-history executor."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from ....adapters.persistence.operations import (
    OperationJournalRepository,
    OperationLeaseFilesystemRepository,
    OperationSecureReferenceRepository,
)
from ....adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from ....adapters.persistence.storage import (
    SecureObjectNamespaceDefinition,
    StorageCustodyDisposition,
    StorageNamespaceScope,
)
from ....core import (
    FiledHistoryDiscoverySignal,
    OperationCancellation,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationLifecycle,
)
from ....core.classification import SensitivityClass
from ....domain.deadlines import TaxpayerProfile
from ....tests.secure_namespace_registration import registered_objects
from ....tests.secure_sql import isolated_runtime_profile
from ...operations import (
    OperationEffectEvent,
    OperationLogRecord,
    OperationPhaseEvent,
    OperationProgressEvent,
    OperationRegistry,
    OperationReplayLimit,
    OperationRequest,
    OperationSupervisor,
)
from .._filed_data_capture import (
    FiledHistoryDiscoveryPair,
    FiledHistoryDiscoveryPort,
    FiledHistoryDiscoveryReport,
    FiledHistoryOnboardingRun,
    FiledHistoryPairOutcome,
    _CaptureAccumulator,
    _persisted_bulk_filed_capture_report,
    pull_filed_history,
)
from .._filed_history_operation import (
    FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE,
    FILED_HISTORY_OPERATION_DEFINITION_ID,
    FILED_HISTORY_PAIR_PROGRESS_UNIT,
    FILED_HISTORY_PAIR_REFUSAL_CODE,
    FILED_HISTORY_PHASE_CLEANUP,
    FILED_HISTORY_PHASE_DISCOVERY,
    FILED_HISTORY_PHASE_EXECUTION,
    FILED_HISTORY_PHASE_NOTIFICATIONS,
    FILED_HISTORY_PHASE_PREFLIGHT,
    FILED_HISTORY_PHASE_RESULT,
    FILED_HISTORY_PHASE_SETTLEMENT,
    FiledHistoryOperationRequest,
    _result_reference,
    _settled_effect,
    build_filed_history_operation_definition,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 24, 20, tzinfo=UTC)
_NAMESPACE = SecureObjectNamespaceDefinition(
    key="filed_history_operation_executor_test",
    namespace="cadrumo-test.live.filed-history-operation",
    owner="cadrumo.application.live.tests.test_filed_history_operation_executor",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=1,
    object_key_grammar="{content_digest}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)


class _DeterministicFiledHistoryDiscoveryPort:
    """A strict-model local discovery port with an optional real async boundary.

    The composition deliberately owns one narrow discovery port so it can be
    exercised without arming an authenticated AEAT session.  This is that port's
    deterministic implementation: downstream capture, accounting, persistence,
    and supervisor durability remain the production implementations.
    """

    def __init__(
        self,
        *,
        entered: asyncio.Event | None = None,
        release: asyncio.Event | None = None,
    ) -> None:
        self._entered = entered
        self._release = release

    async def __call__(
        self,
        *,
        profile: TaxpayerProfile | None = None,
        today: date | None = None,
    ) -> FiledHistoryDiscoveryReport:
        del profile, today
        if self._entered is not None:
            self._entered.set()
        if self._release is not None:
            await self._release.wait()
        return FiledHistoryDiscoveryReport(
            pairs=(
                FiledHistoryDiscoveryPair(
                    modelo="100",
                    ejercicio=2000,
                    signals=(FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,),
                ),
            ),
            register_options_read=True,
        )


def _local_pull(discover: FiledHistoryDiscoveryPort):
    """Bind the real canonical composition to its deterministic discovery port."""

    async def pull(payload, repository, events):
        return await pull_filed_history(
            output_root=payload.output_root,
            profile=payload.profile,
            today=payload.today,
            limit=payload.limit,
            dry_run=payload.dry_run,
            discover=discover,
            sync_run_repository=repository,
            events=events,
        )

    return pull


def test_definition_declares_recorded_non_stoppable_execution(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        definition = build_filed_history_operation_definition(
            sync_run_repository=SyncRunRecordRepository(),
            pull=_local_pull(_DeterministicFiledHistoryDiscoveryPort()),
        )

    assert definition.definition_id == FILED_HISTORY_OPERATION_DEFINITION_ID
    assert definition.request_type is FiledHistoryOperationRequest
    assert definition.capabilities.durability is OperationDurability.RECORDED
    assert definition.capabilities.cancellation is OperationCancellation.UNSUPPORTED
    assert definition.capabilities.deadline is OperationDeadline.ABSENT


def test_supervisor_records_ordered_safe_progress_and_truthful_zero_effect(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        discovery_entered = asyncio.Event()
        release_discovery = asyncio.Event()
        definition = build_filed_history_operation_definition(
            sync_run_repository=SyncRunRecordRepository(),
            pull=_local_pull(
                _DeterministicFiledHistoryDiscoveryPort(
                    entered=discovery_entered,
                    release=release_discovery,
                ),
            ),
        )
        journal = OperationJournalRepository(storage_root=tmp_path / "operations")
        supervisor = OperationSupervisor(
            registry=OperationRegistry(definitions=(definition,)),
            journal=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=tmp_path / "operations"),
            operands=OperationSecureReferenceRepository(
                objects=registered_objects(profile.repository, _NAMESPACE),
                namespace=_NAMESPACE,
            ),
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        request = OperationRequest(
            definition_id=definition.definition_id,
            subject_ref=profile.bucket_id,
            payload=FiledHistoryOperationRequest(
                output_root=tmp_path / "filed",
                today=date(2026, 3, 15),
            ),
        )

        async def run():
            operation_id = await supervisor.submit(request, operation_id="3" * 64)
            start_task = asyncio.create_task(supervisor.start(operation_id))
            for _ in range(100):
                if discovery_entered.is_set():
                    break
                if start_task.done():
                    await start_task
                await asyncio.sleep(0)
            else:
                raise AssertionError("filed-history pull did not reach deterministic discovery")
            assert start_task.done() is False
            in_flight_events = (
                await asyncio.wait_for(
                    supervisor.replay(operation_id, 0, limit=OperationReplayLimit(100)),
                    timeout=1,
                )
            ).events
            assert [event.phase_code for event in in_flight_events if isinstance(event, OperationPhaseEvent)] == [
                FILED_HISTORY_PHASE_PREFLIGHT,
                FILED_HISTORY_PHASE_EXECUTION,
                FILED_HISTORY_PHASE_DISCOVERY,
            ]
            release_discovery.set()
            snapshot = await start_task
            assert snapshot.lifecycle is OperationLifecycle.RUNNING
            assert snapshot.phase_code == FILED_HISTORY_PHASE_SETTLEMENT
            assert snapshot.effect is OperationEffect.NONE
            events = (await supervisor.replay(operation_id, 0, limit=OperationReplayLimit(100))).events
            return snapshot, events

        snapshot, events = asyncio.run(run())

    assert snapshot.identity.definition_id == FILED_HISTORY_OPERATION_DEFINITION_ID
    assert snapshot.events[-1].code == FILED_HISTORY_PHASE_SETTLEMENT
    assert [event.phase_code for event in events if isinstance(event, OperationPhaseEvent)] == [
        FILED_HISTORY_PHASE_PREFLIGHT,
        FILED_HISTORY_PHASE_EXECUTION,
        FILED_HISTORY_PHASE_DISCOVERY,
        FILED_HISTORY_PHASE_NOTIFICATIONS,
        FILED_HISTORY_PHASE_RESULT,
        FILED_HISTORY_PHASE_CLEANUP,
        FILED_HISTORY_PHASE_SETTLEMENT,
    ]
    assert [
        (event.completed, event.total, event.unit_code) for event in events if isinstance(event, OperationProgressEvent)
    ] == [
        (0, 1, FILED_HISTORY_PAIR_PROGRESS_UNIT),
        (1, 1, FILED_HISTORY_PAIR_PROGRESS_UNIT),
    ]
    assert [event.code for event in events if isinstance(event, OperationLogRecord)] == [
        FILED_HISTORY_PAIR_REFUSAL_CODE,
        FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE,
    ]
    assert [event.effect for event in events if isinstance(event, OperationEffectEvent)] == [
        OperationEffect.UNKNOWN,
        OperationEffect.NONE,
    ]


def test_supervisor_records_a_dry_run_with_no_effect(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        definition = build_filed_history_operation_definition(
            sync_run_repository=SyncRunRecordRepository(),
            pull=_local_pull(_DeterministicFiledHistoryDiscoveryPort()),
        )
        journal = OperationJournalRepository(storage_root=tmp_path / "operations")
        supervisor = OperationSupervisor(
            registry=OperationRegistry(definitions=(definition,)),
            journal=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=tmp_path / "operations"),
            operands=OperationSecureReferenceRepository(
                objects=registered_objects(profile.repository, _NAMESPACE),
                namespace=_NAMESPACE,
            ),
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        request = OperationRequest(
            definition_id=definition.definition_id,
            subject_ref=profile.bucket_id,
            payload=FiledHistoryOperationRequest(
                output_root=tmp_path / "filed",
                today=date(2026, 3, 15),
                dry_run=True,
            ),
        )
        assert request.payload.dry_run is True

        async def run():
            operation_id = await supervisor.submit(request, operation_id="4" * 64)
            return await supervisor.start(operation_id)

        snapshot = asyncio.run(run())

    assert snapshot.effect is OperationEffect.NONE
    assert all(
        event.effect is not OperationEffect.UNKNOWN
        for event in snapshot.events
        if isinstance(event, OperationEffectEvent)
    )


def test_canonical_writer_reference_resolves_the_exact_encrypted_sync_run(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = SyncRunRecordRepository()
        report = _persisted_bulk_filed_capture_report(
            output_root=tmp_path / "filed",
            modelos=("303",),
            year_from=2025,
            year_to=2025,
            accumulator=_CaptureAccumulator(),
            failures=[],
            bucket_id=profile.bucket_id,
            sync_run_repository=repository,
        )

        reference = report.sync_run_ref
        assert reference is not None
        stored = repository.load(reference)

        assert stored is not None
        assert repository.extract_identifier(stored) == reference
        assert stored.bucket_id == profile.bucket_id
        assert _result_reference(FiledHistoryOnboardingRun(sync_run_ref=reference)) == reference


@pytest.mark.parametrize(
    ("run", "expected"),
    [
        (FiledHistoryOnboardingRun(dry_run=True), OperationEffect.NONE),
        (
            FiledHistoryOnboardingRun(
                pairs=(
                    FiledHistoryPairOutcome(
                        modelo="303",
                        ejercicio=2025,
                        signals=(FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,),
                        refused=True,
                        failure_type="RegisterRefused",
                        failure_message="safe local refusal",
                    ),
                ),
            ),
            OperationEffect.NONE,
        ),
        (FiledHistoryOnboardingRun(captured_count=1, reached_count=1), OperationEffect.UPDATED),
        (
            FiledHistoryOnboardingRun(
                captured_count=1,
                reached_count=1,
                stage_failures=("notificaciones: safe local refusal",),
            ),
            OperationEffect.PARTIAL,
        ),
    ],
)
def test_settled_effect_classifies_only_committed_units(
    run: FiledHistoryOnboardingRun,
    expected: OperationEffect,
) -> None:
    """A completed canonical result never leaves normal zero writes unknown."""
    assert _settled_effect(run) is expected
