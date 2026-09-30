"""Focused contract checks for registered notification snapshot capture."""

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
from ...application.live.notification_ports import (
    NotificationsPorts,
    NotificationsSnapshot,
    NotificationType,
    RemoteNotification,
)
from ...application.live.notifications import PersistedNotificationsSnapshot
from ...application.live.notifications_capture_operation import (
    NOTIFICATIONS_CAPTURE_DEFINITION_ID,
    NotificationsCaptureOperationReport,
    NotificationsCapturePublicResultV1,
    NotificationsCaptureRequest,
    build_notifications_capture_definition,
    build_notifications_capture_registration,
    resolve_notifications_capture_access,
)
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
from ...domain.calculations.registry.authority import bundled_indexed_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)
_PROFILE_ID = UUID("11111111-1111-4111-8111-111111111111")


class _SnapshotRepository:
    def __init__(self, events: list[str], *, bucket_id: str = str(_PROFILE_ID)) -> None:
        self.bucket_id = bucket_id
        self.snapshots: dict[str, PersistedNotificationsSnapshot] = {}
        self.events = events

    def exists(self, snapshot_id: str) -> bool:
        return snapshot_id in self.snapshots

    def load(self, snapshot_id: str) -> PersistedNotificationsSnapshot:
        return self.snapshots[snapshot_id]

    def list_snapshots(self) -> tuple[PersistedNotificationsSnapshot, ...]:
        return tuple(self.snapshots.values())

    def resolve(self, snapshot_id: str) -> PersistedNotificationsSnapshot:
        return self.snapshots[snapshot_id]

    def save(self, snapshot: PersistedNotificationsSnapshot) -> None:
        self.events.append("snapshot-save")
        self.snapshots[str(snapshot.snapshot_id)] = snapshot


class _Events:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def phase(self, phase_code: str) -> None:
        self.events.append(f"phase:{phase_code}")

    async def effect(self, effect: OperationEffect) -> None:
        self.events.append(f"effect:{effect.value}")


class _Cancellation:
    def __init__(self, events: list[str], *, refuse: bool = False) -> None:
        self.events = events
        self.refuse = refuse

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        self.events.append("guard-enter")
        if self.refuse:
            raise ProfileAccessRefusedError(AccessDenialCode.GRANT_INACTIVE)
        try:
            yield
        finally:
            self.events.append("guard-exit")


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


class _Operands:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.value: BaseModel | None = None

    async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        self.events.append("result-put")
        self.value = operand
        return "result-ref"


class _Cleanup:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def own(self, resource: object, *, family: object) -> None:
        del resource
        self.events.append(f"resource-owned:{getattr(family, 'value', family)}")


class _Context:
    def __init__(self, events: list[str], *, authority: object, refuse: bool = False) -> None:
        self.identity = OperationIdentity(
            operation_id="a" * 64,
            definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        )
        self.authority_operation = authority
        self.events = _Events(events)
        self.cancellation = _Cancellation(events, refuse=refuse)
        self.operands = _Operands(events)
        self.cleanup = _Cleanup(events)


def _snapshot() -> NotificationsSnapshot:
    row = RemoteNotification(
        certificado_id="1234567890",
        tipo=NotificationType.NOTIFICACION,
        concepto="Notificación sintética",
        titular_nif="X1234567L",
        titular_nombre="Titular sintético",
        destinatario_nif="X1234567L",
        destinatario_nombre="Titular sintético",
        fecha_emision=_NOW.date(),
        fecha_notificacion=None,
        modo_notificacion=None,
        leida=False,
        source_url="https://sede.agenciatributaria.gob.es/Sede/notificaciones",
        mode="read",
    )
    return NotificationsSnapshot(
        rows=(row,),
        captured_at=_NOW,
        source_url="https://sede.agenciatributaria.gob.es/Sede/notificaciones",
    )


async def _run_to_terminal(supervisor: OperationSupervisor, operation_id: str) -> OperationPersistedSnapshot:
    await supervisor.start(operation_id)
    return await supervisor.settled(operation_id)


