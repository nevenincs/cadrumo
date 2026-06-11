"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ._declarations_support import (
    _COTEJO_QUERY_URL,
    _DECLARATIONS_LISTING_URL,
    _FIXTURE_ROOT,
    _MODELO_303_2022_RECORD_DESIGN,
    UTC,
    AnyHttpUrl,
    Decimal,
    Declaracion,
    FiledDeclaracionArtefact,
    Path,
    Profile,
    SedeParseError,
    Settings,
    _declaration_row,
    _declarations_page_shape_context,
    _extract_csv_from_url,
    _filed_observation,
    _modelo_130_snapshot,
    _modelo_303_design_position,
    _modelo_303_page_03_payload,
    _modelo_snapshot,
    _observed_casillas_from_submitted_file,
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


def test_modelo_303_submitted_file_fallback_extracts_result_casillas() -> None:
    snapshot = _modelo_snapshot("303", filing_year=2025, period="1T")
    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
        content_type="application/octet-stream",
        byte_count=600,
        sha256="0" * 64,
        captured_at=datetime(2025, 3, 28, 13, 7, 33, tzinfo=UTC),
    )

    observed = _observed_casillas_from_submitted_file(
        snapshot=snapshot,
        declaration=_declaration_row(
            expediente_id="202430313521429A",
            presented_at=datetime(2025, 3, 28, 13, 7, 33, tzinfo=UTC),
        ),
        body=_modelo_303_page_03_payload(
            casilla_110="00000000000000000",
            casilla_78="00000000000000000",
            casilla_87="00000000000000000",
            casilla_69="N0000000000025802",
            casilla_71="N0000000000025802",
        ),
        artefact=artefact,
    )

    assert {casilla.casilla_id: casilla.value for casilla in observed} == {
        "110": "0",
        "78": "0",
        "87": "0",
        "69": "-258.02",
        "71": "-258.02",
    }


def test_modelo_303_2022_submitted_file_fallback_uses_2022_result_position() -> None:
    snapshot = _modelo_snapshot("303", filing_year=2022, period="1T")
    casilla_71_position = _modelo_303_design_position(_MODELO_303_2022_RECORD_DESIGN, casilla_id="71")
    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
        content_type="application/octet-stream",
        byte_count=1017,
        sha256="0" * 64,
        captured_at=datetime(2022, 4, 20, 13, 7, 33, tzinfo=UTC),
    )

    observed = _observed_casillas_from_submitted_file(
        snapshot=snapshot,
        declaration=_declaration_row(
            ejercicio=2022,
            period="1T",
            expediente_id="202230313521429A",
            presented_at=datetime(2022, 4, 20, 13, 7, 33, tzinfo=UTC),
        ),
        body=_modelo_303_page_03_payload(
            casilla_110="00000000000000000",
            casilla_78="00000000000000000",
            casilla_87="00000000000000000",
            casilla_69="N0000000000025802",
            casilla_71="N0000000000025802",
            casilla_71_position=casilla_71_position,
            filler_at_374="X",
        ),
        artefact=artefact,
    )

    assert {casilla.casilla_id: casilla.value for casilla in observed}["71"] == "-258.02"
    assert next(casilla for casilla in observed if casilla.casilla_id == "71").source_locator == (
        f"record:T30303:pos:{casilla_71_position}:width:17"
    )


def test_modelo_303_submitted_file_fallback_refuses_invalid_page_record_footer() -> None:
    snapshot = _modelo_snapshot("303", filing_year=2025, period="1T")
    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl(_DECLARATIONS_LISTING_URL),
        content_type="application/octet-stream",
        byte_count=1017,
        sha256="0" * 64,
        captured_at=datetime(2025, 3, 28, 13, 7, 33, tzinfo=UTC),
    )
    body = bytearray(
        _modelo_303_page_03_payload(
            casilla_110="00000000000000000",
            casilla_78="00000000000000000",
            casilla_87="00000000000000000",
            casilla_69="N0000000000025802",
            casilla_71="N0000000000025802",
        ),
    )
    body[1005:1017] = b"</T30303001>"

    with pytest.raises(SedeParseError, match="invalid page-03 footer"):
        _observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=_declaration_row(
                expediente_id="202430313521429A",
                presented_at=datetime(2025, 3, 28, 13, 7, 33, tzinfo=UTC),
            ),
            body=bytes(body),
            artefact=artefact,
        )


def test_modelo_303_filed_observation_derives_compensation_available() -> None:
    observation = _filed_observation(
        modelo="303",
        ejercicio=2024,
        period="4T",
        casilla_values={"87": Decimal("0"), "69": Decimal("-258.02")},
    )

    derived = _with_derived_303_compensation_available_observation(observation)
    registry_observation = registry_observation_from_filed_declaration(derived)

    assert {casilla.casilla_id: casilla.value for casilla in derived.casillas}[
        "iva.compensacion-disponible-fin-periodo"
    ] == "258.02"
    assert registry_observation.casilla_values["iva.compensacion-disponible-fin-periodo"] == Decimal("258.02")


class TestParseListbox:
    """Verify :func:`_parse_listbox` extracts typed Declaracion rows from the post-Buscar HTML."""

    def test_modelo_100_2022_parses_one_row(self) -> None:
        """Assert the Modelo 100 / 2022 fixture parses to a single fully-populated row."""
        html = (_FIXTURE_ROOT / "declaraciones-modelo-100-2022.html").read_text(encoding="utf-8")
        rows = _parse_listbox(html, modelo="100", ejercicio=2022)
        assert len(rows) == 1
        row = rows[0]
        assert row.modelo == "100"
        assert row.ejercicio == 2022
        assert row.expediente_id == "202210013522222A"
        assert row.period == "0A"
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
        rows = _parse_listbox(html, modelo="130", ejercicio=2026)

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
        row = _parse_listbox(html, modelo="130", ejercicio=2026)[0]

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
        rows = _parse_listbox(html, modelo="130", ejercicio=2024)
        assert rows == ()

    def test_missing_listbox_raises_parse_error(self) -> None:
        """Assert HTML without a listbox raises :exc:`SedeParseError`."""
        with pytest.raises(SedeParseError, match=r"listbox|missing|parse"):
            _parse_listbox("<html><body>not a listbox</body></html>", modelo="100", ejercicio=2022)


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
        settings = Settings(aeat_token_dir=tmp_path)
        profile = Profile(name="test-declarations", storage_state_path=tmp_path / "state.json")
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

    def test_too_long_csv_rejected(self) -> None:
        """Assert a CSV longer than the AEAT maximum is rejected."""
        with pytest.raises(SedeParseError, match="does not match AEAT shape"):
            _extract_csv_from_url(f"{self._COTEJO}{'A' * 32}")

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
            period="2T",
            expediente_id="202610013522222A",
            estado="ALTA",
            presented_at=datetime(2026, 7, 1, 10, 0, 0, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )

        with pytest.raises(SedeParseError, match="does not match declaration"):
            _verify_submitted_file_context(resolved.fields_by_id, parsed.fields, declaration=declaration)
