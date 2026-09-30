"""Guard and receipt checks for the registered notification document pull."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ..notification_document_capture_operation import (
    NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID,
    NotificationDocumentCaptureOperationReport,
    NotificationDocumentCapturePublicResultV1,
    NotificationDocumentCaptureRequest,
    build_notification_document_capture_definition,
    build_notification_document_capture_registration,
)
from ..notification_documents import (
    NotificationDocumentCustody,
    NotificationDocumentRecord,
    NotificationDocumentService,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PROFILE_ID = UUID("11111111-1111-4111-8111-111111111111")
_CERTIFICADO = "2699101808461"
_NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)


def _record() -> NotificationDocumentRecord:
    return NotificationDocumentRecord(
        certificado_id=_CERTIFICADO,
        bucket_id=str(_PROFILE_ID),
        attachment_id="a" * 64,
        document_sha256="a" * 64,
        byte_size=47,
        source_url="https://sede.agenciatributaria.gob.es/example",
        fetched_at=_NOW,
        sancion=None,
        parse_refusal="no text layer",
    )


def test_service_fetches_only_after_legal_guard_and_persists_under_fresh_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    document = object()

    def legal_guard(_row: object) -> None:
        events.append("legal-guard")

    async def fetch(_session: object, _row: object, *, settings: object) -> object:
        assert settings is not None
        events.append("remote-fetch")
        return document

    service = NotificationDocumentService(
        settings=cast(Any, object()),
        attachment_store=cast(Any, object()),
        repository_factory=cast(Any, object()),
        content_guard=cast(Any, legal_guard),
        document_fetcher=cast(Any, fetch),
        document_reader=cast(Any, object()),
    )
    custody = NotificationDocumentCustody(record=_record(), already_in_custody=False)

    def persist_document(*, bucket_id: str, row: object, document: object) -> NotificationDocumentCustody:
        assert bucket_id == str(_PROFILE_ID)
        assert row is not None and document is not None
        events.append("local-custody")
        return custody

    monkeypatch.setattr(service, "persist_document", persist_document)

    @asynccontextmanager
    async def guard() -> AsyncIterator[None]:
        events.append("commit-enter")
        try:
            yield
        finally:
            events.append("commit-exit")

    result = asyncio.run(
        service.pull_document(bucket_id=str(_PROFILE_ID), session=object(), row=cast(Any, object()), effect_guard=guard)
    )
    assert result is custody
    assert events == ["legal-guard", "remote-fetch", "commit-enter", "local-custody", "commit-exit"]


def test_registered_pull_owns_process_and_projects_dedup_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    from .. import notification_document_capture_operation as module

    events: list[str] = []
    authority = object()
    custody = NotificationDocumentCustody(record=_record(), already_in_custody=True)
    identity = OperationIdentity(
        operation_id="b" * 64,
        definition_id=NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
    )

    class Resources:
        @contextmanager
        def activate(self):
            events.append("resources-activate")
            try:
                yield
            finally:
                events.append("resources-deactivate")

        async def close(self) -> None:
            events.append("resources-close")

    class Events:
        async def phase(self, phase: str) -> None:
            events.append(phase)

        async def effect(self, effect: OperationEffect) -> None:
            events.append(f"effect:{effect.value}")

    class Cancellation:
        @asynccontextmanager
        async def irreversible_section(self) -> AsyncIterator[None]:
            events.append("commit-enter")
            try:
                yield
            finally:
                events.append("commit-exit")

    class Operands:
        report: NotificationDocumentCaptureOperationReport | None = None

        async def put(self, report: NotificationDocumentCaptureOperationReport, *, written_at: datetime) -> str:
            assert written_at.tzinfo is not None
            self.report = report
            events.append("result-put")
            return "result-ref"

    class Cleanup:
        def own(self, resource: object, *, family: object) -> None:
            assert resource is resources and getattr(family, "value", family) == "process"
            events.append("process-owned")

    resources = Resources()
    operands = Operands()
    context = SimpleNamespace(
        identity=identity,
        authority_operation=authority,
        events=Events(),
        cancellation=Cancellation(),
        operands=operands,
        cleanup=Cleanup(),
    )
    composition = SimpleNamespace(
        notifications_ports=object(),
        certificate_secret_backend_factory=object(),
        browser_session_factory=object(),
        operator_scope_ports=object(),
    )
    monkeypatch.setattr(module, "require_active_bucket_id", lambda: str(_PROFILE_ID))

    def preflight(profile_id: UUID, pinned: object) -> None:
        assert profile_id == _PROFILE_ID and pinned is authority
        events.append("provider-preflight")

    async def pull(**kwargs: object) -> NotificationDocumentCustody:
        assert kwargs["authority_operation"] is authority
        assert kwargs["certificado_id"] == _CERTIFICADO
        events.append("remote-fetch")
        guard = cast(Any, kwargs["effect_guard"])
        async with guard():
            events.append("local-custody")
        return custody

    monkeypatch.setattr(module, "pull_notification_document", pull)
    definition = build_notification_document_capture_definition(
        lambda: cast(Any, composition), lambda: cast(Any, object()), lambda: cast(Any, resources), preflight
    )
    request = OperationRequest(
        definition_id=NOTIFICATION_DOCUMENT_CAPTURE_DEFINITION_ID,
        subject_ref=identity.subject_ref,
        payload=NotificationDocumentCaptureRequest(profile_id=_PROFILE_ID, certificado_id=_CERTIFICADO),
    )
    reference = asyncio.run(definition.executor_factory.build().execute(request, cast(Any, context)))
    assert reference == "result-ref"
    assert operands.report is not None
    assert events.index("remote-fetch") < events.index("commit-enter") < events.index("local-custody")
    assert "effect:unknown" in events and "effect:none" in events
    assert "process-owned" in events
    registration = build_notification_document_capture_registration(definition)
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=0,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=_NOW,
        result_ref=reference,
    )
    projector = registration.result_projector
    assert projector is not None
    projection = projector(operands.report, receipt)
    assert isinstance(projection, NotificationDocumentCapturePublicResultV1)
    assert projection.already_in_custody
    assert projection.bucket_id == str(_PROFILE_ID)
    assert projection.sancion is None
