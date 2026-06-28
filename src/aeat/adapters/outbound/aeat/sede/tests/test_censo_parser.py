"""Real-behavior tests for the G313 (Mis Datos Censales) HTML parser.

The fixture below is a synthetic minimal projection of the AEAT
"Mis Datos Censales" result page: real ZK-rendered markup with the
Spanish field labels in the order operators see them. The parser is
contract-tested against this fixture so the structural shape is
locked even before a captured live HTML sample lands in the
repository.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from textwrap import dedent

import pytest

from .._censo import CensoFactSet, CensoParseError, parse_g313_html

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_FULL_FIXTURE = dedent(
    """
    <html>
      <body>
        <table class="datos-censales">
          <tr><td>Referencia catastral:</td><td>1234567AB1234S0001WX</td></tr>
          <tr><td>Vivienda habitual:</td><td>Sí</td></tr>
          <tr><td>Fecha de alta de la actividad:</td><td>15/03/2018</td></tr>
          <tr><td>Fecha de baja de la actividad:</td><td></td></tr>
          <tr><td>Tipo de establecimiento:</td><td>propio</td></tr>
          <tr><td>Porcentaje de retención:</td><td>15%</td></tr>
          <tr><td>Superficie total de la vivienda:</td><td>120,50 m²</td></tr>
          <tr><td>Superficie afecta a la actividad:</td><td>24,10 m²</td></tr>
          <tr><td>Epígrafe IAE:</td><td>721</td></tr>
        </table>
      </body>
    </html>
    """,
)


def test_full_fixture_parses_into_typed_envelope() -> None:
    result = parse_g313_html(_FULL_FIXTURE)

    assert isinstance(result, CensoFactSet)
    assert result.fiscal_address_cadastral_reference == "1234567AB1234S0001WX"
    assert result.fiscal_address_is_habitual_vivienda is True
    assert result.activity_start_date == date(2018, 3, 15)
    assert result.activity_end_date is None
    assert result.establecimiento_type == "propio"
    assert result.elected_withholding_pct == "15"
    assert result.vivienda_office_total_m2 == Decimal("120.50")
    assert result.vivienda_office_office_m2 == Decimal("24.10")
    assert result.iae_epigraph == "721"


def test_sparse_fixture_yields_none_for_missing_labels() -> None:
    sparse = "<html><body><p>Referencia catastral: 1234567AB1234S0001WX</p></body></html>"

    result = parse_g313_html(sparse)

    assert result.fiscal_address_cadastral_reference == "1234567AB1234S0001WX"
    assert result.activity_start_date is None
    assert result.vivienda_office_total_m2 is None
    assert result.elected_withholding_pct is None


def test_malformed_date_raises_typed_parse_error() -> None:
    bad = "<p>Fecha de alta de la actividad: 2018-03-15</p>"

    with pytest.raises(CensoParseError) as exc:
        parse_g313_html(bad)

    assert exc.value.failure_mode == "live_navigation_failed"
    assert "activity_start_date" in str(exc.value)


def test_malformed_m2_raises_typed_parse_error() -> None:
    bad = "<p>Superficie total de la vivienda: ABC m²</p>"

    with pytest.raises(CensoParseError) as exc:
        parse_g313_html(bad)

    assert "vivienda_office_total_m2" in str(exc.value)


def test_malformed_cadastral_raises_typed_parse_error() -> None:
    bad = "<p>Referencia catastral: NOTACADASTRAL</p>"

    with pytest.raises(CensoParseError) as exc:
        parse_g313_html(bad)

    assert "cadastral" in str(exc.value)


def test_baja_date_populates_activity_end_date() -> None:
    fixture = "<p>Fecha de alta de la actividad: 01/01/2020</p><p>Fecha de baja de la actividad: 31/12/2024</p>"

    result = parse_g313_html(fixture)

    assert result.activity_start_date == date(2020, 1, 1)
    assert result.activity_end_date == date(2024, 12, 31)
