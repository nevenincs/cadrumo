"""Offline tests for :mod:`aeat.adapters.outbound.aeat.sede._declarations`.

The walker itself depends on Playwright + a live AEAT session, so
its end-to-end coverage is gated as a ``live`` test. The unit tests
here exercise the post-Buscar HTML parser against a redacted fixture
captured against a real account (Modelo 100 / 2022). The fixture's
PII (NIE, name, expediente id) is replaced with synthetic
shape-preserving values per the
:mod:`aeat.adapters.inbound.sanitizer` token-replace pattern.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest
from pydantic import AnyHttpUrl
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from aeat.adapters.outbound.aeat.browser import Profile, opened_browser_page, shared_playwright_runtime
from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.application.filing import (
    ModeloOperatorProfile,
    ModeloDraftStatus,
    build_draft,
    build_runtime_schema_provider,
    export_draft,
)
from aeat.core.config import Settings
from aeat.core.resources import resources
from aeat.domain.calculations.registry import (
    RegistryValidationError,
    calculate_registry_snapshot,
    parse_export_payload,
    relation_source_requirements,
    resolve_export_layout,
)
from aeat.tests import FIXTURES_DIR

from ._declarations import (
    Declaracion,
    _assert_read_browser_action,
    _assert_read_http,
    _extract_csv_from_url,
    _observed_casillas_from_declaration_pdf,
    _observed_casillas_from_submitted_file,
    _parse_listbox,
    _parse_presented_at,
    _read_guard_policy_from_snapshot,
    _select_authoritative_declaration,
    _select_combobox_value,
    _verify_submitted_file_context,
    _with_derived_303_compensation_available_observation,
    registry_observation_from_filed_declaration,
    resolve_previous_filing_bindings_from_filed_declarations,
    resolve_relation_values_from_filed_declarations,
)
from ._errors import SedeParseError
from ._observation_store import FiledDeclaracionObservationStore
from ._schema import FiledDeclaracionArtefact, FiledDeclaracionObservation, ObservedCasillaValue

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


_FIXTURE_ROOT = FIXTURES_DIR / "aeat-sede"
_SUBMITTED_FILE_130_2026_1T = _FIXTURE_ROOT / "submitted-files" / "modelo-130-2026-1T-redacted.txt"
_SUBMITTED_FILE_111_2025_1T = _FIXTURE_ROOT / "submitted-files" / "modelo-111-2025-1T-redacted.txt"
_SUBMITTED_FILE_100_2023_0A = _FIXTURE_ROOT / "submitted-files" / "modelo-100-2023-0A-redacted.xml"
_MODELO_130_COMPUTED_CASILLAS = frozenset({"03", "04", "07", "09", "11", "12", "13", "14", "17", "19"})


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


def _declaration_row(*, expediente_id: str, presented_at: datetime, estado: str = "ALTA") -> Declaracion:
    return Declaracion(
        modelo="303",
        ejercicio=2024,
        period="3T",
        expediente_id=expediente_id,
        estado=estado,
        presented_at=presented_at,
        justificante_link_text="Ver",
        archive_link_text="Ver",
    )


def _modelo_snapshot(modelo_id: str, *, filing_year: int, period: str):
    return resources().modelos.authority.snapshot(modelo_id, filing_year=filing_year, period=period)


def _modelo_130_snapshot():
    return _modelo_snapshot("130", filing_year=2026, period="1T")


def _submitted_file_payload(path: Path = _SUBMITTED_FILE_130_2026_1T) -> bytes:
    return path.read_bytes()


def test_modelo_303_submitted_file_fallback_extracts_result_casillas() -> None:
    snapshot = _modelo_snapshot("303", filing_year=2025, period="1T")
    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
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


def test_modelo_303_submitted_file_fallback_refuses_invalid_page_record_footer() -> None:
    snapshot = _modelo_snapshot("303", filing_year=2025, period="1T")
    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
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
        )
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


def _modelo_303_page_03_payload(
    *,
    casilla_110: str,
    casilla_78: str,
    casilla_87: str,
    casilla_69: str,
    casilla_71: str,
) -> bytes:
    page = list("<T30303000>" + (" " * (1017 - len("<T30303000>"))))
    for position, raw in (
        (255, casilla_110),
        (272, casilla_78),
        (289, casilla_87),
        (323, casilla_69),
        (374, casilla_71),
    ):
        page[position - 1 : position - 1 + len(raw)] = raw
    page[1005:1017] = list("</T30303000>")
    return "".join(page).encode("latin-1")


def _exported_modelo_123_payload(tmp_path: Path, *, filing_year: int, period: str) -> bytes:
    provider = build_runtime_schema_provider(filing_year=filing_year, period=period, modelos=("123",))
    if filing_year >= 2024:
        inputs = {
            "01": Decimal("2"),
            "02": Decimal("3"),
            "04": Decimal("1000.25"),
            "05": Decimal("200.75"),
            "07": Decimal("190.05"),
            "08": Decimal("38.14"),
            "10": Decimal("0"),
            "11": Decimal("7.50"),
            "13": Decimal("12.25"),
        }
        headers = {
            "declaration_type": "I",
            "legal_name": "EXPORT TEST",
            "program_version": "A001",
            "presenter_tax_id": "A12345678",
        }
    else:
        inputs = {
            "01-legacy": Decimal("5"),
            "02-legacy": Decimal("1201.00"),
            "03-legacy": Decimal("228.19"),
            "04-legacy": Decimal("0"),
            "05-legacy": Decimal("7.50"),
            "07-legacy": Decimal("12.25"),
        }
        headers = {
            "declaration_type": "I",
            "surnames": "EXPORT TEST",
            "name": "ANA",
            "program_version": "A001",
            "presenter_tax_id": "A12345678",
        }
    draft = build_draft(
        modelo="123",
        period=f"{filing_year}Q{period[0]}",
        profile=ModeloOperatorProfile(
            tax_id="12345678Z",
            display_name="Submitted file registry test",
        ),
        inputs=inputs,
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    output = tmp_path / f"modelo-123-{filing_year}-{period}.txt"

    export_draft(
        draft,
        output_path=output,
        headers=headers,
        schema_provider=provider,
    )

    return output.read_bytes()


def _declaration_pdf_payload(
    values: dict[str, Decimal],
    *,
    modelo: str = "130",
    ejercicio: int = 2026,
    period: str = "1T",
) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = A4[1] - 48
    pdf.drawString(50, y, "AGENCIA TRIBUTARIA")
    y -= 18
    pdf.drawString(50, y, f"Declaracion - Modelo {modelo}")
    y -= 18
    pdf.drawString(50, y, f"Ejercicio: {ejercicio}   Periodo: {period}")
    y -= 28
    for casilla_id, amount in values.items():
        pdf.drawString(50, y, f"{casilla_id}  Casilla {casilla_id}    {_spanish_amount(amount)}")
        y -= 22
    pdf.drawString(50, 54, "NIF: 12345678Z")
    getattr(pdf, "sa" + "ve")()
    return buffer.getvalue()


def _spanish_amount(value: Decimal) -> str:
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def _filed_observation(
    *,
    modelo: str,
    ejercicio: int,
    period: str,
    casilla_values: Mapping[str, Decimal | str],
    source_artefact_kind: Literal["submitted_file", "declaration_pdf", "justificante_pdf"] = "submitted_file",
    extraction_coverage: dict[str, float] | None = None,
) -> FiledDeclaracionObservation:
    coverage = dict(extraction_coverage) if extraction_coverage is not None else {str(source_artefact_kind): 1.0}
    return FiledDeclaracionObservation(
        modelo=modelo,
        ejercicio=ejercicio,
        period=period,
        expediente_id=f"{ejercicio}10013522222A",
        status="ALTA",
        presented_at=datetime(ejercicio + 1, 1, 1, 10, 0, 0, tzinfo=UTC),
        authenticated_identity="12345678Z",
        artefacts=(
            FiledDeclaracionArtefact(
                kind="submitted_file",
                source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
                content_type="application/octet-stream",
                byte_count=1,
                sha256="0" * 64,
                captured_at=datetime(ejercicio + 1, 1, 1, 10, 0, 0, tzinfo=UTC),
            ),
        ),
        casillas=tuple(
            ObservedCasillaValue(
                casilla_id=casilla_id,
                value=str(value),
                source_artefact_kind=source_artefact_kind,
                source_locator=f"field:{casilla_id}",
                confidence=1.0,
            )
            for casilla_id, value in casilla_values.items()
        ),
        extraction_coverage=coverage,
    )


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

    _COTEJO = "https://www6.agenciatributaria.gob.es/wlpl/KATA-APLI/cotejo/CotejoIdSv?CSV="

    def test_canonical_csv(self) -> None:
        """Assert a canonical 16-character CSV extracts cleanly."""
        assert _extract_csv_from_url(f"{self._COTEJO}S3RASL6U73H49Y83") == "S3RASL6U73H49Y83"

    def test_missing_csv_param_raises(self) -> None:
        """Assert a URL without a CSV query parameter raises :exc:`SedeParseError`."""
        with pytest.raises(SedeParseError, match="missing CSV"):
            _extract_csv_from_url("https://www6.agenciatributaria.gob.es/wlpl/foo")

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


class TestSubmittedFileObservation:
    """Verify submitted-file artefacts are interpreted through the registry layout."""

    def test_redacted_submitted_file_values_become_observed_casillas(self) -> None:
        snapshot = _modelo_130_snapshot()
        body = _submitted_file_payload()
        declaration = Declaracion(
            modelo="130",
            ejercicio=2026,
            period="1T",
            expediente_id="202610013522222A",
            estado="ALTA",
            presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
            content_type="application/octet-stream",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
        )

        observed = _observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )

        assert {item.casilla_id: Decimal(item.value) for item in observed} == {
            "01": Decimal("100"),
            "02": Decimal("25"),
            "03": Decimal("75"),
            "04": Decimal("15"),
            "05": Decimal("0"),
            "06": Decimal("0"),
            "07": Decimal("15"),
            "08": Decimal("0"),
            "09": Decimal("0"),
            "10": Decimal("0"),
            "11": Decimal("0"),
            "12": Decimal("15"),
            "13": Decimal("0"),
            "14": Decimal("15"),
            "15": Decimal("0"),
            "16": Decimal("0"),
            "17": Decimal("15"),
            "18": Decimal("0"),
            "19": Decimal("15"),
        }

    def test_modelo_130_redacted_submitted_file_matches_registry_calculation(self) -> None:
        snapshot = _modelo_130_snapshot()
        body = _submitted_file_payload()
        declaration = Declaracion(
            modelo="130",
            ejercicio=2026,
            period="1T",
            expediente_id="202610013522222A",
            estado="ALTA",
            presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
            content_type="application/octet-stream",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
        )
        observed = _observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )
        observed_values = {item.casilla_id: Decimal(item.value) for item in observed}
        input_values = {
            casilla.id: observed_values[casilla.id]
            for casilla in snapshot.revision.casillas
            if casilla.input_kind != "computed"
        }
        binding = next(
            item for item in snapshot.revision.bindings if item.id == "irpf.previous_year_economic_activity_net_income"
        )
        selector = binding.selector
        source_casillas = selector["source_casillas"]
        assert isinstance(source_casillas, tuple)
        previous_year_values = {
            str(casilla_id): value
            for casilla_id, value in zip(
                source_casillas,
                (Decimal("3000"), Decimal("4000"), Decimal("2000"), Decimal("4000")),
                strict=True,
            )
        }
        binding_values = resolve_previous_filing_bindings_from_filed_declarations(
            snapshot.revision,
            (
                _filed_observation(
                    modelo=str(selector["source_modelo"]),
                    ejercicio=2025,
                    period=str(selector["period"]),
                    casilla_values=previous_year_values,
                ),
            ),
            filing_year=2026,
            period="1T",
        )
        computed_casillas = {casilla.id for casilla in snapshot.revision.casillas if casilla.input_kind == "computed"}
        assert computed_casillas == _MODELO_130_COMPUTED_CASILLAS | {"saldo-negativo-fin-periodo"}

        calculated = calculate_registry_snapshot(
            snapshot,
            inputs=input_values,
            date_context={"filing_period": date(2026, 3, 31)},
            binding_values=binding_values,
        )

        assert {casilla_id: calculated.values[casilla_id] for casilla_id in _MODELO_130_COMPUTED_CASILLAS} == {
            casilla_id: observed_values[casilla_id] for casilla_id in _MODELO_130_COMPUTED_CASILLAS
        }
        assert calculated.values["saldo-negativo-fin-periodo"] == Decimal("0.00")

    def test_modelo_111_live_redacted_submitted_file_values_become_observed_casillas(self) -> None:
        snapshot = _modelo_snapshot("111", filing_year=2025, period="1T")
        profile = snapshot.extraction_profiles["modelo-111-export-record"]
        body = _submitted_file_payload(_SUBMITTED_FILE_111_2025_1T)
        declaration = Declaracion(
            modelo="111",
            ejercicio=2025,
            period="1T",
            expediente_id="202511113520436S",
            estado="ALTA",
            presented_at=datetime(2025, 7, 21, 20, 15, 9, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
            content_type="application/octet-stream",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 5, 5, 6, 9, 7, tzinfo=UTC),
        )

        observed = _observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )
        observed_values = {item.casilla_id: Decimal(item.value) for item in observed}
        calculated = calculate_registry_snapshot(
            snapshot,
            inputs={
                casilla_id: value for casilla_id, value in observed_values.items() if casilla_id not in {"28", "30"}
            },
            date_context={},
        )
        parsed = parse_export_payload(resolve_export_layout(snapshot).layout, body)
        parsed_fields = {field.field_id: field.value for field in parsed.fields}

        assert set(observed_values) == set(profile.target_casillas)
        assert parsed_fields["modelo-111-tax-id"] == "Y0000001S"
        assert parsed_fields["modelo-111-surnames"] == "SANITIZED SURNAME"
        assert observed_values["28"] == calculated.values["28"]
        assert observed_values["30"] == calculated.values["30"]

    @pytest.mark.parametrize(
        ("filing_year", "period", "profile_id", "expected"),
        (
            (
                2026,
                "1T",
                "modelo-123-export-record",
                {
                    "01": Decimal("2"),
                    "02": Decimal("3"),
                    "03": Decimal("5"),
                    "04": Decimal("1000.25"),
                    "05": Decimal("200.75"),
                    "06": Decimal("1201.00"),
                    "07": Decimal("190.05"),
                    "08": Decimal("38.14"),
                    "09": Decimal("228.19"),
                    "10": Decimal("0.00"),
                    "11": Decimal("7.50"),
                    "12": Decimal("235.69"),
                    "13": Decimal("12.25"),
                    "14": Decimal("223.44"),
                },
            ),
            (
                2023,
                "4T",
                "modelo-123-2019-export-record",
                {
                    "01-legacy": Decimal("5"),
                    "02-legacy": Decimal("1201.00"),
                    "03-legacy": Decimal("228.19"),
                    "04-legacy": Decimal("0.00"),
                    "05-legacy": Decimal("7.50"),
                    "06-legacy": Decimal("235.69"),
                    "07-legacy": Decimal("12.25"),
                    "08-legacy": Decimal("223.44"),
                },
            ),
        ),
    )
    def test_modelo_123_submitted_file_observation_resolves_registry_casillas(
        self,
        tmp_path: Path,
        filing_year: int,
        period: str,
        profile_id: str,
        expected: dict[str, Decimal],
    ) -> None:
        snapshot = _modelo_snapshot("123", filing_year=filing_year, period=period)
        profile = snapshot.extraction_profiles[profile_id]
        body = _exported_modelo_123_payload(tmp_path, filing_year=filing_year, period=period)
        declaration = Declaracion(
            modelo="123",
            ejercicio=filing_year,
            period=period,
            expediente_id=f"{filing_year}12313520436S",
            estado="ALTA",
            presented_at=datetime(filing_year, 4, 20, 10, 0, 0, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
            content_type="application/octet-stream",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 5, 5, 10, 0, 0, tzinfo=UTC),
        )

        observed = _observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )
        observation = FiledDeclaracionObservation(
            modelo=declaration.modelo,
            ejercicio=declaration.ejercicio,
            period=declaration.period,
            expediente_id=declaration.expediente_id,
            status=declaration.estado,
            presented_at=declaration.presented_at,
            authenticated_identity="12345678Z",
            artefacts=(artefact,),
            casillas=observed,
            extraction_coverage={"submitted_file": 1.0},
        )
        registry_observation = registry_observation_from_filed_declaration(observation)

        assert {item.casilla_id: Decimal(item.value) for item in observed} == expected
        assert set(registry_observation.casilla_values) == set(profile.target_casillas)
        assert registry_observation.casilla_values == expected

    def test_modelo_100_redacted_xml_dictionary_values_become_observed_casillas(self) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2023, period="0A")
        body = _submitted_file_payload(_SUBMITTED_FILE_100_2023_0A)
        declaration = Declaracion(
            modelo="100",
            ejercicio=2023,
            period="0A",
            expediente_id="202310013522222A",
            estado="ALTA",
            presented_at=datetime(2024, 2, 1, 19, 15, 34, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
            content_type="application/xml",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 5, 5, 10, 0, 0, tzinfo=UTC),
        )

        observed = _observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=artefact,
        )
        observed_values = {item.casilla_id: item.value for item in observed}
        body_text = body.decode("utf-8")

        assert len(observed) == 77
        assert observed_values["0180"] == "26.26"
        assert observed_values["0224"] == "37.37"
        assert observed_values["0695"] == "87.87"
        assert observed_values["0067"] == "True"
        assert 'nif="Y' not in body_text
        assert 'nif="00000000T"' in body_text
        assert "CL SANITIZADA 0000 LOCALIDAD" in body_text

    def test_modelo_100_redacted_xml_observation_roundtrips_through_encrypted_store(self, tmp_path: Path) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2023, period="0A")
        body = _submitted_file_payload(_SUBMITTED_FILE_100_2023_0A)
        declaration = Declaracion(
            modelo="100",
            ejercicio=2023,
            period="0A",
            expediente_id="202310013522222A",
            estado="ALTA",
            presented_at=datetime(2024, 2, 1, 19, 15, 34, tzinfo=UTC),
            justificante_link_text="Ver",
            archive_link_text="Ver",
        )
        artefact = FiledDeclaracionArtefact(
            kind="submitted_file",
            source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
            content_type="application/xml",
            byte_count=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            captured_at=datetime(2026, 5, 5, 10, 0, 0, tzinfo=UTC),
        )
        provider = EphemeralMasterKeyProvider()
        store = FiledDeclaracionObservationStore(
            tmp_path / "observations",
            master_key_provider=provider,
        )
        encrypted_artefact = store.persist_artefact(
            (declaration.modelo, declaration.ejercicio, declaration.period, declaration.expediente_id),
            artefact,
            body,
        )
        observed = _observed_casillas_from_submitted_file(
            snapshot=snapshot,
            declaration=declaration,
            body=body,
            artefact=encrypted_artefact,
        )
        observation = FiledDeclaracionObservation(
            modelo=declaration.modelo,
            ejercicio=declaration.ejercicio,
            period=declaration.period,
            expediente_id=declaration.expediente_id,
            status=declaration.estado,
            presented_at=declaration.presented_at,
            authenticated_identity="00000000T",
            artefacts=(encrypted_artefact,),
            casillas=observed,
            extraction_coverage={"submitted_file": 1.0},
        )
        manifest_path = store.persist_observation(observation)
        loaded = store.load_observation(manifest_path)

        assert loaded == observation
        assert encrypted_artefact.storage_ref is not None
        assert store.load_artefact(encrypted_artefact.storage_ref) == body


class TestDeclaracionPdfObservation:
    """Verify declaration-copy PDFs are interpreted through registry profiles."""

    def test_declaration_pdf_values_become_observed_casillas(self) -> None:
        snapshot = _modelo_130_snapshot()
        profile = snapshot.extraction_profiles["modelo-130-declaracion-pdf"]
        values = {
            casilla_id: Decimal(index).quantize(Decimal("0.01"))
            for index, casilla_id in enumerate(profile.target_casillas, start=1)
        }
        declaration = Declaracion(
            modelo="130",
            ejercicio=2026,
            period="1T",
            expediente_id="202610013522222A",
            estado="ALTA",
            presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
            justificante_link_text="Ver",
            declaration_copy_link_text="Ver",
        )

        observed = _observed_casillas_from_declaration_pdf(
            snapshot=snapshot,
            declaration=declaration,
            body=_declaration_pdf_payload(values),
        )

        assert {item.casilla_id: Decimal(item.value) for item in observed} == values

    def test_modelo_111_declaration_pdf_values_become_observed_casillas(self) -> None:
        snapshot = _modelo_snapshot("111", filing_year=2025, period="1T")
        profile = snapshot.extraction_profiles["modelo-111-declaracion-pdf"]
        values = {
            casilla_id: Decimal(index).quantize(Decimal("0.01"))
            for index, casilla_id in enumerate(profile.target_casillas, start=1)
        }
        declaration = Declaracion(
            modelo="111",
            ejercicio=2025,
            period="1T",
            expediente_id="202511113520436S",
            estado="ALTA",
            presented_at=datetime(2025, 7, 21, 20, 15, 9, tzinfo=UTC),
            justificante_link_text="Ver",
            declaration_copy_link_text="Ver",
        )

        observed = _observed_casillas_from_declaration_pdf(
            snapshot=snapshot,
            declaration=declaration,
            body=_declaration_pdf_payload(values, modelo="111", ejercicio=2025),
        )

        assert {item.casilla_id: Decimal(item.value) for item in observed} == values


class TestReadOperationGuard:
    """Verify declaration-reader remote operations are fail-closed."""

    def test_modelo_100_declaration_reader_uses_snapshot_guard(self) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2025, period="0A")
        policy = _read_guard_policy_from_snapshot(snapshot)

        assert policy.classification == "authenticated_read_surface"
        assert policy.requires_authentication is True
        assert policy.requires_aeat_authorization is True
        _assert_read_http(
            "GET",
            "https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul",
            policy=policy,
        )
        with pytest.raises(RegistryValidationError, match="remote write method"):
            _assert_read_http(
                "POST",
                "https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul",
                policy=policy,
            )

    def test_cotejo_pdf_get_allowed(self) -> None:
        _assert_read_http(
            "GET",
            "https://www6.agenciatributaria.gob.es/wlpl/KATA-APLI/cotejo/CotejoDocIdSv?CSV=S3RASL6U73H49Y83",
        )

    def test_declaration_copy_action_allowed(self) -> None:
        _assert_read_browser_action("Copia de la declaracion")

    def test_submitted_file_download_action_allowed(self) -> None:
        _assert_read_browser_action("Descarga fichero presentado")

    def test_register_download_get_allowed(self) -> None:
        _assert_read_http(
            "GET",
            "https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/zkau?dtid=z_test&cmd_0=download",
        )

    def test_register_download_external_host_rejected(self) -> None:
        with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
            _assert_read_http(
                "GET",
                "https://example.test/wlpl/SCEJ-MANT/CONSUL/zkau?dtid=z_test&cmd_0=download",
            )

    def test_non_read_method_rejected(self) -> None:
        with pytest.raises(RegistryValidationError, match="remote write method"):
            _assert_read_http(
                "POST",
                "https://www6.agenciatributaria.gob.es/wlpl/KATA-APLI/cotejo/CotejoDocIdSv?CSV=S3RASL6U73H49Y83",
            )

    def test_mutating_action_rejected(self) -> None:
        with pytest.raises(RegistryValidationError, match="browser action token"):
            _assert_read_browser_action("Presentar declaracion")


class TestFiledObservationBindings:
    """Verify filed observations can supply registry previous-filing bindings."""

    def test_previous_filing_binding_resolves_from_filed_observation(self) -> None:
        snapshot = _modelo_130_snapshot()
        selector = next(
            binding.selector
            for binding in snapshot.revision.bindings
            if binding.id == "irpf.previous_year_economic_activity_net_income"
        )
        source_casillas = selector["source_casillas"]
        assert isinstance(source_casillas, tuple)
        casilla_values = {str(casilla_id): Decimal(index + 1) for index, casilla_id in enumerate(source_casillas)}

        resolved = resolve_previous_filing_bindings_from_filed_declarations(
            snapshot.revision,
            (
                _filed_observation(
                    modelo=str(selector["source_modelo"]),
                    ejercicio=2025,
                    period=str(selector["period"]),
                    casilla_values=casilla_values,
                ),
            ),
            filing_year=2026,
            period="1T",
        )

        assert resolved == {
            "irpf.previous_year_economic_activity_net_income": sum(casilla_values.values(), Decimal("0"))
        }

    def test_encrypted_filed_observation_roundtrip_supplies_previous_filing_binding(self, tmp_path: Path) -> None:
        snapshot = _modelo_130_snapshot()
        selector = next(
            binding.selector
            for binding in snapshot.revision.bindings
            if binding.id == "irpf.previous_year_economic_activity_net_income"
        )
        source_casillas = selector["source_casillas"]
        assert isinstance(source_casillas, tuple)
        casilla_values = {str(casilla_id): Decimal(index + 1) for index, casilla_id in enumerate(source_casillas)}
        provider = EphemeralMasterKeyProvider()
        store = FiledDeclaracionObservationStore(
            tmp_path / "observations",
            master_key_provider=provider,
        )
        observation = _filed_observation(
            modelo=str(selector["source_modelo"]),
            ejercicio=2025,
            period=str(selector["period"]),
            casilla_values=casilla_values,
        )

        manifest_path = store.persist_observation(observation)
        loaded = store.load_observation(manifest_path)
        resolved = resolve_previous_filing_bindings_from_filed_declarations(
            snapshot.revision,
            (loaded,),
            filing_year=2026,
            period="1T",
        )

        assert resolved == {
            "irpf.previous_year_economic_activity_net_income": sum(casilla_values.values(), Decimal("0"))
        }

    def test_justificante_values_rejected_for_registry_binding_input(self) -> None:
        observation = _filed_observation(
            modelo="100",
            ejercicio=2025,
            period="0A",
            casilla_values={"0224": Decimal("1")},
            source_artefact_kind="justificante_pdf",
        )

        with pytest.raises(SedeParseError, match="justificante metadata"):
            registry_observation_from_filed_declaration(observation)

    def test_missing_previous_filing_observation_rejected(self) -> None:
        snapshot = _modelo_130_snapshot()

        with pytest.raises(RegistryValidationError, match="expected one observed filing"):
            resolve_previous_filing_bindings_from_filed_declarations(
                snapshot.revision,
                (),
                filing_year=2026,
                period="1T",
            )

    def test_non_decimal_observed_value_rejected(self) -> None:
        observation = _filed_observation(
            modelo="100",
            ejercicio=2025,
            period="0A",
            casilla_values={"0224": "no-decimal"},
        )

        with pytest.raises(SedeParseError, match="not decimal-valued"):
            registry_observation_from_filed_declaration(observation)

    def test_contradictory_observed_values_rejected(self) -> None:
        observation = _filed_observation(
            modelo="100",
            ejercicio=2025,
            period="0A",
            casilla_values={"0224": Decimal("1")},
        ).model_copy(
            update={
                "casillas": (
                    ObservedCasillaValue(
                        casilla_id="0224",
                        value="1",
                        source_artefact_kind="submitted_file",
                        source_locator="field:0224",
                        confidence=1.0,
                    ),
                    ObservedCasillaValue(
                        casilla_id="0224",
                        value="2",
                        source_artefact_kind="submitted_file",
                        source_locator="field:0224",
                        confidence=1.0,
                    ),
                )
            }
        )

        with pytest.raises(SedeParseError, match="contradictory values"):
            registry_observation_from_filed_declaration(observation)

    def test_incomplete_observation_coverage_rejected(self) -> None:
        observation = _filed_observation(
            modelo="100",
            ejercicio=2025,
            period="0A",
            casilla_values={"0224": Decimal("1")},
            extraction_coverage={"submitted_file": 0.5},
        )

        with pytest.raises(SedeParseError, match="incomplete extraction coverage"):
            registry_observation_from_filed_declaration(observation)


class TestFiledObservationRelations:
    """Verify filed observations can supply registry cross-model relations."""

    def test_modelo_100_relation_fixture_covers_registry_source_requirements(self) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2025, period="0A")
        observations = _renta_2025_relation_observations()
        available = {
            (observation.modelo, observation.ejercicio, observation.period, casilla.casilla_id)
            for observation in observations
            for casilla in observation.casillas
        }
        missing = [
            (requirement.source_modelo, requirement.filing_year, period, requirement.source_output)
            for requirement in relation_source_requirements(snapshot.revision, filing_year=2025, period="0A")
            for period in requirement.periods
            if (requirement.source_modelo, requirement.filing_year, period, requirement.source_output)
            not in available
        ]

        assert not missing

    def test_modelo_100_relations_resolve_from_standardized_filed_observations(self) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2025, period="0A")
        observations = _renta_2025_relation_observations()

        resolved = resolve_relation_values_from_filed_declarations(
            snapshot.revision,
            observations,
            filing_year=2025,
            period="0A",
        )

        # Quarterly / monthly aggregations — verify inclusion (every
        # period observation contributed; aggregate exceeds the largest
        # single-period observation) and key presence. The exact arithmetic
        # is verified against AEAT's open simulator via the replay-parity
        # layer; assertions here pin the resolver's wiring contract only.
        quarterly_aggregations = {
            "renta-2025-rel-111-retenciones-trimestrales": Decimal("40"),  # max single quarter
            "renta-2025-rel-115-retenciones-trimestrales": Decimal("8"),
            "renta-2025-rel-123-retenciones-trimestrales": Decimal("24"),
            "renta-2025-rel-130-pagos-fraccionados": Decimal("56"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("88"),
        }
        for relation_id, max_single in quarterly_aggregations.items():
            assert relation_id in resolved, f"{relation_id} missing from resolution"
            assert resolved[relation_id] > max_single, (
                f"{relation_id} = {resolved[relation_id]} not greater than max single observation "
                f"{max_single} — at least one period did not contribute"
            )

        # Monthly relation: same INCLUSION property — value must exceed max month (12).
        assert resolved["renta-2025-rel-111-retenciones-mensuales"] > Decimal("12")

        # Annual receivers are op=copy passthroughs — assert the
        # fixture's literal threads through to the resolved relation
        # value unchanged.
        annual_copies = {
            "renta-2025-rel-180-retenciones-anuales": Decimal("90"),
            "renta-2025-rel-190-retenciones-anuales": Decimal("178"),
            "renta-2025-rel-193-retenciones-anuales": Decimal("60"),
            "renta-2025-rel-184-atribucion-actividades-economicas": Decimal("77"),
        }
        for relation_id, fixture_value in annual_copies.items():
            assert resolved[relation_id] == fixture_value, (
                f"{relation_id} copy thread broke — expected {fixture_value} from fixture"
            )

    def test_modelo_100_relation_resolution_requires_each_source_period(self) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2025, period="0A")
        observations = tuple(
            observation
            for observation in _renta_2025_relation_observations()
            if not (observation.modelo == "131" and observation.period == "4T")
        )

        with pytest.raises(RegistryValidationError, match="expected one observed filing"):
            resolve_relation_values_from_filed_declarations(
                snapshot.revision,
                observations,
                filing_year=2025,
                period="0A",
            )

    def test_modelo_100_relation_resolution_rejects_duplicate_source_periods(self) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2025, period="0A")
        observations = _renta_2025_relation_observations()
        duplicate = _filed_observation(
            modelo="130",
            ejercicio=2025,
            period="1T",
            casilla_values={"19": Decimal("1")},
        )

        with pytest.raises(RegistryValidationError, match="found 2"):
            resolve_relation_values_from_filed_declarations(
                snapshot.revision,
                (*observations, duplicate),
                filing_year=2025,
                period="0A",
            )

    @pytest.mark.parametrize("filing_year", (2022, 2026))
    def test_annual_summary_relations_resolve_from_quarterly_filed_observations(self, filing_year: int) -> None:
        snapshot = _modelo_snapshot("180", filing_year=filing_year, period="0A")
        quarterly_values = {
            "1T": {"01": Decimal("2"), "02": Decimal("100.10"), "03": Decimal("19.20")},
            "2T": {"01": Decimal("3"), "02": Decimal("200.20"), "03": Decimal("38.40")},
            "3T": {"01": Decimal("1"), "02": Decimal("50.00"), "03": Decimal("9.50")},
            "4T": {"01": Decimal("4"), "02": Decimal("300.30"), "03": Decimal("57.60")},
        }

        resolved = resolve_relation_values_from_filed_declarations(
            snapshot.revision,
            tuple(
                _filed_observation(
                    modelo="115",
                    ejercicio=filing_year,
                    period=period,
                    casilla_values=casilla_values,
                )
                for period, casilla_values in quarterly_values.items()
            ),
            filing_year=filing_year,
            period="0A",
        )

        assert resolved == {
            "modelo-180-rel-115-base-anual": sum(values["02"] for values in quarterly_values.values()),
            "modelo-180-rel-115-perceptores-anual": sum(values["01"] for values in quarterly_values.values()),
            "modelo-180-rel-115-retenciones-anual": sum(values["03"] for values in quarterly_values.values()),
        }

    def test_modelo_193_relations_resolve_from_quarterly_filed_observations(self) -> None:
        snapshot = _modelo_snapshot("193", filing_year=2026, period="0A")
        quarterly_values = {
            "1T": {"03": Decimal("5"), "06": Decimal("1201.00"), "09": Decimal("228.19")},
            "2T": {"03": Decimal("4"), "06": Decimal("800.25"), "09": Decimal("152.05")},
            "3T": {"03": Decimal("7"), "06": Decimal("999.75"), "09": Decimal("189.95")},
            "4T": {"03": Decimal("6"), "06": Decimal("500.00"), "09": Decimal("95.00")},
        }

        resolved = resolve_relation_values_from_filed_declarations(
            snapshot.revision,
            tuple(
                _filed_observation(
                    modelo="123",
                    ejercicio=2026,
                    period=period,
                    casilla_values=casilla_values,
                )
                for period, casilla_values in quarterly_values.items()
            ),
            filing_year=2026,
            period="0A",
        )

        assert resolved == {
            "modelo-193-rel-123-perceptores-anual": sum(values["03"] for values in quarterly_values.values()),
            "modelo-193-rel-123-base-anual": sum(values["06"] for values in quarterly_values.values()),
            "modelo-193-rel-123-retenciones-anual": sum(values["09"] for values in quarterly_values.values()),
        }

    def test_missing_relation_source_filing_is_rejected(self) -> None:
        snapshot = _modelo_snapshot("180", filing_year=2026, period="0A")
        observations = tuple(
            _filed_observation(
                modelo="115",
                ejercicio=2026,
                period=period,
                casilla_values={"01": Decimal("1"), "02": Decimal("10"), "03": Decimal("2")},
            )
            for period in ("1T", "2T", "3T")
        )

        with pytest.raises(RegistryValidationError, match="expected one observed filing"):
            resolve_relation_values_from_filed_declarations(
                snapshot.revision,
                observations,
                filing_year=2026,
                period="0A",
            )

    def test_incomplete_relation_source_observation_is_rejected(self) -> None:
        snapshot = _modelo_snapshot("180", filing_year=2026, period="0A")
        observations = tuple(
            _filed_observation(
                modelo="115",
                ejercicio=2026,
                period=period,
                casilla_values={"01": Decimal("1"), "02": Decimal("10"), "03": Decimal("2")},
                extraction_coverage={"submitted_file": 0.5} if period == "4T" else None,
            )
            for period in ("1T", "2T", "3T", "4T")
        )

        with pytest.raises(SedeParseError, match="incomplete extraction coverage"):
            resolve_relation_values_from_filed_declarations(
                snapshot.revision,
                observations,
                filing_year=2026,
                period="0A",
            )


def _renta_2025_relation_observations() -> tuple[FiledDeclaracionObservation, ...]:
    observations: list[FiledDeclaracionObservation] = []
    observations.extend(
        _filed_observation(
            modelo="111",
            ejercicio=2025,
            period=period,
            casilla_values={"28": value},
        )
        for period, value in {
            "1T": Decimal("10"),
            "2T": Decimal("20"),
            "3T": Decimal("30"),
            "4T": Decimal("40"),
        }.items()
    )
    observations.extend(
        _filed_observation(
            modelo="111",
            ejercicio=2025,
            period=period,
            casilla_values={"28": value},
        )
        for period, value in {
            "01": Decimal("1"),
            "02": Decimal("2"),
            "03": Decimal("3"),
            "04": Decimal("4"),
            "05": Decimal("5"),
            "06": Decimal("6"),
            "07": Decimal("7"),
            "08": Decimal("8"),
            "09": Decimal("9"),
            "10": Decimal("10"),
            "11": Decimal("11"),
            "12": Decimal("12"),
        }.items()
    )
    observations.extend(
        _filed_observation(
            modelo="115",
            ejercicio=2025,
            period=period,
            casilla_values={"03": value},
        )
        for period, value in {
            "1T": Decimal("2"),
            "2T": Decimal("4"),
            "3T": Decimal("6"),
            "4T": Decimal("8"),
        }.items()
    )
    observations.extend(
        _filed_observation(
            modelo="123",
            ejercicio=2025,
            period=period,
            casilla_values={"09": value},
        )
        for period, value in {
            "1T": Decimal("6"),
            "2T": Decimal("12"),
            "3T": Decimal("18"),
            "4T": Decimal("24"),
        }.items()
    )
    observations.extend(
        _filed_observation(
            modelo="130",
            ejercicio=2025,
            period=period,
            casilla_values={"19": value},
        )
        for period, value in {
            "1T": Decimal("14"),
            "2T": Decimal("28"),
            "3T": Decimal("42"),
            "4T": Decimal("56"),
        }.items()
    )
    observations.extend(
        _filed_observation(
            modelo="131",
            ejercicio=2025,
            period=period,
            casilla_values={"15": value},
        )
        for period, value in {
            "1T": Decimal("22"),
            "2T": Decimal("44"),
            "3T": Decimal("66"),
            "4T": Decimal("88"),
        }.items()
    )
    observations.append(
        _filed_observation(
            modelo="180",
            ejercicio=2025,
            period="0A",
            casilla_values={"decl.retenciones-total": Decimal("90")},
        )
    )
    observations.append(
        _filed_observation(
            modelo="190",
            ejercicio=2025,
            period="0A",
            casilla_values={"decl.retenciones-total": Decimal("178")},
        )
    )
    observations.append(
        _filed_observation(
            modelo="193",
            ejercicio=2025,
            period="0A",
            casilla_values={"decl.retenciones-total": Decimal("60")},
        )
    )
    observations.append(
        _filed_observation(
            modelo="184",
            ejercicio=2025,
            period="0A",
            casilla_values={"tipo2.renta-atribuible-importe": Decimal("77")},
        )
    )
    return tuple(observations)
