"""Modelo 232 synthetic declaration parser fixture tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..errors import DeclaracionParseError
from ..parser import parse_declaracion
from ._parser_boundary_support import (
    _expected_period,
)
from ._parser_synthetic_m232_support import (
    _DECL_CNAE_CASILLA,
    _DECL_EJERCICIO_CASILLA,
    _DECL_TIPO_EJERCICIO_CASILLA,
    _M232_FIXTURE_PARAMS,
    _M232_OPEN_ENDED_REVISION_ID,
    _M232_PROFILE_CASILLAS,
    _M232_UNSUPPORTED_FIXTURE_PARAMS,
    _first_supported_filing_year,
    _write_modelo_232_declaration_pdf,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]


_FLOOR_YEAR = _first_supported_filing_year()
# A ``None`` fixture is rendered at the envelope floor: the bundled synthetic
# fixtures print ejercicios below it, and the open-ended revision covers it.
_POSITIVE_CASES: tuple[tuple[Path | None, int, str, str], ...] = (
    *_M232_FIXTURE_PARAMS,
    (None, _FLOOR_YEAR, _M232_OPEN_ENDED_REVISION_ID, str(_FLOOR_YEAR)),
)


@pytest.mark.parametrize(
    "fixture_path,year,revision_id,expected_ejercicio",
    _POSITIVE_CASES,
    ids=[
        f"{revision_id}-{'bundled' if path is not None else 'rendered'}-{year}"
        for path, year, revision_id, _ejercicio in _POSITIVE_CASES
    ],
)
@pytest.mark.usefixtures("operation")
def test_parser_extracts_modelo_232_synthetic_fixture_targets(
    fixture_path: Path | None,
    year: int,
    revision_id: str,
    expected_ejercicio: str,
    tmp_path: Path,
) -> None:
    """Round-trip the M232 synthetic layout inside the support envelope.

    Ground truth is the AEAT-published Diseño de Registro for Modelo 232:
      src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_232/files/
        01-232-orden-hfp-816-2017-ejercicio-2016-y-siguientes-actualizado-15-01-2020-145-kb-xlsx.xlsx
        02-232-orden-hfp-816-2017-ejercicios-2016-2017-146-kb-xlsx.xlsx

    AEAT DR field descriptions, present in both XLSX files:
      DR23200 row 9:  "Ejercicio de devengo (EEEE)"
      DR23201 row 17: "2.Devengo - Tipo de Ejercicio"
      DR23201 row 20: "2.Devengo - C.N.A.E. actividad principal"
    """
    if fixture_path is None:
        fixture_path = tmp_path / f"{year}-0A.pdf"
        _write_modelo_232_declaration_pdf(fixture_path, ejercicio=year)

    _assert_modelo_232_round_trip(
        fixture_path,
        year=year,
        revision_id=revision_id,
        expected_ejercicio=expected_ejercicio,
    )


@pytest.mark.parametrize(
    "fixture_path,year,revision_id,expected_ejercicio",
    _M232_UNSUPPORTED_FIXTURE_PARAMS,
    ids=[revision_id for _path, _year, revision_id, _ejercicio in _M232_UNSUPPORTED_FIXTURE_PARAMS],
)
def test_parser_refuses_modelo_232_synthetic_fixture_below_the_supported_floor(
    fixture_path: Path,
    year: int,
    revision_id: str,
    expected_ejercicio: str,
) -> None:
    """A fixture for a year outside the support envelope is refused, never resolved."""
    with pytest.raises(DeclaracionParseError):
        parse_declaracion(fixture_path, modelo_override="232", año_override=year, period_override="0A")


def _assert_modelo_232_round_trip(
    fixture_path: Path,
    *,
    year: int,
    revision_id: str,
    expected_ejercicio: str,
) -> None:
    filing = parse_declaracion(
        fixture_path,
        modelo_override="232",
        año_override=year,
        period_override="0A",
    )

    assert filing.modelo == "232"
    assert filing.period == _expected_period(year, "0A")
    assert filing.tax_id == "Y0000001S"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "232"
    assert filing.registry_snapshot_ref.revision_id == revision_id
    assert filing.registry_snapshot_ref.modelo_year == year
    assert filing.registry_snapshot_ref.period == "0A"

    values = {value.casilla_id: value.printed_value for value in filing.values}
    assert set(values.keys()) == _M232_PROFILE_CASILLAS, (
        f"expected exactly {{decl.ejercicio, decl.tipo-ejercicio, decl.cnae}}, got {set(values.keys())!r}"
    )

    assert values[_DECL_EJERCICIO_CASILLA] == expected_ejercicio, (
        f"decl.ejercicio: expected {expected_ejercicio!r} from AEAT-grounded DR23200 fixture, "
        f"got {values[_DECL_EJERCICIO_CASILLA]!r}"
    )

    assert values[_DECL_TIPO_EJERCICIO_CASILLA] is not None, "decl.tipo-ejercicio: expected a non-None extracted value"
    assert values[_DECL_CNAE_CASILLA] == "6201", (
        f"decl.cnae: expected '6201' from AEAT-grounded DR23201 fixture "
        f"(DR field: 'C.N.A.E. actividad principal'), got {values[_DECL_CNAE_CASILLA]!r}"
    )
