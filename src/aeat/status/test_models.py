"""Unit tests for the AEAT status wire schemas (#43).

Every schema is exercised against a canonical-accept payload and at
least one malformed-reject payload (wrong type, missing field, extra
field). Inputs are passed through ``model_validate`` rather than
direct kwargs so the ``strict=True`` path is exercised the same way
it will be in production. No mocks, no patches, no fakes.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from . import (
    AeatStatusKind,
    BorradorIrpf,
    CalendarioEntry,
    DatosFiscales,
    Devolucion,
    Expediente,
    Notificacion,
    Payor,
    PayorKind,
)

pytestmark = pytest.mark.unit

_URL = "https://sede.agenciatributaria.gob.es/wlpl/TC-UTIL/Expediente?COPT=Y"
_NOW = datetime(2026, 4, 12, 10, 0, tzinfo=UTC)


class TestAeatStatusKind:
    def test_values(self) -> None:
        assert AeatStatusKind.EXPEDIENTE.value == "expediente"
        assert AeatStatusKind.BORRADOR_IRPF.value == "borrador_irpf"

    def test_closed_set(self) -> None:
        assert {k.value for k in AeatStatusKind} == {
            "expediente",
            "notificacion",
            "devolucion",
            "borrador_irpf",
            "datos_fiscales",
            "calendario",
        }


def _expediente_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "expediente_id": "2025X1234567L0001",
        "modelo": "130",
        "period": "2025-1T",
        "status": "Presentada",
        "presented_at": _NOW,
        "csv": "ABCD1234EFGH5678",
        "justificante_url": "https://sede.agenciatributaria.gob.es/wlpl/justificante?id=ABCD",
        "source_page_url": _URL,
        "fetched_at": _NOW,
    }
    payload.update(overrides)
    return payload


class TestExpediente:
    def test_accepts_canonical(self) -> None:
        rec = Expediente.model_validate(_expediente_payload())
        assert rec.modelo == "130"
        assert rec.csv == "ABCD1234EFGH5678"

    def test_frozen(self) -> None:
        rec = Expediente.model_validate(_expediente_payload())
        with pytest.raises(ValidationError):
            rec.modelo = "303"  # type: ignore[misc]

    def test_rejects_missing_required(self) -> None:
        payload = _expediente_payload()
        del payload["modelo"]
        with pytest.raises(ValidationError):
            Expediente.model_validate(payload)

    def test_rejects_extra_field(self) -> None:
        with pytest.raises(ValidationError):
            Expediente.model_validate(_expediente_payload(extra_field="nope"))

    def test_rejects_wrong_type(self) -> None:
        with pytest.raises(ValidationError):
            Expediente.model_validate(_expediente_payload(modelo=130))

    def test_rejects_blank_expediente_id(self) -> None:
        with pytest.raises(ValidationError):
            Expediente.model_validate(_expediente_payload(expediente_id=""))

    def test_allows_null_csv_and_justificante(self) -> None:
        rec = Expediente.model_validate(
            _expediente_payload(csv=None, justificante_url=None),
        )
        assert rec.csv is None
        assert rec.justificante_url is None


def _notificacion_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "notificacion_id": "NOTIF-2026-0001",
        "kind": "requerimiento",
        "title": {"es": "Requerimiento 303", "en": "Request 303", "hu": "303 kérés"},
        "body_excerpt": {"es": "Se requiere…", "en": "You are required…", "hu": "Kérjük…"},
        "received_at": _NOW,
        "due_at": _NOW,
        "source_page_url": _URL,
        "fetched_at": _NOW,
    }
    payload.update(overrides)
    return payload


class TestNotificacion:
    def test_accepts_canonical(self) -> None:
        rec = Notificacion.model_validate(_notificacion_payload())
        assert rec.kind == "requerimiento"

    def test_rejects_wrong_title_type(self) -> None:
        with pytest.raises(ValidationError):
            Notificacion.model_validate(_notificacion_payload(title="plain string"))


def _devolucion_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "modelo": "100",
        "period": "2024",
        "amount": Decimal("1234.56"),
        "status": "Pagada",
        "expected_payment_date": date(2026, 6, 1),
        "source_page_url": _URL,
        "fetched_at": _NOW,
    }
    payload.update(overrides)
    return payload


class TestDevolucion:
    def test_accepts_canonical(self) -> None:
        rec = Devolucion.model_validate(_devolucion_payload())
        assert rec.amount == Decimal("1234.56")

    def test_rejects_float_amount(self) -> None:
        with pytest.raises(ValidationError):
            Devolucion.model_validate(_devolucion_payload(amount=1234.56))


class TestBorradorIrpf:
    def test_accepts_canonical(self) -> None:
        rec = BorradorIrpf.model_validate(
            {
                "year": 2025,
                "status": "Disponible",
                "total_a_devolver": Decimal("500.00"),
                "total_a_pagar": None,
                "source_page_url": _URL,
                "fetched_at": _NOW,
            },
        )
        assert rec.year == 2025

    def test_rejects_year_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            BorradorIrpf.model_validate(
                {
                    "year": 1900,
                    "status": "Disponible",
                    "total_a_devolver": None,
                    "total_a_pagar": None,
                    "source_page_url": _URL,
                    "fetched_at": _NOW,
                },
            )


class TestPayorAndDatosFiscales:
    def test_payor_accepts_canonical(self) -> None:
        payor = Payor.model_validate(
            {
                "name": "Acme SA",
                "tax_id": "A12345678",
                "kind": PayorKind.EMPLOYER,
                "gross_amount": Decimal("30000.00"),
                "retencion": Decimal("4500.00"),
            },
        )
        assert payor.kind is PayorKind.EMPLOYER

    def test_payor_rejects_unknown_kind(self) -> None:
        with pytest.raises(ValidationError):
            Payor.model_validate(
                {
                    "name": "Acme",
                    "tax_id": "A12345678",
                    "kind": "unknown",
                    "gross_amount": Decimal("1"),
                    "retencion": Decimal("0"),
                },
            )

    def test_datos_fiscales_accepts_tuple_of_payors(self) -> None:
        dfs = DatosFiscales.model_validate(
            {
                "year": 2025,
                "payors": (
                    {
                        "name": "Acme",
                        "tax_id": "A12345678",
                        "kind": PayorKind.EMPLOYER,
                        "gross_amount": Decimal("1"),
                        "retencion": Decimal("0"),
                    },
                ),
                "source_page_url": _URL,
                "fetched_at": _NOW,
            },
        )
        assert len(dfs.payors) == 1


class TestCalendarioEntry:
    def test_accepts_canonical(self) -> None:
        entry = CalendarioEntry.model_validate(
            {
                "modelo": "303",
                "period": "2025-2T",
                "opens_on": date(2025, 7, 1),
                "closes_on": date(2025, 7, 20),
                "source_page_url": _URL,
                "fetched_at": _NOW,
            },
        )
        assert entry.modelo == "303"

    def test_rejects_missing_closes_on(self) -> None:
        with pytest.raises(ValidationError):
            CalendarioEntry.model_validate(
                {
                    "modelo": "303",
                    "period": "2025-2T",
                    "opens_on": date(2025, 7, 1),
                    "closes_on": "not-a-date",
                    "source_page_url": _URL,
                    "fetched_at": _NOW,
                },
            )
