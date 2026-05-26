"""Offline parser tests for AEAT IVA compensation wallet captures."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....core.config import Settings
from .....domain.calculations.registry import RegistryValidationError
from ._errors import SedeParseError
from ._iva_compensation_wallet import (
    IVA_COMPENSATION_WALLET_URL,
    PRE303_PRESENTATION_SERVICE_URL,
    _assert_read_browser_action,
    _assert_read_http,
    _wallet_execute_gate_status,
    is_aeat_wallet_auth_gate_redirect,
    parse_iva_compensation_wallet_html,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]

_EXTERNAL = Settings.external_constants()
_AEAT_AUTH_GATE_URL = f"{_EXTERNAL.aeat.domains.sede}{_EXTERNAL.aeat.sede_paths.auth_gate_4033}"
_WALLET_ERROR_PREFIX = "adapters.aeat.iva_wallet.errors"


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
        source_url=IVA_COMPENSATION_WALLET_URL,
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

    with pytest.raises(SedeParseError) as exc_info:
        parse_iva_compensation_wallet_html(
            html,
            taxpayer_nif="12345678Z",
            authenticated_identity="12345678Z",
            target_year=2026,
            target_period="2T",
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        )
    _assert_wallet_error_key(exc_info.value, "missing_wallet_table")


def test_parse_iva_compensation_wallet_html_refuses_unexecuted_empty_wallet_surface() -> None:
    html = f"""
    <html>
      <head><title>Cartera de cuotas a compensar</title></head>
      <body>
        <h1>Cartera de cuotas de IVA a compensar</h1>
        <form id="Form" method="post" action="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}">
          <input id="ejecutar" name="ejecutar" type="submit" />
        </form>
      </body>
    </html>
    """

    with pytest.raises(SedeParseError) as exc_info:
        parse_iva_compensation_wallet_html(
            html,
            taxpayer_nif="12345678Z",
            authenticated_identity="12345678Z",
            target_year=2026,
            target_period="2T",
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        )
    _assert_wallet_error_key(exc_info.value, "missing_wallet_table")


def test_parse_iva_compensation_wallet_html_refuses_execute_shell_as_empty_wallet() -> None:
    html = f"""
    <html>
      <head><title>Cartera de cuotas a compensar</title></head>
      <body>
        <h1>Cartera de cuotas de IVA a compensar</h1>
        <form id="Form" method="post" action="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}"></form>
        <input id="ejecutar" name="ejecutar" type="submit" />
      </body>
    </html>
    """

    with pytest.raises(SedeParseError) as exc_info:
        parse_iva_compensation_wallet_html(
            html,
            taxpayer_nif="12345678Z",
            authenticated_identity="12345678Z",
            target_year=2026,
            target_period="2T",
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        )
    _assert_wallet_error_key(exc_info.value, "missing_wallet_table")


def test_parse_iva_compensation_wallet_html_accepts_executed_empty_wallet_shell_only_when_authorized() -> None:
    html = f"""
    <html>
      <head><title>Cartera de cuotas a compensar</title></head>
      <body>
        <h1>Cartera de cuotas de IVA a compensar</h1>
        <form id="Form" method="post" action="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}">
          <input type="hidden" name="ejercicio" value="2026" />
        </form>
      </body>
    </html>
    """

    observation = parse_iva_compensation_wallet_html(
        html,
        taxpayer_nif="12345678Z",
        authenticated_identity="12345678Z",
        target_year=2026,
        target_period="2T",
        source_url=IVA_COMPENSATION_WALLET_URL,
        captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        allow_empty_wallet_shell=True,
    )

    assert observation.rows == ()
    assert observation.total_pending == Decimal("0")


def test_parse_iva_compensation_wallet_html_refuses_authorized_empty_wallet_shell_with_execute_control() -> None:
    html = f"""
    <html>
      <head><title>Cartera de cuotas a compensar</title></head>
      <body>
        <h1>Cartera de cuotas de IVA a compensar</h1>
        <form id="Form" method="post" action="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}">
          <input id="ejecutar" name="ejecutar" type="submit" />
        </form>
      </body>
    </html>
    """

    with pytest.raises(SedeParseError) as exc_info:
        parse_iva_compensation_wallet_html(
            html,
            taxpayer_nif="12345678Z",
            authenticated_identity="12345678Z",
            target_year=2026,
            target_period="2T",
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
            allow_empty_wallet_shell=True,
        )
    _assert_wallet_error_key(exc_info.value, "missing_wallet_table")


def test_parse_iva_compensation_wallet_html_redacts_invalid_wallet_values_from_errors() -> None:
    sensitive_value = "negative-wallet-amount=999999"
    html = f"""
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
            <td>{sensitive_value}</td>
            <td>4T</td>
            <td>1.500,00</td>
            <td>300,00</td>
            <td>1.200,00</td>
          </tr>
        </tbody>
      </table>
    </body></html>
    """

    with pytest.raises(SedeParseError) as exc_info:
        parse_iva_compensation_wallet_html(
            html,
            taxpayer_nif="12345678Z",
            authenticated_identity="12345678Z",
            target_year=2026,
            target_period="2T",
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        )

    exc = exc_info.value
    _assert_wallet_error_key(exc, "generation_year_unparseable")
    assert sensitive_value not in str(exc)
    assert sensitive_value not in repr(exc.context)
    assert exc.context is not None
    assert exc.context["value_length"] == len(sensitive_value)
    assert "value_sha256" in exc.context


def test_wallet_execute_gate_detection_identifies_read_query_shape() -> None:
    html = f"""
    <html><body>
      <form id="Form" method="post" action="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}">
        <input id="ejecutar" name="ejecutar" type="submit" />
      </form>
    </body></html>
    """

    status = _wallet_execute_gate_status(html, expected_path=_EXTERNAL.aeat.sede_paths.iva_compensation_wallet)

    assert status == "wallet-execute-submit-present"


def test_iva_wallet_read_guard_allows_declared_wallet_read_post_surface() -> None:
    _assert_read_http("POST", IVA_COMPENSATION_WALLET_URL)


def test_iva_wallet_read_guard_rejects_unclassified_browser_action() -> None:
    with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
        _assert_read_browser_action("wallet-unreviewed-click")


def test_iva_wallet_read_guard_allows_own_name_representation_gate() -> None:
    _assert_read_browser_action("representation-gate-own-name-continue")


def test_iva_wallet_read_guard_allows_wallet_execute_read_query() -> None:
    _assert_read_browser_action("wallet-execute-read-query")


def test_iva_wallet_auth_gate_detector_matches_aeat_4033_redirect() -> None:
    assert is_aeat_wallet_auth_gate_redirect(_AEAT_AUTH_GATE_URL)
    assert not is_aeat_wallet_auth_gate_redirect(IVA_COMPENSATION_WALLET_URL)


def test_iva_wallet_live_routes_are_centralized_external_constants() -> None:
    assert (
        f"{_EXTERNAL.aeat.domains.www1}{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}"
    ) == IVA_COMPENSATION_WALLET_URL
    assert (
        f"{_EXTERNAL.aeat.domains.www1}{_EXTERNAL.aeat.pre303.presentation_service_path}"
    ) == PRE303_PRESENTATION_SERVICE_URL


def test_iva_wallet_sede_errors_do_not_use_raw_positional_messages() -> None:
    source_path = Path(__file__).with_name("_iva_compensation_wallet.py")
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id not in {"SedeNavigationError", "SedeParseError"}:
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if not isinstance(first_arg, ast.Constant | ast.JoinedStr):
            continue
        has_translated_message = any(keyword.arg == "translated_message" for keyword in node.keywords)
        if not has_translated_message:
            violations.append(f"{source_path.name}:{node.lineno}:{node.func.id}")

    assert violations == []


def _assert_wallet_error_key(exc: SedeParseError, suffix: str) -> None:
    assert exc.args == ()
    assert exc.translated_message == f"{_WALLET_ERROR_PREFIX}.{suffix}"
