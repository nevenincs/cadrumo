"""A capture that only refreshed the AEAT session still releases its result.

When the remote read writes the provider session but stores nothing new, the
executor reports UPDATED for the session write. The registered projector must
accept the receipt the executor itself published for that outcome.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.operation_definition import OperationDefinition
from ...operations.registry import OperationPublicDefinitionRegistrationV1
from .. import notification_document_capture_operation as document_module
from .. import notifications_capture_operation as notifications_module
from ..live_operation_registration import require_live_capture_receipt
from ..notification_document_capture_operation import (
    NotificationDocumentCapturePublicResultV1,
    NotificationDocumentCaptureRequest,
    build_notification_document_capture_definition,
    build_notification_document_capture_registration,
)
from ..notification_documents import NotificationDocumentCustody, NotificationDocumentRecord
from ..notifications import NotificationsCaptureOutcome, PersistedNotificationsSnapshot
from ..notifications_capture_operation import (
    NOTIFICATIONS_CAPTURE_DEFINITION_ID,
    NotificationsCapturePublicResultV1,
    NotificationsCaptureRequest,
    build_notifications_capture_definition,
    build_notifications_capture_registration,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PROFILE_ID = UUID("11111111-1111-4111-8111-111111111111")
_NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)


class _Resources:
    @contextmanager
    def activate(self):
        yield

    async def close(self) -> None:
        return None


class _Events:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []

    async def phase(self, phase: str) -> None:
        del phase

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        yield


class _Operands:
    report: BaseModel | None = None

    async def put(self, report: BaseModel, *, written_at: datetime) -> str:
        del written_at
        self.report = report
        return "c" * 64


class _Cleanup:
    def own(self, resource: object, *, family: object) -> None:
        del resource, family


def _execute_and_project(
    definition: OperationDefinition,
    registration: OperationPublicDefinitionRegistrationV1,
    payload: BaseModel,
) -> BaseModel:
    """Run the real executor, then project its result against the receipt it published."""
    identity = OperationIdentity(
        operation_id="b" * 64,
        definition_id=definition.definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
    )
    events = _Events()
    operands = _Operands()
    context = SimpleNamespace(
        identity=identity,
        authority_operation=object(),
        events=events,
        cancellation=_Cancellation(),
        operands=operands,
        cleanup=_Cleanup(),
    )
    request = OperationRequest[BaseModel](
        definition_id=definition.definition_id, subject_ref=identity.subject_ref, payload=payload
    )
    reference = asyncio.run(definition.executor_factory.create().execute(request, cast(Any, context)))
    assert isinstance(reference, str)
    assert operands.report is not None
    published_effect = events.effects[-1]
    assert published_effect is OperationEffect.UPDATED
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=0,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=published_effect,
        settled_at=_NOW,
        result_ref=reference,
    )
    projector = registration.result_projector
    assert projector is not None
    return projector(operands.report, receipt)


async def _write_session(on_session_write: Callable[[OperationEffect], Any]) -> None:
    await on_session_write(OperationEffect.UNKNOWN)
    await on_session_write(OperationEffect.UPDATED)


def _composition() -> Any:
    return SimpleNamespace(
        notifications_ports=object(),
        certificate_secret_backend_factory=object(),
        browser_session_factory=object(),
        operator_scope_ports=object(),
    )


def test_notifications_capture_releases_a_session_only_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    snapshot = PersistedNotificationsSnapshot(
        snapshot_id="d" * 64,
        bucket_id=str(_PROFILE_ID),
        captured_at=_NOW,
        source_url="https://sede.agenciatributaria.gob.es/example",
        rows=(),
        persisted_at=_NOW,
    )

    async def capture(**kwargs: object) -> NotificationsCaptureOutcome:
        await _write_session(cast(Any, kwargs["on_session_write"]))
        return NotificationsCaptureOutcome(snapshot=snapshot, newly_persisted=False)

    monkeypatch.setattr(notifications_module, "require_active_bucket_id", lambda: str(_PROFILE_ID))
    monkeypatch.setattr(notifications_module, "capture_notifications_with_outcome", capture)
    definition = build_notifications_capture_definition(
        lambda *, operation: _composition(), lambda: cast(Any, _Resources()), lambda _profile, _operation: None
    )

    projection = _execute_and_project(
        definition,
        build_notifications_capture_registration(definition),
        NotificationsCaptureRequest(profile_id=_PROFILE_ID),
    )

    assert isinstance(projection, NotificationsCapturePublicResultV1)
    assert projection.snapshot_id == snapshot.snapshot_id


def test_notification_document_capture_releases_a_session_only_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    record = NotificationDocumentRecord(
        certificado_id="2699101808461",
        bucket_id=str(_PROFILE_ID),
        attachment_id="a" * 64,
        document_sha256="a" * 64,
        byte_size=47,
        source_url="https://sede.agenciatributaria.gob.es/example",
        fetched_at=_NOW,
        sancion=None,
        parse_refusal="no text layer",
    )

    async def pull(**kwargs: object) -> NotificationDocumentCustody:
        await _write_session(cast(Any, kwargs["on_session_write"]))
        return NotificationDocumentCustody(record=record, already_in_custody=True)

    monkeypatch.setattr(document_module, "require_active_bucket_id", lambda: str(_PROFILE_ID))
    monkeypatch.setattr(document_module, "pull_notification_document", pull)
    definition = build_notification_document_capture_definition(
        lambda *, operation: _composition(),
        lambda: cast(Any, object()),
        lambda: cast(Any, _Resources()),
        lambda _profile, _operation: None,
    )

    projection = _execute_and_project(
        definition,
        build_notification_document_capture_registration(definition),
        NotificationDocumentCaptureRequest(profile_id=_PROFILE_ID, certificado_id=record.certificado_id),
    )

    assert isinstance(projection, NotificationDocumentCapturePublicResultV1)
    assert projection.already_in_custody


@pytest.mark.parametrize(
    ("stored", "effect", "accepted"),
    [
        (True, OperationEffect.UPDATED, True),
        (True, OperationEffect.NONE, False),
        (False, OperationEffect.NONE, True),
        (False, OperationEffect.UPDATED, True),
        (False, OperationEffect.PARTIAL, False),
    ],
)
def test_capture_receipt_accepts_only_the_effects_its_outcome_can_publish(
    stored: bool, effect: OperationEffect, accepted: bool
) -> None:
    identity = OperationIdentity(
        operation_id="b" * 64,
        definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE_ID)),
    )
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=0,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=effect,
        settled_at=_NOW,
        result_ref="c" * 64,
    )

    def check() -> None:
        require_live_capture_receipt(
            receipt,
            definition_id=NOTIFICATIONS_CAPTURE_DEFINITION_ID,
            bucket_id=str(_PROFILE_ID),
            stored=stored,
            message="capture contradicts its receipt",
        )

    if accepted:
        check()
    else:
        with pytest.raises(ValueError, match="capture contradicts its receipt"):
            check()
