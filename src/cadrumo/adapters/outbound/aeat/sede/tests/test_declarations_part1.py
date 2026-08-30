"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ......core.casilla_id import CasillaId, validated_casilla_id
from ._declarations_support import (
    _COTEJO_QUERY_URL,
    _DECLARATIONS_LISTING_URL,
    _FIXTURE_ROOT,
    UTC,
    Decimal,
    Declaracion,
    Path,
    Period,
    Profile,
    SedeParseError,
    Settings,
    _declaration_row,
    _declarations_page_shape_context,
    _extract_csv_from_url,
    _filed_observation,
    _modelo_130_snapshot,
    _modelo_snapshot,
    _parse_listbox,
    _parse_presented_at,
    _select_authoritative_declaration,
    _select_combobox_value,
    _submitted_file_payload,
    _verify_submitted_file_context,
    _with_derived_303_compensation_available_observation,
    datetime,
    opened_browser_page,
    parse_export_payload,
    registry_observation_from_filed_declaration,
    resolve_export_layout,
    shared_playwright_runtime,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = validated_casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores"
)
_M303_COMPENSACION_APLICADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-aplicada-periodo")
_M303_POSTERIOR_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_M303_RESULTADO_CASILLA: CasillaId = validated_casilla_id("iva.resultado")
_M303_GENERADA_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-generada-periodo")
_M303_DISPONIBLE_CASILLA: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_PRINTED_COMPENSATION_REFERENCE_CASILLA: CasillaId = validated_casilla_id("87")


def test_authoritative_declaration_selection_uses_latest_alta_row_for_duplicate_period() -> None:
    older = _declaration_row(
        expediente_id="202430313521426G",
        presented_at=datetime(2025, 3, 27, 17, 31, 56, tzinfo=UTC),
    )
    newer = _declaration_row(
        expediente_id="202430313521428B",
        presented_at=datetime(2025, 3, 28, 13, 4, 47, tzinfo=UTC),
    )

    selected = _select_authoritative_declaration(
        (older, newer),
        modelo="303",
        ejercicio=2024,
        period="3T",
        context="previous-filing requirement",
    )

    assert selected.expediente_id == "202430313521428B"


def test_declarations_page_shape_context_redacts_url_query_and_input_values() -> None:
    html = """
    <html>
      <head><title>Consulta de declaraciones presentadas</title></head>
      <body>
        <label>Modelo (*)</label>
        <label>Ejercicio (*)</label>
        <button class="z-button">Buscar</button>
        <input type="hidden" name="session" value="QUERY-CANARY" />
        <div class="z-listbox">
          <div class="z-listheader">Expediente</div>
          <div class="z-listitem"><div class="z-listcell">ROW-CANARY</div></div>
        </div>
      </body>
    </html>
    """

    context = _declarations_page_shape_context(
        html,
        landing_url=f"{_DECLARATIONS_LISTING_URL}?token=QUERY-CANARY",
        stage="post_buscar",
        modelo="303",
        ejercicio=2026,
    )

    assert context["landing_url"] == _DECLARATIONS_LISTING_URL
    assert context["has_modelo_label"] is True
    assert context["has_ejercicio_label"] is True
    assert context["has_buscar_button"] is True
    assert context["listbox_count"] == 1
    assert context["listitem_count"] == 1
    assert "QUERY-CANARY" not in str(context)
    assert "ROW-CANARY" not in str(context)
    assert context["raw_sha256"]


def test_declarations_page_shape_context_carries_page_text_so_the_leak_assertion_can_fire() -> None:
    """Positive control for the two ``not in str(context)`` assertions above.

    Both pass for two unrelated reasons they cannot tell apart: because
    something redacted the value, or because the shape reader never reads that
    part of the page at all. ``QUERY-CANARY`` sits in an ``input``'s ``value``
    and ``ROW-CANARY`` in a ``z-listcell``; the reader carries neither, so on
    their own those assertions are evidence about the reader's field selection,
    not about redaction, and they would read exactly the same if page text
    could never reach ``str(context)`` by any route.

    This is what makes them evidence. The canary is placed where the reader
    does carry text verbatim through ``bounded_text`` -- the ``title`` and the
    ``z-listheader`` -- and the assertion is inverted: it must be PRESENT. The
    listheader is the deliberate choice over any other carried field, because
    it is the nearest neighbour of the ``z-listcell`` the sibling watches: the
    two sit in the same widget, and the whole claim is that the boundary
    between them is real. A change that stopped list text reaching the context
    reds this test at the moment the sibling's pass would have gone vacuous,
    rather than silently.

    It pins a CHANNEL, not a permission. Column headings and the page title are
    deliberately recorded in a shape diagnostic; row cells and input values
    deliberately are not.
    """
    html = """
    <html>
      <head><title>TITLE-CANARY</title></head>
      <body>
        <div class="z-listbox">
          <div class="z-listheader">HEADER-CANARY</div>
          <div class="z-listitem"><div class="z-listcell">row text</div></div>
        </div>
      </body>
    </html>
    """

    context = _declarations_page_shape_context(
        html,
        landing_url=_DECLARATIONS_LISTING_URL,
        stage="post_buscar",
        modelo="303",
        ejercicio=2026,
    )

    assert "TITLE-CANARY" in str(context)
    assert "HEADER-CANARY" in str(context)
    assert context["list_headers"] == ("HEADER-CANARY",)


