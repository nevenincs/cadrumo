"""CLI surface tests for `aeat app live notifications {list, view, document}`."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import TypedDict, cast
from uuid import UUID

import pytest
import typer
from click.testing import Result
from pydantic import ValidationError

from ....application.live.notification_document_capture_operation import NotificationDocumentCapturePublicResultV1
from ....application.live.notification_document_read_operation import (
    NotificationDocumentHistoryEntryPublicV1,
    NotificationDocumentHistoryPublicResultV1,
    NotificationDocumentSancionPublicV1,
    NotificationDocumentViewPublicResultV1,
)
from ....core.json_contract import Notice, NoticeSeverity
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....tests.aeat_literal_fixtures import NOTIFICATION_DETALLE_SEDE_URL_FIXTURE
from .. import _app_live_notifications_cli as handler
from .. import runtime_notification_document_capture as capture_bridge
from .. import runtime_notification_document_read as bridge
from .._app_live_notifications_payloads import (
    NotificationDocumentHistoryResult,
    NotificationDocumentPullResult,
    NotificationDocumentViewResult,
)
from ..errors import CliRefusedBoundaryError
from ..registered_operation_contracts import RegisteredOperationCompletion
from ..registered_operation_errors import submitted_operation_error
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _invoke_notifications(args: Sequence[str]) -> Result:
    return invoke_cached_cli(["app", "live", "notifications", *args])


def test_notification_snapshot_payloads_refuse_malformed_identity_time_url_and_count() -> None:
    """Notification transport preserves the persisted snapshot's strict fields."""

    from .._app_live_notifications_payloads import NotificationsCaptureResult, NotificationSnapshotListingPayload

    instant = datetime(2026, 8, 1, tzinfo=UTC)
    with pytest.raises(ValidationError):
        NotificationSnapshotListingPayload(snapshot_id="bad", captured_at=instant, row_count=0)
    with pytest.raises(ValidationError):
        NotificationSnapshotListingPayload(snapshot_id="a" * 64, captured_at="not-a-timestamp", row_count=0)
    with pytest.raises(ValidationError):
        NotificationSnapshotListingPayload(snapshot_id="a" * 64, captured_at=instant, row_count=-1)
    with pytest.raises(ValidationError):
        NotificationsCaptureResult(
            bucket_id="00000000-0000-4000-8000-000000000000",
            snapshot_id="a" * 64,
            captured_at=instant,
            persisted_at=instant,
            row_count=0,
            source_url="",
        )


# ── Notification document leaves ───────────────────────────────────────────
#
# The registered operation and encrypted-service tests cover custody. These
# handler tests inject its typed public result so the CLI projection can be
# checked without trying to share in-process storage with a profile worker.

_CERT = "2699101808461"
_CERT2 = "2699101808462"
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OPERATION_ID = "a" * 64
_DETAIL_URL = f"{NOTIFICATION_DETALLE_SEDE_URL_FIXTURE}?ncc=2699101808461"


class _NotificationDocumentShared(TypedDict):
    """Common typed fields passed to notification document payload models."""

    bucket_id: str
    certificado_id: str
    attachment_id: str
    document_sha256: str
    byte_size: int
    source_url: str
    fetched_at: datetime


def _sancion(certificado_id: str) -> NotificationDocumentSancionPublicV1:
    """Build a synthetic public projection with decimal scale preserved."""
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
        document_sha256="d" * 64,
    )


def _view_projection(*, parsed: bool = False) -> NotificationDocumentViewPublicResultV1:
    return NotificationDocumentViewPublicResultV1(
        bucket_id=str(_PROFILE),
        certificado_id=_CERT,
        attachment_id="d" * 64,
        document_sha256="d" * 64,
        byte_size=123,
        source_url=_DETAIL_URL,
        fetched_at=datetime(2025, 3, 6, 7, 8, tzinfo=UTC),
        sancion_parsed=parsed,
        sancion=_sancion(_CERT) if parsed else None,
        parse_refusal=None if parsed else "No extractable text layer",
        mode="read",
    )


def _history_projection(*, count: int = 2) -> NotificationDocumentHistoryPublicResultV1:
    rows = (
        NotificationDocumentHistoryEntryPublicV1(
            certificado_id=_CERT,
            fetched_at=datetime(2025, 3, 6, 7, 8, tzinfo=UTC),
            sancion=_sancion(_CERT),
        ),
        NotificationDocumentHistoryEntryPublicV1(
            certificado_id=_CERT2,
            fetched_at=datetime(2025, 3, 5, 7, 8, tzinfo=UTC),
            sancion=_sancion(_CERT2),
        ),
    )
    return NotificationDocumentHistoryPublicResultV1(
        bucket_id=str(_PROFILE),
        count=count,
        documents=rows[:count],
    )


def _view_read(projection: NotificationDocumentViewPublicResultV1) -> bridge.NotificationDocumentViewRead:
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )
    return bridge.NotificationDocumentViewRead(completion=completion, projection=projection)


def _history_read(
    projection: NotificationDocumentHistoryPublicResultV1,
) -> bridge.NotificationDocumentHistoryRead:
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )
    return bridge.NotificationDocumentHistoryRead(completion=completion, projection=projection)


