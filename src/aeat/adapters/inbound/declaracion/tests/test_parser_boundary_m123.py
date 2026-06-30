"""Modelo 123 parser boundary corpus tests."""

from __future__ import annotations

import pytest

from ._parser_boundary_support import (
    _MODELO_123_2023_SYNTHETIC_FIXTURE,
    _MODELO_123_2024_SYNTHETIC_FIXTURE,
    _MODELO_123_CURRENT_EXPECTED_TARGETS,
    _MODELO_123_HISTORICAL_EXPECTED_TARGETS,
    Decimal,
    Path,
    _expected_casilla_values,
    _expected_period,
    _modelo_snapshot,
    _write_declaration_pdf,
    parse_declaracion,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def test_parser_extracts_modelo_123_current_registry_profile_targets_from_pdf(tmp_path: Path) -> None:
    snapshot = _modelo_snapshot("123", filing_year=2026, period="1T")
    profile = snapshot.extraction_profiles["modelo-123-declaracion-pdf"]
    assert tuple(target.casilla_id for target in profile.target_casillas) == _MODELO_123_CURRENT_EXPECTED_TARGETS
    values = {
        target.casilla_id: Decimal(index).quantize(Decimal("0.01"))
        for index, target in enumerate(profile.target_casillas, start=1)
    }
    pdf_path = tmp_path / "modelo-123-2026.pdf"
    _write_declaration_pdf(pdf_path, modelo="123", ejercicio="2026", values=values)

    filing = parse_declaracion(pdf_path, modelo_override="123", año_override=2026)

    assert filing.modelo == "123"
    assert filing.period == _expected_period(2026, "1T")
    assert filing.tax_id == "00000000T"
    assert {value.casilla_id: value.printed_value for value in filing.values} == values


def test_parser_extracts_modelo_123_historical_registry_profile_targets_from_pdf(tmp_path: Path) -> None:
    snapshot = _modelo_snapshot("123", filing_year=2023, period="4T")
    profile = snapshot.extraction_profiles["modelo-123-2019-declaracion-pdf"]
    assert tuple(target.casilla_id for target in profile.target_casillas) == _MODELO_123_HISTORICAL_EXPECTED_TARGETS
    values = {
        target.casilla_id: Decimal(index).quantize(Decimal("0.01"))
        for index, target in enumerate(profile.target_casillas, start=1)
    }
    pdf_path = tmp_path / "modelo-123-2023.pdf"
    _write_declaration_pdf(pdf_path, modelo="123", ejercicio="2023", period="4T", values=values)

    filing = parse_declaracion(pdf_path, modelo_override="123", año_override=2023)

    assert filing.modelo == "123"
    assert filing.period == _expected_period(2023, "4T")
    assert filing.tax_id == "00000000T"
    assert {value.casilla_id: value.printed_value for value in filing.values} == values


def test_parser_extracts_modelo_123_2024_corpus_round_trip() -> None:
    """Round-trip: parse the committed M123 2024-y-siguientes synthetic fixture."""
    filing = parse_declaracion(
        _MODELO_123_2024_SYNTHETIC_FIXTURE,
        modelo_override="123",
        año_override=2024,
        period_override="1T",
    )

    assert filing.modelo == "123"
    assert filing.period == _expected_period(2024, "1T")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "123"
    assert filing.registry_snapshot_ref.revision_id == "2024-y-siguientes"
    assert filing.registry_snapshot_ref.modelo_year == 2024
    assert filing.registry_snapshot_ref.period == "1T"

    values = {value.casilla_id: value.printed_value for value in filing.values}
    assert set(values.keys()) == set(_MODELO_123_CURRENT_EXPECTED_TARGETS), (
        f"expected exactly the 14 M123 2024+ profile casillas, got {set(values.keys())!r}"
    )

    expected_values = _expected_casilla_values(
        {
            "01": Decimal("5.00"),
            "02": Decimal("3.00"),
            "03": Decimal("8.00"),
            "04": Decimal("10000.00"),
            "05": Decimal("5000.00"),
            "06": Decimal("15000.00"),
            "07": Decimal("1900.00"),
            "08": Decimal("950.00"),
            "09": Decimal("2850.00"),
            "10": Decimal("0.00"),
            "11": Decimal("0.00"),
            "12": Decimal("2850.00"),
            "13": Decimal("0.00"),
            "14": Decimal("2850.00"),
        },
    )
    for casilla_id, expected_value in expected_values.items():
        assert values[casilla_id] == expected_value, (
            f"casilla {casilla_id}: expected {expected_value!r}, got {values[casilla_id]!r}"
        )


def test_parser_extracts_modelo_123_2023_historical_corpus_round_trip() -> None:
    """Round-trip: parse the committed M123 2019-2023 revision synthetic fixture."""
    filing = parse_declaracion(
        _MODELO_123_2023_SYNTHETIC_FIXTURE,
        modelo_override="123",
        año_override=2023,
        period_override="1T",
    )

    assert filing.modelo == "123"
    assert filing.period == _expected_period(2023, "1T")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "123"
    assert filing.registry_snapshot_ref.revision_id == "2019-2023"
    assert filing.registry_snapshot_ref.modelo_year == 2023
    assert filing.registry_snapshot_ref.period == "1T"

    values = {value.casilla_id: value.printed_value for value in filing.values}
    assert set(values.keys()) == set(_MODELO_123_HISTORICAL_EXPECTED_TARGETS), (
        f"expected exactly the 8 M123 2019-2023 profile casillas, got {set(values.keys())!r}"
    )

    expected_values = _expected_casilla_values(
        {
            "01": Decimal("4.00"),
            "02": Decimal("8000.00"),
            "03": Decimal("1520.00"),
            "04": Decimal("0.00"),
            "05": Decimal("0.00"),
            "06": Decimal("1520.00"),
            "07": Decimal("0.00"),
            "08": Decimal("1520.00"),
        },
    )
    for casilla_id, expected_value in expected_values.items():
        assert values[casilla_id] == expected_value, (
            f"casilla {casilla_id}: expected {expected_value!r}, got {values[casilla_id]!r}"
        )