def test_declarations_page_shape_context_field_set_is_closed() -> None:
    """The guard for ``ROW-CANARY``, which no witness can supply.

    The witness above works for ``QUERY-CANARY`` because the reader carries
    title and header text and can therefore be shown to surface page text at
    all. It cannot be written for ``ROW-CANARY``: nothing here carries
    ``z-listcell`` text, so there is no channel to demonstrate, and
    ``assert "ROW-CANARY" not in str(context)`` is a permanent statement about
    which fields this reader selects rather than about redaction. Chasing it
    with another witness would only restate the confusion.

    The regression it is really standing guard over is someone adding a field
    that does carry row text -- a cell projection, a first-row sample, a
    matched-expediente echo -- and the instrument for that is a closed field
    set, not a canary. Adding a key reds this test and forces the author to say
    what the new field carries.

    The sibling wallet reader gets this for free: ``_WalletPageShape`` is a
    ``TypedDict``, so its shape cannot grow unnoticed. This one returns a bare
    ``dict[str, object]`` built from an inline literal, so it can. The reader
    with no structural guard is precisely the one whose leak assertion watches a
    channel that does not exist.
    """
    context = _declarations_page_shape_context(
        "<html><head><title>t</title></head><body></body></html>",
        landing_url=_DECLARATIONS_LISTING_URL,
        stage="post_buscar",
    )

    assert set(context) == {
        "stage",
        "modelo",
        "ejercicio",
        "landing_url",
        "title",
        "has_modelo_label",
        "has_ejercicio_label",
        "has_buscar_button",
        "has_no_results_text",
        "listbox_count",
        "listitem_count",
        "comboitem_count",
        "table_count",
        "form_count",
        "buttons",
        "list_headers",
        "raw_sha256",
    }


def test_modelo_303_filed_observation_derives_compensation_available() -> None:
    observation = _filed_observation(
        modelo="303",
        ejercicio=2024,
        period="4T",
        casilla_values={
            _M303_POSTERIOR_CASILLA: Decimal("0"),
            _M303_RESULTADO_CASILLA: Decimal("-258.02"),
        },
    )

    derived = _with_derived_303_compensation_available_observation(observation)
    registry_observation = registry_observation_from_filed_declaration(derived)
    registry_casillas = {
        casilla.id: casilla for casilla in _modelo_snapshot("303", filing_year=2024, period="4T").revision.casillas
    }

    assert {casilla.casilla_id: casilla.value for casilla in derived.casillas}[_M303_DISPONIBLE_CASILLA] == "258.02"
    assert registry_observation.casilla_values[_M303_DISPONIBLE_CASILLA] == Decimal("258.02")
    observation_by_id = {casilla.casilla_id: casilla for casilla in registry_observation.observations}
    available_observation = observation_by_id[_M303_DISPONIBLE_CASILLA]
    registry_casilla = registry_casillas[_M303_DISPONIBLE_CASILLA]
    assert available_observation.legal_refs == registry_casilla.legal_refs
    assert available_observation.source_refs == registry_casilla.source_refs
    derived_value = next(casilla for casilla in derived.casillas if casilla.casilla_id == _M303_DISPONIBLE_CASILLA)
    assert derived_value.source_artefact_kind == "derived_carry_policy"


