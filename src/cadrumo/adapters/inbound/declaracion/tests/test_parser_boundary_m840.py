"""Modelo 840 parser boundary synthetic fixture tests."""

from __future__ import annotations

import pytest

from .....core.casilla_id import CasillaId
from ..parser import parse_declaracion
from .parser_boundary_casillas import (
    M840_EJERCICIO_CASILLA,
    M840_TIPO_DECLARACION_CASILLA,
)
from .parser_boundary_support import (
    MODELO_840_SYNTHETIC_FIXTURE,
    expected_period,
    specimen_period,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter, pytest.mark.usefixtures("operation")]

_SPECIMEN_PERIOD = specimen_period(MODELO_840_SYNTHETIC_FIXTURE)

_M840_EXPECTED_VALUES: dict[CasillaId, str] = {
    M840_EJERCICIO_CASILLA: str(_SPECIMEN_PERIOD.filing_year),
    M840_TIPO_DECLARACION_CASILLA: "Alta",
}


def test_parser_extracts_modelo_840_synthetic_fixture_targets() -> None:
    """Round-trip the sanitized M840 synthetic fixture through the parser.

    Ground truth is the AEAT-published printed form PDF at:
      src/cadrumo/_data/corpus/aeat_official/formularios_publicados/modelo_840/files/
        01-840-modelo-declaracion-iae-alta-variacion-baja-pdf.pdf
    (hash-pinned by registry source `aeat-modelo-840-form`)

    The fixture reproduces the corpus-confirmed labels "14Ejercicio:" and
    "15Declaracion de:" with sanitized values on the same line.
    """
    filing = parse_declaracion(
        MODELO_840_SYNTHETIC_FIXTURE,
        modelo_override="840",
        año_override=_SPECIMEN_PERIOD.filing_year,
        period_override="0A",
    )

    assert filing.modelo == "840"
    assert filing.period == expected_period(_SPECIMEN_PERIOD.filing_year, "0A")
    assert filing.tax_id == "Y0001006P"
    assert filing.registry_snapshot_ref is not None
    assert filing.registry_snapshot_ref.modelo == "840"
    assert filing.registry_snapshot_ref.modelo_year == _SPECIMEN_PERIOD.filing_year
    assert filing.registry_snapshot_ref.period == "0A"

    assert {value.casilla_id: value.printed_value for value in filing.values} == _M840_EXPECTED_VALUES
