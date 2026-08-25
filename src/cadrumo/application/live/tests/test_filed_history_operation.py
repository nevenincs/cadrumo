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
    DeclaracionesRegisterSession,
    FiledDeclarationAvailability,
    FiledDeclarationAvailabilityReport,
)
from ....adapters.persistence.operations import (
    OperationJournalRepository,
    OperationLeaseFilesystemRepository,
    operation_secure_reference_repository,
)
from ....adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from ....core import (
    FiledHistoryDiscoverySignal,
    OperationCancellation,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationEventKind,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....tests.offline_aeat_register import aeat_sede_fixture, open_routed_declarations_register
from ....tests.secure_sql import isolated_runtime_profile
from ...operations import (
    OperationRegistry,
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
from .. import (
    build_filed_history_operation_registration as public_build_filed_history_operation_registration,
)
from .._filed_data_capture import (
    FILED_HISTORY_DECLARATION_PROGRESS_UNIT,
    ExpectedFiledDeclarationGrid,
    FiledHistoryDiscoveryPair,
    FiledHistoryDiscoveryPort,
    FiledHistoryDiscoveryReport,
    FiledHistoryOnboardingRun,
    FiledHistoryPairOutcome,
    filed_history_discovery_report,
    pull_filed_history,
)
from .._filed_history_operation import (
    FILED_HISTORY_IVA_WALLET_REFUSAL_CODE,
    FILED_HISTORY_NOTIFICATIONS_REFUSAL_CODE,
    FILED_HISTORY_OPERATION_DEFINITION_ID,
    FILED_HISTORY_PAIR_PROGRESS_UNIT,
    FILED_HISTORY_PAIR_REFUSAL_CODE,
    FILED_HISTORY_PHASE_CLEANUP,
    FILED_HISTORY_PHASE_DISCOVERY,
    FILED_HISTORY_PHASE_EXECUTION,
    FILED_HISTORY_PHASE_IVA_WALLET,
    FILED_HISTORY_PHASE_NOTIFICATIONS,
    FILED_HISTORY_PHASE_PREFLIGHT,
    FILED_HISTORY_PHASE_RESULT,
    FILED_HISTORY_PHASE_SETTLEMENT,
    FiledHistoryOperationRequest,
    _settled_effect,
    build_filed_history_operation_definition,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 24, 20, tzinfo=UTC)


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
        profile: TaxpayerProfile | None = None,
        today: date | None = None,
    ) -> FiledHistoryDiscoveryReport:
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
    *,
    register: DeclaracionesRegisterSession | None = None,
):
    """Bind the canonical composition to deterministic discovery/register inputs."""

    async def pull(payload, profile, repository, events):
        return await pull_filed_history(
            output_root=payload.output_root,
            profile=profile,
            today=payload.today,
            limit=payload.limit,
            dry_run=payload.dry_run,
            discover=discover,
            register=register,
            sync_run_repository=repository,
            events=events,
        )

    return pull


def _registered_filed_history_definition(definition):
    """Enroll the live definition through its public registration contract."""
    return OperationRegistry(
        definitions=(definition,),
        public_registrations=(public_build_filed_history_operation_registration(definition),),
    )


def _routed_pull(discover: FiledHistoryDiscoveryPort):
    """Run canonical composition through the real locally routed register adapter."""
    document = aeat_sede_fixture("declaraciones-register-form-complete-synthetic")

    async def pull(payload, profile, repository, events):
        async with open_routed_declarations_register((document,), ver_click_timeout_ms=1500) as (register, routed):
            run = await pull_filed_history(
                output_root=payload.output_root,
                profile=profile,
                today=payload.today,
                limit=payload.limit,
                dry_run=payload.dry_run,
                discover=discover,
                register=register,
                sync_run_repository=repository,
                events=events,
            )
            assert not routed.pending
            return run

    return pull


def _composition_discovery(*pairs: FiledHistoryDiscoveryPair) -> FiledHistoryDiscoveryPort:
    """Supply strict discovery facts to the canonical composition boundary."""

    async def discover(
        *,
        profile: TaxpayerProfile | None = None,
        today: date | None = None,
    ) -> FiledHistoryDiscoveryReport:
        del profile, today
        return FiledHistoryDiscoveryReport(
            pairs=pairs,
            register_options_read=True,
            profile_year_span_determined=False,
        )

    return discover


def _composition_pair(modelo: str = "100") -> FiledHistoryDiscoveryPair:
    return FiledHistoryDiscoveryPair(
        modelo=modelo,
        ejercicio=2000,
        signals=(FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,),
    )


