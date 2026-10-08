"""Real calculation dependencies must survive human form projection with authored labels."""

import pytest

from cadrumo.application.storage.calc_sheets.engine import build_export_plan
from cadrumo.application.storage.calc_sheets.form_workbook import add_form_workbook
from cadrumo.application.storage.calc_sheets.records import TabName
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.config import override_settings
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.modelo_localization import binding_locale_key

from ..compiler.authority import compiled_bundled_authority
from ..form_layout.coverage import coverage_rows
from ..workbook_probe import probe_revision

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


@pytest.fixture(scope="module")
def authority():
    return compiled_bundled_authority()


@pytest.mark.parametrize(
    ("modelo", "revision"),
    [
        ("180", "2019-2022"),
        ("180", "2023-y-siguientes"),
        *(("190", revision) for revision in ("2022", "2023", "2024", "2025-y-siguientes")),
        *(("193", revision) for revision in ("2022", "2023", "2024", "2025-y-siguientes")),
        ("200", "2024"),
        ("200", "2025-y-siguientes"),
        *(("714", revision) for revision in ("2022", "2023", "2024", "2025")),
        ("720", "2013-y-siguientes"),
    ],
)
def test_previously_unlabelled_dependencies_compile_real_revision(authority, modelo, revision):
    row = next(
        row for row in coverage_rows(authority.modelos) if (row.modelo_id, row.revision_id) == (modelo, revision)
    )
    result = probe_revision(authority, row)
    assert result.status == "compiled", f"{result.stage}: {result.message}; {result.context}"
    assert result.value_cells > 0
    if modelo == "190":
        frame = result.frame
        assert frame is not None
        snapshot = authority.snapshot(
            modelo,
            filing_year=frame.filing_year,
            period=frame.period,
            on=frame.on,
            revision_id=revision,
            grade=RegistryAuthorityGrade.CALCULATION,
        )
        with override_settings(cadrumo_output_language="es"), validating_governed_facts(authority):
            plan = add_form_workbook(build_export_plan(snapshot), snapshot)
        casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
        assert len(snapshot.revision.form_layouts) == 1
        layout = snapshot.revision.form_layouts[0]
        headings = {
            column.official_heading or casillas[column.casilla_id].label
            for page in layout.pages
            for section in page.sections
            for block in section.blocks
            if block.kind == "repeating"
            for column in block.columns
        }
        assert headings
        displayed = {cell.value for cell in plan.value_cells if cell.address.tab == TabName.FORM}
        assert headings <= displayed
        assert all(height.height_pixels <= 409 for height in plan.row_heights)


@pytest.mark.parametrize("language", ("es", "en", "ca", "hu"))
@pytest.mark.parametrize(
    ("modelo", "binding"),
    (
        ("180", "modelo-180-115-base-anual"),
        ("190", "modelo-190-perceptor-rows-incapacidad-ingreso-a-cuenta-total"),
        ("190", "modelo-190-111-ganancias-dinerario-importe-anual"),
        ("193", "modelo-193-perceptor-rows-base-total"),
        ("200", "modelo-200-profile-new-entity-flag"),
        ("714", "m714-m100-base-imponible-general"),
        ("720", "modelo-720.type_1.nombre-contacto"),
    ),
)
def test_authored_dependency_families_have_real_translations(language, modelo, binding):
    key = binding_locale_key(modelo, binding, "label")
    label = lookup_translation(key, locale=language)
    assert label and label.strip() and label not in (key, binding)


def test_labels_preserve_specific_eligibility_and_forestry_meaning():
    eligibility = lookup_translation(
        binding_locale_key("200", "modelo-200-profile-new-entity-flag", "label"), locale="es"
    )
    forestry = lookup_translation(
        binding_locale_key("190", "modelo-190-111-ganancias-dinerario-importe-anual", "label"), locale="es"
    )
    withholding_total = lookup_translation(
        binding_locale_key("193", "modelo-193-perceptor-rows-retenciones-total", "label"), locale="es"
    )
    assert eligibility and "dos primeros períodos con beneficios" in eligibility
    assert forestry and "forestales" in forestry
    assert withholding_total and "retenciones e ingresos a cuenta" in withholding_total