def test_capture_executor_fetches_before_fresh_guard_and_projects_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ...application.live import notifications as notifications_module
    from ...application.live import notifications_capture_operation as capture_module

    events: list[str] = []
    repository = _SnapshotRepository(events)

    class Query:
        async def fetch(self, session: object, *, settings: object) -> NotificationsSnapshot:
            del settings
            assert cast(Any, session).identity_nif == "X1234567L"
            events.append("remote-fetch")
            return _snapshot()

    ports = NotificationsPorts(
        snapshot_query=cast(Any, Query()),
        snapshot_repository_factory=lambda _bucket_id: cast(SnapshotRepository[Any], repository),
    )
    composition = SimpleNamespace(
        notifications_ports=ports,
        certificate_secret_backend_factory=object(),
        browser_session_factory=object(),
        operator_scope_ports=object(),
    )
    resources = _Resources(events)

    with bundled_indexed_authority().operation() as authority:
        context = _Context(events, authority=authority)
        monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: str(_PROFILE_ID))

        async def active_session(**kwargs: object) -> tuple[object, object]:
            assert kwargs["authority_operation"] is authority
            assert kwargs["operation"] == "live-notifications-pull"
            events.append("authenticated-session")
            return SimpleNamespace(identity_nif="X1234567L"), object()

        monkeypatch.setattr(notifications_module, "active_verified_session", active_session)

        def provider_preflight(profile_id: UUID, operation: object) -> None:
            events.append(f"provider-preflight:{profile_id}:{operation is authority}")

        executor = build_notifications_capture_definition(
            composition_factory=lambda: cast(Any, composition),
            browser_resources_factory=lambda: cast(Any, resources),
            provider_preflight=provider_preflight,
        ).executor_factory.build()
        request = OperationRequest(
            definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE_ID)),
            payload=NotificationsCaptureRequest(profile_id=_PROFILE_ID),
        )
        reference = asyncio.run(executor.execute(request, cast(Any, context)))

        assert reference == "result-ref"
        assert events.index("remote-fetch") < events.index("guard-enter") < events.index("snapshot-save")
        assert "resource-owned:process" in events
        assert events.count("guard-enter") == 2
        assert "effect:unknown" in events
        assert f"effect:{OperationEffect.UPDATED.value}" in events
        report = context.operands.value
        assert isinstance(report, NotificationsCaptureOperationReport)
        assert report.newly_persisted

        registration = build_notifications_capture_registration(
            build_notifications_capture_definition(
                composition_factory=lambda: cast(Any, composition),
                browser_resources_factory=lambda: cast(Any, resources),
                provider_preflight=lambda _profile_id, _operation: None,
            )
        )
        receipt = OperationTerminalReceipt(
            identity=context.identity,
            revision=0,
            condition=OperationTerminalCondition.SUCCEEDED,
            effect=OperationEffect.UPDATED,
            settled_at=_NOW,
            result_ref=reference,
        )
        projection = registration.result_projector(report, receipt) if registration.result_projector else None

    assert isinstance(projection, NotificationsCapturePublicResultV1)
    assert projection.bucket_id == str(_PROFILE_ID)
    assert projection.row_count == 1
    assert projection.source_url == _snapshot().source_url
    assert set(projection.model_dump()) == {
        "bucket_id",
        "snapshot_id",
        "captured_at",
        "persisted_at",
        "row_count",
        "source_url",
    }


