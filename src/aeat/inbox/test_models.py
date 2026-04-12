"""Unit tests for the inbox pydantic models.

Covers schema round-trip, strict-validation rejections, and the
:class:`Inbox` unique-id invariant.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, ValidationError

from aeat.i18n import Translatable
from aeat.inbox import (
    Inbox,
    Notificacion,
    NotificacionKind,
    NotificacionPriority,
)

_SUBJECT: Translatable = {"es": "Requerimiento de información", "en": "Information request", "hu": "Tájékoztatáskérés"}
_BODY: Translatable = {"es": "Solicitamos...", "en": "We request...", "hu": "Kérjük..."}
_URL = AnyHttpUrl("https://sede.agenciatributaria.gob.es/notif/AEAT-0001")
_RECEIVED = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)


def _sample_notificacion(
    *,
    notificacion_id: str = "AEAT-0001",
    received_at: datetime = _RECEIVED,
    effective_at: datetime | None = None,
    acknowledged_at: datetime | None = None,
    acknowledged_by: str | None = None,
    attached_pdf_sha256: str | None = None,
    attached_pdf_path: Path | None = None,
    appeal_deadline: date | None = None,
) -> Notificacion:
    """Return a minimal valid :class:`Notificacion` with patchable fields."""
    return Notificacion(
        notificacion_id=notificacion_id,
        kind=NotificacionKind.REQUERIMIENTO,
        priority=NotificacionPriority.CRITICAL,
        subject=_SUBJECT,
        body_excerpt=_BODY,
        received_at=received_at,
        effective_at=effective_at if effective_at is not None else received_at,
        appeal_deadline=appeal_deadline,
        attached_pdf_path=attached_pdf_path,
        attached_pdf_sha256=attached_pdf_sha256,
        source_url=_URL,
        acknowledged_at=acknowledged_at,
        acknowledged_by=acknowledged_by,
    )


@pytest.mark.unit
class TestNotificacion:
    def test_round_trip(self) -> None:
        original = _sample_notificacion()
        reloaded = Notificacion.model_validate_json(original.model_dump_json())
        assert reloaded == original

    def test_rejects_effective_before_received(self) -> None:
        with pytest.raises(ValidationError):
            _sample_notificacion(
                received_at=datetime(2026, 4, 2, tzinfo=UTC),
                effective_at=datetime(2026, 4, 1, tzinfo=UTC),
            )

    def test_rejects_ack_half_set(self) -> None:
        with pytest.raises(ValidationError):
            _sample_notificacion(acknowledged_at=datetime(2026, 4, 2, tzinfo=UTC))
        with pytest.raises(ValidationError):
            _sample_notificacion(acknowledged_by="gw")

    def test_rejects_ack_before_received(self) -> None:
        with pytest.raises(ValidationError):
            _sample_notificacion(
                acknowledged_at=datetime(2026, 3, 1, tzinfo=UTC),
                acknowledged_by="gw",
            )

    def test_rejects_bad_pdf_sha(self) -> None:
        with pytest.raises(ValidationError):
            _sample_notificacion(attached_pdf_sha256="deadbeef")

    def test_rejects_empty_id(self) -> None:
        with pytest.raises(ValidationError):
            _sample_notificacion(notificacion_id="")

    def test_frozen(self) -> None:
        record = _sample_notificacion()
        with pytest.raises(ValidationError):
            record.notificacion_id = "AEAT-0002"  # type: ignore[misc]


@pytest.mark.unit
class TestInbox:
    def test_round_trip(self) -> None:
        record = _sample_notificacion()
        inbox = Inbox(entries={record.notificacion_id: record})
        reloaded = Inbox.model_validate_json(inbox.model_dump_json())
        assert reloaded.get("AEAT-0001") == record

    def test_rejects_mismatched_key(self) -> None:
        record = _sample_notificacion(notificacion_id="AEAT-0001")
        with pytest.raises(ValidationError):
            Inbox(entries={"AEAT-OTHER": record})

    def test_upsert_and_values(self) -> None:
        inbox = Inbox()
        assert inbox.values() == ()
        record = _sample_notificacion()
        inbox.upsert(record)
        assert inbox.values() == (record,)
        assert inbox.get("AEAT-0001") == record
        assert inbox.get("missing") is None
