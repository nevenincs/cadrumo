"""Canonical conformance proof for the recorded filed-history operation."""

from __future__ import annotations

import asyncio
import importlib
import subprocess
import sys
import textwrap
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest

from ....adapters.outbound.aeat.sede import (
    FiledDeclarationAvailability,
    FiledDeclarationAvailabilityReport,
)
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
from .. import (
    FILED_HISTORY_OPERATION_DEFINITION_ID as PUBLIC_FILED_HISTORY_OPERATION_DEFINITION_ID,
)
from .. import (
    FiledHistoryOnboardingRun as PublicFiledHistoryOnboardingRun,
)
from .. import (
    FiledHistoryOperationRequest as PublicFiledHistoryOperationRequest,
)
from .. import __all__ as public_names
from .. import (
    build_filed_history_operation_definition as public_build_filed_history_operation_definition,
)
from .._filed_data_capture import (
    ExpectedFiledDeclarationGrid,
    FiledHistoryDiscoveryPort,
    FiledHistoryDiscoveryReport,
    FiledHistoryOnboardingRun,
    FiledHistoryPairOutcome,
    _CaptureAccumulator,
    _persisted_bulk_filed_capture_report,
    filed_history_discovery_report,
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
    owner="cadrumo.application.live.tests.test_filed_history_operation",
    sensitivity=SensitivityClass.FINANCIAL,
    schema_version=1,
    object_key_grammar="{content_digest}",
    scope=StorageNamespaceScope.BUCKET_LOCAL,
    custody_disposition=StorageCustodyDisposition.PROCESS_LOCAL,
)


class _FixtureBackedFiledHistoryDiscovery:
    """Resolve one scope through the real register-option parser and models."""

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
        return filed_history_discovery_report(
            expected=ExpectedFiledDeclarationGrid(),
            availability=FiledDeclarationAvailabilityReport(
                items=(FiledDeclarationAvailability(modelo="303", ejercicios=(2025,)),),
                discovered_at=_NOW,
            ),
        )


def _local_pull(discover: FiledHistoryDiscoveryPort):
    """Bind the canonical composition to fixture-backed production discovery."""

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
            pull=_local_pull(_FixtureBackedFiledHistoryDiscovery()),
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
                _FixtureBackedFiledHistoryDiscovery(
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
            with pytest.raises(ValueError, match="operation does not support cancellation"):
                await supervisor.request_cancel(operation_id)
            release_discovery.set()
            snapshot = await start_task
            assert snapshot.lifecycle is OperationLifecycle.TERMINAL
            assert snapshot.phase_code == FILED_HISTORY_PHASE_SETTLEMENT
            assert snapshot.effect is OperationEffect.NONE
            assert snapshot.execution_deadline is None
            assert snapshot.cleanup_deadline is None
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
            pull=_local_pull(_FixtureBackedFiledHistoryDiscovery()),
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
            snapshot = await supervisor.start(operation_id)
            events = (await supervisor.replay(operation_id, 0, limit=OperationReplayLimit(100))).events
            return snapshot, events

        snapshot, events = asyncio.run(run())

    assert snapshot.effect is OperationEffect.NONE
    assert all(
        event.effect is not OperationEffect.UNKNOWN
        for event in events
        if isinstance(event, OperationEffectEvent)
    )
    assert [
        (event.completed, event.total, event.unit_code)
        for event in events
        if isinstance(event, OperationProgressEvent)
    ] == [
        (0, 1, FILED_HISTORY_PAIR_PROGRESS_UNIT),
        (1, 1, FILED_HISTORY_PAIR_PROGRESS_UNIT),
    ]


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
        run = FiledHistoryOnboardingRun(sync_run_ref=reference)
        assert _result_reference(run) == reference
        assert _settled_effect(run) is OperationEffect.UPDATED
        assert (
            _settled_effect(
                run.model_copy(update={"stage_failures": ("notificaciones: safe local refusal",)}),
            )
            is OperationEffect.PARTIAL
        )


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


def test_filed_history_operation_contract_resolves_from_the_public_facade() -> None:
    """The facade exposes the request contract and composed definition factory."""
    live = importlib.import_module("..", package=__package__)
    definition = public_build_filed_history_operation_definition(
        sync_run_repository=SyncRunRecordRepository(),
    )

    assert PUBLIC_FILED_HISTORY_OPERATION_DEFINITION_ID == "live.filed-history.pull"
    assert definition.definition_id == PUBLIC_FILED_HISTORY_OPERATION_DEFINITION_ID
    assert definition.request_type is PublicFiledHistoryOperationRequest
    assert definition.result_type is PublicFiledHistoryOnboardingRun
    assert definition.executor_factory.request_type is PublicFiledHistoryOperationRequest
    assert definition.executor_factory.executor_type.__module__.endswith("._filed_history_operation")
    assert definition.executor_factory.build().__class__.__module__.endswith("._filed_history_operation")
    assert public_build_filed_history_operation_definition.__module__.endswith("._filed_history_operation")
    assert PublicFiledHistoryOperationRequest.__module__.endswith("._filed_history_operation")
    assert live.FILED_HISTORY_OPERATION_DEFINITION_ID is PUBLIC_FILED_HISTORY_OPERATION_DEFINITION_ID
    assert live.FiledHistoryOperationRequest is PublicFiledHistoryOperationRequest
    assert live.build_filed_history_operation_definition is public_build_filed_history_operation_definition


def test_filed_history_operation_facade_does_not_publish_executor_or_phase_internals() -> None:
    """The executable implementation and phase codes remain owner-private."""
    live = importlib.import_module("..", package=__package__)

    assert "FiledHistoryOperationExecutor" not in public_names
    assert "FiledHistoryPull" not in public_names
    assert "FILED_HISTORY_PHASE_EXECUTION" not in public_names
    assert not hasattr(live, "FiledHistoryOperationExecutor")
    assert not hasattr(live, "FiledHistoryPull")
    assert not hasattr(live, "FILED_HISTORY_PHASE_EXECUTION")


def test_filed_history_operation_public_names_are_unique_and_resolvable() -> None:
    """Every promised facade member resolves to a value rather than a module."""
    live = importlib.import_module("..", package=__package__)

    assert len(public_names) == len(set(public_names))
    assert all(not name.startswith("_") for name in public_names)
    assert all(hasattr(live, name) for name in public_names)
    assert all(not isinstance(getattr(live, name), ModuleType) for name in public_names)

    operation_names = [
        "FILED_HISTORY_OPERATION_DEFINITION_ID",
        "FiledHistoryOperationRequest",
        "build_filed_history_operation_definition",
    ]
    assert operation_names == sorted(operation_names)


def test_importing_live_keeps_filed_history_operation_lazy() -> None:
    """Importing the live facade does not load the operation implementation."""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and inline code under test
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import sys
                import cadrumo.application.live

                assert "cadrumo.application.live._filed_history_operation" not in sys.modules
                """,
            ),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
