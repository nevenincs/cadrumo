"""CLI surface tests for `aeat app live notifications {list, view, document}`."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import TypedDict

import pytest
from click.testing import Result
from pydantic import ValidationError

from ....adapters.outbound.aeat.sede import NotificationDocument, RemoteNotification
from ....application.live.tests import build_service, sancion_pdf_bytes, served_document
from ....core.bucket_pointer import require_active_bucket_id
from ....core.hashing import sha256_hex
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.aeat_literal_fixtures import NOTIFICATION_DETALLE_SEDE_URL_FIXTURE
from ....tests.cli_envelope import unwrap_cli_result, unwrap_envelope_notices
from ....tests.cli_runner import invoke_cached_cli

# INTENTIONAL: integration because it exercises the notifications CLI surface against
# isolated local storage without contacting AEAT.
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id="00000000-0000-4000-8000-000000000000",
    settings_overrides=lambda tmp_path: {"cadrumo_live_state_dir": tmp_path / "probe-live-state"},
)


def _invoke_notifications(args: Sequence[str]) -> Result:
    return invoke_cached_cli(["app", "live", "notifications", *args])


def test_notifications_list_is_empty_on_fresh_bucket() -> None:
    result = _invoke_notifications(["list"])
    assert result.exit_code == 0, result.output
    assert "count\t0" in result.output


def test_notifications_show_refuses_unknown_snapshot() -> None:
    result = _invoke_notifications(["view", "no-such-snapshot"])
    assert result.exit_code != 0


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
# The custody these tests read back is written through the real service, the
# real encrypted attachment store and the real secure-object repository inside
# an isolated profile root. Nothing is mocked: a stub returning what the
# assertion wants would prove only that the assertion was written.

_CERT = "2699101808461"
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


def _read_row() -> RemoteNotification:
    """Build the notification row AEAT already reports as read."""
    return RemoteNotification(
        certificado_id=_CERT,
        tipo="notificacion",
        concepto="Acuerdo de imposicion de sancion",
        titular_nif="12345678Z",
        titular_nombre="Nombre Apellido",
        destinatario_nif="12345678Z",
        destinatario_nombre="Nombre Apellido",
        fecha_emision=date(2026, 3, 2),
        fecha_notificacion=date(2026, 3, 4),
        modo_notificacion="Comparecencia electronica",
        leida=True,
        source_url=_DETAIL_URL,
    )


def _take_custody_of_an_unreadable_document() -> str:
    """Store one document the reader refuses, and return the owning bucket id.

    A document with no text layer is the honest fixture for the read-back leaf:
    it exercises the refusal path the notice reports, and it does so without
    putting a taxpayer's real sanción figures in this repository.
    """
    data = b"%PDF-1.4 this carries no extractable text layer"
    bucket_id = require_active_bucket_id()
    build_service(bucket_id=bucket_id).persist_document(
        bucket_id=bucket_id,
        row=_read_row(),
        document=NotificationDocument(
            certificado_id=_CERT,
            pdf_bytes=data,
            pdf_sha256=sha256_hex(data),
            source_url=_DETAIL_URL,
        ),
    )
    return bucket_id


def test_document_subgroup_offers_only_the_contract_named_verbs() -> None:
    """The fetch verb is ``pull``; no capture/fetch/refresh/sync/download alias exists."""
    result = _invoke_notifications(["document", "--help"])
    assert result.exit_code == 0, result.output
    assert "pull" in result.output
    assert "view" in result.output
    assert "history" in result.output
    for forbidden in ("capture", "refresh", "fetch", "download", "sync"):
        assert forbidden not in result.output, forbidden


def test_document_view_reads_stored_custody_with_no_aeat_session_available() -> None:
    """The read-back leaf completes against local custody alone.

    The absence of the auth-preflight banner is the load-bearing assertion: it
    is emitted by every leaf that reaches for an authenticated session, so its
    absence is evidence this verb never went near one. There is no AEAT
    provider configured in this environment either, so a leaf that did would
    not have completed.
    """
    _take_custody_of_an_unreadable_document()

    result = _invoke_notifications(["document", "view", _CERT])

    assert result.exit_code == 0, result.output
    assert f"certificado_id\t{_CERT}" in result.output
    assert "sancion_parsed\tFalse" in result.output
    assert "auth_preflight" not in result.output


def test_document_view_refuses_a_certificado_that_is_not_in_custody() -> None:
    """A certificado with no stored document refuses rather than reporting an empty one."""
    result = _invoke_notifications(["document", "view", "9999999999999"])
    assert result.exit_code != 0


def test_document_view_reports_an_unparsed_document_identically_in_json_and_text() -> None:
    """One notice, two renderings, rebuilt from the same value so they cannot drift."""
    _take_custody_of_an_unreadable_document()

    text = _invoke_notifications(["document", "view", _CERT])
    emitted = invoke_cached_cli(["--format", "json", "app", "live", "notifications", "document", "view", _CERT])

    assert text.exit_code == 0, text.output
    assert emitted.exit_code == 0, emitted.output
    notices = unwrap_envelope_notices(emitted.output)
    unparsed = [notice for notice in notices if notice["code"] == "live.notifications.document.unparsed"]
    assert len(unparsed) == 1, notices
    assert unparsed[0]["severity"] == "info"
    assert unparsed[0]["context"]["certificado_id"] == _CERT
    assert unparsed[0]["context"]["parse_refusal"]
    assert f"notice\tlive.notifications.document.unparsed\t{unparsed[0]['message']}" in text.output

    result = unwrap_cli_result(emitted)
    assert result["sancion"] is None
    assert result["sancion_parsed"] is False
    assert result["parse_refusal"]
    assert result["document_sha256"] == result["attachment_id"]


def test_a_document_payload_cannot_claim_a_reading_it_does_not_carry() -> None:
    """The flag, the reading and the refusal must agree, or the payload refuses.

    A payload asserting a reading it does not carry, or reporting neither a
    reading nor a reason for its absence, would let an operator conclude the
    served act held no figures when the truth is that nobody read it.
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
    with pytest.raises(ValidationError):
        NotificationDocumentViewResult(**shared, sancion_parsed=False, sancion=None, parse_refusal=None)

    refused = NotificationDocumentPullResult(
        **shared,
        sancion_parsed=False,
        sancion=None,
        parse_refusal="no text layer",
        already_in_custody=True,
    )
    assert refused.already_in_custody is True
    assert refused.mode == "read"


