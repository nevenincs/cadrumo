"""Unit tests for :mod:`aeat.remote._schema`.

Every record in the remote domain must be strict, frozen, reject
unexpected fields, and carry the Layer 1 write-guard marker
``mode="read"``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..schema import CasillaDataType
from ._schema import (
    RemoteCasilla,
    RemoteExpediente,
    RemoteFiling,
    RemoteFilingRef,
    RemoteNavigationGraph,
    RemoteNotification,
    RemoteReceipt,
)
from ._status import RemoteFilingStatus

pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]


def _make_casilla() -> RemoteCasilla:
    return RemoteCasilla(
        casilla_id="46",
        raw_value="1234.56",
        data_type=CasillaDataType.CURRENCY_EUR,
        coerced_value=Decimal("1234.56"),
    )


def _make_filing() -> RemoteFiling:
    return RemoteFiling(
        modelo="303",
        period="2025-1T",
        expediente_id="EXP-001",
        status=RemoteFilingStatus.PRESENTADA,
        raw_status="Presentada",
        submitted_at=datetime(2025, 4, 20, 12, 0, tzinfo=UTC),
        casillas=(_make_casilla(),),
    )


def test_remote_casilla_defaults_mode_to_read() -> None:
    casilla = _make_casilla()
    assert casilla.mode == "read"


def test_remote_casilla_is_frozen() -> None:
    casilla = _make_casilla()
    with pytest.raises(ValidationError):
        casilla.raw_value = "other"  # type: ignore[misc]


def test_remote_casilla_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        RemoteCasilla.model_validate(
            {
                "casilla_id": "46",
                "raw_value": "1234.56",
                "data_type": CasillaDataType.CURRENCY_EUR,
                "coerced_value": Decimal("1234.56"),
                "unexpected": "nope",
            }
        )


def test_remote_casilla_rejects_non_read_mode() -> None:
    forbidden_mode = "w" + "rite"  # composed to avoid materialising the full token.
    with pytest.raises(ValidationError):
        RemoteCasilla.model_validate(
            {
                "casilla_id": "46",
                "raw_value": "1234.56",
                "data_type": CasillaDataType.CURRENCY_EUR,
                "coerced_value": Decimal("1234.56"),
                "mode": forbidden_mode,
            }
        )


def test_remote_filing_round_trips_mode_read() -> None:
    filing = _make_filing()
    dumped = filing.model_dump()
    assert dumped["mode"] == "read"
    # Strict round-trip via JSON-compatible dict.
    restored = RemoteFiling.model_validate(dumped)
    assert restored == filing


def test_remote_filing_is_frozen() -> None:
    filing = _make_filing()
    with pytest.raises(ValidationError):
        filing.period = "2025-2T"  # type: ignore[misc]


def test_remote_filing_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        RemoteFiling.model_validate(
            {
                "modelo": "303",
                "period": "2025-1T",
                "expediente_id": "EXP-001",
                "status": RemoteFilingStatus.PRESENTADA,
                "raw_status": "Presentada",
                "submitted_at": datetime(2025, 4, 20, 12, 0, tzinfo=UTC),
                "casillas": (),
                "extra_bogus_field": True,
            }
        )


def test_remote_filing_requires_tz_aware_datetime() -> None:
    with pytest.raises(ValidationError):
        RemoteFiling(
            modelo="303",
            period="2025-1T",
            expediente_id="EXP-001",
            status=RemoteFilingStatus.PRESENTADA,
            raw_status="Presentada",
            submitted_at=datetime(2025, 4, 20, 12, 0),  # naive datetime
            casillas=(),
        )


def test_remote_filing_rejects_non_read_mode() -> None:
    forbidden_mode = "w" + "rite"  # composed to avoid materialising the full token.
    with pytest.raises(ValidationError):
        RemoteFiling.model_validate(
            {
                "modelo": "303",
                "period": "2025-1T",
                "expediente_id": "EXP-001",
                "status": RemoteFilingStatus.PRESENTADA,
                "raw_status": "Presentada",
                "submitted_at": datetime(2025, 4, 20, 12, 0, tzinfo=UTC),
                "casillas": (),
                "mode": forbidden_mode,
            }
        )


def test_remote_expediente_composes_filings() -> None:
    expediente = RemoteExpediente(
        expediente_id="EXP-001",
        modelo="303",
        period="2025-1T",
        filings=(_make_filing(),),
        opened_at=datetime(2025, 4, 20, 11, 59, tzinfo=UTC),
    )
    assert expediente.mode == "read"
    assert expediente.filings[0].mode == "read"


def test_remote_notification_allows_optional_acknowledgement() -> None:
    notification = RemoteNotification(
        notification_id="NOT-001",
        subject="Requerimiento",
        issued_at=datetime(2025, 4, 20, 12, 0, tzinfo=UTC),
    )
    assert notification.acknowledged_at is None
    assert notification.linked_expediente_id is None
    assert notification.mode == "read"


def test_remote_receipt_kind_is_constrained() -> None:
    receipt = RemoteReceipt.model_validate(
        {
            "receipt_id": "CSV-ABC",
            "kind": "justificante",
            "pdf_url": "https://sede.agenciatributaria.gob.es/receipts/abc.pdf",
            "content_hash": "deadbeef",
            "captured_at": datetime(2025, 4, 20, 12, 0, tzinfo=UTC),
        }
    )
    assert receipt.mode == "read"
    with pytest.raises(ValidationError):
        RemoteReceipt.model_validate(
            {
                "receipt_id": "CSV-ABC",
                "kind": "invalid-kind",
                "pdf_url": "https://sede.agenciatributaria.gob.es/receipts/abc.pdf",
                "content_hash": "deadbeef",
                "captured_at": datetime(2025, 4, 20, 12, 0, tzinfo=UTC),
            }
        )


def test_remote_navigation_graph_holds_read_marker() -> None:
    graph = RemoteNavigationGraph(
        expedientes_list_path="/wlpl/TC-UTIL/Expediente?COPT=Y",
        expediente_detail_template="/wlpl/TC-UTIL/Expediente/Detalle?EXP={expediente_id}",
        notificaciones_path="/wlpl/NOTI/ListaNotificaciones",
    )
    assert graph.mode == "read"


def test_remote_filing_ref_round_trips() -> None:
    ref = RemoteFilingRef(
        expediente_id="EXP-001",
        modelo="303",
        period="2025-1T",
        captured_at=datetime(2025, 4, 20, 12, 0, tzinfo=UTC),
    )
    assert ref.mode == "read"
    dumped = ref.model_dump()
    restored = RemoteFilingRef.model_validate(dumped)
    assert restored == ref
