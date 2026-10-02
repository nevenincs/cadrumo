"""Synthetic supervisor proof for exact-profile notification snapshot reads."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.live.notification_ports import (
    NotificationSnapshotQueryProtocol,
    NotificationsPorts,
    NotificationsSnapshot,
    NotificationType,
    RemoteNotification,
)
from cadrumo.application.live.notifications import (
    NotificationsSnapshotNotFoundError,
    PersistedNotificationsSnapshot,
)
from cadrumo.application.live.notifications_read_operation import (
    NOTIFICATIONS_LATEST_DEFINITION_ID,
    NOTIFICATIONS_LIST_DEFINITION_ID,
    NOTIFICATIONS_SHOW_DEFINITION_ID,
    NotificationsLatestPublicResultV1,
    NotificationsLatestRequest,
    NotificationsListPublicResultV1,
    NotificationsListRequest,
    NotificationsShowPublicResultV1,
    NotificationsShowRequest,
    build_notifications_latest_definition,
    build_notifications_latest_registration,
    build_notifications_list_definition,
    build_notifications_list_registration,
    build_notifications_show_definition,
    build_notifications_show_registration,
)
from cadrumo.application.live.snapshot_base import SnapshotRepository
from cadrumo.application.operations.access_resolution import OperationAccessContext, resolve_operation_access
from cadrumo.application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.application.operations.persistence.journal import OperationPersistedSnapshot
from cadrumo.application.operations.projection_services import OperationResultProjectionService
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from cadrumo.application.operations.supervisor import OperationSupervisor
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessDenialCode, Availability
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 24, 20, tzinfo=UTC)


class _NeverQuery:
    """Provide the capture port while making accidental AEAT access visible."""

    async def fetch(self, session: object, *, settings: object) -> NotificationsSnapshot:
        del session, settings
        raise AssertionError("a local notifications snapshot read must not query AEAT")


class _SnapshotRepository:
    """Small in-memory implementation of the encrypted snapshot repository port."""

    def __init__(self, *, bucket_id: str, snapshots: tuple[PersistedNotificationsSnapshot, ...]) -> None:
        self._bucket_id = bucket_id
        self.snapshots = list(snapshots)

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    def exists(self, snapshot_id: str) -> bool:
        return any(snapshot.snapshot_id == snapshot_id for snapshot in self.snapshots)

    def load(self, snapshot_id: str) -> PersistedNotificationsSnapshot:
        for snapshot in self.snapshots:
            if snapshot.snapshot_id == snapshot_id:
                return snapshot
        raise KeyError(snapshot_id)

    def list_snapshots(self) -> tuple[PersistedNotificationsSnapshot, ...]:
        return tuple(self.snapshots)

    def resolve(self, snapshot_id: str) -> PersistedNotificationsSnapshot:
        matches = tuple(
            snapshot
            for snapshot in self.snapshots
            if snapshot.snapshot_id == snapshot_id or snapshot.snapshot_id.startswith(snapshot_id)
        )
        if not matches:
            raise NotificationsSnapshotNotFoundError(
                translated_message="application.live.notifications.errors.snapshot_not_found",
                context={"snapshot_id": snapshot_id},
            )
        if len(matches) > 1:
            raise NotificationsSnapshotNotFoundError(
                translated_message="application.live.notifications.errors.snapshot_prefix_ambiguous",
                context={"snapshot_id": snapshot_id, "match_count": len(matches)},
            )
        return matches[0]

    def save(self, snapshot: PersistedNotificationsSnapshot) -> None:
        self.snapshots.append(snapshot)


def _snapshot(*, bucket_id: str, snapshot_id: str, captured_at: datetime) -> PersistedNotificationsSnapshot:
    row = RemoteNotification(
        certificado_id="1234567890",
        tipo=NotificationType.NOTIFICACION,
        concepto="Notificación sintética",
        titular_nif="X1234567L",
        titular_nombre="Titular sintético",
        destinatario_nif="X1234567L",
        destinatario_nombre="Titular sintético",
        fecha_emision=captured_at.date(),
        fecha_notificacion=None,
        modo_notificacion=None,
        leida=False,
        source_url="https://sede.example/notification/1234567890",
        mode="read",
    )
    return PersistedNotificationsSnapshot(
        snapshot_id=snapshot_id,
        bucket_id=bucket_id,
        captured_at=captured_at,
        source_url="https://sede.example/notifications",
        authenticated_identity="X1234567L",
        rows=(row,),
        persisted_at=captured_at + timedelta(seconds=1),
    )


def _ports_factory(repository: _SnapshotRepository):
    def build() -> NotificationsPorts:
        return NotificationsPorts(
            snapshot_query=cast(NotificationSnapshotQueryProtocol, _NeverQuery()),
            snapshot_repository_factory=lambda _bucket_id: cast(SnapshotRepository[Any], repository),
        )

    return build


async def _run_to_terminal(supervisor: OperationSupervisor, operation_id: str) -> OperationPersistedSnapshot:
    await supervisor.start(operation_id)
    return await supervisor.settled(operation_id)


def test_registered_notification_reads_are_exact_profile_and_project_closed_results(tmp_path: Path) -> None:
    """Record list, full view, and latest solely from a synthetic local repository."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        old_snapshot = _snapshot(
            bucket_id=profile.bucket_id,
            snapshot_id="1" * 64,
            captured_at=_NOW,
        )
        latest_snapshot = _snapshot(
            bucket_id=profile.bucket_id,
            snapshot_id="2" * 64,
            captured_at=_NOW + timedelta(minutes=1),
        )
        repository = _SnapshotRepository(bucket_id=profile.bucket_id, snapshots=(old_snapshot, latest_snapshot))
        factory = _ports_factory(repository)

        list_definition = build_notifications_list_definition(factory)
        show_definition = build_notifications_show_definition(factory)
        latest_definition = build_notifications_latest_definition(factory)
        list_registration = build_notifications_list_registration(list_definition)
        show_registration = build_notifications_show_registration(show_definition)
        latest_registration = build_notifications_latest_registration(latest_definition)
        registry = OperationRegistry(
            definitions=tuple(
                sorted((list_definition, show_definition, latest_definition), key=lambda item: item.definition_id)
            ),
            public_registrations=tuple(
                sorted(
                    (list_registration, show_registration, latest_registration),
                    key=lambda item: item.contract.definition_id,
                )
            ),
        )

        requests: tuple[
            tuple[OperationRequest[BaseModel], type[BaseModel], OperationPublicDefinitionRegistrationV1], ...
        ] = (
            (
                OperationRequest(
                    definition_id=NOTIFICATIONS_LIST_DEFINITION_ID,
                    subject_ref=profile_operation_subject(profile.bucket_id),
                    payload=NotificationsListRequest(profile_id=profile_id),
                ),
                NotificationsListPublicResultV1,
                list_registration,
            ),
            (
                OperationRequest(
                    definition_id=NOTIFICATIONS_SHOW_DEFINITION_ID,
                    subject_ref=profile_operation_subject(profile.bucket_id),
                    payload=NotificationsShowRequest(profile_id=profile_id, snapshot_id="222"),
                ),
                NotificationsShowPublicResultV1,
                show_registration,
            ),
            (
                OperationRequest(
                    definition_id=NOTIFICATIONS_LATEST_DEFINITION_ID,
                    subject_ref=profile_operation_subject(profile.bucket_id),
                    payload=NotificationsLatestRequest(profile_id=profile_id),
                ),
                NotificationsLatestPublicResultV1,
                latest_registration,
            ),
        )

        for request, _result_type, registration in requests:
            access_context = OperationAccessContext(
                profile_id=profile_id,
                destination_id=uuid4(),
                action=AccessAction.SUBMIT,
                frontend=OperationFrontendProjection.CLI,
                contract=registration.contract,
                published_authority=Availability.AVAILABLE,
                authority_operation=authority,
            )
            admitted = resolve_operation_access(registry=registry, request=request, context=access_context)
            assert admitted.request.profile_id == profile_id
            assert admitted.request.period_independent
            assert admitted.policy.requires_all_periods
            assert AccessAction.COMMIT not in admitted.policy.actions

            foreign_profile_id = uuid4()
            foreign_request = request.model_copy(
                update={
                    "subject_ref": profile_operation_subject(str(foreign_profile_id)),
                    "payload": request.payload.model_copy(update={"profile_id": foreign_profile_id}),
                }
            )
            with pytest.raises(ProfileAccessRefusedError) as refusal:
                resolve_operation_access(
                    registry=registry,
                    request=foreign_request,
                    context=access_context,
                )
            assert refusal.value.reason is AccessDenialCode.PROFILE_MISMATCH

        assert list_definition.action_reference is not None
        assert list_definition.action_reference.action_id == "operator.live.notifications.list"
        assert show_definition.action_reference is None
        assert latest_definition.action_reference is None
        for definition in (list_definition, show_definition, latest_definition):
            assert definition.capabilities.owned_resources == frozenset()
            assert OperationFrontendProjection.MCP in definition.permitted_frontends

        durable_root = tmp_path / "operations"
        journal = OperationJournalRepository(storage_root=durable_root)
        leases = OperationLeaseFilesystemRepository(storage_root=durable_root)
        operands = operation_secure_reference_repository(objects=profile.repository)
        supervisor = OperationSupervisor(
            authority_operation=authority,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )
        result_service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)

        async def run(
            request: OperationRequest[BaseModel], operation_id: str, result_type: type[BaseModel]
        ) -> tuple[OperationPersistedSnapshot, OperationResultProjectionSuccessV1[BaseModel]]:
            submitted_id = await supervisor.submit(request, operation_id=operation_id)
            terminal = await _run_to_terminal(supervisor, submitted_id)
            contract = registry.lookup_public_contract(request.definition_id)
            assert contract.result_schema is not None
            projected = await result_service.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=submitted_id,
                    terminal_revision=terminal.revision,
                    definition_contract_digest=contract.definition_contract_digest,
                    result_schema=contract.result_schema,
                ),
                result_type,
            )
            assert isinstance(projected, OperationResultProjectionSuccessV1)
            return terminal, cast(OperationResultProjectionSuccessV1[BaseModel], projected)

        async def run_terminal(request: OperationRequest[BaseModel], operation_id: str) -> OperationPersistedSnapshot:
            submitted_id = await supervisor.submit(request, operation_id=operation_id)
            return await _run_to_terminal(supervisor, submitted_id)

        list_terminal, list_projected = asyncio.run(run(requests[0][0], "3" * 64, requests[0][1]))
        show_terminal, show_projected = asyncio.run(run(requests[1][0], "4" * 64, requests[1][1]))
        latest_terminal, latest_projected = asyncio.run(run(requests[2][0], "5" * 64, requests[2][1]))
        unknown_show_request = OperationRequest(
            definition_id=NOTIFICATIONS_SHOW_DEFINITION_ID,
            subject_ref=profile_operation_subject(profile.bucket_id),
            payload=NotificationsShowRequest(profile_id=profile_id, snapshot_id="f" * 64),
        )
        unknown_show_terminal = asyncio.run(run_terminal(unknown_show_request, "6" * 64))
        repository.snapshots.clear()
        empty_latest_terminal, empty_latest_projected = asyncio.run(run(requests[2][0], "a" * 64, requests[2][1]))

    for terminal in (list_terminal, show_terminal, latest_terminal, empty_latest_terminal):
        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is OperationEffect.NONE
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.effect is OperationEffect.NONE
    assert unknown_show_terminal.terminal_condition is not OperationTerminalCondition.SUCCEEDED

    listed = list_projected.projection
    assert isinstance(listed, NotificationsListPublicResultV1)
    assert listed.bucket_id == profile.bucket_id
    assert listed.count == 2
    assert tuple((row.snapshot_id, row.row_count) for row in listed.rows) == (("1" * 64, 1), ("2" * 64, 1))
    assert "source_url" not in listed.model_dump()

    shown = show_projected.projection
    assert isinstance(shown, NotificationsShowPublicResultV1)
    assert (shown.snapshot_id, shown.source_url, shown.row_count) == ("2" * 64, "https://sede.example/notifications", 1)
    row = shown.rows[0]
    assert (row.certificado_id, row.concepto, row.fecha_emision, row.mode) == (
        "1234567890",
        "Notificación sintética",
        _NOW.date(),
        "read",
    )
    assert "authenticated_identity" not in shown.model_dump()
    assert set(row.model_dump()) == {
        "certificado_id",
        "tipo",
        "concepto",
        "titular_nif",
        "titular_nombre",
        "destinatario_nif",
        "destinatario_nombre",
        "fecha_emision",
        "fecha_notificacion",
        "modo_notificacion",
        "leida",
        "source_url",
        "mode",
    }

    latest = latest_projected.projection
    assert isinstance(latest, NotificationsLatestPublicResultV1)
    assert (latest.snapshot_id, latest.row_count, latest.source_url) == (
        "2" * 64,
        1,
        "https://sede.example/notifications",
    )

    empty_latest = empty_latest_projected.projection
    assert isinstance(empty_latest, NotificationsLatestPublicResultV1)
    assert empty_latest.snapshot_id is None
    assert empty_latest.captured_at is None
    assert empty_latest.source_url is None
    assert empty_latest.row_count is None


