"""The electronic 349 keeps summary, operator and correction facts distinct."""

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema_form_layouts import FormRepeatingGroupBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_only_summary_boxes_have_official_numbers() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/349")).revisions["2020-y-siguientes"]
    (layout,) = revision.form_layouts
    assert form_layout_failures(revision) == ()
    assert layout.seed_source == "authored" and layout.review.state == "generated"
    assert {p.casilla_id: str(p.box_number) for p in layout.placements if p.box_number} == {
        "decl.numero-operadores": "01",
        "decl.importe-operaciones": "02",
        "decl.numero-rectificaciones": "03",
        "decl.importe-rectificaciones": "04",
    }
    assert {p.casilla_id for p in layout.placements} == {c.id for c in revision.casillas}
    assert not any(p.workbook_exclusion for p in layout.placements)


def test_corrections_keep_operator_identity_period_and_both_amounts() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/349")).revisions["2020-y-siguientes"]
    (layout,) = revision.form_layouts
    assert len(layout.pages) == 3
    operator = layout.pages[1].sections[0].blocks[0]
    correction = layout.pages[2].sections[0].blocks[0]
    assert isinstance(operator, FormRepeatingGroupBlock)
    assert isinstance(correction, FormRepeatingGroupBlock)
    assert operator.export_record_id == "modelo-349-operador"
    assert correction.export_record_id == "modelo-349-rectificacion"
    assert [column.casilla_id for column in correction.columns] == [
        "op.codigo-pais",
        "op.nif-comunitario",
        "op.apellidos-razon-social",
        "op.clave-operacion",
        "rect.ejercicio-rectificado",
        "rect.periodo-rectificado",
        "rect.base-rectificada",
        "rect.base-anterior",
        "sustituto.nif",
        "sustituto.apellidos-razon-social",
    ]
    assert "op.base-imponible" in {column.casilla_id for column in operator.columns}
    assert "op.base-imponible" not in {column.casilla_id for column in correction.columns}


def test_summary_exposes_exact_taxpayer_period_and_contact_owners() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/349")).revisions["2020-y-siguientes"]
    sections = {s.id: s for s in revision.form_layouts[0].pages[0].sections}
    assert set(sections) == {"identificacion", "periodo", "contacto", "resumen-importes", "declaracion"}
    context = {
        block.export_field_id
        for section in sections.values()
        for block in section.blocks
        if block.kind == "context_field"
    }
    assert context == {
        "modelo-349-decl-nif",
        "modelo-349-decl-apellidos-razon-social",
        "modelo-349-decl-year",
        "modelo-349-decl-period-code",
        "modelo-349-decl-persona-relacion-nombre",
        "modelo-349-decl-persona-relacion-telefono",
    }
