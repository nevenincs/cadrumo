"""Supervisor proof for exact-profile local notification-document reads."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from cadrumo.adapters.persistence.operations.secure_references import operation_secure_reference_repository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.live.notification_document_read_operation import (
    NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID,
    NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID,
    NotificationDocumentHistoryPublicResultV1,
    NotificationDocumentHistoryRequest,
    NotificationDocumentViewPublicResultV1,
    NotificationDocumentViewRequest,
    build_notification_document_history_definition,
    build_notification_document_history_registration,
    build_notification_document_view_definition,
    build_notification_document_view_registration,
)
from cadrumo.application.live.notification_documents import (
    NotificationDocumentNotFoundError,
    NotificationDocumentRecord,
    NotificationDocumentService,
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
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.domain.attachments.protocols import AttachmentStoreProtocol
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.notifications.sancion import SancionLiquidacion

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)
_CERTIFICADO = "2699101808461"
_OTHER_CERTIFICADO = "2596230606502"
_DIGEST = "a" * 64


class _DocumentRepository:
    """In-memory repository port returning only the records installed by a test."""

    def __init__(self, bucket_id: str, records: tuple[NotificationDocumentRecord, ...]) -> None:
        self.bucket_id = bucket_id
        self.records = records

    def exists(self, snapshot_id: str) -> bool:
        return any(record.snapshot_id == snapshot_id for record in self.records)

    def load(self, snapshot_id: str) -> NotificationDocumentRecord:
        for record in self.records:
            if record.snapshot_id == snapshot_id:
                return record
        raise NotificationDocumentNotFoundError(
            translated_message="application.live.notifications.errors.document_not_found",
            context={"certificado_id": snapshot_id},
        )

    def list_snapshots(self) -> tuple[NotificationDocumentRecord, ...]:
        return self.records

    def resolve(self, snapshot_id: str) -> NotificationDocumentRecord:
        return self.load(snapshot_id)

    def save(self, snapshot: NotificationDocumentRecord) -> None:
        self.records += (snapshot,)


class _NeverFetch:
    async def __call__(self, *args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("a local notification-document read must not fetch from AEAT")


class _NeverRead:
    def read(self, document: object) -> tuple[None, None]:
        del document
        raise AssertionError("a local notification-document read must not reread PDF bytes")


def _sancion(*, certificado_id: str, digest: str = _DIGEST) -> SancionLiquidacion:
    return SancionLiquidacion(
        certificado_id=certificado_id,
        clave_liquidacion="A2860024500012345",
        referencia="2024/0001234",
        nif="12345678Z",
        objeto_tributario="sancion",
        base_sancion=Decimal("3687.120"),
        porcentaje_minimo=Decimal("50.00"),
        sancion_resultante=Decimal("1843.560"),
        reduccion_conformidad=Decimal("553.070"),
        reduccion_pronto_pago=Decimal("516.20"),
        diferencia=Decimal("774.290"),
        importe_a_ingresar=Decimal("774.290"),
        document_sha256=digest,
    )


def _record(
    *,
    bucket_id: str,
    certificado_id: str,
    fetched_at: datetime,
    parsed: bool = True,
) -> NotificationDocumentRecord:
    reading = _sancion(certificado_id=certificado_id) if parsed else None
    return NotificationDocumentRecord(
        certificado_id=certificado_id,
        bucket_id=bucket_id,
        attachment_id=_DIGEST,
        document_sha256=_DIGEST,
        byte_size=4096,
        source_url=f"https://sede.example/notification/{certificado_id}",
        fetched_at=fetched_at,
        sancion=reading,
        parse_refusal=None if parsed else "SancionParseError: no text layer",
    )


def _service_factory(repository: _DocumentRepository):
    def build() -> NotificationDocumentService:
        return NotificationDocumentService(
            settings=cast(Any, object()),
            attachment_store=cast(AttachmentStoreProtocol, object()),
            repository_factory=lambda _bucket_id: cast(SnapshotRepository[NotificationDocumentRecord], repository),
            content_guard=lambda _row: None,
            document_fetcher=cast(Any, _NeverFetch()),
            document_reader=cast(Any, _NeverRead()),
        )

    return build


def _registry(repository: _DocumentRepository) -> OperationRegistry:
    service_factory = _service_factory(repository)
    view = build_notification_document_view_definition(service_factory)
    history = build_notification_document_history_definition(service_factory)
    registrations = (
        build_notification_document_view_registration(view),
        build_notification_document_history_registration(history),
    )
    return OperationRegistry(
        definitions=tuple(sorted((view, history), key=lambda item: item.definition_id)),
        public_registrations=tuple(sorted(registrations, key=lambda item: item.contract.definition_id)),
    )


async def _run_to_terminal(supervisor: OperationSupervisor, operation_id: str) -> OperationPersistedSnapshot:
    await supervisor.start(operation_id)
    return await supervisor.settled(operation_id)


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    profile_id: UUID,
    action: AccessAction,
    destination_id: UUID,
    authority: object,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=destination_id,
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        authority_operation=cast(Any, authority),
    )


def test_registered_document_reads_project_safe_local_results_with_none_receipts(tmp_path: Path) -> None:
    """View and history read the bucket repository and disclose closed DTOs only."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        repository = _DocumentRepository(
            profile.bucket_id,
            (
                _record(bucket_id=profile.bucket_id, certificado_id=_CERTIFICADO, fetched_at=_NOW),
                _record(
                    bucket_id=profile.bucket_id,
                    certificado_id=_OTHER_CERTIFICADO,
                    fetched_at=_NOW + timedelta(minutes=1),
                ),
                _record(
                    bucket_id=profile.bucket_id,
                    certificado_id="1234567890",
                    fetched_at=_NOW + timedelta(minutes=2),
                    parsed=False,
                ),
            ),
        )
        registry = _registry(repository)
        view_registration = registry.lookup_public_registration(NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID)
        requests: tuple[tuple[OperationRequest[BaseModel], type[BaseModel]], ...] = (
            (
                OperationRequest(
                    definition_id=NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID,
                    subject_ref=profile_operation_subject(profile.bucket_id),
                    payload=NotificationDocumentViewRequest(profile_id=profile_id, certificado_id=_CERTIFICADO),
                ),
                NotificationDocumentViewPublicResultV1,
            ),
            (
                OperationRequest(
                    definition_id=NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID,
                    subject_ref=profile_operation_subject(profile.bucket_id),
                    payload=NotificationDocumentHistoryRequest(profile_id=profile_id),
                ),
                NotificationDocumentHistoryPublicResultV1,
            ),
        )

        for request, _result_type in requests:
            registration = registry.lookup_public_registration(request.definition_id)
            submit = resolve_operation_access(
                registry=registry,
                request=request,
                context=_access_context(
                    registration,
                    profile_id=profile_id,
                    action=AccessAction.SUBMIT,
                    destination_id=uuid4(),
                    authority=authority,
                ),
            )
            assert submit.request.period_independent
            assert submit.policy.requires_all_periods
            assert AccessAction.COMMIT not in submit.policy.actions

            result_context = _access_context(
                registration,
                profile_id=profile_id,
                action=AccessAction.RESULT,
                destination_id=uuid4(),
                authority=authority,
            )
            result_access = resolve_operation_access(registry=registry, request=request, context=result_context)
            assert result_access.policy.disclosures
            assert all(
                item.projection_id == registration.contract.result_schema.schema_id
                for item in result_access.policy.disclosures
            )
            expected_category = (
                {DisclosureCategory.PROFILE_VALUES, DisclosureCategory.TAX_VALUES}
                if request.definition_id == NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID
                else {DisclosureCategory.TAX_VALUES}
            )
            assert {item.category for item in result_access.policy.disclosures} == expected_category

        foreign_id = uuid4()
        foreign_request = requests[0][0].model_copy(
            update={
                "subject_ref": profile_operation_subject(str(foreign_id)),
                "payload": requests[0][0].payload.model_copy(update={"profile_id": foreign_id}),
            }
        )
        with pytest.raises(ProfileAccessRefusedError) as refusal:
            resolve_operation_access(
                registry=registry,
                request=foreign_request,
                context=_access_context(
                    view_registration,
                    profile_id=profile_id,
                    action=AccessAction.SUBMIT,
                    destination_id=uuid4(),
                    authority=authority,
                ),
            )
        assert refusal.value.reason is AccessDenialCode.PROFILE_MISMATCH

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
        ) -> tuple[OperationPersistedSnapshot, BaseModel]:
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
            return terminal, projected.projection

        view_terminal, view_result = asyncio.run(run(requests[0][0], "3" * 64, requests[0][1]))
        history_terminal, history_result = asyncio.run(run(requests[1][0], "4" * 64, requests[1][1]))

    for terminal in (view_terminal, history_terminal):
        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is OperationEffect.NONE
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.effect is OperationEffect.NONE

    assert isinstance(view_result, NotificationDocumentViewPublicResultV1)
    assert view_result.bucket_id == profile.bucket_id
    assert view_result.certificado_id == _CERTIFICADO
    assert view_result.sancion_parsed
    assert view_result.sancion is not None
    assert view_result.sancion.base_sancion == "3687.120"
    assert view_result.sancion.reduccion_pronto_pago == "516.20"
    assert view_result.sancion.document_sha256 == _DIGEST
    assert set(view_result.model_dump()) == {
        "bucket_id",
        "certificado_id",
        "attachment_id",
        "document_sha256",
        "byte_size",
        "source_url",
        "fetched_at",
        "sancion_parsed",
        "sancion",
        "parse_refusal",
        "mode",
    }

    assert isinstance(history_result, NotificationDocumentHistoryPublicResultV1)
    assert history_result.bucket_id == profile.bucket_id
    assert history_result.count == 2
    assert tuple(row.certificado_id for row in history_result.documents) == (_OTHER_CERTIFICADO, _CERTIFICADO)
    assert tuple(row.sancion.base_sancion for row in history_result.documents) == ("3687.120", "3687.120")
    assert "attachment_id" not in history_result.model_dump()
    assert "source_url" not in history_result.model_dump()
    assert "parse_refusal" not in history_result.model_dump()


