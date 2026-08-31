"""Canonical conformance proof for the recorded filed-history operation."""

from __future__ import annotations

import ast
import asyncio
import importlib
import inspect
import subprocess
import sys
import textwrap
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.sede.declarations import DeclaracionesRegisterSession
from ....adapters.outbound.aeat.sede.schema import FiledDeclarationAvailability, FiledDeclarationAvailabilityReport
from ....adapters.persistence.operations.journal import OperationJournalRepository
from ....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ....adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from ....core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from ....core.operations import (
    OperationCancellation,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationEventKind,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....tests.offline_aeat_register import aeat_sede_fixture, open_routed_declarations_register
from ....tests.secure_sql import isolated_runtime_profile
from ...operations.frontend_contracts import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...operations.models import OperationRequest
from ...operations.projection_services import OperationResultProjectionService
from ...operations.registry import OperationRegistry
from ...operations.supervisor import OperationSupervisor
from ..filed_data_capture import (
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
from ..filed_history_operation import (
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
    build_filed_history_operation_registration,
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
        public_registrations=(build_filed_history_operation_registration(definition),),
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
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = SyncRunRecordRepository()
        operands = operation_secure_reference_repository(objects=profile.repository)

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
            operands=operands,
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
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = SyncRunRecordRepository()
        operands = operation_secure_reference_repository(objects=profile.repository)
        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=lambda: repository,
            pull=_routed_pull(_DeterministicFiledHistoryDiscovery(modelo="100", ejercicio=2025)),
        )
        registry = _registered_filed_history_definition(definition)
        durable_root = tmp_path / "result-projection-operations"
        journal = OperationJournalRepository(storage_root=durable_root)
        leases = OperationLeaseFilesystemRepository(storage_root=durable_root)
        supervisor = OperationSupervisor(
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
            subject_ref=profile.bucket_id,
            payload=FiledHistoryOperationRequest(
                output_root=tmp_path / "result-projection-filed", today=date(2026, 3, 15)
            ),
        )
        result_service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)

        async def run():
            operation_id = await supervisor.submit(request, operation_id="a" * 64)
            terminal = await supervisor.start(operation_id)
            contract = registry.lookup_public_contract(definition.definition_id)
            assert contract.result_schema is not None
            resolved = await result_service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=operation_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                )
            )
            return resolved

        resolved = asyncio.run(run())

        assert isinstance(resolved, OperationResultProjectionSuccessV1)
        projection = resolved.projection
        assert projection.iva_wallet_status
        assert projection.notificaciones_status
        assert projection.sync_run_ref is not None
        assert isinstance(projection.evidence_notices, tuple)
        assert isinstance(projection.pairs, tuple) and projection.pairs
        assert projection.pairs[0].refused is True
        assert projection.pairs[0].failure_type
        assert isinstance(projection.selection_rows, tuple)

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


def test_filed_history_operation_contract_has_one_public_defining_module() -> None:
    """The operation contract resolves identically from its one public owner."""
    operation = importlib.import_module("..filed_history_operation", package=__package__)
    definition = build_filed_history_operation_definition(
        sync_run_repository_factory=SyncRunRecordRepository,
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


def test_public_registration_uses_a_strict_profile_free_request_schema(tmp_path: Path) -> None:
    """The public request resolves taxpayer facts from the active subject, not JSON."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        definition = build_filed_history_operation_definition(
            sync_run_repository_factory=SyncRunRecordRepository,
        )
        registration = build_filed_history_operation_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))

    request_schema = registration.schema_bindings[0].model_type.model_json_schema(mode="validation")

    assert registry.lookup_public_registration(definition.definition_id) is registration
    assert tuple(request_schema["properties"]) == ("output_root", "today", "limit", "dry_run")
    assert "TaxpayerProfile" not in request_schema.get("$defs", {})


def test_active_profile_resolution_uses_the_workflow_persistence_definition() -> None:
    """The live operation imports the repository from its defining module."""
    module = importlib.import_module("..filed_history_operation", package=__package__)
    module_file = module.__file__
    assert module_file is not None
    source = Path(module_file).read_text(encoding="utf-8")

    assert "from cadrumo.application.workflow.persistence import workflow_state_repository" in source
    assert "from ..workflow import workflow_state_repository" not in source


def test_live_package_is_inert_and_public_leaves_have_no_private_remnants() -> None:
    """The package owns no facade contract and its source tree names no retired leaf."""
    root = Path(__file__).resolve().parents[5]
    live_root = root / "src" / "cadrumo" / "application" / "live"

    assert not tuple(path for path in live_root.glob("_*.py") if path.name != "__init__.py")
    for source_path in (root / "src").rglob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        assert "cadrumo.application.live._" not in source, source_path
        tree = ast.parse(source, filename=str(source_path))
        assert not any(
            isinstance(node, ast.ImportFrom) and node.module in {"cadrumo.application.live", "application.live"}
            for node in ast.walk(tree)
        ), source_path


def test_importing_live_keeps_the_package_boundary_inert() -> None:
    """Importing only the package binds neither a facade nor a public leaf."""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and inline code under test
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import sys
                import cadrumo.application.live

                assert "cadrumo.application.live.filed_history_operation" not in sys.modules
                assert cadrumo.application.live.__all__ == ()
                """,
            ),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
