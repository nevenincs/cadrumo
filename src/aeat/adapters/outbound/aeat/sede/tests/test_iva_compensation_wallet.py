"""Offline parser tests for AEAT IVA compensation wallet captures."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ......core import Period
from ......core.config import Settings
from ......core.external_constants import UTF_8_ENCODING
from ......domain.calculations.registry import RegistryValidationError
from ...browser import Profile, opened_browser_page, shared_playwright_runtime
from .._errors import SedeNavigationError, SedeParseError
from .._iva_compensation_wallet import (
    IVA_COMPENSATION_WALLET_URL,
    PRE303_PRESENTATION_SERVICE_URL,
    _assert_read_browser_action,
    _assert_read_http,
    _dump_wallet_diagnostic,
    _wait_for_wallet_execute_initial_shape,
)
from .._iva_compensation_wallet_parsing import (
    _assert_own_name_representation_form_html,
    _parse_spanish_decimal,
    _wallet_execute_gate_status,
    _wallet_page_shape_context,
    _wallet_row_from_cells,
    discover_iva_compensation_wallet_entrypoint,
    is_aeat_wallet_auth_gate_redirect,
    parse_iva_compensation_wallet_html,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_EXTERNAL = Settings.external_constants()
_AEAT_AUTH_GATE_URL = f"{_EXTERNAL.aeat.domains.sede}{_EXTERNAL.aeat.sede_paths.auth_gate_4033}"
_SYNTHETIC_TAXPAYER_REF = "synthetic-taxpayer"
_TARGET_PERIOD = Period.from_year_and_code(2026, "2T")


def _cartera_results_html(*, total: str, rows: str) -> str:
    """Build a cartera results page mirroring AEAT's real own-name wallet shape.

    The aggregate line and the ``Ejercicio``/``Período``/``Cuota Disponible``
    detail table reproduce the structure captured from the live AEAT surface
    (configured IVA compensation wallet path after own-name + ejercicio/período query).
    """
    return f"""
    <html><head><title>Cartera de cuotas de IVA a compensar</title></head><body>
      <h1>Cartera de cuotas de IVA a compensar</h1>
      <ul>
        <li class="sei_cols"><strong class="azul">Ejercicio:</strong>&nbsp;<span class="notraducir">2026</span></li>
        <li class="sei_cols"><strong class="azul">Período:</strong>&nbsp;<span class="notraducir">2T</span></li>
      </ul>
      <ul>
        <li class="ancho_99"><strong class="azul">Cuotas a compensar pendientes de períodos anteriores:</strong>
          &nbsp;<span class="notraducir">{total}</span></li>
      </ul>
      <table class="bloque_cen" id="tablaResultados" title="Resultados">
        <caption>&nbsp;</caption>
        <thead>
          <tr>
            <th class="texto_cen">Ejercicio</th>
            <th class="texto_cen">Período</th>
            <th class="texto_cen">Cuota Disponible</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </body></html>
    """


def test_parse_iva_compensation_wallet_html_extracts_disponible_rows_and_total() -> None:
    html = _cartera_results_html(
        total="1.900,50",
        rows=(
            '<tr><td class="texto_cen">2024</td><td class="texto_cen">4T</td>'
            '<td class="texto_der">                 1.500,00</td></tr>'
            '<tr><td class="texto_cen">2025</td><td class="texto_cen">1T</td>'
            '<td class="texto_der">                 400,50</td></tr>'
        ),
    )

    observation = parse_iva_compensation_wallet_html(
        html,
        taxpayer_nif=_SYNTHETIC_TAXPAYER_REF,
        authenticated_identity=_SYNTHETIC_TAXPAYER_REF,
        target_year=2026,
        target_period=_TARGET_PERIOD,
        source_url=IVA_COMPENSATION_WALLET_URL,
        captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
    )

    # The aggregate "pendientes de períodos anteriores" line is the contract total.
    assert observation.total_pending == Decimal("1900.50")
    assert len(observation.rows) == 2
    assert observation.rows[0].generation_year == 2024
    assert observation.rows[0].generation_period == Period.from_year_and_code(2024, "4T")
    assert observation.rows[0].pending_amount == Decimal("1500.00")
    # AEAT's cartera consultation surface does not break out generated/applied.
    assert observation.rows[0].generated_amount is None
    assert observation.rows[0].applied_amount is None
    assert observation.rows[1].generation_year == 2025
    assert observation.rows[1].generation_period == Period.from_year_and_code(2025, "1T")
    assert observation.rows[1].pending_amount == Decimal("400.50")
    assert observation.raw_sha256 is not None


def test_parse_iva_compensation_wallet_html_does_not_under_declare_a_populated_cartera() -> None:
    """Regression: a populated cartera must never parse to a silent zero wallet.

    The live ``allow_empty_wallet_shell`` path must not swallow a results page that
    carries a non-zero aggregate and detail rows.
    """
    html = _cartera_results_html(
        total="123,45",
        rows="<tr><td>2024</td><td>4T</td><td>123,45</td></tr>",
    )

    observation = parse_iva_compensation_wallet_html(
        html,
        taxpayer_nif=_SYNTHETIC_TAXPAYER_REF,
        authenticated_identity=_SYNTHETIC_TAXPAYER_REF,
        target_year=2026,
        target_period=_TARGET_PERIOD,
        source_url=IVA_COMPENSATION_WALLET_URL,
        captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        allow_empty_wallet_shell=True,
    )

    assert observation.total_pending == Decimal("123.45")
    assert len(observation.rows) == 1


def test_parse_iva_compensation_wallet_html_accepts_zero_aggregate_empty_cartera() -> None:
    """A genuinely empty cartera prints the aggregate at 0,00 with no detail rows."""
    html = """
    <html><head><title>Cartera de cuotas de IVA a compensar</title></head><body>
      <h1>Cartera de cuotas de IVA a compensar</h1>
      <li class="ancho_99"><strong>Cuotas a compensar pendientes de períodos anteriores:</strong>
        <span>0,00</span></li>
    </body></html>
    """

    observation = parse_iva_compensation_wallet_html(
        html,
        taxpayer_nif=_SYNTHETIC_TAXPAYER_REF,
        authenticated_identity=_SYNTHETIC_TAXPAYER_REF,
        target_year=2026,
        target_period=_TARGET_PERIOD,
        source_url=IVA_COMPENSATION_WALLET_URL,
        captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
    )

    assert observation.total_pending == Decimal("0")
    assert observation.rows == ()


def test_parse_iva_compensation_wallet_html_rejects_summary_row_mismatch() -> None:
    """The aggregate total must reconcile with the sum of detail rows."""
    html = _cartera_results_html(
        total="999,99",
        rows="<tr><td>2024</td><td>4T</td><td>123,45</td></tr>",
    )

    with pytest.raises(SedeParseError, match="does not equal the sum"):
        parse_iva_compensation_wallet_html(
            html,
            taxpayer_nif=_SYNTHETIC_TAXPAYER_REF,
            authenticated_identity=_SYNTHETIC_TAXPAYER_REF,
            target_year=2026,
            target_period=_TARGET_PERIOD,
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        )


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
            taxpayer_nif=_SYNTHETIC_TAXPAYER_REF,
            authenticated_identity=_SYNTHETIC_TAXPAYER_REF,
            target_year=2026,
            target_period=_TARGET_PERIOD,
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        )


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

    with pytest.raises(SedeParseError, match="recognizable IVA compensation wallet table"):
        parse_iva_compensation_wallet_html(
            html,
            taxpayer_nif=_SYNTHETIC_TAXPAYER_REF,
            authenticated_identity=_SYNTHETIC_TAXPAYER_REF,
            target_year=2026,
            target_period=_TARGET_PERIOD,
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        )


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

    with pytest.raises(SedeParseError, match="recognizable IVA compensation wallet table"):
        parse_iva_compensation_wallet_html(
            html,
            taxpayer_nif=_SYNTHETIC_TAXPAYER_REF,
            authenticated_identity=_SYNTHETIC_TAXPAYER_REF,
            target_year=2026,
            target_period=_TARGET_PERIOD,
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        )


def test_parse_iva_compensation_wallet_html_refuses_executed_empty_wallet_shell_without_zero_aggregate() -> None:
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

    with pytest.raises(SedeParseError, match="explicit zero aggregate"):
        parse_iva_compensation_wallet_html(
            html,
            taxpayer_nif=_SYNTHETIC_TAXPAYER_REF,
            authenticated_identity=_SYNTHETIC_TAXPAYER_REF,
            target_year=2026,
            target_period=_TARGET_PERIOD,
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
            allow_empty_wallet_shell=True,
        )


def test_parse_iva_compensation_wallet_html_refuses_wrong_rendered_target_period() -> None:
    html = _cartera_results_html(
        total="123,45",
        rows="<tr><td>2024</td><td>4T</td><td>123,45</td></tr>",
    )

    with pytest.raises(SedeParseError, match="does not match requested period"):
        parse_iva_compensation_wallet_html(
            html,
            taxpayer_nif=_SYNTHETIC_TAXPAYER_REF,
            authenticated_identity=_SYNTHETIC_TAXPAYER_REF,
            target_year=2026,
            target_period=Period.from_year_and_code(2026, "1T"),
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        )


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

    with pytest.raises(SedeParseError, match="recognizable IVA compensation wallet table"):
        parse_iva_compensation_wallet_html(
            html,
            taxpayer_nif=_SYNTHETIC_TAXPAYER_REF,
            authenticated_identity=_SYNTHETIC_TAXPAYER_REF,
            target_year=2026,
            target_period=_TARGET_PERIOD,
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
            allow_empty_wallet_shell=True,
        )


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


def test_wallet_execute_initial_shape_waits_for_delayed_submit() -> None:
    pending_html = "<html><body><main></main></body></html>"
    wallet_html = f"""
    <html><body>
      <form id="Form" method="post" action="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}">
        <input id="ejecutar" name="ejecutar" type="submit" />
      </form>
    </body></html>
    """
    pages = [pending_html, pending_html, wallet_html]

    async def content() -> str:
        if len(pages) == 1:
            return pages[0]
        return pages.pop(0)

    async def run() -> tuple[str, str]:
        return await _wait_for_wallet_execute_initial_shape(
            content=content,
            expected_path=_EXTERNAL.aeat.sede_paths.iva_compensation_wallet,
            timeout_ms=2_000,
        )

    html, status = asyncio.run(run())

    assert html == wallet_html
    assert status == "wallet-execute-submit-present"


def test_iva_wallet_read_guard_allows_declared_wallet_read_post_surface() -> None:
    _assert_read_http("POST", IVA_COMPENSATION_WALLET_URL)


def test_iva_wallet_read_guard_rejects_unclassified_browser_action() -> None:
    with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
        _assert_read_browser_action("wallet-unreviewed-click")


def test_iva_wallet_read_guard_allows_own_name_representation_gate() -> None:
    _assert_read_browser_action(_EXTERNAL.aeat.pre303.representation_own_name_action_label)


def test_iva_wallet_read_guard_allows_wallet_execute_read_query() -> None:
    _assert_read_browser_action(_EXTERNAL.aeat.pre303.wallet_execute_read_action_label)


def test_iva_wallet_read_guard_allows_discovered_entrypoint_open() -> None:
    _assert_read_browser_action(_EXTERNAL.aeat.pre303.wallet_discovered_entrypoint_action_label)


def test_own_name_representation_guard_accepts_dialogo_dispatcher_shape() -> None:
    landing_url = f"{_EXTERNAL.aeat.domains.www6}{_EXTERNAL.aeat.clave_movil.dialogo_representacion_path}"
    html = f"""
    <html><body>
      <form id="repForm" method="get" action="{_EXTERNAL.aeat.clave_movil.dialogo_representacion_path}">
        <input id="ref" name="ref" type="hidden" />
        <input id="tipoIden" name="tipoIden" type="hidden" />
        <input id="borrar" name="borrar" type="hidden" />
        <input id="propio" name="representacion" type="radio" checked="checked" />
        <input id="representante" name="representacion" type="radio" />
        <input id="nif" name="nif" type="text" />
        <input id="nombre" name="nombre" type="text" />
        <button type="submit">Continuar</button>
      </form>
    </body></html>
    """

    _assert_own_name_representation_form_html(
        html,
        landing_url=landing_url,
        expected_path=_EXTERNAL.aeat.sede_paths.iva_compensation_wallet,
    )


def test_own_name_representation_guard_rejects_representative_selection() -> None:
    landing_url = f"{_EXTERNAL.aeat.domains.www6}{_EXTERNAL.aeat.clave_movil.dialogo_representacion_path}"
    html = f"""
    <html><body>
      <form id="repForm" method="get" action="{_EXTERNAL.aeat.clave_movil.dialogo_representacion_path}">
        <input id="propio" name="representacion" type="radio" />
        <input id="representante" name="representacion" type="radio" checked="checked" />
        <button type="submit">Continuar</button>
      </form>
    </body></html>
    """

    with pytest.raises(SedeNavigationError, match="representative mode selected"):
        _assert_own_name_representation_form_html(
            html,
            landing_url=landing_url,
            expected_path=_EXTERNAL.aeat.sede_paths.iva_compensation_wallet,
        )


def test_own_name_representation_guard_rejects_prefilled_represented_taxpayer_text() -> None:
    landing_url = f"{_EXTERNAL.aeat.domains.www6}{_EXTERNAL.aeat.clave_movil.dialogo_representacion_path}"
    html = f"""
    <html><body>
      <form id="repForm" method="get" action="{_EXTERNAL.aeat.clave_movil.dialogo_representacion_path}">
        <input id="propio" name="representacion" type="radio" checked="checked" />
        <input id="representante" name="representacion" type="radio" />
        <input id="nif" name="nif" type="text" value="represented-taxpayer-canary" />
        <button type="submit">Continuar</button>
      </form>
    </body></html>
    """

    with pytest.raises(SedeNavigationError, match="represented-taxpayer text fields"):
        _assert_own_name_representation_form_html(
            html,
            landing_url=landing_url,
            expected_path=_EXTERNAL.aeat.sede_paths.iva_compensation_wallet,
        )


def test_discover_iva_compensation_wallet_entrypoint_from_pre303_link() -> None:
    query = "ignored=token"
    html = f"""
    <html><body>
      <a href="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}?{query}">
        Consulta de la cartera de cuotas de IVA a compensar
      </a>
    </body></html>
    """

    discovered = discover_iva_compensation_wallet_entrypoint(
        html,
        base_url=PRE303_PRESENTATION_SERVICE_URL,
    )

    assert discovered == f"{IVA_COMPENSATION_WALLET_URL}?{query}"


def test_discover_iva_compensation_wallet_entrypoint_drops_fragment() -> None:
    query = "ignored=token"
    html = f"""
    <html><body>
      <a href="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}?{query}#fragment">
        Consulta de la cartera de cuotas de IVA a compensar
      </a>
    </body></html>
    """

    discovered = discover_iva_compensation_wallet_entrypoint(
        html,
        base_url=PRE303_PRESENTATION_SERVICE_URL,
    )

    assert discovered == f"{IVA_COMPENSATION_WALLET_URL}?{query}"


def test_discover_iva_compensation_wallet_entrypoint_rejects_non_aeat_host() -> None:
    html = f"""
    <html><body>
      <a href="https://example.invalid{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}">
        Consulta de la cartera de cuotas de IVA a compensar
      </a>
    </body></html>
    """

    discovered = discover_iva_compensation_wallet_entrypoint(
        html,
        base_url=PRE303_PRESENTATION_SERVICE_URL,
    )

    assert discovered is None


def test_iva_wallet_auth_gate_detector_matches_aeat_4033_redirect() -> None:
    assert is_aeat_wallet_auth_gate_redirect(_AEAT_AUTH_GATE_URL)
    assert not is_aeat_wallet_auth_gate_redirect(IVA_COMPENSATION_WALLET_URL)


def test_wallet_shape_context_redacts_url_query_and_input_values() -> None:
    html = f"""
    <html><body>
      <form id="Form" method="post" action="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}">
        <input id="session" name="session" type="hidden" value="QUERY-CANARY" />
      </form>
    </body></html>
    """

    context = _wallet_page_shape_context(
        html,
        landing_url=f"{IVA_COMPENSATION_WALLET_URL}?token=QUERY-CANARY#fragment",
    )

    assert context["landing_url"] == IVA_COMPENSATION_WALLET_URL
    assert "QUERY-CANARY" not in str(context)
    assert context["raw_sha256"]


def test_wallet_shape_context_reports_discovered_wallet_entrypoints_without_query_values() -> None:
    html = f"""
    <html><body>
      <a href="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}?token=QUERY-CANARY">
        Consulta de la cartera de cuotas de IVA a compensar
      </a>
      <form id="Form" method="post" action="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}">
        <input id="session" name="session" type="hidden" value="QUERY-CANARY" />
      </form>
    </body></html>
    """

    context = _wallet_page_shape_context(
        html,
        landing_url=f"{IVA_COMPENSATION_WALLET_URL}?token=QUERY-CANARY#fragment",
    )

    assert context["wallet_entrypoint_count"] == 2
    assert context["wallet_entrypoint_paths"] == (
        _EXTERNAL.aeat.sede_paths.iva_compensation_wallet,
        _EXTERNAL.aeat.sede_paths.iva_compensation_wallet,
    )
    assert "QUERY-CANARY" not in str(context)


@pytest.mark.asyncio
async def test_wallet_diagnostic_dump_writes_only_redacted_structural_summary(tmp_path: Path) -> None:
    html = f"""
    <html><body>
      <form id="Form" method="post" action="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}">
        <input id="session" name="session" type="hidden" value="QUERY-CANARY" />
      </form>
      <table>
        <tr><th>Ejercicio</th><th>Período</th><th>Cuota Disponible</th></tr>
        <tr><td>2026</td><td>2T</td><td>123,45</td></tr>
      </table>
    </body></html>
    """
    settings = Settings(aeat_token_dir=tmp_path)
    profile = Profile(name="wallet-diagnostic", storage_state_path=tmp_path / "state.json")

    async with (
        shared_playwright_runtime() as playwright,
        opened_browser_page(playwright, settings, profile) as (page, _context),
    ):
        await page.set_content(html)
        await _dump_wallet_diagnostic(page, label="unit", dump_dir=tmp_path / "diagnostics")

    summary = (tmp_path / "diagnostics" / "unit-summary.txt").read_text(encoding=UTF_8_ENCODING)
    assert "raw_sha256=" in summary
    assert "QUERY-CANARY" not in summary
    assert "123,45" not in summary
    assert "Cuota Disponible" not in summary


def test_iva_wallet_live_routes_are_centralized_external_constants() -> None:
    assert (
        f"{_EXTERNAL.aeat.domains.www1}{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}"
    ) == IVA_COMPENSATION_WALLET_URL
    assert (
        f"{_EXTERNAL.aeat.domains.www1}{_EXTERNAL.aeat.pre303.presentation_service_path}"
    ) == PRE303_PRESENTATION_SERVICE_URL


# ---------------------------------------------------------------------------
# contract/contract — empty IVA wallet period/amount cells carry translated_message
# ---------------------------------------------------------------------------


def test_parse_spanish_decimal_empty_cell_raises_with_translated_message() -> None:
    """_parse_spanish_decimal raises SedeParseError with a rendered translated_message.

    The translated_message must be set (not None) and must be a rendered locale
    string (not the raw key) so the CLI error boundary can surface a localised
    operator message for the empty-amount-cell condition.
    """
    with pytest.raises(SedeParseError) as exc_info:
        _parse_spanish_decimal("")

    exc = exc_info.value
    assert exc.translated_message is not None
    # Must not be the raw locale key (self-referencing fallback).
    assert exc.translated_message != "adapters.sede.errors.iva_wallet_empty_amount_cell"
    # Must be a non-trivial rendered string.
    assert len(exc.translated_message) > 10


def test_wallet_row_from_cells_empty_period_raises_with_translated_message() -> None:
    """_wallet_row_from_cells raises SedeParseError with a rendered translated_message.

    A row where cells[1] (the period) is blank must carry a non-None
    translated_message that is a rendered locale string (not the raw key)
    so CLI error rendering can localise the operator message.
    """
    cells = ["2026", "", "1.500,00", "300,00", "1.200,00"]

    with pytest.raises(SedeParseError) as exc_info:
        _wallet_row_from_cells(cells)

    exc = exc_info.value
    assert exc.translated_message is not None
    # Must not be the raw locale key.
    assert exc.translated_message != "adapters.sede.errors.iva_wallet_empty_period_cell"
    assert len(exc.translated_message) > 10


def test_parse_spanish_decimal_whitespace_only_cell_raises_with_translated_message() -> None:
    """A whitespace-only amount cell normalises to empty and raises SedeParseError."""
    with pytest.raises(SedeParseError) as exc_info:
        _parse_spanish_decimal("   \xa0  ")

    exc = exc_info.value
    assert exc.translated_message is not None
    assert exc.translated_message != "adapters.sede.errors.iva_wallet_empty_amount_cell"
    assert len(exc.translated_message) > 10
