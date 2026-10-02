"""Canonical conformance proof for the recorded filed-history operation."""

from __future__ import annotations

import ast
import asyncio
import importlib
import inspect
import textwrap
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.outbound.aeat.browser.factory import BrowserRuntimeResourceScope, default_browser_session_factory
from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.application.storage.sync_runs.records import SyncRunRecordRepositoryProtocol
from cadrumo.core.config import load_settings
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.deadlines.models import IVARegime
from cadrumo.entrypoints.live_state_composition import compose_notifications_ports

from ...adapters.outbound.aeat.sede.schema import FiledDeclarationAvailability, FiledDeclarationAvailabilityReport
from ...adapters.outbound.aeat.sede.tests.declarations_register_test_support import (
    RoutedFiledDataCapturePort,
    aeat_sede_fixture,
    open_routed_declarations_register,
)
from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from ...application.auth.operator_scope_ports import OperatorScopePorts
from ...application.auth.protocols import BrowserSessionFactoryPort
from ...application.live.filed_data_capture import (
    FILED_HISTORY_DECLARATION_PROGRESS_UNIT,
    FILED_HISTORY_IVA_WALLET_REFUSAL_CODE,
    FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE,
    FILED_HISTORY_PAIR_PROGRESS_UNIT,
    FILED_HISTORY_PAIR_REFUSAL_CODE,
    FILED_HISTORY_PHASE_DISCOVERY,
    FILED_HISTORY_PHASE_IVA_WALLET,
    FILED_HISTORY_PHASE_NOTIFICATIONS,
    ExpectedFiledDeclarationGrid,
    FiledHistoryDiscoveryPair,
    FiledHistoryDiscoveryPort,
    FiledHistoryDiscoveryReport,
    FiledHistoryOnboardingRun,
    FiledHistoryPairOutcome,
    filed_history_discovery_report,
    pull_filed_history,
)
from ...application.live.filed_data_ports import FiledDataCapturePort, FiledEffectGuard
from ...application.live.filed_history_operation import (
    FILED_HISTORY_OPERATION_DEFINITION_ID,
    FILED_HISTORY_PHASE_CLEANUP,
    FILED_HISTORY_PHASE_EXECUTION,
    FILED_HISTORY_PHASE_PREFLIGHT,
    FILED_HISTORY_PHASE_RESULT,
    FILED_HISTORY_PHASE_SETTLEMENT,
    FiledHistoryComposition,
    FiledHistoryOperationRequest,
    FiledHistoryPublicResultV1,
    FiledHistoryPull,
    build_filed_history_operation_definition,
    build_filed_history_operation_registration,
    settled_filed_history_effect,
)
from ...application.live.filed_observation_ports import FiledObservationPersistencePorts
from ...application.live.iva_remote_state_ports import IvaRemoteStatePort
from ...application.live.notification_ports import NotificationsPorts
from ...application.live.session import SessionWriteReporter
from ...application.live.tests.filed_observation_test_support import in_memory_filed_observation_test_bundle
from ...application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...application.operations.capabilities import OperationOwnedResource
from ...application.operations.errors import OperationUnsettledError
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationRequest, OperationTerminalReceipt
from ...application.operations.owner import OperationEventEmitter
from ...application.operations.persistence.journal import OperationPersistedSnapshot, OperationSecureReferenceStore
from ...application.operations.projection_services import OperationResultProjectionService
from ...application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...application.operations.supervisor import OperationSupervisor
from ...application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    Availability,
    DisclosureCategory,
)
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.access_policy import operation_scope_refusal
from ...core.async_cleanup import AsyncResourceCleanupError, close_async_resources
from ...core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from ...core.operations import (
    OperationCancellation,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationEventKind,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.register_scoping_signal import RegisterScopingSignal
from ...domain.deadlines.models import TaxpayerProfile

_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 24, 20, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class _TestFiledHistoryComposition:
    """Bind the canonical in-memory observation bundle to live outer ports."""

    ports: FiledObservationPersistencePorts
    filed_data_port: FiledDataCapturePort
    iva_remote_state_port: IvaRemoteStatePort
    notifications_ports: NotificationsPorts
    certificate_secret_backend_factory: CertificateSecretBackendFactory
    browser_session_factory: BrowserSessionFactoryPort
    operator_scope_ports: OperatorScopePorts


async def _run_to_terminal(supervisor: OperationSupervisor, operation_id: str) -> OperationPersistedSnapshot:
    """Admit the operation and wait for the supervised task that settles it."""
    await supervisor.start(operation_id)
    return await supervisor.settled(operation_id)


def _test_filed_history_composition(output_root: Path) -> FiledHistoryComposition:
    """Compose deterministic observation ports with the real outer capabilities."""
    del output_root
    bundle = in_memory_filed_observation_test_bundle()
    return _TestFiledHistoryComposition(
        ports=bundle.ports,
        filed_data_port=bundle.filed_data_port,
        iva_remote_state_port=bundle.iva_remote_state_port,
        notifications_ports=compose_notifications_ports(settings=load_settings()),
        certificate_secret_backend_factory=build_certificate_secret_backend,
        browser_session_factory=default_browser_session_factory,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )


class _DeterministicFiledHistoryDiscovery:
    """Resolve one scope through the real register-option parser and models."""

    def __init__(
        self,
        *,
        modelo: str = "100",
        ejercicio: int = 2000,
        entered: asyncio.Event | None = None,
        release: asyncio.Event | None = None,
    ) -> None:
        self._entered = entered
        self._release = release
        self._modelo = modelo
        self._ejercicio = ejercicio
        self.profile: TaxpayerProfile | None = None

    async def __call__(
        self,
        *,
        filed_data_port,
        profile: TaxpayerProfile | None = None,
        today: date | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> FiledHistoryDiscoveryReport:
        del filed_data_port
        assert effect_guard is not None and on_session_write is not None
        self.profile = profile
        del today
        if self._entered is not None:
            self._entered.set()
        if self._release is not None:
            await self._release.wait()
        return filed_history_discovery_report(
            expected=ExpectedFiledDeclarationGrid(),
            availability=FiledDeclarationAvailabilityReport(
                items=(
                    FiledDeclarationAvailability(
                        modelo=self._modelo,
                        ejercicios=(self._ejercicio,),
                    ),
                ),
                discovered_at=_NOW,
            ),
        )


def _local_pull(
    discover: FiledHistoryDiscoveryPort,
) -> FiledHistoryPull:
    """Bind the canonical composition to deterministic discovery/register inputs."""

    async def pull(
        payload: FiledHistoryOperationRequest,
        profile: TaxpayerProfile | None,
        repository: SyncRunRecordRepositoryProtocol,
        events: OperationEventEmitter,
        ports: FiledObservationPersistencePorts,
        filed_data_port: FiledDataCapturePort,
        iva_remote_state_port: IvaRemoteStatePort,
        notifications_ports: NotificationsPorts,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
        browser_session_factory: BrowserSessionFactoryPort,
        operator_scope_ports: OperatorScopePorts,
        effect_guard: FiledEffectGuard,
        on_session_write: SessionWriteReporter,
    ) -> FiledHistoryOnboardingRun:
        return await pull_filed_history(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            browser_session_factory=browser_session_factory,
            operator_scope_ports=operator_scope_ports,
            iva_remote_state_port=iva_remote_state_port,
            notifications_ports=notifications_ports,
            ports=ports,
            filed_data_port=filed_data_port,
            output_root=payload.output_root,
            profile=profile,
            today=payload.today,
            limit=payload.limit,
            dry_run=payload.dry_run,
            discover=discover,
            sync_run_repository=repository,
            events=events,
            effect_guard=effect_guard,
            on_session_write=on_session_write,
        )

    return pull


def _registered_filed_history_definition(definition):
    """Enroll the live definition through its public registration contract."""
    return OperationRegistry(
        definitions=(definition,),
        public_registrations=(build_filed_history_operation_registration(definition),),
    )


def _routed_pull(discover: FiledHistoryDiscoveryPort):
    """Run canonical composition through the real locally routed register adapter."""
    document = aeat_sede_fixture("declaraciones-register-form-complete-synthetic")

    async def pull(
        payload: FiledHistoryOperationRequest,
        profile: TaxpayerProfile | None,
        repository: SyncRunRecordRepositoryProtocol,
        events: OperationEventEmitter,
        ports: FiledObservationPersistencePorts,
        filed_data_port: FiledDataCapturePort,
        iva_remote_state_port: IvaRemoteStatePort,
        notifications_ports: NotificationsPorts,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
        browser_session_factory: BrowserSessionFactoryPort,
        operator_scope_ports: OperatorScopePorts,
        effect_guard: FiledEffectGuard,
        on_session_write: SessionWriteReporter,
    ) -> FiledHistoryOnboardingRun:
        del filed_data_port
        async with open_routed_declarations_register((document,), ver_click_timeout_ms=1500) as (register, routed):
            run = await pull_filed_history(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                browser_session_factory=browser_session_factory,
                operator_scope_ports=operator_scope_ports,
                iva_remote_state_port=iva_remote_state_port,
                notifications_ports=notifications_ports,
                ports=ports,
                filed_data_port=RoutedFiledDataCapturePort(register),
                output_root=payload.output_root,
                profile=profile,
                today=payload.today,
                limit=payload.limit,
                dry_run=payload.dry_run,
                discover=discover,
                sync_run_repository=repository,
                events=events,
                effect_guard=effect_guard,
                on_session_write=on_session_write,
            )
            assert not routed.pending
            return run

    return pull


def _composition_discovery(
    *pairs: FiledHistoryDiscoveryPair,
    scoping_signal: RegisterScopingSignal = RegisterScopingSignal.INCONCLUSIVE,
) -> FiledHistoryDiscoveryPort:
    """Supply strict discovery facts to the canonical composition boundary."""

    async def discover(
        *,
        filed_data_port,
        profile: TaxpayerProfile | None = None,
        today: date | None = None,
        effect_guard: FiledEffectGuard | None = None,
        on_session_write: SessionWriteReporter | None = None,
    ) -> FiledHistoryDiscoveryReport:
        del filed_data_port, profile, today, effect_guard, on_session_write
        return FiledHistoryDiscoveryReport(
            pairs=pairs,
            register_options_read=True,
            profile_year_span_determined=False,
            scoping_signal=scoping_signal,
        )

    return discover


def _composition_pair(modelo: str = "100") -> FiledHistoryDiscoveryPair:
    return FiledHistoryDiscoveryPair(
        modelo=modelo,
        ejercicio=2000,
        signals=(FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,),
    )


def _run_composition(*pairs: FiledHistoryDiscoveryPair, tmp_path: Path, dry_run: bool = False):
    composition = _test_filed_history_composition(tmp_path)
    return asyncio.run(
        pull_filed_history(
            certificate_secret_backend_factory=composition.certificate_secret_backend_factory,
            browser_session_factory=composition.browser_session_factory,
            operator_scope_ports=composition.operator_scope_ports,
            iva_remote_state_port=composition.iva_remote_state_port,
            notifications_ports=composition.notifications_ports,
            ports=composition.ports,
            filed_data_port=composition.filed_data_port,
            output_root=tmp_path,
            today=date(2026, 3, 15),
            dry_run=dry_run,
            discover=_composition_discovery(*pairs),
        ),
    )


def test_canonical_composition_preserves_every_discovered_pair_and_refusal(tmp_path: Path) -> None:
    run = _run_composition(_composition_pair("100"), _composition_pair("303"), tmp_path=tmp_path)

    assert [(pair.modelo, pair.ejercicio) for pair in run.pairs] == [("100", 2000), ("303", 2000)]
    assert all(pair.refused for pair in run.pairs)
    assert all(pair.failure_type == "LiveApplicationInputError" for pair in run.pairs)
    assert run.evidence_notices == ()


def test_canonical_composition_preserves_the_discovery_scoping_signal(tmp_path: Path) -> None:
    discovery = _composition_discovery(
        _composition_pair("303"),
        scoping_signal=RegisterScopingSignal.LIKELY_UNIVERSAL,
    )
    composition = _test_filed_history_composition(tmp_path)

    run = asyncio.run(
        pull_filed_history(
            certificate_secret_backend_factory=composition.certificate_secret_backend_factory,
            browser_session_factory=composition.browser_session_factory,
            operator_scope_ports=composition.operator_scope_ports,
            iva_remote_state_port=composition.iva_remote_state_port,
            notifications_ports=composition.notifications_ports,
            ports=composition.ports,
            filed_data_port=composition.filed_data_port,
            output_root=tmp_path,
            discover=discovery,
        )
    )

    assert run.scoping_signal is RegisterScopingSignal.LIKELY_UNIVERSAL


def test_canonical_composition_dry_run_preserves_scope_without_provenance(tmp_path: Path) -> None:
    pairs = (_composition_pair("100"), _composition_pair("303"))
    normal = _run_composition(*pairs, tmp_path=tmp_path)
    preview = _run_composition(*pairs, tmp_path=tmp_path, dry_run=True)

    assert [(pair.modelo, pair.ejercicio) for pair in preview.pairs] == [
        (pair.modelo, pair.ejercicio) for pair in normal.pairs
    ]
    assert preview.dry_run is True
    assert preview.sync_run_ref is None
    assert preview.iva_wallet_status == "not_attempted"
    assert preview.notificaciones_status == "not_attempted"


def test_canonical_composition_empty_discovery_short_circuits_truthfully(tmp_path: Path) -> None:
    discovery = _composition_discovery(scoping_signal=RegisterScopingSignal.LIKELY_NIF_SCOPED)
    composition = _test_filed_history_composition(tmp_path)
    run = asyncio.run(
        pull_filed_history(
            certificate_secret_backend_factory=composition.certificate_secret_backend_factory,
            browser_session_factory=composition.browser_session_factory,
            operator_scope_ports=composition.operator_scope_ports,
            iva_remote_state_port=composition.iva_remote_state_port,
            notifications_ports=composition.notifications_ports,
            ports=composition.ports,
            filed_data_port=composition.filed_data_port,
            output_root=tmp_path,
            discover=discovery,
        )
    )

    assert run.pairs == ()
    assert run.scoping_signal is RegisterScopingSignal.LIKELY_NIF_SCOPED
    assert run.stage_failures == ("discovery: no modelo/ejercicio pair to walk",)


def test_definition_declares_recorded_non_stoppable_execution(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=SyncRunRecordRepository,
            composition_factory=_test_filed_history_composition,
            browser_resources_factory=BrowserRuntimeResourceScope,
            pull=_local_pull(_DeterministicFiledHistoryDiscovery()),
            provider_preflight=lambda _profile_id, _operation: None,
        )

    assert definition.definition_id == FILED_HISTORY_OPERATION_DEFINITION_ID
    assert definition.request_type is FiledHistoryOperationRequest
    assert definition.capabilities.durability is OperationDurability.RECORDED
    assert definition.capabilities.cancellation is OperationCancellation.UNSUPPORTED
    assert definition.capabilities.deadline is OperationDeadline.ABSENT
    assert definition.capabilities.owned_resources == frozenset({OperationOwnedResource.PROCESS})


def test_supervisor_refuses_a_foreign_payload_profile_before_capture(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, ExitStack() as stack:
        authority_operation = stack.enter_context(bundled_indexed_authority().operation())
        discovery_entered = asyncio.Event()
        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=SyncRunRecordRepository,
            composition_factory=_test_filed_history_composition,
            browser_resources_factory=BrowserRuntimeResourceScope,
            pull=_local_pull(_DeterministicFiledHistoryDiscovery(entered=discovery_entered)),
            provider_preflight=lambda _profile_id, _operation: None,
        )
        journal = OperationJournalRepository(storage_root=tmp_path / "operations")
        supervisor = OperationSupervisor(
            authority_operation=authority_operation,
            registry=_registered_filed_history_definition(definition),
            journal=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=tmp_path / "operations"),
            operands=operation_secure_reference_repository(objects=profile.repository),
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        request = OperationRequest(
            definition_id=definition.definition_id,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=FiledHistoryOperationRequest(
                profile_id=UUID("22222222-2222-4222-8222-222222222222"),
                output_root=tmp_path / "filed",
                dry_run=True,
            ),
        )

        async def run() -> OperationPersistedSnapshot:
            operation_id = await supervisor.submit(request, operation_id="3" * 64)
            return await _run_to_terminal(supervisor, operation_id)

        terminal = asyncio.run(run())
        assert terminal.terminal_condition is OperationTerminalCondition.FAILED
        assert terminal.effect is OperationEffect.NONE
        assert not discovery_entered.is_set()


def test_supervisor_records_ordered_safe_progress_and_truthful_zero_effect(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, ExitStack() as stack:
        authority_operation = stack.enter_context(bundled_indexed_authority().operation())
        discovery_entered = asyncio.Event()
        release_discovery = asyncio.Event()
        discovery = _DeterministicFiledHistoryDiscovery(
            entered=discovery_entered,
            release=release_discovery,
        )
        taxpayer = TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime("GENERAL"))
        pull = _local_pull(discovery)
        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=SyncRunRecordRepository,
            composition_factory=_test_filed_history_composition,
            browser_resources_factory=BrowserRuntimeResourceScope,
            pull=pull,
            profile_resolver=lambda _operation: taxpayer,
            provider_preflight=lambda _profile_id, _operation: None,
        )
        journal = OperationJournalRepository(storage_root=tmp_path / "operations")
        leases = OperationLeaseFilesystemRepository(storage_root=tmp_path / "operations")
        operands = operation_secure_reference_repository(objects=profile.repository)
        supervisor = OperationSupervisor(
            authority_operation=authority_operation,
            registry=_registered_filed_history_definition(definition),
            journal=journal,
            event_stream=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        request = OperationRequest(
            definition_id=definition.definition_id,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=FiledHistoryOperationRequest(
                profile_id=UUID(profile.bucket_id),
                output_root=tmp_path / "filed",
                today=date(2026, 3, 15),
            ),
        )

        async def run():
            operation_id = await supervisor.submit(request, operation_id="3" * 64)
            start_task = asyncio.create_task(_run_to_terminal(supervisor, operation_id))
            # Admission and the executor's first phases do real journal I/O, so
            # the discovery barrier is awaited on time rather than on a count of
            # scheduler turns. A task that ends first surfaces its own failure.
            entered = asyncio.create_task(discovery_entered.wait())
            await asyncio.wait({entered, start_task}, timeout=10, return_when=asyncio.FIRST_COMPLETED)
            if not discovery_entered.is_set():
                entered.cancel()
                if start_task.done():
                    await start_task
                raise AssertionError("filed-history pull did not reach deterministic discovery")
            assert start_task.done() is False
            in_flight_events = (
                await asyncio.wait_for(
                    supervisor.replay(operation_id, 0, limit=100),
                    timeout=1,
                )
            ).events
            try:
                assert [event.phase_code for event in in_flight_events if event.kind is OperationEventKind.PHASE] == [
                    FILED_HISTORY_PHASE_PREFLIGHT,
                    FILED_HISTORY_PHASE_EXECUTION,
                    FILED_HISTORY_PHASE_DISCOVERY,
                ]
                with pytest.raises(ValueError, match="operation does not support cancellation"):
                    await supervisor.request_cancel(operation_id)
            finally:
                release_discovery.set()
            snapshot = await start_task
            assert snapshot.lifecycle is OperationLifecycle.TERMINAL
            assert snapshot.phase_code == FILED_HISTORY_PHASE_SETTLEMENT
            assert snapshot.effect is OperationEffect.NONE
            assert snapshot.execution_deadline is None
            assert snapshot.cleanup_deadline is None
            events = (await supervisor.replay(operation_id, 0, limit=100)).events
            result_ref = snapshot.terminal_receipt.result_ref if snapshot.terminal_receipt is not None else None
            result = await operands.resolve(result_ref, FiledHistoryOnboardingRun) if result_ref is not None else None
            return snapshot, events, result

        snapshot, events, result = asyncio.run(run())

    assert snapshot.identity.definition_id == FILED_HISTORY_OPERATION_DEFINITION_ID
    assert result is not None
    assert result.sync_run_ref is None
    assert snapshot.events[-1].code == "operation.terminal"
    assert [event.phase_code for event in events if event.kind is OperationEventKind.PHASE] == [
        FILED_HISTORY_PHASE_PREFLIGHT,
        FILED_HISTORY_PHASE_EXECUTION,
        FILED_HISTORY_PHASE_DISCOVERY,
        FILED_HISTORY_PHASE_IVA_WALLET,
        FILED_HISTORY_PHASE_NOTIFICATIONS,
        FILED_HISTORY_PHASE_RESULT,
        FILED_HISTORY_PHASE_CLEANUP,
        FILED_HISTORY_PHASE_SETTLEMENT,
    ]
    assert [
        (event.completed, event.total, event.unit_code) for event in events if event.kind is OperationEventKind.PROGRESS
    ] == [
        (0, 1, FILED_HISTORY_PAIR_PROGRESS_UNIT),
        (1, 1, FILED_HISTORY_PAIR_PROGRESS_UNIT),
    ]
    assert [event.code for event in events if event.kind is OperationEventKind.LOG] == [
        FILED_HISTORY_PAIR_REFUSAL_CODE,
        FILED_HISTORY_IVA_WALLET_REFUSAL_CODE,
        FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE,
    ]
    assert [event.effect for event in events if event.kind is OperationEventKind.EFFECT] == [
        OperationEffect.UNKNOWN,
        OperationEffect.NONE,
    ]
    assert discovery.profile is taxpayer


def test_supervisor_records_a_dry_run_with_no_effect(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, ExitStack() as stack:
        authority_operation = stack.enter_context(bundled_indexed_authority().operation())
        repository = SyncRunRecordRepository()
        sync_namespace_before = repository.secure_object_repository.namespace_payload_hashes(repository.namespace)
        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=lambda: repository,
            composition_factory=_test_filed_history_composition,
            browser_resources_factory=BrowserRuntimeResourceScope,
            pull=_routed_pull(_DeterministicFiledHistoryDiscovery(modelo="100", ejercicio=2025)),
            provider_preflight=lambda _profile_id, _operation: None,
        )
        journal = OperationJournalRepository(storage_root=tmp_path / "operations")
        leases = OperationLeaseFilesystemRepository(storage_root=tmp_path / "operations")
        operands = operation_secure_reference_repository(objects=profile.repository)
        supervisor = OperationSupervisor(
            authority_operation=authority_operation,
            registry=_registered_filed_history_definition(definition),
            journal=journal,
            event_stream=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        request = OperationRequest(
            definition_id=definition.definition_id,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=FiledHistoryOperationRequest(
                profile_id=UUID(profile.bucket_id),
                output_root=tmp_path / "filed",
                today=date(2026, 3, 15),
                dry_run=True,
            ),
        )
        assert request.payload.dry_run is True

        async def run():
            operation_id = await supervisor.submit(request, operation_id="4" * 64)
            snapshot = await _run_to_terminal(supervisor, operation_id)
            events = (await supervisor.replay(operation_id, 0, limit=100)).events
            receipt = snapshot.terminal_receipt
            assert receipt is not None
            reference = receipt.result_ref
            assert reference is not None
            result = await operands.resolve(reference, FiledHistoryOnboardingRun)
            return snapshot, events, result

        snapshot, events, result = asyncio.run(run())
        sync_namespace_after = repository.secure_object_repository.namespace_payload_hashes(repository.namespace)

    assert snapshot.lifecycle is OperationLifecycle.TERMINAL
    assert snapshot.effect is OperationEffect.NONE
    assert result.dry_run is True
    assert result.sync_run_ref is None
    assert sync_namespace_after == sync_namespace_before == {}
    assert result.pairs[0].walk_attempted is True
    assert result.pairs[0].walk_completed is True
    assert result.pairs[0].row_count == 2
    assert result.pairs[0].captured_count == 0
    assert result.pairs[0].is_a_genuine_empty is False
    assert all(
        event.effect is not OperationEffect.UNKNOWN for event in events if event.kind is OperationEventKind.EFFECT
    )
    assert [
        (event.completed, event.total, event.unit_code) for event in events if event.kind is OperationEventKind.PROGRESS
    ] == [
        (0, 1, FILED_HISTORY_PAIR_PROGRESS_UNIT),
        (1, 1, FILED_HISTORY_PAIR_PROGRESS_UNIT),
        (0, 2, FILED_HISTORY_DECLARATION_PROGRESS_UNIT),
        (1, 2, FILED_HISTORY_DECLARATION_PROGRESS_UNIT),
        (2, 2, FILED_HISTORY_DECLARATION_PROGRESS_UNIT),
    ]


def test_supervisor_receipt_joins_the_exact_encrypted_child_after_settlement(tmp_path: Path) -> None:
    """Successful settlement preserves the writer-owned child identity end to end.

    The top-level ``result_ref`` is now always the stored-operand reference
    for the full settled run (never substituted with the encrypted child's
    own key), so one typed public door can resolve it regardless of whether
    a sync-run child exists. Child provenance travels as the run's own
    ``sync_run_ref`` field and is independently loadable through the
    sync-run repository.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, ExitStack() as stack:
        authority_operation = stack.enter_context(bundled_indexed_authority().operation())
        repository = SyncRunRecordRepository()
        operands = operation_secure_reference_repository(objects=profile.repository)

        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=lambda: repository,
            composition_factory=_test_filed_history_composition,
            browser_resources_factory=BrowserRuntimeResourceScope,
            pull=_routed_pull(_DeterministicFiledHistoryDiscovery(modelo="100", ejercicio=2025)),
            provider_preflight=lambda _profile_id, _operation: None,
        )
        durable_root = tmp_path / "terminal-operations"
        journal = OperationJournalRepository(storage_root=durable_root)
        leases = OperationLeaseFilesystemRepository(storage_root=durable_root)
        supervisor = OperationSupervisor(
            authority_operation=authority_operation,
            registry=_registered_filed_history_definition(definition),
            journal=journal,
            event_stream=journal,
            leases=leases,
            operands=operands,
            owner_id="5" * 64,
            lease_token_factory=lambda: "6" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        request = OperationRequest(
            definition_id=definition.definition_id,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=FiledHistoryOperationRequest(
                profile_id=UUID(profile.bucket_id),
                output_root=tmp_path / "terminal-filed",
                today=date(2026, 3, 15),
            ),
        )

        async def run():
            operation_id = await supervisor.submit(request, operation_id="7" * 64)
            terminal = await _run_to_terminal(supervisor, operation_id)
            reloaded = await journal.load(operation_id)
            replay = await journal.read_after(operation_id, 0, limit=100)
            assert terminal.terminal_receipt is not None
            assert terminal.terminal_receipt.result_ref is not None
            settled_run = await operands.resolve(terminal.terminal_receipt.result_ref, FiledHistoryOnboardingRun)
            return terminal, reloaded, replay.events, settled_run

        terminal, reloaded, events, settled_run = asyncio.run(run())

        receipt = terminal.terminal_receipt
        assert receipt is not None
        reference = receipt.result_ref
        assert reference is not None
        assert settled_run.sync_run_ref is not None
        stored = repository.load(settled_run.sync_run_ref)
        assert stored is not None
        assert repository.secure_object_repository.namespace_payload_hashes(repository.namespace)
        assert repository.extract_identifier(stored) == settled_run.sync_run_ref
        assert stored.bucket_id == profile.bucket_id
        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is OperationEffect.PARTIAL
        assert reloaded == terminal
        phases = [event for event in events if event.kind is OperationEventKind.PHASE]
        cleanup = next(event for event in phases if event.phase_code == FILED_HISTORY_PHASE_CLEANUP)
        settlement = next(event for event in phases if event.phase_code == FILED_HISTORY_PHASE_SETTLEMENT)
        terminal_event = next(event for event in events if event.kind is OperationEventKind.TERMINAL)
        assert cleanup.sequence < settlement.sequence < terminal_event.sequence
        assert terminal_event.receipt.result_ref == reference


async def _history_accounting_projection_roundtrips(
    operands: OperationSecureReferenceStore,
    registration: OperationPublicDefinitionRegistrationV1,
    receipt: OperationTerminalReceipt,
) -> tuple[FiledHistoryPublicResultV1, ...]:
    """Check secure scalar accounting projections without claiming acquisition."""
    assert registration.result_projector is not None
    projections: list[FiledHistoryPublicResultV1] = []
    for dry_run, attempted, completed, rows, reached, captured in (
        (True, True, True, 2, 2, 0),
        (True, False, False, 0, 0, 0),
        (False, True, True, 2, 2, 2),
    ):
        pair = FiledHistoryPairOutcome(
            modelo="303",
            ejercicio=2025,
            signals=(FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,),
            walk_attempted=attempted,
            walk_completed=completed,
            row_count=rows,
            reached_count=reached,
            captured_count=captured,
        )
        run = FiledHistoryOnboardingRun(pairs=(pair,), dry_run=dry_run, reached_count=reached, captured_count=captured)
        reference = await operands.put(run, written_at=_NOW)
        restored = await operands.resolve(reference, FiledHistoryOnboardingRun)
        public = registration.result_projector(restored, receipt)
        wire = FiledHistoryPublicResultV1.model_validate_json(public.model_dump_json())
        projected_pair = wire.pairs[0]
        assert (projected_pair.walk_attempted, projected_pair.walk_completed) == (attempted, completed)
        assert (projected_pair.row_count, projected_pair.reached_count, projected_pair.captured_count) == (
            rows,
            reached,
            captured,
        )
        assert restored.genuinely_empty_pairs == ()
        projections.append(wire)
    return tuple(projections)


def test_frontend_projects_the_public_result_without_the_private_type(tmp_path: Path) -> None:
    """A frontend resolves evidence, IVA wallet, notificaciones and provenance
    through the public result-projection door alone.

    This function's own body never names the private
    ``FiledHistoryOnboardingRun`` type -- checked below by AST inspection of
    this very function -- yet still recovers every fact
    ``FiledHistoryPublicResultV1`` declares, resolved purely through
    ``OperationResultProjectionService`` and the operation's public schema
    identity.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, ExitStack() as stack:
        authority_operation = stack.enter_context(bundled_indexed_authority().operation())
        repository = SyncRunRecordRepository()
        operands = operation_secure_reference_repository(objects=profile.repository)
        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=lambda: repository,
            composition_factory=_test_filed_history_composition,
            browser_resources_factory=BrowserRuntimeResourceScope,
            pull=_routed_pull(_DeterministicFiledHistoryDiscovery(modelo="100", ejercicio=2025)),
            provider_preflight=lambda _profile_id, _operation: None,
        )
        registry = _registered_filed_history_definition(definition)
        durable_root = tmp_path / "result-projection-operations"
        journal = OperationJournalRepository(storage_root=durable_root)
        leases = OperationLeaseFilesystemRepository(storage_root=durable_root)
        supervisor = OperationSupervisor(
            authority_operation=authority_operation,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=leases,
            operands=operands,
            owner_id="8" * 64,
            lease_token_factory=lambda: "9" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        request = OperationRequest(
            definition_id=definition.definition_id,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=FiledHistoryOperationRequest(
                profile_id=UUID(profile.bucket_id),
                output_root=tmp_path / "result-projection-filed",
                today=date(2026, 3, 15),
            ),
        )
        result_service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)

        async def run():
            operation_id = await supervisor.submit(request, operation_id="a" * 64)
            terminal = await _run_to_terminal(supervisor, operation_id)
            contract = registry.lookup_public_contract(definition.definition_id)
            assert contract.result_schema is not None
            resolved = await result_service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                FiledHistoryPublicResultV1,
            )
            assert terminal.terminal_receipt is not None
            roundtrips = await _history_accounting_projection_roundtrips(
                operands, registry.lookup_public_registration(definition.definition_id), terminal.terminal_receipt
            )
            return resolved, roundtrips

        resolved, roundtrips = asyncio.run(run())

        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        projection = resolved.projection
        assert projection.iva_wallet_status
        assert projection.notificaciones_status
        assert projection.sync_run_ref is not None
        assert isinstance(projection.evidence_notices, tuple)
        assert isinstance(projection.pairs, tuple) and projection.pairs
        assert projection.pairs[0].refused is True
        assert projection.pairs[0].failure_type
        assert projection.pairs[0].walk_attempted is True
        assert projection.pairs[0].walk_completed is True
        assert projection.pairs[0].row_count == 2
        assert projection.pairs[0].reached_count == projection.reached_count
        assert projection.pairs[0].captured_count == projection.captured_count
        preview, unwalked, persisted = roundtrips
        assert (preview.pairs[0].row_count, preview.captured_count) == (2, 0)
        assert unwalked.pairs[0].walk_completed is False
        assert (persisted.pairs[0].row_count, persisted.captured_count) == (2, 2)

    source = textwrap.dedent(inspect.getsource(test_frontend_projects_the_public_result_without_the_private_type))
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "FiledHistoryOnboardingRun" not in names


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
                        walk_attempted=True,
                        walk_completed=False,
                        reached_count=0,
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
    assert settled_filed_history_effect(run) is expected


def test_filed_history_operation_contract_has_one_public_defining_module() -> None:
    """The operation contract resolves identically from its one public owner."""
    operation = importlib.import_module("...application.live.filed_history_operation", package=__package__)
    definition = build_filed_history_operation_definition(
        sync_run_repository_factory=SyncRunRecordRepository,
        composition_factory=_test_filed_history_composition,
        browser_resources_factory=BrowserRuntimeResourceScope,
    )

    assert FILED_HISTORY_OPERATION_DEFINITION_ID == "live.filed-history.pull"
    assert definition.definition_id == FILED_HISTORY_OPERATION_DEFINITION_ID
    assert definition.request_type is FiledHistoryOperationRequest
    assert definition.result_type is FiledHistoryOnboardingRun
    assert definition.executor_factory.request_type is FiledHistoryOperationRequest
    assert definition.executor_factory.executor_type.__module__.endswith(".filed_history_operation")
    assert definition.executor_factory.build().__class__.__module__.endswith(".filed_history_operation")
    assert build_filed_history_operation_definition.__module__.endswith(".filed_history_operation")
    assert FiledHistoryOperationRequest.__module__.endswith(".filed_history_operation")
    assert operation.FILED_HISTORY_OPERATION_DEFINITION_ID is FILED_HISTORY_OPERATION_DEFINITION_ID
    assert operation.FiledHistoryOperationRequest is FiledHistoryOperationRequest
    assert operation.build_filed_history_operation_definition is build_filed_history_operation_definition
    assert operation.build_filed_history_operation_registration is build_filed_history_operation_registration


def test_public_registration_uses_a_strict_profile_bound_request_schema(tmp_path: Path) -> None:
    """The public request binds the profile without carrying taxpayer facts."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=SyncRunRecordRepository,
            composition_factory=_test_filed_history_composition,
            browser_resources_factory=BrowserRuntimeResourceScope,
        )
        registration = build_filed_history_operation_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))

    request_schema = registration.schema_bindings[0].model_type.model_json_schema(mode="validation")

    assert registry.lookup_public_registration(definition.definition_id) is registration
    assert tuple(request_schema["properties"]) == ("profile_id", "output_root", "today", "limit", "dry_run")
    assert "TaxpayerProfile" not in request_schema.get("$defs", {})


def test_filed_history_access_requires_whole_profile_commit_and_result_disclosure(tmp_path: Path) -> None:
    profile_id = UUID("11111111-1111-4111-8111-111111111111")
    definition = build_filed_history_operation_definition(
        sync_run_repository_factory=SyncRunRecordRepository,
        composition_factory=_test_filed_history_composition,
        browser_resources_factory=BrowserRuntimeResourceScope,
    )
    registration = build_filed_history_operation_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = OperationRequest[BaseModel](
        definition_id=definition.definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        payload=FiledHistoryOperationRequest(profile_id=profile_id, output_root=tmp_path / "filed"),
    )

    def context(action: AccessAction, admitted_request=None) -> OperationAccessContext:
        return OperationAccessContext(
            profile_id=profile_id,
            destination_id=uuid4(),
            action=action,
            frontend=OperationFrontendProjection.CLI,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
            admitted_request=admitted_request,
        )

    submitted = resolve_operation_access(registry=registry, request=request, context=context(AccessAction.SUBMIT))
    assert submitted.request.periods == frozenset()
    assert submitted.request.period_independent
    assert submitted.policy.requires_all_periods
    assert AccessAction.COMMIT in submitted.policy.actions
    finite_scope = AccessScope(
        operations=frozenset({definition.definition_id}),
        actions=submitted.policy.actions,
        disclosures=frozenset(),
        periods=frozenset({Period.from_year_and_code(2025, "1T")}),
        allow_period_independent=True,
        allow_delegation=False,
    )
    finite_refusal = operation_scope_refusal(request=submitted.request, policy=submitted.policy, scope=finite_scope)
    assert finite_refusal is not None and finite_refusal.code is AccessDenialCode.PERIOD_DENIED
    no_commit_scope = finite_scope.model_copy(
        update={"periods": None, "actions": finite_scope.actions - {AccessAction.COMMIT}}
    )
    commit_request = submitted.request.model_copy(update={"action": AccessAction.COMMIT})
    commit_refusal = operation_scope_refusal(request=commit_request, policy=submitted.policy, scope=no_commit_scope)
    assert commit_refusal is not None and commit_refusal.code is AccessDenialCode.OPERATION_DENIED
    committed = resolve_operation_access(
        registry=registry, request=request, context=context(AccessAction.COMMIT, submitted.request)
    )
    assert committed.request.periods == frozenset()
    disclosed = resolve_operation_access(
        registry=registry, request=request, context=context(AccessAction.RESULT, submitted.request)
    )
    assert {permission.category for permission in disclosed.policy.disclosures} == {DisclosureCategory.TAX_VALUES}

    foreign = request.model_copy(update={"subject_ref": profile_operation_subject(str(uuid4()))})
    with pytest.raises(ProfileAccessRefusedError) as refusal:
        resolve_operation_access(registry=registry, request=foreign, context=context(AccessAction.SUBMIT))
    assert refusal.value.reason is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.parametrize("attached_primary", [False, True], ids=["direct-cleanup", "attached-primary"])
@pytest.mark.parametrize("persistent_failure", [False, True], ids=["released", "unsettled"])
def test_supervisor_retains_filed_provider_cleanup_before_terminal_settlement(
    tmp_path: Path, attached_primary: bool, persistent_failure: bool
) -> None:
    """Failed provider owners must settle before the real supervisor publishes a receipt."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, ExitStack() as stack:
        authority_operation = stack.enter_context(bundled_indexed_authority().operation())
        primary = ValueError("synthetic filed provider failure")
        failures: list[BaseException] = []

        class ProviderOwner:
            """Expose the real cleanup transfer with an independently controlled release."""

            def __init__(self) -> None:
                self.calls = 0
                self.released = False
                self.retry_entered = asyncio.Event()
                self.allow_retry = asyncio.Event()
                self.failure = OSError("synthetic provider close failure")
                self.fail_settlement = persistent_failure

            async def close(self) -> None:
                self.calls += 1
                if self.calls <= 2:
                    raise self.failure
                self.retry_entered.set()
                await asyncio.wait_for(self.allow_retry.wait(), timeout=10)
                if self.fail_settlement:
                    raise self.failure
                self.released = True

        owner = ProviderOwner()

        async def pull(
            payload: FiledHistoryOperationRequest,
            taxpayer: TaxpayerProfile | None,
            repository: SyncRunRecordRepositoryProtocol,
            events: OperationEventEmitter,
            ports: FiledObservationPersistencePorts,
            filed_data_port: FiledDataCapturePort,
            iva_remote_state_port: IvaRemoteStatePort,
            notifications_ports: NotificationsPorts,
            certificate_secret_backend_factory: CertificateSecretBackendFactory,
            browser_session_factory: BrowserSessionFactoryPort,
            operator_scope_ports: OperatorScopePorts,
            effect_guard: FiledEffectGuard,
            on_session_write: SessionWriteReporter,
        ) -> FiledHistoryOnboardingRun:
            try:
                if attached_primary:
                    try:
                        raise primary
                    finally:
                        await close_async_resources(owner, task_name="filed-provider-body-close", close_attempts=2)
                await close_async_resources(
                    owner, task_name="filed-provider-close", close_attempts=2, primary_error=None
                )
            except BaseException as error:
                failures.append(error)
                raise
            raise AssertionError("the provider's original cleanup unexpectedly succeeded")

        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=SyncRunRecordRepository,
            composition_factory=_test_filed_history_composition,
            browser_resources_factory=BrowserRuntimeResourceScope,
            pull=pull,
            profile_resolver=lambda _operation: None,
            provider_preflight=lambda _profile_id, _operation: None,
        )
        journal = OperationJournalRepository(storage_root=tmp_path / "operations")
        operands = operation_secure_reference_repository(objects=profile.repository)
        supervisor = OperationSupervisor(
            authority_operation=authority_operation,
            registry=_registered_filed_history_definition(definition),
            journal=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=tmp_path / "operations"),
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        request = OperationRequest(
            definition_id=definition.definition_id,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=FiledHistoryOperationRequest(
                profile_id=UUID(profile.bucket_id), output_root=tmp_path / "filed", today=date(2026, 3, 15)
            ),
        )

        async def run() -> None:
            operation_id = await supervisor.submit(request, operation_id="5" * 64)
            settlement = asyncio.create_task(_run_to_terminal(supervisor, operation_id))
            entered = asyncio.create_task(owner.retry_entered.wait())
            try:
                await asyncio.wait({entered, settlement}, timeout=10, return_when=asyncio.FIRST_COMPLETED)
                if not owner.retry_entered.is_set():
                    if settlement.done():
                        await settlement
                    raise AssertionError("the original failed provider owner was not adopted for settlement")
                assert owner.calls == 3
                assert owner.released is False
                assert settlement.done() is False
                in_flight = await supervisor.inspect(operation_id)
                assert in_flight.lifecycle is OperationLifecycle.RUNNING
                assert in_flight.effect is OperationEffect.UNKNOWN
                assert in_flight.terminal_receipt is None
                assert len(failures) == 1
                if attached_primary:
                    assert failures[0] is primary
                    original_cleanup = primary.__dict__["async_cleanup_error"]
                else:
                    original_cleanup = failures[0]
                assert isinstance(original_cleanup, AsyncResourceCleanupError)
                assert original_cleanup.resources == (owner,)
            finally:
                owner.allow_retry.set()
                if not entered.done():
                    entered.cancel()
                await asyncio.gather(entered, return_exceptions=True)

            if persistent_failure:
                with pytest.raises(OperationUnsettledError) as unsettled:
                    await asyncio.wait_for(settlement, timeout=10)
                retained = unsettled.value.__cause__
                assert isinstance(retained, AsyncResourceCleanupError)
                assert retained.resources == (owner,)
                pending = await supervisor.inspect(operation_id)
                assert pending.lifecycle is OperationLifecycle.RUNNING
                assert pending.effect is OperationEffect.UNKNOWN
                assert pending.terminal_receipt is None
                assert owner.calls == 3
                assert owner.released is False
                owner.fail_settlement = False
                await retained.retry_cleanup()
                assert owner.calls == 4
                assert owner.released is True
                assert (await supervisor.inspect(operation_id)).terminal_receipt is None
            else:
                terminal = await asyncio.wait_for(settlement, timeout=10)
                assert terminal.lifecycle is OperationLifecycle.TERMINAL
                assert terminal.terminal_condition is OperationTerminalCondition.FAILED
                assert terminal.effect is OperationEffect.UNKNOWN
                assert terminal.terminal_receipt is not None
                assert owner.calls == 3
                assert owner.released is True

        asyncio.run(run())


def test_canonical_composition_retains_cartesian_only_planning_refusals(tmp_path: Path) -> None:
    """Actual planning preserves every refusal without adding discovery signals."""
    first = _composition_pair("100")
    second = FiledHistoryDiscoveryPair(
        modelo="303",
        ejercicio=2001,
        signals=(FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,),
    )
    run = _run_composition(first, second, tmp_path=tmp_path, dry_run=True)

    assert [(pair.modelo, pair.ejercicio) for pair in run.pairs] == [("100", 2000), ("303", 2001)]
    assert len(run.refused_pairs) == 2 and all(pair.failure_type == "LiveApplicationInputError" for pair in run.pairs)
    assert all(pair.signals == (FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,) for pair in run.pairs)
    # The same real rectangular planner refuses the two additional coordinates.
    # Their facts must survive the discovery-only join without fabricated rows.
    assert run.stage_failures == (
        "filed_capture: modelo 100 ejercicio 2001: LiveApplicationInputError",
        "filed_capture: modelo 303 ejercicio 2000: LiveApplicationInputError",
    )
    assert run.reached_count == 0 and run.captured_count == 0 and run.sync_run_ref is None
    assert settled_filed_history_effect(run) is OperationEffect.NONE