def test_document_history_lists_two_parsed_documents_without_a_total() -> None:
    bucket_id = require_active_bucket_id()
    service = build_service(bucket_id=bucket_id)
    for certificado_id in ("2699101808461", "2699101808462"):
        service.persist_document(
            bucket_id=bucket_id,
            row=_read_row().model_copy(update={"certificado_id": certificado_id}),
            document=served_document(certificado_id=certificado_id, data=sancion_pdf_bytes()),
        )

    emitted = invoke_cached_cli(["--format", "json", "app", "live", "notifications", "document", "history"])

    assert emitted.exit_code == 0, emitted.output
    result = unwrap_cli_result(emitted)
    assert result["count"] == 2
    assert {row["certificado_id"] for row in result["documents"]} == {"2699101808461", "2699101808462"}
    assert not any("total" in key.casefold() or "balance" in key.casefold() for key in result)
    notices = unwrap_envelope_notices(emitted.output)
    history = [notice for notice in notices if notice["code"] == "live.notifications.document.history_not_balance"]
    assert len(history) == 1
    assert history[0]["context"] == {"document_count": "2", "total_computed": "false"}

    text = _invoke_notifications(["document", "history"])
    assert text.exit_code == 0, text.output
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
        assert f"{field}\t" in text.output


def test_empty_document_history_still_carries_the_no_balance_notice() -> None:
    emitted = invoke_cached_cli(["--format", "json", "app", "live", "notifications", "document", "history"])
    assert emitted.exit_code == 0, emitted.output
    assert unwrap_cli_result(emitted)["documents"] == []
    assert any(
        notice["code"] == "live.notifications.document.history_not_balance"
        for notice in unwrap_envelope_notices(emitted.output)
    )
