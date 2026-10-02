"""Registered notification-document reads preserve exact scope and CLI output."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
import typer
from pydantic import BaseModel

from ....application.live.notification_document_read_operation import (
    NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID,
    NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID,
    NotificationDocumentHistoryEntryPublicV1,
    NotificationDocumentHistoryPublicResultV1,
    NotificationDocumentHistoryRequest,
    NotificationDocumentSancionPublicV1,
    NotificationDocumentViewPublicResultV1,
    NotificationDocumentViewRequest,
)
from ....application.runtime.contracts import RuntimeRefusalCode
from ....core.json_contract import Notice
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .. import _app_live_notifications_cli as handler
from .. import runtime_notification_document_read as bridge
from .._app_live_notifications_payloads import (
    NotificationDocumentHistoryResult,
    NotificationDocumentViewResult,
    SancionReadingPayload,
)
from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import RegisteredOperationCompletion

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_CERT = "2699101808461"
_CERT2 = "2699101808462"
_FETCHED_AT = datetime(2025, 3, 6, 7, 8, tzinfo=UTC)
_DETAIL_URL = f"https://sede.example/notification?ncc={_CERT}"
_DIGEST = "d" * 64


def _sancion(certificado_id: str) -> NotificationDocumentSancionPublicV1:
    return NotificationDocumentSancionPublicV1(
        certificado_id=certificado_id,
        clave_liquidacion="clv-001",
        referencia="SANC-2025-001",
        nif="12345678Z",
        objeto_tributario="sancion",
        base_sancion="1000.00",
        porcentaje_minimo="50.00",
        sancion_resultante="500.00",
        reduccion_conformidad="50.00",
        reduccion_pronto_pago=None,
        diferencia="450.00",
        importe_a_ingresar="450.00",
        document_sha256=_DIGEST,
    )


def _view_projection(*, parsed: bool = True) -> NotificationDocumentViewPublicResultV1:
    sancion = _sancion(_CERT) if parsed else None
    return NotificationDocumentViewPublicResultV1(
        bucket_id=str(_PROFILE),
        certificado_id=_CERT,
        attachment_id=_DIGEST,
        document_sha256=_DIGEST,
        byte_size=123,
        source_url=_DETAIL_URL,
        fetched_at=_FETCHED_AT,
        sancion_parsed=parsed,
        sancion=sancion,
        parse_refusal=None if parsed else "No extractable text layer",
        mode="read",
    )


def _history_projection() -> NotificationDocumentHistoryPublicResultV1:
    return NotificationDocumentHistoryPublicResultV1(
        bucket_id=str(_PROFILE),
        count=2,
        documents=(
            NotificationDocumentHistoryEntryPublicV1(
                certificado_id=_CERT,
                fetched_at=_FETCHED_AT,
                sancion=_sancion(_CERT),
            ),
            NotificationDocumentHistoryEntryPublicV1(
                certificado_id=_CERT2,
                fetched_at=_FETCHED_AT,
                sancion=_sancion(_CERT2),
            ),
        ),
    )


def _bind(
    monkeypatch: pytest.MonkeyPatch,
    projections: Mapping[str, BaseModel],
    *,
    effect: OperationEffect = OperationEffect.NONE,
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED,
    refusal_code: str | None = None,
) -> tuple[list[tuple[BaseModel, dict[str, object]]], list[UUID]]:
    bound_profiles: list[UUID] = []
    client = object()

    def require_client(_ctx: object, *, expected_profile_id: UUID) -> object:
        bound_profiles.append(expected_profile_id)
        return client

    monkeypatch.setattr(bridge, "require_profile_client", require_client)
    submitted: list[tuple[BaseModel, dict[str, object]]] = []

    def submit(submitted_client: object, request: BaseModel, **kwargs: object):
        assert submitted_client is client
        submitted.append((request, kwargs))
        definition_id = cast(str, kwargs["definition_id"])
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projections[definition_id],
            effect=effect,
            terminal_condition=condition,
            refusal_code=refusal_code,
        )

    monkeypatch.setattr(bridge, "run_registered_operation", submit)
    return submitted, bound_profiles


def _context() -> typer.Context:
    return cast(typer.Context, cast(object, None))


def test_view_and_history_submit_exact_profile_requests_and_accept_none_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projections: dict[str, BaseModel] = {
        NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID: _view_projection(),
        NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID: _history_projection(),
    }
    submitted, bound_profiles = _bind(monkeypatch, projections)

    view = bridge.read_notification_document_view_for_cli(
        _context(),
        profile_id=_PROFILE,
        certificado_id=_CERT,
    )
    history = bridge.read_notification_document_history_for_cli(_context(), profile_id=_PROFILE)

    assert bound_profiles == [_PROFILE, _PROFILE]
    assert view.completion.operation_id == history.completion.operation_id == _OPERATION_ID
    assert view.projection == _view_projection()
    assert history.projection == _history_projection()
    assert [request for request, _ in submitted] == [
        NotificationDocumentViewRequest(profile_id=_PROFILE, certificado_id=_CERT),
        NotificationDocumentHistoryRequest(profile_id=_PROFILE),
    ]
    for (_request, options), definition_id, result_type in zip(
        submitted,
        (NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID, NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID),
        (NotificationDocumentViewPublicResultV1, NotificationDocumentHistoryPublicResultV1),
        strict=True,
    ):
        assert options["definition_id"] == definition_id
        assert options["subject_ref"] == profile_operation_subject(str(_PROFILE))
        assert options["result_type"] is result_type
        assert options["request_version"] == options["result_version"] == 1


@pytest.mark.parametrize(
    ("kind", "projection_update", "effect", "condition", "refusal_code"),
    [
        ("view", {"bucket_id": "foreign"}, OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED, None),
        ("view", {"certificado_id": _CERT2}, OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED, None),
        ("history", {"bucket_id": "foreign"}, OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED, None),
        ("history", {"count": 0}, OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED, None),
        ("view", {}, OperationEffect.UPDATED, OperationTerminalCondition.SUCCEEDED, None),
        ("view", {}, OperationEffect.NONE, OperationTerminalCondition.REFUSED, None),
        ("view", {}, OperationEffect.NONE, OperationTerminalCondition.SUCCEEDED, RuntimeRefusalCode.UNAVAILABLE.value),
    ],
)
def test_scope_or_receipt_mismatch_refuses_with_correlated_operation(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    projection_update: dict[str, object],
    effect: OperationEffect,
    condition: OperationTerminalCondition,
    refusal_code: str | None,
) -> None:
    projections: dict[str, BaseModel] = {
        NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID: _view_projection(),
        NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID: _history_projection(),
    }
    definition_id = (
        NOTIFICATION_DOCUMENT_VIEW_DEFINITION_ID if kind == "view" else NOTIFICATION_DOCUMENT_HISTORY_DEFINITION_ID
    )
    projections[definition_id] = projections[definition_id].model_copy(update=projection_update)
    _bind(
        monkeypatch,
        projections,
        effect=effect,
        condition=condition,
        refusal_code=refusal_code,
    )

    with pytest.raises(CliRefusedBoundaryError) as error:
        if kind == "view":
            bridge.read_notification_document_view_for_cli(
                _context(),
                profile_id=_PROFILE,
                certificado_id=_CERT,
            )
        else:
            bridge.read_notification_document_history_for_cli(_context(), profile_id=_PROFILE)

    assert error.value.context is not None
    assert error.value.context["operation_id"] == _OPERATION_ID
    assert error.value.context["reason"] == RuntimeRefusalCode.INVALID_FRAME.value


def test_document_view_preserves_unparsed_payload_notice_and_text(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _view_projection(parsed=False)
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )
    read = bridge.NotificationDocumentViewRead(completion=completion, projection=projection)
    monkeypatch.setattr(handler, "active_bucket_id_or_refuse", lambda: str(_PROFILE))
    monkeypatch.setattr(handler, "read_notification_document_view_for_cli", lambda *_args, **_kwargs: read)
    envelopes: list[dict[str, object]] = []
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))

    handler.notifications_document_view(_context(), _CERT)

    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "app.live.notifications.document.view"
    result = cast(NotificationDocumentViewResult, envelope["result"])
    assert result.bucket_id == str(_PROFILE)
    assert result.certificado_id == _CERT
    assert result.attachment_id == result.document_sha256 == _DIGEST
    assert result.sancion is None
    assert result.sancion_parsed is False
    assert result.parse_refusal == "No extractable text layer"
    notices = cast(list[Notice], envelope["notices"])
    assert len(notices) == 1
    assert notices[0].code == "live.notifications.document.unparsed"
    lines = cast(list[str], envelope["lines"])
    assert "sancion_parsed\tFalse" in lines
    assert any(line.startswith("notice\tlive.notifications.document.unparsed\t") for line in lines)


def test_document_history_preserves_parsed_rows_without_an_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = _history_projection()
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )
    read = bridge.NotificationDocumentHistoryRead(completion=completion, projection=projection)
    monkeypatch.setattr(handler, "active_bucket_id_or_refuse", lambda: str(_PROFILE))
    monkeypatch.setattr(handler, "read_notification_document_history_for_cli", lambda *_args, **_kwargs: read)
    envelopes: list[dict[str, object]] = []
    monkeypatch.setattr(handler, "emit_envelope", lambda *_args, **kwargs: envelopes.append(kwargs))

    handler.notifications_document_history(_context())

    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["command"] == "app.live.notifications.document.history"
    result = cast(NotificationDocumentHistoryResult, envelope["result"])
    assert result.bucket_id == str(_PROFILE)
    assert result.count == 2
    assert [row.certificado_id for row in result.documents] == [_CERT, _CERT2]
    assert result.documents[0].sancion == SancionReadingPayload(
        certificado_id=_CERT,
        clave_liquidacion="clv-001",
        referencia="SANC-2025-001",
        nif="12345678Z",
        objeto_tributario="sancion",
        base_sancion="1000.00",
        porcentaje_minimo="50.00",
        sancion_resultante="500.00",
        reduccion_conformidad="50.00",
        reduccion_pronto_pago=None,
        diferencia="450.00",
        importe_a_ingresar="450.00",
        document_sha256=_DIGEST,
    )
    notices = cast(list[Notice], envelope["notices"])
    assert len(notices) == 1
    assert notices[0].code == "live.notifications.document.history_not_balance"
    assert notices[0].context == {"document_count": "2", "total_computed": "false"}
    lines = cast(list[str], envelope["lines"])
    assert "count\t2" in lines
    assert "base_sancion\t1000.00" in lines
    assert "reduccion_conformidad\t50.00" in lines
    assert all("total" not in field.casefold() and "balance" not in field.casefold() for field in result.model_dump())
