"""Unit tests for the filing-history pydantic models.

Covers schema round-trip through JSON, strict-validation rejections,
invariant checks on :class:`FiledModeloMetadata`, and the
:class:`FilingHistory` unique-id invariant.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import AnyHttpUrl, ValidationError

from . import (
    FiledModelo,
    FiledModeloMetadata,
    FilingHistory,
    HistoryModelo,
    RawCalculationPayload,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.domain_aeat_remote,
    pytest.mark.domain_local_state,
]


_URL = AnyHttpUrl("https://sede.agenciatributaria.gob.es/detalle/0001")
_JUSTIFICANTE_URL = AnyHttpUrl("https://sede.agenciatributaria.gob.es/justificante/0001")
_PRESENTED = datetime(2025, 4, 15, 10, 22, 31, tzinfo=UTC)
_FETCHED = datetime(2025, 4, 15, 10, 25, 0, tzinfo=UTC)


def _make_metadata(
    *,
    expediente_id: str = "2025X1234567L0001",
    modelo: str = "130",
    period: str = "2025-1T",
    status: str = "Presentada",
    presented_at: datetime = _PRESENTED,
    tax_id: str = "X1234567L",
    csv: str | None = "ABCD1234EFGH5678",
    justificante_url: AnyHttpUrl | None = _JUSTIFICANTE_URL,
    complementaria_of: str | None = None,
    source_page_url: AnyHttpUrl = _URL,
    fetched_at: datetime = _FETCHED,
) -> FiledModeloMetadata:
    return FiledModeloMetadata(
        expediente_id=expediente_id,
        modelo=modelo,
        period=period,
        status=status,
        presented_at=presented_at,
        tax_id=tax_id,
        csv=csv,
        justificante_url=justificante_url,
        complementaria_of=complementaria_of,
        source_page_url=source_page_url,
        fetched_at=fetched_at,
    )


def _make_calculations(
    *,
    casillas: dict[str, str] | None = None,
    total_a_ingresar: Decimal | None = Decimal("2000.00"),
    total_a_devolver: Decimal | None = Decimal("0.00"),
    resultado_a_compensar: Decimal | None = None,
    source_page_url: AnyHttpUrl = _URL,
    fetched_at: datetime = _FETCHED,
) -> RawCalculationPayload:
    return RawCalculationPayload(
        casillas=casillas if casillas is not None else {"01": "12.345,67", "02": "2.345,67"},
        total_a_ingresar=total_a_ingresar,
        total_a_devolver=total_a_devolver,
        resultado_a_compensar=resultado_a_compensar,
        source_page_url=source_page_url,
        fetched_at=fetched_at,
    )


class TestHistoryModelo:
    def test_values_are_stable(self) -> None:
        assert HistoryModelo.MODELO_130.value == "130"
        assert HistoryModelo.MODELO_303.value == "303"
        assert HistoryModelo.MODELO_390.value == "390"

    def test_is_closed(self) -> None:
        assert {member.value for member in HistoryModelo} == {"130", "303", "390"}


class TestFiledModeloMetadata:
    def test_round_trip_json(self) -> None:
        record = _make_metadata()
        reloaded = FiledModeloMetadata.model_validate_json(record.model_dump_json())
        assert reloaded == record

    def test_frozen(self) -> None:
        record = _make_metadata()
        with pytest.raises(ValidationError):
            record.modelo = "303"  # type: ignore[misc]

    def test_extra_forbid(self) -> None:
        payload = {
            "expediente_id": "2025X1234567L0001",
            "modelo": "130",
            "period": "2025-1T",
            "status": "Presentada",
            "presented_at": _PRESENTED.isoformat(),
            "tax_id": "X1234567L",
            "source_page_url": str(_URL),
            "fetched_at": _FETCHED.isoformat(),
            "extra_field": "boom",
        }
        with pytest.raises(ValidationError):
            FiledModeloMetadata.model_validate(payload)

    def test_expediente_id_must_be_alnum(self) -> None:
        with pytest.raises(ValidationError):
            _make_metadata(expediente_id="has space")

    def test_presented_at_in_future_rejected(self) -> None:
        future = datetime.now(UTC) + timedelta(days=30)
        with pytest.raises(ValidationError):
            _make_metadata(
                presented_at=future,
                fetched_at=future + timedelta(minutes=1),
            )

    def test_fetched_before_presented_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_metadata(
                presented_at=_PRESENTED,
                fetched_at=_PRESENTED - timedelta(hours=1),
            )


class TestRawCalculationPayload:
    def test_round_trip_json(self) -> None:
        calc = _make_calculations()
        reloaded = RawCalculationPayload.model_validate_json(calc.model_dump_json())
        assert reloaded == calc

    def test_empty_casillas_is_valid(self) -> None:
        calc = _make_calculations(casillas={})
        assert calc.casillas == {}

    def test_invalid_casilla_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make_calculations(casillas={"not valid": "1"})

    def test_extra_forbid(self) -> None:
        payload = {
            "casillas": {},
            "source_page_url": str(_URL),
            "fetched_at": _FETCHED.isoformat(),
            "boom": "x",
        }
        with pytest.raises(ValidationError):
            RawCalculationPayload.model_validate(payload)


class TestFiledModelo:
    def test_round_trip_json(self) -> None:
        record = FiledModelo(
            metadata=_make_metadata(),
            calculations=_make_calculations(),
        )
        reloaded = FiledModelo.model_validate_json(record.model_dump_json())
        assert reloaded == record

    def test_source_url_mismatch_rejected(self) -> None:
        mismatched_calc = _make_calculations(
            source_page_url=AnyHttpUrl("https://sede.agenciatributaria.gob.es/other"),
        )
        with pytest.raises(ValidationError):
            FiledModelo(
                metadata=_make_metadata(),
                calculations=mismatched_calc,
            )

    def test_fetched_at_mismatch_rejected(self) -> None:
        mismatched_calc = _make_calculations(
            fetched_at=_FETCHED + timedelta(seconds=1),
        )
        with pytest.raises(ValidationError):
            FiledModelo(
                metadata=_make_metadata(),
                calculations=mismatched_calc,
            )

    def test_parse_warnings_default_empty(self) -> None:
        record = FiledModelo(
            metadata=_make_metadata(),
            calculations=_make_calculations(),
        )
        assert record.parse_warnings == ()


class TestFilingHistory:
    def test_empty_history_round_trips(self) -> None:
        history = FilingHistory()
        reloaded = FilingHistory.model_validate_json(history.model_dump_json())
        assert reloaded == history
        assert reloaded.values() == ()

    def test_upsert_and_get(self) -> None:
        history = FilingHistory()
        record = FiledModelo(
            metadata=_make_metadata(),
            calculations=_make_calculations(),
        )
        history.upsert(record)
        assert history.get(record.metadata.expediente_id) == record
        assert history.values() == (record,)

    def test_key_must_equal_expediente_id(self) -> None:
        record = FiledModelo(
            metadata=_make_metadata(),
            calculations=_make_calculations(),
        )
        with pytest.raises(ValidationError):
            FilingHistory(entries={"WRONG_KEY": record})

    def test_round_trip_with_records(self) -> None:
        record = FiledModelo(
            metadata=_make_metadata(),
            calculations=_make_calculations(),
        )
        history = FilingHistory()
        history.upsert(record)
        reloaded = FilingHistory.model_validate_json(history.model_dump_json())
        assert reloaded.values() == (record,)
