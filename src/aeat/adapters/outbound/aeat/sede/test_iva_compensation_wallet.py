"""Offline parser tests for AEAT IVA compensation wallet captures."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ._errors import SedeParseError
from ._iva_compensation_wallet import is_aeat_wallet_auth_gate_redirect, parse_iva_compensation_wallet_html

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def test_parse_iva_compensation_wallet_html_extracts_generation_rows_and_total() -> None:
    html = """
    <html><body>
      <table id="cartera">
        <thead>
          <tr>
            <th>Ejercicio</th>
            <th>Periodo</th>
            <th>Cuota generada</th>
            <th>Cuota aplicada</th>
            <th>Cuota pendiente</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>2025</td>
            <td>4T</td>
            <td>1.500,00</td>
            <td>300,00</td>
            <td>1.200,00</td>
          </tr>
          <tr>
            <td>2026</td>
            <td>1T</td>
            <td>400,50</td>
            <td>0,00</td>
            <td>400,50</td>
          </tr>
        </tbody>
      </table>
    </body></html>
    """

    observation = parse_iva_compensation_wallet_html(
        html,
        taxpayer_nif="12345678Z",
        authenticated_identity="12345678Z",
        target_year=2026,
        target_period="2T",
        source_url="https://www1.agenciatributaria.gob.es/wlpl/DAI3-RUTI/CarteraCuotas",
        captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
    )

    assert observation.total_pending == Decimal("1600.50")
    assert observation.rows[0].generation_year == 2025
    assert observation.rows[0].generation_period == "4T"
    assert observation.rows[0].generated_amount == Decimal("1500.00")
    assert observation.rows[0].applied_amount == Decimal("300.00")
    assert observation.rows[0].pending_amount == Decimal("1200.00")
    assert observation.rows[1].pending_amount == Decimal("400.50")
    assert observation.raw_sha256 is not None


def test_parse_iva_compensation_wallet_html_refuses_unrecognized_page() -> None:
    html = """
    <html><body>
      <table>
        <tr><th>Referencia</th><th>Estado</th></tr>
        <tr><td>sin-datos</td><td>ok</td></tr>
      </table>
    </body></html>
    """

    with pytest.raises(SedeParseError, match="recognizable IVA compensation wallet table"):
        parse_iva_compensation_wallet_html(
            html,
            taxpayer_nif="12345678Z",
            authenticated_identity="12345678Z",
            target_year=2026,
            target_period="2T",
            source_url="https://www1.agenciatributaria.gob.es/wlpl/DAI3-RUTI/CarteraCuotas",
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        )


def test_iva_wallet_auth_gate_detector_matches_aeat_4033_redirect() -> None:
    assert is_aeat_wallet_auth_gate_redirect("https://sede.agenciatributaria.gob.es/Sede/errores/erro4033.html")
    assert not is_aeat_wallet_auth_gate_redirect("https://www1.agenciatributaria.gob.es/wlpl/DAI3-RUTI/CarteraCuotas")