def test_supervisor_settles_capture_with_fresh_commit_and_dedup_receipts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ...application.live import notifications as notifications_module
    from ...application.live import notifications_capture_operation as capture_module

    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        events: list[str] = []
        repository = _SnapshotRepository(events, bucket_id=profile.bucket_id)

        class Query:
            async def fetch(self, session: object, *, settings: object) -> NotificationsSnapshot:
                del settings
                assert cast(Any, session).identity_nif == "X1234567L"
                events.append("remote-fetch")
                return _snapshot()

        ports = NotificationsPorts(
            snapshot_query=cast(Any, Query()),
            snapshot_repository_factory=lambda _bucket_id: cast(SnapshotRepository[Any], repository),
        )
        composition = SimpleNamespace(
            notifications_ports=ports,
            certificate_secret_backend_factory=object(),
            browser_session_factory=object(),
            operator_scope_ports=object(),
        )
        resources: list[_Resources] = []
        monkeypatch.setattr(capture_module, "require_active_bucket_id", lambda: profile.bucket_id)

        async def active_session(**kwargs: object) -> tuple[object, object]:
            assert kwargs["authority_operation"] is authority
            assert kwargs["operation"] == "live-notifications-pull"
            events.append("authenticated-session")
            return SimpleNamespace(identity_nif="X1234567L"), object()

        monkeypatch.setattr(notifications_module, "active_verified_session", active_session)

        def provider_preflight(profile_id_arg: UUID, pinned_authority: object) -> None:
            assert profile_id_arg == profile_id
            assert pinned_authority is authority
            events.append("provider-preflight")

        def resources_factory() -> _Resources:
            resource = _Resources(events)
            resources.append(resource)
            return resource

        definition = build_notifications_capture_definition(
            composition_factory=lambda: cast(Any, composition),
            browser_resources_factory=resources_factory,
            provider_preflight=provider_preflight,
        )
        registration = build_notifications_capture_registration(definition)
        registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
        request = OperationRequest(
            definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=NotificationsCaptureRequest(profile_id=profile_id),
        )
        access_context = OperationAccessContext(
            profile_id=profile_id,
            destination_id=uuid4(),
            action=AccessAction.SUBMIT,
            frontend=OperationFrontendProjection.MCP,
            contract=registration.contract,
            published_authority=Availability.AVAILABLE,
        )
        admitted = resolve_operation_access(registry=registry, request=request, context=access_context)
        assert admitted.request.period_independent
        assert admitted.policy.requires_all_periods
        assert AccessAction.COMMIT in admitted.policy.actions

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
            contract = registry.lookup_public_contract(NOTIFICATIONS_CAPTURE_DEFINITION_ID)
            assert contract.result_schema is not None
            projected = await result_service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=submitted_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                NotificationsCapturePublicResultV1,
            )
            return terminal, projected

        async def run_both():
            return await run("3" * 64), await run("4" * 64)

        (first_terminal, first_projected), (second_terminal, second_projected) = asyncio.run(run_both())

    assert first_terminal.lifecycle is OperationLifecycle.TERMINAL
    assert second_terminal.lifecycle is OperationLifecycle.TERMINAL
    assert first_terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert second_terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert first_terminal.effect is OperationEffect.UPDATED
    assert second_terminal.effect is OperationEffect.NONE
    assert isinstance(first_projected, OperationResultProjectionSuccessV1)
    assert isinstance(second_projected, OperationResultProjectionSuccessV1)
    first_result = first_projected.projection
    second_result = second_projected.projection
    assert isinstance(first_result, NotificationsCapturePublicResultV1)
    assert isinstance(second_result, NotificationsCapturePublicResultV1)
    assert first_result.bucket_id == profile.bucket_id
    assert first_result.snapshot_id == second_result.snapshot_id
    assert first_result.row_count == 1
    assert first_result.source_url == _snapshot().source_url
    assert len(repository.snapshots) == 1
    assert events.count("snapshot-save") == 1
    assert events.index("remote-fetch") < events.index("guard-enter") < events.index("snapshot-save")
    assert len(resources) == 2
    assert all(resource.closed and resource.close_calls == 1 for resource in resources)


def test_capture_access_is_whole_profile_and_requires_commit() -> None:
    definition = build_notifications_capture_definition(
        composition_factory=lambda: cast(Any, object()),
        browser_resources_factory=lambda: cast(Any, object()),
        provider_preflight=lambda _profile_id, _operation: None,
    )
    registration = build_notifications_capture_registration(definition)
    request = OperationRequest(
        definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
        payload=NotificationsCaptureRequest(profile_id=_PROFILE_ID),
    )
    context = OperationAccessContext(
        profile_id=_PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )

    access = resolve_notifications_capture_access(request, context)

    assert access.request.profile_id == _PROFILE_ID
    assert access.request.period_independent
    assert access.policy.requires_all_periods
    assert AccessAction.COMMIT in access.policy.actions

    foreign_id = uuid4()
    foreign_request = request.model_copy(
        update={
            "subject_ref": profile_operation_subject(str(foreign_id)),
            "payload": NotificationsCaptureRequest(profile_id=foreign_id),
        }
    )
    with pytest.raises(ProfileAccessRefusedError) as refusal:
        resolve_notifications_capture_access(foreign_request, context)
    assert refusal.value.reason is AccessDenialCode.PROFILE_MISMATCH
