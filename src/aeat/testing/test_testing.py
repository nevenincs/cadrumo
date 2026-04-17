"""Unit tests for :mod:`aeat.testing`.

These tests load the hand-curated synthetic filing corpus under
``tests/fixtures/filing_history/`` through the public loader and
assert the schema invariants that issue #14 pins.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ..errors import FilingFixtureError
from ..filing import FilingDraftStatus
from . import (
    SYNTHETIC_FIXTURES_ROOT,
    FilingRecord,
    FilingRecordPeriodKind,
    FilingRecordScenario,
    FixtureCasilla,
    compute_record_id,
    load_filing_history,
)

_EXPECTED_MODELOS = frozenset({"130", "303", "390"})
_EXPECTED_SCENARIOS = frozenset(
    {
        FilingRecordScenario.CLEAN,
        FilingRecordScenario.COMPLEMENTARIA,
        FilingRecordScenario.WITH_ERRORS,
        FilingRecordScenario.AMENDED,
        FilingRecordScenario.CANCELLED,
        FilingRecordScenario.ROUNDING,
    }
)


def _sample_casillas() -> tuple[FixtureCasilla, ...]:
    return (
        FixtureCasilla(casilla_id="01", label="Ingresos", value=Decimal("1000.00")),
        FixtureCasilla(casilla_id="02", label="Gastos", value=Decimal("250.00")),
    )


def _valid_payload() -> dict[str, object]:
    return {
        "synthetic": True,
        "_comment": "SYNTHETIC FIXTURE — test payload.",
        "record_id": "abc1234567890def",
        "modelo": "130",
        "period": "2024Q1",
        "period_kind": "QUARTERLY",
        "profile_tax_id": "00000000T",
        "status": "ACKNOWLEDGED",
        "scenario": "CLEAN",
        "casillas": [
            {"casilla_id": "01", "label": "Ingresos", "value": "1000.00"},
            {"casilla_id": "02", "label": "Gastos", "value": "250.00"},
        ],
        "totals": {"rendimiento_neto": "750.00"},
        "created_at": "2024-04-05T09:00:00+00:00",
        "submitted_at": "2024-04-15T09:00:00+00:00",
        "acknowledged_at": "2024-04-16T09:00:00+00:00",
        "source": "synthetic",
        "complementaria_of": None,
        "notes": "test",
    }


@pytest.mark.unit
def test_synthetic_fixtures_root_points_at_expected_directory() -> None:
    assert SYNTHETIC_FIXTURES_ROOT.is_dir()
    assert SYNTHETIC_FIXTURES_ROOT.name == "filing_history"
    assert SYNTHETIC_FIXTURES_ROOT.parent.name == "fixtures"


@pytest.mark.unit
def test_load_all_records_parse_cleanly() -> None:
    records = list(load_filing_history())
    assert len(records) >= 17
    assert all(isinstance(r, FilingRecord) for r in records)


@pytest.mark.unit
def test_expected_modelo_set() -> None:
    modelos = {r.modelo for r in load_filing_history()}
    assert modelos == _EXPECTED_MODELOS


@pytest.mark.unit
def test_every_scenario_is_covered() -> None:
    scenarios = {r.scenario for r in load_filing_history()}
    assert scenarios == _EXPECTED_SCENARIOS


@pytest.mark.unit
def test_every_record_is_synthetic() -> None:
    for record in load_filing_history():
        assert record.synthetic is True
        assert record.source == "synthetic"


@pytest.mark.unit
def test_every_file_has_comment_marker() -> None:
    for path in SYNTHETIC_FIXTURES_ROOT.rglob("*.json"):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data.get("synthetic") is True, f"{path} missing synthetic marker"
        comment = data.get("_comment")
        assert isinstance(comment, str) and comment.strip(), f"{path} missing _comment"
        assert "SYNTHETIC" in comment.upper(), f"{path} _comment lacks SYNTHETIC keyword"


@pytest.mark.unit
def test_filter_by_modelo() -> None:
    records = list(load_filing_history(modelo="130"))
    assert records, "expected at least one modelo 130 record"
    assert {r.modelo for r in records} == {"130"}


@pytest.mark.unit
def test_filter_by_modelo_and_period() -> None:
    records = list(load_filing_history(modelo="130", period="2024Q1"))
    assert records, "expected at least one 130/2024Q1 record"
    for r in records:
        assert r.modelo == "130"
        assert r.period == "2024Q1"


@pytest.mark.unit
def test_filter_by_unknown_modelo_raises() -> None:
    with pytest.raises(FilingFixtureError):
        list(load_filing_history(modelo="999"))


@pytest.mark.unit
def test_period_kind_matches_period_string() -> None:
    for record in load_filing_history():
        period = record.period
        kind = record.period_kind
        if kind is FilingRecordPeriodKind.ANNUAL:
            assert period.isdigit() and len(period) == 4
        elif kind is FilingRecordPeriodKind.QUARTERLY:
            assert len(period) == 6 and period[4].upper() == "Q"
        elif kind is FilingRecordPeriodKind.MONTHLY:
            assert len(period) == 7 and period[4] == "-"


@pytest.mark.unit
def test_status_enum_is_filing_draft_status() -> None:
    for record in load_filing_history():
        assert isinstance(record.status, FilingDraftStatus)


@pytest.mark.unit
def test_record_ids_are_unique() -> None:
    ids = [r.record_id for r in load_filing_history()]
    assert len(ids) == len(set(ids))


@pytest.mark.unit
def test_totals_are_decimals() -> None:
    for record in load_filing_history():
        assert record.totals, f"{record.record_id} has empty totals"
        for name, value in record.totals.items():
            assert isinstance(value, Decimal), f"{record.record_id} total {name} is {type(value)}"


@pytest.mark.unit
def test_refuses_non_synthetic_flag() -> None:
    payload = _valid_payload()
    payload["synthetic"] = False
    with pytest.raises(ValidationError):
        FilingRecord.model_validate(payload)


@pytest.mark.unit
def test_refuses_missing_comment_marker() -> None:
    payload = _valid_payload()
    payload.pop("_comment")
    with pytest.raises(ValidationError):
        FilingRecord.model_validate(payload)


@pytest.mark.unit
def test_refuses_empty_comment_marker() -> None:
    payload = _valid_payload()
    payload["_comment"] = ""
    with pytest.raises(ValidationError):
        FilingRecord.model_validate(payload)


@pytest.mark.unit
def test_refuses_non_synthetic_source() -> None:
    payload = _valid_payload()
    payload["source"] = "real"
    with pytest.raises(ValidationError):
        FilingRecord.model_validate(payload)


@pytest.mark.unit
def test_extra_fields_forbidden() -> None:
    payload = _valid_payload()
    payload["mystery"] = "boom"
    with pytest.raises(ValidationError):
        FilingRecord.model_validate(payload)


@pytest.mark.unit
def test_compute_record_id_is_stable_and_order_independent() -> None:
    casillas = _sample_casillas()
    a = compute_record_id(
        modelo="130",
        period="2024Q1:CLEAN",
        profile_tax_id="00000000T",
        casillas=casillas,
    )
    b = compute_record_id(
        modelo="130",
        period="2024Q1:CLEAN",
        profile_tax_id="00000000T",
        casillas=tuple(reversed(casillas)),
    )
    assert a == b
    assert len(a) == 16


@pytest.mark.unit
def test_malformed_json_raises_filing_fixture_error(tmp_path: Path) -> None:
    from ._loader import _load_one

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(FilingFixtureError):
        _load_one(bad)


@pytest.mark.unit
def test_complementaria_of_targets_existing_records() -> None:
    by_id = {r.record_id: r for r in load_filing_history()}
    for record in by_id.values():
        if record.complementaria_of is None:
            continue
        assert record.complementaria_of in by_id, (
            f"{record.record_id} references missing parent {record.complementaria_of}"
        )
