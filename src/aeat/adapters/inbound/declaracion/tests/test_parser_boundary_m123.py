"""Modelo 123 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_m123_support import (
    _M123_CORPUS_CASE_IDS,
    _M123_CORPUS_CASES,
    _M123_PROFILE_TARGET_CASE_IDS,
    _M123_PROFILE_TARGET_CASES,
)
from ._parser_boundary_support import (
    CasillaId,
    Decimal,
    Path,
    _expected_period,
    _modelo_snapshot,
    _write_declaration_pdf,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


@pytest.mark.parametrize(
    ("case_id", "year", "period", "profile_id", "expected_targets"),
    _M123_PROFILE_TARGET_CASES,
    ids=_M123_PROFILE_TARGET_CASE_IDS,
)
def test_parser_extracts_modelo_123_registry_profile_targets_from_pdf(
    tmp_path: Path,
    case_id: str,
    year: int,
    period: str,
    profile_id: str,
    expected_targets: tuple[CasillaId, ...],
) -> None:
    snapshot = _modelo_snapshot("123", filing_year=year, period=period)
    profile = snapshot.extraction_profiles[profile_id]
    assert tuple(target.casilla_id for target in profile.target_casillas) == expected_targets
    values = {
        target.casilla_id: Decimal(index).quantize(Decimal("0.01"))
        for index, target in enumerate(profile.target_casillas, start=1)
    }
    pdf_path = tmp_path / f"modelo-123-{case_id}.pdf"
    _write_declaration_pdf(pdf_path, modelo="123", ejercicio=str(year), period=period, values=values)

    filing = parse_declaracion(pdf_path, modelo_override="123", año_override=year)

    assert filing.modelo == "123"
    assert filing.period == _expected_period(year, period)
    assert filing.tax_id == "00000000T"
    assert {value.casilla_id: value.printed_value for value in filing.values} == values


@pytest.mark.parametrize(
    ("case_id", "fixture", "year", "period", "revision_id", "expected_targets", "expected_values"),
    _M123_CORPUS_CASES,
    ids=_M123_CORPUS_CASE_IDS,
)
def test_parser_extracts_modelo_123_corpus_round_trip(
    case_id: str,
    fixture: Path,
    year: int,
    period: str,
    revision_id: str,
    expected_targets: tuple[CasillaId, ...],
    expected_values: dict[CasillaId, Decimal],
) -> None:
    """Round-trip committed M123 synthetic fixtures for current and historical revisions."""
    filing = parse_declaracion(
        fixture,
        modelo_override="123",
        año_override=year,
        period_override=period,
    )

    assert filing.modelo == "123"
    assert filing.period == _expected_period(year, period)
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "123"
    assert filing.registry_snapshot_ref.revision_id == revision_id
    assert filing.registry_snapshot_ref.modelo_year == year
    assert filing.registry_snapshot_ref.period == period

    values = {value.casilla_id: value.printed_value for value in filing.values}
    assert set(values.keys()) == set(expected_targets), (
        f"{case_id}: expected exactly the M123 profile casillas, got {set(values.keys())!r}"
    )
    for casilla_id, expected_value in expected_values.items():
        assert values[casilla_id] == expected_value, (
            f"{case_id}: casilla {casilla_id}: expected {expected_value!r}, got {values[casilla_id]!r}"
        )