def test_modelo_303_filed_observation_derives_compensation_available_from_registry_formula() -> None:
    observation = _filed_observation(
        modelo="303",
        ejercicio=2024,
        period="4T",
        casilla_values={
            _M303_POSTERIOR_CASILLA: Decimal("10.00"),
            _M303_RESULTADO_CASILLA: Decimal("-999.99"),
            _M303_GENERADA_CASILLA: Decimal("2.50"),
        },
    )

    derived = _with_derived_303_compensation_available_observation(observation)

    derived_value = next(casilla for casilla in derived.casillas if casilla.casilla_id == _M303_DISPONIBLE_CASILLA)
    assert derived_value.value == "12.50"
    assert derived_value.source_artefact_kind == "derived_registry_formula"
    assert derived_value.source_locator == (f"formula:{_M303_POSTERIOR_CASILLA}+{_M303_GENERADA_CASILLA}")


def test_registry_observation_from_filed_declaration_refuses_noncanonical_casilla_ids() -> None:
    observation = _filed_observation(
        modelo="303",
        ejercicio=2024,
        period="4T",
        casilla_values={_M303_PRINTED_COMPENSATION_REFERENCE_CASILLA: Decimal("0")},
    )

    with pytest.raises(SedeParseError, match=r"canonical casilla\.id"):
        registry_observation_from_filed_declaration(observation)


class TestParseListbox:
    """Verify :func:`_parse_listbox` extracts typed Declaracion rows from the post-Buscar HTML."""

    def test_modelo_100_2022_parses_one_row(self) -> None:
        """Assert the Modelo 100 / 2022 fixture parses to a single fully-populated row."""
        html = (_FIXTURE_ROOT / "declaraciones-modelo-100-2022.html").read_text(encoding="utf-8")
        rows = _parse_listbox(html, modelo="100", ejercicio=2022).rows
        assert len(rows) == 1
        row = rows[0]
        assert row.modelo == "100"
        assert row.ejercicio == 2022
        assert row.expediente_id == "202210013522222A"
        assert row.period == Period.from_year_and_code(2022, "0A")
        assert row.estado == "ALTA"
        assert row.presented_at == datetime(
            year=2024,
            month=2,
            day=1,
            hour=19,
            minute=15,
            second=34,
            tzinfo=UTC,
        )
        assert row.justificante_link_text == "Ver"
        assert row.archive_link_text == "Ver"
        assert row.declaration_copy_link_text is None
        assert row.mode == "read"

    def test_declaration_row_refuses_period_year_mismatch(self) -> None:
        with pytest.raises(ValueError, match=r"period\.filing_year must match ejercicio"):
            Declaracion(
                modelo="130",
                ejercicio=2026,
                period=Period.from_year_and_code(2025, "1T"),
                expediente_id="202610013522222A",
                estado="ALTA",
                presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                justificante_link_text="Ver",
            )

    def test_declaration_copy_column_is_classified_separately(self) -> None:
        html = """
            <div class="z-listbox">
              <tr class="z-listhead">
                <th class="z-listheader"><div>Desistir</div></th>
                <th class="z-listheader"><div>Tipo de solicitud</div></th>
                <th class="z-listheader"><div>Observaciones</div></th>
                <th class="z-listheader"><div>Expediente</div></th>
                <th class="z-listheader"><div>Periodo</div></th>
                <th class="z-listheader"><div>Estado</div></th>
                <th class="z-listheader"><div>Fecha y Hora de presentación</div></th>
                <th class="z-listheader"><div>Copia de la declaración</div></th>
                <th class="z-listheader"><div>Obtención de Justificante</div></th>
                <th class="z-listheader"><div>Descarga fichero presentado</div></th>
              </tr>
              <tr class="z-listitem">
                <td class="z-listcell"><div></div></td>
                <td class="z-listcell"><div></div></td>
                <td class="z-listcell"><div></div></td>
                <td class="z-listcell"><div>202610013522222A</div></td>
                <td class="z-listcell"><div>1T</div></td>
                <td class="z-listcell"><div>ALTA</div></td>
                <td class="z-listcell"><div>20/04/2026 10:00:00</div></td>
                <td class="z-listcell"><button>Ver</button></td>
                <td class="z-listcell"><button>Ver</button></td>
                <td class="z-listcell"><button>Ver</button></td>
              </tr>
            </div>
        """
        rows = _parse_listbox(html, modelo="130", ejercicio=2026).rows

        assert len(rows) == 1
        row = rows[0]
        assert row.declaration_copy_link_text == "Ver"
        assert row.declaration_copy_cell_index == 7
        assert row.justificante_cell_index == 8
        assert row.archive_cell_index == 9

    def test_header_without_submitted_file_does_not_infer_archive_column(self) -> None:
        html = """
            <div class="z-listbox">
              <tr class="z-listhead">
                <th class="z-listheader"><div>Desistir</div></th>
                <th class="z-listheader"><div>Tipo de solicitud</div></th>
                <th class="z-listheader"><div>Observaciones</div></th>
                <th class="z-listheader"><div>Expediente</div></th>
                <th class="z-listheader"><div>Periodo</div></th>
                <th class="z-listheader"><div>Estado</div></th>
                <th class="z-listheader"><div>Fecha y Hora de presentación</div></th>
                <th class="z-listheader"><div>Copia de la declaración</div></th>
                <th class="z-listheader"><div>Obtención de Justificante</div></th>
              </tr>
              <tr class="z-listitem">
                <td class="z-listcell"><div></div></td>
                <td class="z-listcell"><div></div></td>
                <td class="z-listcell"><div></div></td>
                <td class="z-listcell"><div>202610013522222A</div></td>
                <td class="z-listcell"><div>1T</div></td>
                <td class="z-listcell"><div>ALTA</div></td>
                <td class="z-listcell"><div>20/04/2026 10:00:00</div></td>
                <td class="z-listcell"><button>Ver</button></td>
                <td class="z-listcell"><button>Ver</button></td>
              </tr>
            </div>
        """
        row = _parse_listbox(html, modelo="130", ejercicio=2026).rows[0]

        assert row.declaration_copy_link_text == "Ver"
        assert row.archive_link_text is None
        assert row.archive_cell_index is None

    def test_no_results_returns_empty_tuple(self) -> None:
        """Assert the AEAT 'no results' listbox shape parses to the empty tuple."""
        # Synthesise the no-results listbox shape inline.
        html = """
            <div class="z-listbox">
              <table class="z-listbox-body">
                <tr class="z-listitem">
                  <td class="z-listcell">
                    <div class="z-listcell-content">
                      No se han encontrado resultados para la consulta realizada.
                    </div>
                  </td>
                </tr>
              </table>
            </div>
        """
        rows = _parse_listbox(html, modelo="130", ejercicio=2024).rows
        assert rows == ()

    def test_missing_listbox_raises_parse_error(self) -> None:
        """Assert HTML without a listbox raises :exc:`SedeParseError`."""
        with pytest.raises(SedeParseError, match=r"listbox|missing|parse"):
            _parse_listbox("<html><body>not a listbox</body></html>", modelo="100", ejercicio=2022)

    def test_missing_listbox_is_tagged_external_shape_changed(self) -> None:
        """A page with no ``.z-listbox`` container is a portal-drift outcome, not a bare parse error."""
        with pytest.raises(SedeParseError) as exc_info:
            _parse_listbox("<html><body>not a listbox</body></html>", modelo="100", ejercicio=2022)
        assert exc_info.value.failure_mode == "external_shape_changed"
        assert exc_info.value.context is not None
        assert exc_info.value.context["modelo"] == "100"
        assert exc_info.value.context["ejercicio"] == 2022

    def test_missing_justificante_column_is_tagged_external_shape_changed(self) -> None:
        """AEAT dropping/renaming the justificante column is a portal-drift outcome."""
        html = """
            <div class="z-listbox">
              <div class="z-listheader">Tipo</div>
              <div class="z-listheader">Estado</div>
            </div>
        """
        with pytest.raises(SedeParseError) as exc_info:
            _parse_listbox(html, modelo="303", ejercicio=2025)
        assert exc_info.value.failure_mode == "external_shape_changed"
        assert exc_info.value.context is not None
        assert exc_info.value.context["modelo"] == "303"
        assert exc_info.value.context["ejercicio"] == 2025


