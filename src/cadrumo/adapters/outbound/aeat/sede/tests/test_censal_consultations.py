"""Census parser mutation and semantic association checks, using synthetic data."""

from __future__ import annotations

import pytest

from ......application.user_profile.censal_observation import CensalConsultation
from ..censal_datos import READ_GUARD_POLICY, parse_censal_datos
from ..censal_navigation import assert_censal_consultation_request
from ..censal_tables import parse_censal_table
from ..censal_tax_status import parse_censal_tax_status
from ..errors import SedeNavigationError, SedeParseError
from .censal_consultation_fixtures import ACTIVITIES_HTML, OBLIGATIONS_HTML, TAX_HTML, table_document

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_SOURCE = "https://www6.agenciatributaria.gob.es/consulta?nif=PRIVATE#PRIVATE"


@pytest.mark.parametrize("aria", [False, True])
def test_reordered_headers_and_new_columns_keep_their_values(aria: bool) -> None:
    html = table_document(
        "Relación de Actividades",
        ("Estado", "Campo nuevo", "Denominación", "Epígrafe"),
        ("Alta", "UNKNOWN-RETAINED", "ACTIVIDAD", "999"),
    )
    if aria:
        for tag, role in (("table", "table"), ("tr", "row"), ("th", "columnheader"), ("td", "cell")):
            html = html.replace(f"<{tag}>", f'<div role="{role}">').replace(f"</{tag}>", "</div>")
    parsed = parse_censal_table(html, kind="actividades", source_url=_SOURCE)
    cells = parsed.sections[0].rows[0].cells
    assert {cell.column: cell.text for cell in cells} == {
        "Estado": "Alta",
        "Campo nuevo": "UNKNOWN-RETAINED",
        "Denominación": "ACTIVIDAD",
        "Epígrafe": "999",
    }
    assert str(parsed.source_url) == "https://www6.agenciatributaria.gob.es/consulta"
    assert CensalConsultation.model_validate_json(parsed.model_dump_json()) == parsed


def test_blank_end_date_is_retained_without_becoming_a_negative_fact() -> None:
    parsed = parse_censal_table(OBLIGATIONS_HTML, kind="obligaciones", source_url=_SOURCE)
    assert next(cell.text for cell in parsed.sections[0].rows[0].cells if cell.column == "F. Baja Efec.") is None


@pytest.mark.parametrize(
    "html",
    [
        ACTIVITIES_HTML.replace("<td>Alta</td>", ""),
        ACTIVITIES_HTML.replace("<th>F.Baja</th>", "<th>Estado</th>"),
        "<h1>La sesión ha caducado</h1>",
        ACTIVITIES_HTML + "<p>Mostrados los registros 1 a 1 de un total de 10</p>",
    ],
)
def test_ambiguous_incomplete_or_wrong_page_is_refused(html: str) -> None:
    with pytest.raises(SedeParseError):
        parse_censal_table(html, kind="actividades", source_url=_SOURCE)


def test_tax_status_keeps_codes_columns_marks_and_dates() -> None:
    parsed = parse_censal_tax_status(TAX_HTML, source_url=_SOURCE)
    row = next(row for section in parsed.sections for row in section.rows)
    assert row.label == "General"
    assert [(cell.column, cell.text) for cell in row.cells if cell.role == "value"] == [
        ("Alta", "X"),
        ("Baja", None),
        ("Fecha", "01/01/2024"),
    ]
    assert [cell.text for cell in row.cells if cell.role == "casilla"] == ["510", "511"]


def test_tax_status_new_labels_survive_presentation_changes() -> None:
    html = TAX_HTML.replace("General", "Régimen futuro").replace('class="ancho_5"', 'class="new-style"')
    html = html.replace('class="fondo_medio"', 'data-censal-value=""')
    html = html.replace('<span class="ASWeb_multi_idioma">', "<label>").replace("</span>", "</label>")
    parsed = parse_censal_tax_status(html, source_url=_SOURCE)
    row = next(row for section in parsed.sections for row in section.rows)
    assert row.label == "Régimen futuro"
    assert [cell.text for cell in row.cells if cell.role == "value"] == ["X", None, "01/01/2024"]


def test_scripts_cannot_supply_unrendered_tax_answers() -> None:
    html = TAX_HTML.replace("<strong>X</strong>", '<script>document.write("SECRET")</script>')
    parsed = parse_censal_tax_status(html, source_url=_SOURCE)
    row = next(row for section in parsed.sections for row in section.rows)
    assert next(cell.text for cell in row.cells if cell.column == "Alta") is None
    assert "SECRET" not in parsed.model_dump_json()


def test_unlabelled_tax_fieldset_is_refused() -> None:
    with pytest.raises(SedeParseError):
        parse_censal_tax_status(TAX_HTML.replace("legend", "div"), source_url=_SOURCE)


def test_unrecognized_tax_content_cannot_silently_disappear() -> None:
    with pytest.raises(SedeParseError):
        parse_censal_tax_status(
            TAX_HTML.replace("</fieldset>", "<p>New answer: ABC</p></fieldset>", 1), source_url=_SOURCE
        )


def test_missing_tax_section_is_not_an_empty_regime() -> None:
    with pytest.raises(SedeParseError):
        parse_censal_tax_status(TAX_HTML.replace("Otros Impuestos", "New section"), source_url=_SOURCE)


def test_empty_table_requires_an_explicit_result() -> None:
    html = table_document("Relación de Actividades", ("Estado", "Denominación", "Epígrafe"), ())
    with pytest.raises(SedeParseError):
        parse_censal_table(html, kind="actividades", source_url=_SOURCE)
    explicit = html.replace("<tr></tr>", '<tr><td colspan="3">No existen registros</td></tr>')
    assert parse_censal_table(explicit, kind="actividades", source_url=_SOURCE).sections[0].rows == ()


def test_identity_supports_semantic_caption_and_header_markup() -> None:
    html = "<table><caption>Datos Identificativos del Contribuyente</caption><tr><th>NIF</th><td>Y0000001Z</td></tr></table>"
    assert parse_censal_datos(html, source_url=_SOURCE).identity.nif == "Y0000001Z"


def test_identity_conflicting_duplicates_cannot_overwrite_each_other() -> None:
    html = '<table title="Datos Identificativos del Contribuyente"><tr><th>NIF</th><td>Y0000001Z</td></tr><tr><th>NIF</th><td>Y0000002S</td></tr></table>'
    with pytest.raises(SedeParseError):
        parse_censal_datos(html, source_url=_SOURCE)


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_unexpected_navigation_is_refused_before_request(method: str) -> None:
    with pytest.raises(SedeNavigationError):
        assert_censal_consultation_request(READ_GUARD_POLICY, method, "https://www6.agenciatributaria.gob.es/unlisted")