def _context() -> typer.Context:
    return cast(typer.Context, cast(object, None))


class _CapturedEnvelope(TypedDict):
    result: object
    lines: tuple[str, ...]
    notices: tuple[Notice, ...]


def _capture_envelope(monkeypatch: pytest.MonkeyPatch) -> list[_CapturedEnvelope]:
    envelopes: list[_CapturedEnvelope] = []

    def capture(
        _ctx: typer.Context,
        *,
        command: str,
        result: object,
        lines: Iterable[str],
        notices: Sequence[Notice] | None = None,
    ) -> None:
        del command
        envelopes.append({"result": result, "lines": tuple(lines), "notices": tuple(notices or ())})

    monkeypatch.setattr(handler, "active_bucket_id_or_refuse", lambda: str(_PROFILE))
    monkeypatch.setattr(handler, "emit_envelope", capture)
    return envelopes


def test_document_subgroup_offers_only_the_contract_named_verbs() -> None:
    """The fetch verb is ``pull``; no capture/fetch/refresh/sync/download alias exists."""
    result = _invoke_notifications(["document", "--help"])
    assert result.exit_code == 0, result.output
    assert "pull" in result.output
    assert "view" in result.output
    assert "history" in result.output
    for forbidden in ("capture", "refresh", "fetch", "download", "sync"):
        assert forbidden not in result.output, forbidden


def test_document_view_reads_registered_projection_without_aeat_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """The registered local read renders its typed result without auth preflight."""
    envelopes = _capture_envelope(monkeypatch)
    monkeypatch.setattr(
        handler, "read_notification_document_view_for_cli", lambda *_args, **_kwargs: _view_read(_view_projection())
    )
    monkeypatch.setattr(handler, "emit_live_auth_preflight", lambda *_args: pytest.fail("view invoked auth preflight"))

    handler.notifications_document_view(_context(), _CERT)

    assert len(envelopes) == 1
    result = envelopes[0]["result"]
    assert isinstance(result, NotificationDocumentViewResult)
    assert result.certificado_id == _CERT
    assert result.sancion_parsed is False
    assert "sancion_parsed\tFalse" in envelopes[0]["lines"]
    assert "auth_preflight" not in envelopes[0]["lines"]


def test_document_view_refuses_a_certificado_that_is_not_in_custody(monkeypatch: pytest.MonkeyPatch) -> None:
    """A registered not-found refusal remains correlated at the CLI boundary."""

    def refuse(*_args: object, **_kwargs: object) -> bridge.NotificationDocumentViewRead:
        raise submitted_operation_error(
            _OPERATION_ID,
            "notification_document_not_found",
            terminal_condition=OperationTerminalCondition.REFUSED,
            effect=OperationEffect.NONE,
        )

    monkeypatch.setattr(handler, "active_bucket_id_or_refuse", lambda: str(_PROFILE))
    monkeypatch.setattr(handler, "read_notification_document_view_for_cli", refuse)

    with pytest.raises(CliRefusedBoundaryError) as refused:
        handler.notifications_document_view(_context(), "9999999999999")

    assert refused.value.context is not None
    assert refused.value.context["operation_id"] == _OPERATION_ID
    assert refused.value.context["reason"] == "notification_document_not_found"