class TestParsePresentedAt:
    """Verify the Spanish ``dd/mm/YYYY hh:mm:ss`` timestamp shape parses to UTC."""

    def test_canonical_shape(self) -> None:
        """Assert a well-formed Spanish timestamp parses to a UTC :class:`datetime`."""
        result = _parse_presented_at("01/02/2024 19:15:34")
        assert result == datetime(
            year=2024,
            month=2,
            day=1,
            hour=19,
            minute=15,
            second=34,
            tzinfo=UTC,
        )

    def test_invalid_shape_raises_value_error(self) -> None:
        """Assert ISO-style timestamps are rejected."""
        with pytest.raises(ValueError, match=r"presented_at|format|does not match"):
            _parse_presented_at("2024-02-01 19:15:34")

    def test_partial_match_rejected(self) -> None:
        """Assert a date-only string (no time component) is rejected."""
        with pytest.raises(ValueError, match=r"presented_at|format|does not match"):
            _parse_presented_at("01/02/2024")


class TestSearchOptionSelection:
    """Verify AEAT combobox selection failures do not select another offered value."""

    @pytest.mark.asyncio
    async def test_unavailable_ejercicio_option_returns_false_without_selecting_another_year(
        self,
        tmp_path: Path,
    ) -> None:
        settings = Settings(cadrumo_token_dir=tmp_path)
        profile = Profile(name="test-declarations")
        async with (
            shared_playwright_runtime() as playwright,
            opened_browser_page(playwright, settings, profile) as (page, _context),
        ):
            await page.set_content(
                """
                <main>
                  <span>Ejercicio (*)</span>
                  <a class="z-combobox-button" href="#">abrir</a>
                  <div class="z-comboitem-text" onclick="window.selectedYear = this.textContent.trim()">2024</div>
                  <div class="z-comboitem-text" onclick="window.selectedYear = this.textContent.trim()">2025</div>
                </main>
                """,
            )

            selected = await _select_combobox_value(page, label_text="Ejercicio (*)", option_match="2026")
            selected_year = await page.evaluate("window.selectedYear ?? null")

        assert selected is False
        assert selected_year is None