def test_document_read_operations_reject_foreign_bucket_records_before_projection(tmp_path: Path) -> None:
    """A foreign record is refused even when history would omit its unparsed row."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, bundled_indexed_authority().operation() as authority:
        profile_id = UUID(profile.bucket_id)
        foreign_record = _record(
            bucket_id=str(uuid4()),
            certificado_id="1234567890",
            fetched_at=_NOW,
            parsed=False,
        )
        repository = _DocumentRepository(profile.bucket_id, (foreign_record,))
        registry = _registry(repository)
        requests = (
            OperationRequest(
                definition_id=NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID,
                subject_ref=profile_operation_subject(profile.bucket_id),
                payload=NotificationDocumentViewRequest(profile_id=profile_id, certificado_id="1234567890"),
            ),
            OperationRequest(
                definition_id=NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID,
                subject_ref=profile_operation_subject(profile.bucket_id),
                payload=NotificationDocumentHistoryRequest(profile_id=profile_id),
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
            owner_id="5" * 64,
            lease_token_factory=lambda: "6" * 64,
            clock=lambda: _NOW,
            lease_duration=timedelta(minutes=5),
        )

        async def run_all() -> tuple[OperationPersistedSnapshot, ...]:
            terminals: list[OperationPersistedSnapshot] = []
            for index, request in enumerate(requests, start=1):
                submitted_id = await supervisor.submit(request, operation_id=str(index + 6) * 64)
                terminals.append(await _run_to_terminal(supervisor, submitted_id))
            return tuple(terminals)

        terminals = asyncio.run(run_all())

    assert len(terminals) == 2
    assert all(terminal.lifecycle is OperationLifecycle.TERMINAL for terminal in terminals)
    assert all(terminal.terminal_condition is not OperationTerminalCondition.SUCCEEDED for terminal in terminals)
