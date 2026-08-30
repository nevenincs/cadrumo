"""Offline parser tests for AEAT IVA compensation wallet captures."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from pydantic import AnyUrl

from ......core import Period
from ......core.config import Settings
from ......core.decimal import AEAT_THOUSANDS_SEPARATORS
from ......core.external_constants import UTF_8_ENCODING
from ......domain.calculations.registry.errors import RegistryValidationError
from ......domain.calculations.registry.remote_state_guard import RemoteOperation, assert_remote_operation_allowed
from ......tests.aeat_literal_fixtures import (
    AEAT_NON_HOST_AUTHORITY_CANARIES,
    AEAT_SUFFIX_LOOKALIKE_HOST_CANARY,
    CENSAL_WRITE_SURFACE_PATH_CANARIES,
    PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE,
    aeat_url,
    configured_path,
)
from ...browser import Profile, opened_browser_page, shared_playwright_runtime
from .._adapter_utils import is_aeat_auth_gate_redirect
from .._iva_compensation_wallet_parsing import (
    IVA_COMPENSATION_WALLET_READ_POLICY,
    _assert_own_name_representation_form_html,
    _parse_spanish_decimal,
    _wallet_execute_gate_status,
    _wallet_page_shape_context,
    _wallet_row_from_cells,
    discover_iva_compensation_wallet_entrypoint,
    is_aeat_wallet_read_url,
    parse_iva_compensation_wallet_html,
)
from ..errors import SedeFailureMode, SedeNavigationError, SedeParseError
from ..iva_compensation_wallet import (
    IVA_COMPENSATION_WALLET_URL,
    PRE303_PRESENTATION_SERVICE_URL,
    _assert_read_browser_action,
    _assert_read_http,
    _dump_wallet_diagnostic,
    _wait_for_wallet_execute_initial_shape,
    assert_wallet_read_landing,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_EXTERNAL = Settings.external_constants()
_AEAT_AUTH_GATE_URL = f"{_EXTERNAL.aeat.domains.sede}{_EXTERNAL.aeat.sede_paths.auth_gate_4033}"
_SYNTHETIC_TAXPAYER_REF = "synthetic-taxpayer"
_TARGET_PERIOD = Period.from_year_and_code(2026, "2T")

_SEPARATOR_NAMES = {
    ".": "full-stop",
    "\u00a0": "non-breaking-space",
    "\u202f": "narrow-no-break-space",
}
"""Readable test ids for the separators AEAT groups thousands with.

Keyed by escape rather than by a literal code point: two of the three are
invisible in a diff and in an editor, so a literal is corruptible by anything
that touches whitespace. The mapping is asserted complete against
:data:`~core.decimal.AEAT_THOUSANDS_SEPARATORS`, so a separator added there
without a name here fails rather than silently dropping out of the sweep.
"""

assert set(_SEPARATOR_NAMES) == set(AEAT_THOUSANDS_SEPARATORS), (
    "the separator id map has drifted from AEAT_THOUSANDS_SEPARATORS; "
    f"named={sorted(_SEPARATOR_NAMES)!r} declared={sorted(AEAT_THOUSANDS_SEPARATORS)!r}"
)


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


@pytest.mark.parametrize(
    ("separator", "name"),
    [pytest.param(sep, _SEPARATOR_NAMES[sep], id=_SEPARATOR_NAMES[sep]) for sep in AEAT_THOUSANDS_SEPARATORS],
)
def test_an_aggregate_grouped_with_any_printed_separator_reads_the_whole_figure(
    separator: str,
    name: str,
) -> None:
    """No separator AEAT prints may cost the aggregate its leading group.

    The sweep is over every member of
    :data:`~core.decimal.AEAT_THOUSANDS_SEPARATORS` rather than over the two
    that were broken, so a separator added to that set later cannot enter the
    tree with this surface unproven.

    The aggregate is the authoritative "cuotas a compensar pendientes de
    períodos anteriores" line — the compensación carry a taxpayer claims — and
    it is read by an UNANCHORED scan over a labelled line. When that scan's
    separator class was a dot and nothing else, ``1{NBSP}900,50`` yielded the
    fragment ``900,50``, and the fragment then satisfied the anchored shape
    check cleanly, because a fragment of the shape IS the shape. Nothing raised.
    A thousandfold under-read of this figure over-pays.

    The detail rows are omitted deliberately. With rows present the aggregate is
    cross-checked against their sum and a mis-read surfaces as a refusal; it is
    the rows-absent capture — an aggregate AEAT prints with no itemisation — that
    has no second opinion and would have persisted the wrong number silently.
    """
    html = f"""
    <html><head><title>Cartera de cuotas de IVA a compensar</title></head><body>
      <h1>Cartera de cuotas de IVA a compensar</h1>
      <li class="ancho_99"><strong>Cuotas a compensar pendientes de períodos anteriores:</strong>
        <span>1{separator}900,50</span></li>
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

    assert observation.total_pending == Decimal("1900.50"), f"{name}-grouped aggregate lost its leading group"
    assert observation.rows == ()