def _run_composition(*pairs: FiledHistoryDiscoveryPair, tmp_path: Path, dry_run: bool = False):
    return asyncio.run(
        pull_filed_history(
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
    run = _run_composition(tmp_path=tmp_path)

    assert run.pairs == ()
    assert run.stage_failures == ("discovery: no modelo/ejercicio pair to walk",)


def test_definition_declares_recorded_non_stoppable_execution(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=SyncRunRecordRepository,
            pull=_local_pull(_DeterministicFiledHistoryDiscovery()),
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
        discovery = _DeterministicFiledHistoryDiscovery(
            entered=discovery_entered,
            release=release_discovery,
        )
        taxpayer = TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime.GENERAL)
        pull = _local_pull(discovery)
        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=SyncRunRecordRepository,
            pull=pull,
            profile_resolver=lambda: taxpayer,
        )
        journal = OperationJournalRepository(storage_root=tmp_path / "operations")
        leases = OperationLeaseFilesystemRepository(storage_root=tmp_path / "operations")
        operands = operation_secure_reference_repository(objects=profile.repository)
        supervisor = OperationSupervisor(
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
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = SyncRunRecordRepository()
        sync_namespace_before = repository.secure_object_repository.namespace_payload_hashes(repository.namespace)
        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=lambda: repository,
            pull=_routed_pull(_DeterministicFiledHistoryDiscovery(modelo="100", ejercicio=2025)),
        )
        journal = OperationJournalRepository(storage_root=tmp_path / "operations")
        leases = OperationLeaseFilesystemRepository(storage_root=tmp_path / "operations")
        operands = operation_secure_reference_repository(objects=profile.repository)
        supervisor = OperationSupervisor(
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
            events = (await supervisor.replay(operation_id, 0, limit=100)).events
            receipt = snapshot.terminal_receipt
            assert receipt is not None
            result = await operands.resolve(receipt.result_ref, FiledHistoryOnboardingRun)
            return snapshot, events, result

        snapshot, events, result = asyncio.run(run())
        sync_namespace_after = repository.secure_object_repository.namespace_payload_hashes(repository.namespace)

    assert snapshot.lifecycle is OperationLifecycle.TERMINAL
    assert snapshot.effect is OperationEffect.NONE
    assert result.dry_run is True
    assert result.sync_run_ref is None
    assert sync_namespace_after == sync_namespace_before == {}
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
    """Successful settlement preserves the writer-owned child identity end to end."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = SyncRunRecordRepository()

        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=lambda: repository,
            pull=_routed_pull(_DeterministicFiledHistoryDiscovery(modelo="100", ejercicio=2025)),
        )
        durable_root = tmp_path / "terminal-operations"
        journal = OperationJournalRepository(storage_root=durable_root)
        leases = OperationLeaseFilesystemRepository(storage_root=durable_root)
        supervisor = OperationSupervisor(
            registry=_registered_filed_history_definition(definition),
            journal=journal,
            event_stream=journal,
            leases=leases,
            operands=operation_secure_reference_repository(objects=profile.repository),
            owner_id="5" * 64,
            lease_token_factory=lambda: "6" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        request = OperationRequest(
            definition_id=definition.definition_id,
            subject_ref=profile.bucket_id,
            payload=FiledHistoryOperationRequest(
                output_root=tmp_path / "terminal-filed",
                today=date(2026, 3, 15),
            ),
        )

        async def run():
            operation_id = await supervisor.submit(request, operation_id="7" * 64)
            terminal = await supervisor.start(operation_id)
            reloaded = await journal.load(operation_id)
            replay = await journal.read_after(operation_id, 0, limit=100)
            return terminal, reloaded, replay.events

        terminal, reloaded, events = asyncio.run(run())

        receipt = terminal.terminal_receipt
        assert receipt is not None
        reference = receipt.result_ref
        assert reference is not None
        stored = repository.load(reference)
        assert stored is not None
        assert repository.secure_object_repository.namespace_payload_hashes(repository.namespace)
        assert repository.extract_identifier(stored) == reference
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
        sync_run_repository_factory=SyncRunRecordRepository,
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
    assert live.build_filed_history_operation_registration is public_build_filed_history_operation_registration


def test_public_registration_uses_a_strict_profile_free_request_schema(tmp_path: Path) -> None:
    """The public request resolves taxpayer facts from the active subject, not JSON."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        definition = public_build_filed_history_operation_definition(
            sync_run_repository_factory=SyncRunRecordRepository,
        )
        registration = public_build_filed_history_operation_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))

    request_schema = registration.schema_bindings[0].model_type.model_json_schema(mode="validation")

    assert registry.lookup_public_registration(definition.definition_id) is registration
    assert tuple(request_schema["properties"]) == ("output_root", "today", "limit", "dry_run")
    assert "TaxpayerProfile" not in request_schema.get("$defs", {})


def test_active_profile_resolution_uses_the_workflow_public_facade() -> None:
    """The live operation must not reach through workflow's persistence module."""
    module = importlib.import_module(".._filed_history_operation", package=__package__)
    source = Path(module.__file__).read_text(encoding="utf-8")

    assert "from ..workflow import workflow_state_repository" in source
    assert "from ..workflow._persistence import workflow_state_repository" not in source


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
        "build_filed_history_operation_registration",
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