class TestExtractCsvFromUrl:
    """Verify cotejo-URL CSV extraction validates the AEAT shape strictly."""

    _COTEJO = f"{_COTEJO_QUERY_URL}?CSV="

    def test_canonical_csv(self) -> None:
        """Assert a canonical 16-character CSV extracts cleanly."""
        assert _extract_csv_from_url(f"{self._COTEJO}S3RASL6U73H49Y83") == "S3RASL6U73H49Y83"

    def test_missing_csv_param_raises(self) -> None:
        """Assert a URL without a CSV query parameter raises :exc:`SedeParseError`."""
        with pytest.raises(SedeParseError, match="missing CSV"):
            _extract_csv_from_url(_DECLARATIONS_LISTING_URL)

    def test_lowercase_csv_rejected(self) -> None:
        """Assert a lowercase CSV value is rejected (AEAT only emits uppercase)."""
        # AEAT only emits uppercase CSV; lowercase indicates a
        # malformed response or attacker-crafted URL.
        with pytest.raises(SedeParseError, match="does not match AEAT shape"):
            _extract_csv_from_url(f"{self._COTEJO}lowercaseinvalid")

    def test_too_short_csv_rejected(self) -> None:
        """Assert a CSV shorter than the AEAT minimum is rejected."""
        with pytest.raises(SedeParseError, match="does not match AEAT shape"):
            _extract_csv_from_url(f"{self._COTEJO}AB12")

    def test_maximum_length_csv_extracts(self) -> None:
        """The audited 32-character maximum remains a valid AEAT CSV."""
        assert _extract_csv_from_url(f"{self._COTEJO}{'A' * 32}") == "A" * 32

    def test_csv_longer_than_the_maximum_is_rejected(self) -> None:
        """Assert a 33-character CSV is rejected rather than truncated."""
        with pytest.raises(SedeParseError, match="does not match AEAT shape"):
            _extract_csv_from_url(f"{self._COTEJO}{'A' * 33}")

    def test_csv_with_special_chars_rejected(self) -> None:
        """Assert a CSV containing path-traversal characters is rejected."""
        with pytest.raises(SedeParseError, match="does not match AEAT shape"):
            _extract_csv_from_url(f"{self._COTEJO}AAAA1234../../etc")

    def test_multiple_csv_values_rejected(self) -> None:
        """Assert multiple CSV query parameter values are rejected."""
        # AEAT never repeats the CSV parameter; multiple values
        # indicate a malformed response or an attacker-crafted URL.
        with pytest.raises(SedeParseError, match="2 CSV values"):
            _extract_csv_from_url(f"{self._COTEJO}AAAA1234&CSV=BBBB5678")


class TestSubmittedFileContext:
    """Verify submitted files are bound to the declaration row context."""

    def test_period_mismatch_raises_parse_error(self) -> None:
        snapshot = _modelo_130_snapshot()
        resolved = resolve_export_layout(snapshot)
        parsed = parse_export_payload(resolved.layout, _submitted_file_payload())
        declaration = Declaracion(
            modelo="130",
            ejercicio=2026,
            period=Period.from_year_and_code(2026, "2T"),
            expediente_id="202610013522222A",
            estado="ALTA",
            presented_at=datetime(2026, 7, 1, 10, 0, 0, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )

        with pytest.raises(SedeParseError, match="does not match declaration"):
            _verify_submitted_file_context(resolved.fields_by_id, parsed.fields, declaration=declaration)