@pytest.mark.parametrize(
    ("separator", "name"),
    [pytest.param(sep, _SEPARATOR_NAMES[sep], id=_SEPARATOR_NAMES[sep]) for sep in AEAT_THOUSANDS_SEPARATORS],
)
def test_a_cuota_disponible_cell_grouped_with_any_printed_separator_is_read_not_refused(
    separator: str,
    name: str,
) -> None:
    """A row cell must reach the shape check as AEAT printed it, separators intact.

    The row cells were built through the marker-matching normaliser, whose
    ``\\s+`` collapse rewrites both non-breaking spaces to an ASCII space. The
    anchored check refuses an ASCII-space grouping by design — that is AEAT's
    COLUMN separator, and admitting it would let a grammar bridge a label-to-value
    gap — so a genuine ``1{NBSP}500,00`` cell was refused outright by the time it
    arrived. The widening to those separators was real and never reached this
    surface.
    """
    html = _cartera_results_html(
        total=f"1{separator}900,50",
        rows=(
            f'<tr><td class="texto_cen">2024</td><td class="texto_cen">4T</td>'
            f'<td class="texto_der">                 1{separator}500,00</td></tr>'
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

    assert observation.rows[0].pending_amount == Decimal("1500.00"), f"{name}-grouped cell was not read as printed"
    assert observation.total_pending == Decimal("1900.50")
    # The cell survives into the row's own audit label with its printed
    # separator intact, so the persisted evidence still shows what AEAT rendered.
    raw_label = observation.rows[0].raw_label
    assert raw_label is not None
    assert f"1{separator}500,00" in raw_label


def test_a_cuota_disponible_cell_grouped_with_an_ascii_space_is_still_refused() -> None:
    """The half that must never be widened: an ASCII space does not group thousands.

    AEAT reserves it for column separation, so a cell arriving with one is a
    template change to surface, not a figure to read across the gap.
    """
    html = _cartera_results_html(
        total="1.900,50",
        rows="<tr><td>2024</td><td>4T</td><td>1 500,00</td></tr>",
    )

    with pytest.raises(SedeParseError) as exc_info:
        parse_iva_compensation_wallet_html(
            html,
            taxpayer_nif=_SYNTHETIC_TAXPAYER_REF,
            authenticated_identity=_SYNTHETIC_TAXPAYER_REF,
            target_year=2026,
            target_period=_TARGET_PERIOD,
            source_url=IVA_COMPENSATION_WALLET_URL,
            captured_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        )

    assert exc_info.value.failure_mode == SedeFailureMode.EXTERNAL_SHAPE_CHANGED


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


def test_iva_wallet_read_guard_allows_reviewed_browser_read_actions() -> None:
    for action_label in (
        _EXTERNAL.aeat.pre303.representation_own_name_action_label,
        _EXTERNAL.aeat.pre303.wallet_execute_read_action_label,
        _EXTERNAL.aeat.pre303.wallet_discovered_entrypoint_action_label,
    ):
        _assert_read_browser_action(action_label)


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


def test_own_name_representation_guard_rejects_representative_context() -> None:
    landing_url = f"{_EXTERNAL.aeat.domains.www6}{_EXTERNAL.aeat.clave_movil.dialogo_representacion_path}"
    cases = (
        (
            f"""
            <html><body>
              <form id="repForm" method="get" action="{_EXTERNAL.aeat.clave_movil.dialogo_representacion_path}">
                <input id="propio" name="representacion" type="radio" />
                <input id="representante" name="representacion" type="radio" checked="checked" />
                <button type="submit">Continuar</button>
              </form>
            </body></html>
            """,
            "representative mode selected",
        ),
        (
            f"""
            <html><body>
              <form id="repForm" method="get" action="{_EXTERNAL.aeat.clave_movil.dialogo_representacion_path}">
                <input id="propio" name="representacion" type="radio" checked="checked" />
                <input id="representante" name="representacion" type="radio" />
                <input id="nif" name="nif" type="text" value="represented-taxpayer-canary" />
                <button type="submit">Continuar</button>
              </form>
            </body></html>
            """,
            "represented-taxpayer text fields",
        ),
    )

    for html, message in cases:
        with pytest.raises(SedeNavigationError, match=message):
            _assert_own_name_representation_form_html(
                html,
                landing_url=landing_url,
                expected_path=_EXTERNAL.aeat.sede_paths.iva_compensation_wallet,
            )


def test_discover_iva_compensation_wallet_entrypoint_preserves_query_and_drops_fragment() -> None:
    query = "ignored=token"

    for fragment in ("", "#fragment"):
        html = f"""
        <html><body>
          <a href="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}?{query}{fragment}">
            Consulta de la cartera de cuotas de IVA a compensar
          </a>
        </body></html>
        """

        discovered = discover_iva_compensation_wallet_entrypoint(
            html,
            base_url=PRE303_PRESENTATION_SERVICE_URL,
        )

        assert discovered == f"{IVA_COMPENSATION_WALLET_URL}?{query}", fragment


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
    assert is_aeat_auth_gate_redirect(_AEAT_AUTH_GATE_URL)
    assert not is_aeat_auth_gate_redirect(IVA_COMPENSATION_WALLET_URL)


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


def test_wallet_shape_context_carries_page_text_so_the_leak_assertion_can_fire() -> None:
    """Positive control for the ``not in str(context)`` assertion above.

    That assertion passes for two unrelated reasons it cannot tell apart:
    because something redacted the value, or because the shape reader never
    reads that attribute at all. Its canary sits in an ``input``'s ``value``,
    which :func:`_wallet_page_shape_context` does not carry -- so on its own it
    is evidence about the reader's field selection, not about redaction, and it
    would read exactly the same if page text could never reach ``str(context)``
    by any route.

    This is what makes it evidence. The same canary is placed in ``input@id``,
    which the reader does carry verbatim through ``bounded_text``, and the
    assertion is inverted: it must be PRESENT. A change that stopped
    page-derived text reaching ``str(context)`` reds this test at the moment
    the sibling's pass would have gone vacuous, rather than silently.

    It pins a CHANNEL, not a permission. Structural attribute names are
    deliberately recorded in a shape diagnostic and ``value`` deliberately is
    not; the pair states that distinction as something a run can check.
    """
    html = f"""
    <html><body>
      <form id="Form" method="post" action="{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}">
        <input id="QUERY-CANARY" name="session" type="hidden" value="not-read" />
      </form>
    </body></html>
    """

    context = _wallet_page_shape_context(html, landing_url=IVA_COMPENSATION_WALLET_URL)

    assert "QUERY-CANARY" in str(context)
    assert context["inputs"][0]["id"] == "QUERY-CANARY"


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
    settings = Settings(cadrumo_token_dir=tmp_path)
    profile = Profile(name="wallet-diagnostic")

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
    """Both exported URLs come from the registry, on the unnumbered origin.

    This previously asserted each URL equalled a build against
    ``domains.www1``, which pinned a numbered host inside the test meant to
    prove the routes are centralised. AEAT assigns the host that answers a
    session, so asserting one made the test encode the very assumption it
    was guarding against, and it would have refused a correctly de-pinned
    URL. Centralisation is the property worth holding; the number was never
    part of it.
    """
    assert (
        f"{_EXTERNAL.aeat.domains.sede}{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}"
    ) == IVA_COMPENSATION_WALLET_URL
    assert (
        f"{_EXTERNAL.aeat.domains.sede}{_EXTERNAL.aeat.pre303.presentation_service_path}"
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


# ---------------------------------------------------------------------------
# _parse_spanish_decimal requires the two-decimal comma tail every observed
# AEAT wallet cell carries -- a dot-grouped figure lacking it is a template
# shape change, not a value ``strip_thousands=True`` should silently guess.
# ---------------------------------------------------------------------------


def test_parse_spanish_decimal_accepts_the_shapes_the_live_wallet_actually_prints() -> None:
    """Every shape observed in the committed cartera fixtures still parses."""
    assert _parse_spanish_decimal("1.500,00") == Decimal("1500.00")
    assert _parse_spanish_decimal("400,50") == Decimal("400.50")
    assert _parse_spanish_decimal("123,45") == Decimal("123.45")
    assert _parse_spanish_decimal("0,00") == Decimal("0.00")
    assert _parse_spanish_decimal("1.000.000,00") == Decimal("1000000.00")


def test_parse_spanish_decimal_rejects_a_dot_grouped_amount_missing_its_decimal_tail() -> None:
    """A row cell without AEAT's mandatory ``,NN`` tail is a shape change, not a value.

    Before this guard, ``strip_thousands=True`` read every dot as a thousands
    separator unconditionally: ``"1.500"`` (had AEAT ever rendered a wallet
    cell without decimals) would have silently parsed to ``Decimal("1500")``
    with no signal that the page no longer matches what every committed
    fixture shows AEAT actually prints. It must now raise instead.
    """
    with pytest.raises(SedeParseError) as exc_info:
        _parse_spanish_decimal("1.500")

    assert exc_info.value.failure_mode == SedeFailureMode.EXTERNAL_SHAPE_CHANGED


def test_parse_spanish_decimal_rejects_a_bare_integer_amount_cell() -> None:
    """A bare integer with no separator at all is also refused, not silently accepted."""
    with pytest.raises(SedeParseError) as exc_info:
        _parse_spanish_decimal("500")

    assert exc_info.value.failure_mode == SedeFailureMode.EXTERNAL_SHAPE_CHANGED


def test_parse_spanish_decimal_negative_amount_reaches_its_own_refusal_message() -> None:
    """A correctly-shaped negative amount is refused for being negative, not for its shape."""
    with pytest.raises(SedeParseError, match="must be non-negative"):
        _parse_spanish_decimal("-1,00")


def test_wallet_read_guard_admits_sibling_load_balancer_host() -> None:
    """An authenticated wallet pull dispatched to a sibling www{n} host is allowed."""
    drifted = f"{_EXTERNAL.aeat.domains.www12}{_EXTERNAL.aeat.sede_paths.iva_compensation_wallet}"
    result = assert_remote_operation_allowed(
        IVA_COMPENSATION_WALLET_READ_POLICY,
        RemoteOperation(kind="http", method="GET", url=AnyUrl(drifted)),
    )
    assert result.decision == "allowed"


def test_wallet_read_guard_refuses_non_aeat_host() -> None:
    """Widening to the AEAT apex suffix must not admit an off-AEAT host."""
    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        assert_remote_operation_allowed(
            IVA_COMPENSATION_WALLET_READ_POLICY,
            RemoteOperation(kind="http", method="GET", url=AnyUrl("https://attacker.example/read/path")),
        )


class TestLiveSourceUrlAssertion:
    """The live read's source-URL check must accept any host AEAT dispatched to.

    The live test itself never runs outside an operator-approved session,
    so its assertion had never been contradicted. Exercising the assertion
    LOGIC offline is what turns it from an unexamined claim into a checked
    one: the live read stays operator-gated, but whether the check would
    accept a correct read no longer depends on anyone running it.
    """

    @pytest.mark.parametrize("origin_name", ["www1", "www2", "www6", "www12", "sede"])
    def test_a_wallet_read_on_any_dispatch_host_is_accepted(self, origin_name: str) -> None:
        """A successful read is accepted whichever sede host answered."""
        from .test_iva_compensation_wallet_live import _assert_source_url_is_a_wallet_read

        external = Settings.external_constants()
        origin = getattr(external.aeat.domains, origin_name)
        _assert_source_url_is_a_wallet_read(f"{origin}{external.aeat.sede_paths.iva_compensation_wallet}")

    def test_a_non_aeat_host_is_refused(self) -> None:
        """A URL off the AEAT apex is not a wallet read, whatever its path."""
        from .test_iva_compensation_wallet_live import _assert_source_url_is_a_wallet_read

        external = Settings.external_constants()
        with pytest.raises(pytest.fail.Exception, match="not under the AEAT apex"):
            _assert_source_url_is_a_wallet_read(
                f"https://example.invalid{external.aeat.sede_paths.iva_compensation_wallet}",
            )

    def test_another_aeat_route_is_refused(self) -> None:
        """A different AEAT route on a valid host is not a wallet read.

        Without this the check would accept any AEAT URL at all, which is
        weaker than the invariant rather than equal to it.
        """
        from .test_iva_compensation_wallet_live import _assert_source_url_is_a_wallet_read

        external = Settings.external_constants()
        with pytest.raises(pytest.fail.Exception, match="not the wallet route"):
            _assert_source_url_is_a_wallet_read(
                f"{external.aeat.domains.www6}{external.aeat.sede_paths.declarations_listing}",
            )


class TestWalletReadPolicy:
    """Wallet URL admission is delegated to the registered read policy."""

    @pytest.mark.parametrize("origin_name", ["www1", "www2", "www6", "www12", "sede"])
    def test_every_dispatch_host_is_allowed(self, origin_name: str) -> None:
        """No numbered host may be privileged over its siblings."""
        external = Settings.external_constants()
        origin = getattr(external.aeat.domains, origin_name)
        assert is_aeat_wallet_read_url(f"{origin}{external.aeat.sede_paths.iva_compensation_wallet}")

    @pytest.mark.parametrize("host", ["example.invalid", AEAT_SUFFIX_LOOKALIKE_HOST_CANARY, ""])
    def test_a_non_aeat_host_is_refused(self, host: str) -> None:
        """Neither a foreign nor a suffix-lookalike host is a wallet read."""
        external = Settings.external_constants()
        assert not is_aeat_wallet_read_url(f"https://{host}{external.aeat.sede_paths.iva_compensation_wallet}")

    @pytest.mark.parametrize("authority", AEAT_NON_HOST_AUTHORITY_CANARIES)
    def test_non_host_authorities_are_refused(self, authority: str) -> None:
        """User-info and ports cannot bypass the wallet read policy."""
        external = Settings.external_constants()
        assert not is_aeat_wallet_read_url(f"https://{authority}{external.aeat.sede_paths.iva_compensation_wallet}")

    def test_the_wallet_url_names_no_numbered_host(self) -> None:
        """The exported wallet URL must not assert a host the balancer assigns."""
        from .._iva_compensation_wallet_parsing import _WALLET_URL

        external = Settings.external_constants()
        numbered = [
            name
            for name in ("www1", "www2", "www3", "www6", "www12")
            if urlsplit(getattr(external.aeat.domains, name)).netloc in _WALLET_URL
        ]
        assert numbered == [], f"the wallet URL pins a numbered host: {numbered}"


class TestWalletLandingRefusal:
    """Where AEAT served the read, checked after the ``ejecutar`` submit.

    This is the most write-adjacent driver in the package: it fills an
    ejercicio and periodo and clicks a real submit input. That click issues
    a browser form POST, which the first-party HTTP guard never sees and
    which the forbidden-verb source scan permits by design. The post-execute
    shape check reads the returned HTML's own form action -- a DOM AEAT
    controls -- so it is not evidence of the URL served.

    The tests drive the reader's own exported rule, not a copy of it.
    """

    def test_the_pre303_presentation_service_is_admitted(self) -> None:
        assert_wallet_read_landing(PRE303_PRESENTATION_SERVICE_URL)

    def test_the_wallet_itself_is_admitted(self) -> None:
        assert_wallet_read_landing(IVA_COMPENSATION_WALLET_URL)

    def test_a_numbered_load_balancer_host_serving_the_wallet_is_admitted(self) -> None:
        """AEAT assigns the numbered host per session; that dispatch is not a write."""
        aeat = Settings.external_constants().aeat
        assert_wallet_read_landing(f"{aeat.domains.www6}{urlsplit(IVA_COMPENSATION_WALLET_URL).path}")

    @pytest.mark.parametrize("write_path", CENSAL_WRITE_SURFACE_PATH_CANARIES)
    def test_a_real_aeat_write_surface_is_refused(self, write_path: str) -> None:
        """None of these carries a write verb; the path allow-list is what refuses them."""
        with pytest.raises(SedeNavigationError):
            assert_wallet_read_landing(aeat_url("sede", write_path))

    def test_the_procedure_launcher_family_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            assert_wallet_read_landing(aeat_url("sede", f"{PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE}G322.shtml"))

    def test_the_auth_gate_landing_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            assert_wallet_read_landing(aeat_url("sede", configured_path("sede_paths", "auth_gate_4033")))

    def test_a_stalled_traversal_still_on_the_acting_capacity_gate_is_refused(self) -> None:
        """The gate is transit, not rest.

        Every landing rule in this reader sits after a wait that has
        already required the traversal to have left the gate, so resting
        there means the continuation did not complete.
        """
        aeat = Settings.external_constants().aeat
        with pytest.raises(SedeNavigationError):
            assert_wallet_read_landing(f"{aeat.domains.sede}{aeat.clave_movil.dialogo_representacion_path}")

    def test_an_unreadable_landing_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            assert_wallet_read_landing("")