def test_notification_read_operations_reject_foreign_bucket_rows(tmp_path: Path) -> None:
    """A repository result claiming another bucket never settles as successful."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        foreign_snapshot = _snapshot(
            bucket_id=str(uuid4()),
            snapshot_id="6" * 64,
            captured_at=_NOW,
        )
        factory = _ports_factory(_SnapshotRepository(bucket_id=profile.bucket_id, snapshots=(foreign_snapshot,)))
        definitions = (
            build_notifications_list_definition(factory),
            build_notifications_show_definition(factory),
            build_notifications_latest_definition(factory),
        )
        registrations = (
            build_notifications_list_registration(definitions[0]),
            build_notifications_show_registration(definitions[1]),
            build_notifications_latest_registration(definitions[2]),
        )
        registry = OperationRegistry(
            definitions=tuple(sorted(definitions, key=lambda item: item.definition_id)),
            public_registrations=tuple(sorted(registrations, key=lambda item: item.contract.definition_id)),
        )
        requests = (
            OperationRequest(
                definition_id=NOTIFICATIONS_LIST_DEFINITION_ID,
                subject_ref=profile_operation_subject(profile.bucket_id),
                payload=NotificationsListRequest(profile_id=profile_id),
            ),
            OperationRequest(
                definition_id=NOTIFICATIONS_SHOW_DEFINITION_ID,
                subject_ref=profile_operation_subject(profile.bucket_id),
                payload=NotificationsShowRequest(profile_id=profile_id, snapshot_id="6" * 64),
            ),
            OperationRequest(
                definition_id=NOTIFICATIONS_LATEST_DEFINITION_ID,
                subject_ref=profile_operation_subject(profile.bucket_id),
                payload=NotificationsLatestRequest(profile_id=profile_id),
            ),
        )
        durable_root = tmp_path / "operations"
        journal = OperationJournalRepository(storage_root=durable_root)
        supervisor = OperationSupervisor(
            authority_operation=authority,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=durable_root),
            operands=operation_secure_reference_repository(objects=profile.repository),
            owner_id="7" * 64,
            lease_token_factory=lambda: "8" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )

        async def run_all() -> tuple[OperationPersistedSnapshot, ...]:
            terminals: list[OperationPersistedSnapshot] = []
            for index, request in enumerate(requests, start=1):
                operation_id = str(index) * 64
                submitted_id = await supervisor.submit(request, operation_id=operation_id)
                terminals.append(await _run_to_terminal(supervisor, submitted_id))
            return tuple(terminals)

        terminals = asyncio.run(run_all())

    assert len(terminals) == 3
    assert all(terminal.lifecycle is OperationLifecycle.TERMINAL for terminal in terminals)
    assert all(terminal.terminal_condition is not OperationTerminalCondition.SUCCEEDED for terminal in terminals)
