"""Registered exact-profile capture contracts for expedientes snapshots."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.live import expedientes as expedientes_module
from ...application.live.expedientes import PersistedExpedientesSnapshot
from ...application.live.expedientes_capture_operation import (
    EXPEDIENTES_BULK_CAPTURE_DEFINITION_ID,
    EXPEDIENTES_SINGLE_CAPTURE_DEFINITION_ID,
    ExpedientesBulkCapturePublicResultV1,
    ExpedientesBulkCaptureRequest,
    ExpedientesSingleCapturePublicResultV1,
    ExpedientesSingleCaptureRequest,
    build_expedientes_bulk_capture_definition,
    build_expedientes_bulk_capture_registration,
    build_expedientes_single_capture_definition,
    build_expedientes_single_capture_registration,
    resolve_expedientes_bulk_capture_access,
)
from ...application.live.expedientes_ports import ExpedientesDeclaration, ExpedientesPorts
from ...application.live.snapshot_base import SnapshotRepository
from ...application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...application.operations.persistence.journal import OperationPersistedSnapshot
from ...application.operations.projection_services import OperationResultProjectionService
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...application.operations.supervisor import OperationSupervisor
from ...application.user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)
_PROFILE_ID = UUID("11111111-1111-4111-8111-111111111111")


class _SnapshotRepository:
    def __init__(self, events: list[str], *, bucket_id: str) -> None:
        self.bucket_id = bucket_id
        self.snapshots: dict[str, PersistedExpedientesSnapshot] = {}
        self.events = events

    def exists(self, snapshot_id: str) -> bool:
        return snapshot_id in self.snapshots

    def load(self, snapshot_id: str) -> PersistedExpedientesSnapshot:
        return self.snapshots[snapshot_id]

    def list_snapshots(self) -> tuple[PersistedExpedientesSnapshot, ...]:
        return tuple(self.snapshots.values())

    def resolve(self, snapshot_id: str) -> PersistedExpedientesSnapshot:
        return self.snapshots[snapshot_id]

    def save(self, snapshot: PersistedExpedientesSnapshot) -> None:
        self.events.append("snapshot-save")
        self.snapshots[str(snapshot.snapshot_id)] = snapshot


class _Resources:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.closed = False
        self.close_calls = 0

    @contextmanager
    def activate(self):
        self.events.append("resources-activate")
        try:
            yield
        finally:
            self.events.append("resources-deactivate")

    async def close(self) -> None:
        self.closed = True
        self.close_calls += 1
        self.events.append("resources-close")


class _ExecutionAuthority:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def require(self, *, identity: object, request: object, action: AccessAction) -> None:
        assert identity is not None and request is not None
        self.events.append(f"require:{action.value}")

    @asynccontextmanager
    async def commit_guard(self, identity: object) -> AsyncIterator[None]:
        assert identity is not None
        self.events.append("guard-enter")
        try:
            yield
        finally:
            self.events.append("guard-exit")


async def _run_to_terminal(supervisor: OperationSupervisor, operation_id: str) -> OperationPersistedSnapshot:
    await supervisor.start(operation_id)
    return await supervisor.settled(operation_id)


def _declaration(modelo: str = "303") -> ExpedientesDeclaration:
    return ExpedientesDeclaration(
        modelo=modelo,
        ejercicio=2025,
        period=Period.from_year_and_code(2025, "1T"),
        expediente_id="12345678901234567890",
        estado="ALTA",
        tipo_solicitud="Presentación",
        observaciones="Synthetic declaration",
        presented_at=_NOW,
    )


def _access_context(profile_id: UUID, contract: Any) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.MCP,
        contract=contract,
        published_authority=Availability.AVAILABLE,
    )


def test_single_capture_is_profile_bound_guarded_deduplicated_and_supervised(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        events: list[str] = []
        repository = _SnapshotRepository(events, bucket_id=profile.bucket_id)

        class Register:
            async def walk(self, *, modelo: str, ejercicio: int) -> tuple[ExpedientesDeclaration, ...]:
                events.append(f"remote-walk:{modelo}:{ejercicio}")
                return (_declaration(modelo),)

        class Reader:
            @asynccontextmanager
            async def open_register(
                self,
                session: object,
                *,
                settings: object,
                authority_operation: PinnedAuthorityOperation,
            ):
                assert session is not None and settings is not None
                assert authority_operation is authority
                events.append("register-open")
                try:
                    yield Register()
                finally:
                    events.append("register-close")

        ports = ExpedientesPorts(
            declaration_reader=cast(Any, Reader()),
            snapshot_repository_factory=lambda bucket_id: cast(SnapshotRepository[Any], repository),
        )
        resources: list[_Resources] = []
        provider_calls: list[tuple[UUID, PinnedAuthorityOperation]] = []

        async def active_session(**kwargs: object) -> tuple[object, object]:
            assert kwargs["authority_operation"] is authority
            assert kwargs["operation"] == "live-expedientes-read"
            events.append("authenticated-session")
            return SimpleNamespace(identity_nif="X1234567L"), object()

        monkeypatch.setattr(expedientes_module, "active_verified_session", active_session)
        monkeypatch.setattr(expedientes_module, "now", lambda: _NOW)

        def preflight(profile_arg: UUID, pinned: PinnedAuthorityOperation) -> None:
            provider_calls.append((profile_arg, pinned))
            events.append("provider-preflight")

        def resources_factory() -> _Resources:
            resource = _Resources(events)
            resources.append(resource)
            return resource

        definition = build_expedientes_single_capture_definition(
            lambda *, bucket_id: ports,
            cast(Any, object()),
            cast(Any, object()),
            cast(Any, object()),
            resources_factory,
            preflight,
        )
        registration = build_expedientes_single_capture_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        request = OperationRequest(
            definition_id=EXPEDIENTES_SINGLE_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=ExpedientesSingleCaptureRequest(profile_id=profile_id, modelo="303", year=2025),
        )
        access_context = _access_context(profile_id, registration.contract)
        admitted = resolve_operation_access(registry=registry, request=request, context=access_context)
        assert admitted.request.period_independent
        assert admitted.policy.requires_all_periods
        assert AccessAction.COMMIT in admitted.policy.actions

        foreign_profile_id = uuid4()
        foreign_request = request.model_copy(
            update={
                "subject_ref": profile_operation_subject(str(foreign_profile_id)),
                "payload": request.payload.model_copy(update={"profile_id": foreign_profile_id}),
            }
        )
        with pytest.raises(ProfileAccessRefusedError) as refusal:
            resolve_operation_access(registry=registry, request=foreign_request, context=access_context)
        assert refusal.value.reason is AccessDenialCode.PROFILE_MISMATCH

        from ...application.live import expedientes_capture_operation as capture_module

        monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: profile.bucket_id)
        durable_root = tmp_path / "operations"
        journal = OperationJournalRepository(storage_root=durable_root)
        operands = operation_secure_reference_repository(objects=profile.repository)
        supervisor = OperationSupervisor(
            authority_operation=authority,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=durable_root),
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
            execution_authority=_ExecutionAuthority(events),
        )
        result_service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)

        async def run(operation_id: str) -> tuple[OperationPersistedSnapshot, BaseModel]:
            submitted_id = await supervisor.submit(request, operation_id=operation_id)
            terminal = await _run_to_terminal(supervisor, submitted_id)
            contract = registry.lookup_public_contract(EXPEDIENTES_SINGLE_CAPTURE_DEFINITION_ID)
            assert contract.result_schema is not None
            projected = await result_service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=submitted_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                ExpedientesSingleCapturePublicResultV1,
            )
            return terminal, projected

        async def run_twice():
            return await run("3" * 64), await run("4" * 64)

        (first, first_projection), (second, second_projection) = asyncio.run(run_twice())

    assert first.lifecycle is second.lifecycle is OperationLifecycle.TERMINAL
    assert first.terminal_condition is second.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert first.effect is OperationEffect.UPDATED
    assert second.effect is OperationEffect.NONE
    assert isinstance(first_projection, OperationResultProjectionSuccessV1)
    assert isinstance(second_projection, OperationResultProjectionSuccessV1)
    first_result = first_projection.projection
    second_result = second_projection.projection
    assert isinstance(first_result, ExpedientesSingleCapturePublicResultV1)
    assert isinstance(second_result, ExpedientesSingleCapturePublicResultV1)
    assert first_result.bucket_id == profile.bucket_id
    assert first_result.snapshot_id == second_result.snapshot_id
    assert first_result.declaration_count == 1
    assert first_result.source_url == "declarations:modelo=303:ejercicio=2025"
    assert len(repository.snapshots) == 1
    assert events.count("snapshot-save") == 1
    assert (
        events.index("remote-walk:303:2025")
        < events.index("guard-enter")
        < events.index("snapshot-save")
        < events.index("guard-exit")
    )
    assert provider_calls == [(profile_id, authority), (profile_id, authority)]
    assert len(resources) == 2
    assert all(resource.closed and resource.close_calls == 1 for resource in resources)


def test_bulk_capture_projects_isolated_query_failures_after_all_remote_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ...application.live import expedientes_capture_operation as capture_module

    events: list[str] = []
    authority = cast(PinnedAuthorityOperation, object())
    repository = _SnapshotRepository(events, bucket_id=str(_PROFILE_ID))
    identity = OperationIdentity(
        operation_id="a" * 64,
        definition_id=EXPEDIENTES_BULK_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
    )

    class Register:
        async def walk(self, *, modelo: str, ejercicio: int) -> tuple[ExpedientesDeclaration, ...]:
            events.append(f"remote-walk:{modelo}:{ejercicio}")
            if modelo == "AUTH":
                raise ProfileAccessRefusedError(AccessDenialCode.GRANT_INACTIVE)
            if modelo == "303":
                raise RuntimeError("temporary register failure")
            return (_declaration(modelo),)

    class Reader:
        @asynccontextmanager
        async def open_register(
            self,
            session: object,
            *,
            settings: object,
            authority_operation: PinnedAuthorityOperation,
        ):
            assert session is not None and settings is not None
            assert authority_operation is authority
            events.append("register-open")
            try:
                yield Register()
            finally:
                events.append("register-close")

    ports = ExpedientesPorts(
        declaration_reader=cast(Any, Reader()),
        snapshot_repository_factory=lambda _bucket_id: cast(SnapshotRepository[Any], repository),
    )
    monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: str(_PROFILE_ID))

    async def active_session(**kwargs: object) -> tuple[object, object]:
        assert kwargs["authority_operation"] is authority
        assert kwargs["operation"] == "live-expedientes-read"
        events.append("authenticated-session")
        return SimpleNamespace(identity_nif="X1234567L"), object()

    monkeypatch.setattr(expedientes_module, "active_verified_session", active_session)
    monkeypatch.setattr(expedientes_module, "now", lambda: _NOW)

    class Events:
        async def phase(self, phase: str) -> None:
            events.append(f"phase:{phase}")

        async def effect(self, effect: OperationEffect) -> None:
            events.append(f"effect:{effect.value}")

    class Cancellation:
        @asynccontextmanager
        async def irreversible_section(self) -> AsyncIterator[None]:
            events.append("guard-enter")
            try:
                yield
            finally:
                events.append("guard-exit")

    class Operands:
        report: BaseModel | None = None

        async def put(self, report: BaseModel, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            self.report = report
            events.append("result-put")
            return "result-ref"

    class Cleanup:
        def own(self, resource: object, *, family: object) -> None:
            assert getattr(family, "value", family) == "process"
            events.append("process-owned")

    resources = _Resources(events)
    operands = Operands()
    context = SimpleNamespace(
        identity=identity,
        authority_operation=authority,
        events=Events(),
        cancellation=Cancellation(),
        operands=operands,
        cleanup=Cleanup(),
    )
    preflight_calls: list[tuple[UUID, PinnedAuthorityOperation]] = []

    def preflight(profile_id: UUID, pinned: PinnedAuthorityOperation) -> None:
        assert profile_id == _PROFILE_ID and pinned is authority
        preflight_calls.append((profile_id, pinned))

    definition = build_expedientes_bulk_capture_definition(
        lambda *, bucket_id: ports,
        cast(Any, object()),
        cast(Any, object()),
        cast(Any, object()),
        lambda: resources,
        preflight,
    )
    registration = build_expedientes_bulk_capture_registration(definition)
    request = OperationRequest(
        definition_id=EXPEDIENTES_BULK_CAPTURE_DEFINITION_ID,
        subject_ref=identity.subject_ref,
        payload=ExpedientesBulkCaptureRequest(
            profile_id=_PROFILE_ID,
            modelos=("100", "303"),
            year_from=2025,
            year_to=2025,
        ),
    )
    access = resolve_expedientes_bulk_capture_access(request, _access_context(_PROFILE_ID, registration.contract))
    assert access.request.period_independent
    assert access.policy.requires_all_periods
    assert AccessAction.COMMIT in access.policy.actions

    executor = cast(Any, definition.executor_factory.build())
    reference = asyncio.run(executor.execute(request, cast(Any, context)))

    assert reference == "result-ref"
    assert operands.report is not None
    assert events.index("remote-walk:100:2025") < events.index("remote-walk:303:2025")
    assert (
        events.index("register-close")
        < events.index("guard-enter")
        < events.index("snapshot-save")
        < events.index("guard-exit")
    )
    assert events.count("snapshot-save") == 1
    assert preflight_calls == [(_PROFILE_ID, authority)]
    assert "process-owned" in events

    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=0,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=_NOW,
        result_ref=reference,
    )
    projector = registration.result_projector
    assert projector is not None
    projected = projector(operands.report, receipt)
    assert isinstance(projected, ExpedientesBulkCapturePublicResultV1)
    assert projected.bucket_id == str(_PROFILE_ID)
    assert projected.modelos == ("100", "303")
    assert projected.captured_snapshot_count == 1
    assert projected.declaration_count == 1
    assert projected.failed_count == 1
    assert len(projected.snapshot_ids) == 1
    assert (projected.failures[0].modelo, projected.failures[0].year) == ("303", 2025)
    assert projected.failures[0].error_type == "RuntimeError"
    assert "temporary register failure" in projected.failures[0].message

    guard_count = events.count("guard-enter")

    @asynccontextmanager
    async def allow_local_write() -> AsyncIterator[None]:
        yield

    with pytest.raises(ProfileAccessRefusedError) as denial:
        asyncio.run(
            expedientes_module.capture_expedientes_bulk(
                bucket_id=str(_PROFILE_ID),
                year_from=2025,
                year_to=2025,
                modelos=("AUTH",),
                ports=ports,
                certificate_secret_backend_factory=cast(Any, object()),
                browser_session_factory=cast(Any, object()),
                operator_scope_ports=cast(Any, object()),
                authority_operation=authority,
                effect_guard=allow_local_write,
            )
        )
    assert denial.value.reason is AccessDenialCode.GRANT_INACTIVE
    assert events.count("guard-enter") == guard_count
