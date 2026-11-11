"""Registered exact-profile capture contracts for expedientes snapshots."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction

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
from ...application.operations.registry import OperationRegistry
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...core.operations import (
    OperationEffect,
    OperationFrontendProjection,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from .capture_stand_in_support import RecordingExecutionAuthority, RecordingResources
from .supervised_operation_rig import (
    assert_foreign_profile_refused,
    build_supervised_operation,
    operation_access_context,
    run_to_terminal,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon
_FILING_YEAR = newest_authored_edition("100")

_NOW = datetime(_YEAR, 9, 29, 12, tzinfo=UTC)
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


def _declaration(modelo: str = "303") -> ExpedientesDeclaration:
    return ExpedientesDeclaration(
        modelo=modelo,
        ejercicio=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, "1T"),
        expediente_id="12345678901234567890",
        estado="ALTA",
        tipo_solicitud="Presentación",
        observaciones="Synthetic declaration",
        presented_at=_NOW,
    )


def _access_context(profile_id: UUID, contract: Any) -> OperationAccessContext:
    return operation_access_context(
        contract, profile_id=profile_id, frontend=OperationFrontendProjection.EXTERNAL_CLIENT
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
        resources: list[RecordingResources] = []
        provider_calls: list[tuple[UUID, PinnedAuthorityOperation]] = []

        async def active_session(**kwargs: object) -> tuple[object, object]:
            assert kwargs["authority_operation"] is authority
            assert kwargs["operation"] == "live-expedientes-read"
            events.append("authenticated-session")
            return SimpleNamespace(identity_nif="X0001500M"), object()

        monkeypatch.setattr(expedientes_module, "active_verified_session", active_session)
        monkeypatch.setattr(expedientes_module, "now", lambda: _NOW)

        def preflight(profile_arg: UUID, pinned: PinnedAuthorityOperation) -> None:
            provider_calls.append((profile_arg, pinned))
            events.append("provider-preflight")

        def resources_factory() -> RecordingResources:
            resource = RecordingResources(events)
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
            payload=ExpedientesSingleCaptureRequest(profile_id=profile_id, modelo="303", year=_FILING_YEAR),
        )
        access_context = _access_context(profile_id, registration.contract)
        admitted = resolve_operation_access(registry=registry, request=request, context=access_context)
        assert admitted.request.period_independent
        assert admitted.policy.requires_all_periods
        assert AccessAction.COMMIT in admitted.policy.actions

        assert_foreign_profile_refused(registry=registry, request=request, context=access_context)

        from ...application.live import expedientes_capture_operation as capture_module

        monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: profile.bucket_id)
        _, _, _, supervisor, result_service = build_supervised_operation(
            tmp_path=tmp_path,
            objects=profile.repository,
            authority=authority,
            registry=registry,
            now=_NOW,
            execution_authority=RecordingExecutionAuthority(events),
        )

        async def run(operation_id: str) -> tuple[OperationPersistedSnapshot, BaseModel]:
            submitted_id = await supervisor.submit(request, operation_id=operation_id)
            terminal = await run_to_terminal(supervisor, submitted_id)
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
    assert first_result.source_url == f"declarations:modelo=303:ejercicio={_FILING_YEAR}"
    assert len(repository.snapshots) == 1
    assert events.count("snapshot-save") == 1
    assert (
        events.index(f"remote-walk:303:{_FILING_YEAR}")
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
        return SimpleNamespace(identity_nif="X0001500M"), object()

    monkeypatch.setattr(expedientes_module, "active_verified_session", active_session)
    monkeypatch.setattr(expedientes_module, "now", lambda: _NOW)

    class Events:
        async def phase(self, phase: str) -> None:
            events.append(f"phase:{phase}")

        async def effect(self, effect: OperationEffect) -> None:
            events.append(f"effect:{effect.value}")

    class Cancellation:
        @asynccontextmanager
        async def irreversible_section(self) -> AsyncGenerator[None]:
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

    resources = RecordingResources(events)
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
            year_from=_FILING_YEAR,
            year_to=_FILING_YEAR,
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
    assert events.index(f"remote-walk:100:{_FILING_YEAR}") < events.index(f"remote-walk:303:{_FILING_YEAR}")
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
    assert (projected.failures[0].modelo, projected.failures[0].year) == ("303", _FILING_YEAR)
    assert projected.failures[0].error_type == "RuntimeError"
    assert "temporary register failure" in projected.failures[0].message

    guard_count = events.count("guard-enter")

    @asynccontextmanager
    async def allow_local_write() -> AsyncGenerator[None]:
        yield

    with pytest.raises(ProfileAccessRefusedError) as denial:
        asyncio.run(
            expedientes_module.capture_expedientes_bulk(
                bucket_id=str(_PROFILE_ID),
                year_from=_FILING_YEAR,
                year_to=_FILING_YEAR,
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
