"""Modelo 232 synthetic declaration parser fixture tests."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ._parser_boundary_support import (
    _MODELO_232_2016_SYNTHETIC_FIXTURE,
    _MODELO_232_2018_SYNTHETIC_FIXTURE,
    CasillaId,
    _casilla_id,
    _expected_period,
    parse_declaracion,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

_DECL_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.ejercicio")
_DECL_TIPO_EJERCICIO_CASILLA: CasillaId = _casilla_id("decl.tipo-ejercicio")
_DECL_CNAE_CASILLA: CasillaId = _casilla_id("decl.cnae")
_M232_PROFILE_CASILLAS: frozenset[CasillaId] = frozenset(
    {
        _DECL_EJERCICIO_CASILLA,
        _DECL_TIPO_EJERCICIO_CASILLA,
        _DECL_CNAE_CASILLA,
    }
)
_M232_FIXTURE_PARAMS: tuple[tuple[Path, int, str, Decimal], ...] = (
    (_MODELO_232_2016_SYNTHETIC_FIXTURE, 2016, "2016-2017", Decimal("2016")),
    (_MODELO_232_2018_SYNTHETIC_FIXTURE, 2018, "2018-y-siguientes", Decimal("2018")),
)


@pytest.mark.parametrize(
    "fixture_path,year,revision_id,expected_ejercicio",
    _M232_FIXTURE_PARAMS,
    ids=("2016-2017", "2018-y-siguientes"),
)
def test_parser_extracts_modelo_232_synthetic_fixture_targets(
    fixture_path: Path,
    year: int,
    revision_id: str,
    expected_ejercicio: Decimal,
) -> None:
    """Round-trip the sanitized M232 synthetic fixtures through both revisions.

    Ground truth is the AEAT-published Diseño de Registro for Modelo 232:
      src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_232/files/
        01-232-orden-hfp-816-2017-ejercicio-2016-y-siguientes-actualizado-15-01-2020-145-kb-xlsx.xlsx
        02-232-orden-hfp-816-2017-ejercicios-2016-2017-146-kb-xlsx.xlsx

    AEAT DR field descriptions, present in both XLSX files:
      DR23200 row 9:  "Ejercicio de devengo (EEEE)"
      DR23201 row 17: "2.Devengo - Tipo de Ejercicio"
      DR23201 row 20: "2.Devengo - C.N.A.E. actividad principal"
    """
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

    assert values[_DECL_TIPO_EJERCICIO_CASILLA] is not None, (
        "decl.tipo-ejercicio: expected a non-None extracted value"
    )
    assert values[_DECL_CNAE_CASILLA] == "6201", (
        f"decl.cnae: expected '6201' from AEAT-grounded DR23201 fixture "
        f"(DR field: 'C.N.A.E. actividad principal'), got {values[_DECL_CNAE_CASILLA]!r}"
    )