def test_document_view_reports_an_unparsed_document_identically_in_json_and_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same unparsed notice value feeds the JSON envelope and text line."""
    envelopes = _capture_envelope(monkeypatch)
    monkeypatch.setattr(
        handler, "read_notification_document_view_for_cli", lambda *_args, **_kwargs: _view_read(_view_projection())
    )

    handler.notifications_document_view(_context(), _CERT)

    assert len(envelopes) == 1
    emitted = envelopes[0]
    result = emitted["result"]
    assert isinstance(result, NotificationDocumentViewResult)
    assert result.sancion is None
    assert result.sancion_parsed is False
    assert result.parse_refusal == "No extractable text layer"
    assert result.document_sha256 == result.attachment_id
    notices = emitted["notices"]
    unparsed = [notice for notice in notices if notice.code == "live.notifications.document.unparsed"]
    assert len(unparsed) == 1
    assert unparsed[0].severity is NoticeSeverity.INFO
    assert unparsed[0].context == {"certificado_id": _CERT, "parse_refusal": "No extractable text layer"}
    assert f"notice\tlive.notifications.document.unparsed\t{unparsed[0].message}" in emitted["lines"]


def test_document_pull_preserves_comparecencia_and_already_in_custody_notices(monkeypatch: pytest.MonkeyPatch) -> None:
    projection = NotificationDocumentCapturePublicResultV1(
        bucket_id=str(_PROFILE),
        certificado_id=_CERT,
        attachment_id="d" * 64,
        document_sha256="d" * 64,
        byte_size=123,
        source_url=_DETAIL_URL,
        fetched_at=datetime(2025, 3, 6, 7, 8, tzinfo=UTC),
        sancion_parsed=False,
        sancion=None,
        parse_refusal="No extractable text layer",
        mode="read",
        already_in_custody=True,
    )
    completion = RegisteredOperationCompletion(
        operation_id=_OPERATION_ID,
        projection=projection,
        effect=OperationEffect.NONE,
    )
    captured = capture_bridge.NotificationDocumentCapture(completion=completion, projection=projection)
    envelopes = _capture_envelope(monkeypatch)
    monkeypatch.setattr(handler, "emit_live_auth_preflight", lambda *_args: None)
    monkeypatch.setattr(handler, "capture_notification_document_for_cli", lambda *_args, **_kwargs: captured)

    handler.notifications_document_pull(_context(), _CERT)

    assert len(envelopes) == 1
    emitted = envelopes[0]
    result = emitted["result"]
    assert isinstance(result, NotificationDocumentPullResult)
    assert result.already_in_custody is True
    assert result.certificado_id == _CERT
    assert "already_in_custody\tTrue" in emitted["lines"]
    notices = emitted["notices"]
    by_code = {notice.code: notice for notice in notices}
    assert set(by_code) == {
        "live.notifications.document.comparecencia_guarded",
        "live.notifications.document.already_in_custody",
        "live.notifications.document.unparsed",
    }
    assert by_code["live.notifications.document.comparecencia_guarded"].context == {
        "certificado_id": _CERT,
        "comparecencia_performed": "false",
    }
    assert by_code["live.notifications.document.already_in_custody"].context == {
        "certificado_id": _CERT,
        "document_sha256": "d" * 64,
        "fetched_at": "2025-03-06T07:08:00+00:00",
    }
    assert any(line.startswith("notice\tlive.notifications.document.already_in_custody\t") for line in emitted["lines"])


def test_a_document_payload_cannot_claim_a_reading_it_does_not_carry() -> None:
    """The wire flag must agree with the reading it summarises, or the payload refuses.

    ``sancion_parsed`` exists nowhere but on this schema, so this is the only
    layer that can hold it to its definition, and a payload asserting a reading
    it does not carry would send a JSON client after figures that are not
    there.

    That a document carries either a reading or the reason there is none is a
    rule about the stored record, not about this projection, and it is enforced
    on ``NotificationDocumentRecord`` rather than restated here.
    """
    from .._app_live_notifications_payloads import NotificationDocumentPullResult, NotificationDocumentViewResult

    shared: _NotificationDocumentShared = {
        "bucket_id": "00000000-0000-4000-8000-000000000000",
        "certificado_id": _CERT,
        "attachment_id": "a" * 64,
        "document_sha256": "a" * 64,
        "byte_size": 12,
        "source_url": _DETAIL_URL,
        "fetched_at": datetime(2026, 8, 1, tzinfo=UTC),
    }
    with pytest.raises(ValidationError):
        NotificationDocumentViewResult(**shared, sancion_parsed=True, sancion=None, parse_refusal="no text layer")

    refused = NotificationDocumentPullResult(
        **shared,
        sancion_parsed=False,
        sancion=None,
        parse_refusal="no text layer",
        already_in_custody=True,
    )
    assert refused.already_in_custody is True
    assert refused.mode == "read"


def test_document_history_lists_registered_parsed_documents_without_a_total(monkeypatch: pytest.MonkeyPatch) -> None:
    envelopes = _capture_envelope(monkeypatch)
    monkeypatch.setattr(
        handler,
        "read_notification_document_history_for_cli",
        lambda *_args, **_kwargs: _history_read(_history_projection()),
    )

    handler.notifications_document_history(_context())

    assert len(envelopes) == 1
    emitted = envelopes[0]
    result = emitted["result"]
    assert isinstance(result, NotificationDocumentHistoryResult)
    assert result.count == 2
    assert {row.certificado_id for row in result.documents} == {_CERT, _CERT2}
    dumped = result.model_dump(mode="json")
    assert not any("total" in key.casefold() or "balance" in key.casefold() for key in dumped)
    notices = emitted["notices"]
    history = [notice for notice in notices if notice.code == "live.notifications.document.history_not_balance"]
    assert len(history) == 1
    assert history[0].context == {"document_count": "2", "total_computed": "false"}
    lines = emitted["lines"]
    for field in (
        "clave_liquidacion",
        "referencia",
        "objeto_tributario",
        "base_sancion",
        "porcentaje_minimo",
        "sancion_resultante",
        "reduccion_conformidad",
        "reduccion_pronto_pago",
        "diferencia",
        "importe_a_ingresar",
    ):
        assert any(line.startswith(f"{field}\t") for line in lines)
    assert "base_sancion\t1000.00" in lines


def test_empty_document_history_still_carries_the_no_balance_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    envelopes = _capture_envelope(monkeypatch)
    monkeypatch.setattr(
        handler,
        "read_notification_document_history_for_cli",
        lambda *_args, **_kwargs: _history_read(_history_projection(count=0)),
    )

    handler.notifications_document_history(_context())

    assert len(envelopes) == 1
    emitted = envelopes[0]
    result = emitted["result"]
    assert isinstance(result, NotificationDocumentHistoryResult)
    assert result.documents == []
    notices = emitted["notices"]
    assert any(notice.code == "live.notifications.document.history_not_balance" for notice in notices)
