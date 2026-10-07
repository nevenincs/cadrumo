"""The three parallel schemes keep their official detail tables separate."""

from pathlib import Path

import pytest

from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormContextFieldBlock,
    FormFieldBlock,
    FormGridBlock,
)

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_narrow_subtotals_do_not_claim_to_be_the_complete_settlement() -> None:
    with override_settings(cadrumo_output_language="es"):
        modelo = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/369"))
        for revision in modelo.revisions.values():
            total = next(casilla for casilla in revision.casillas if str(casilla.id).endswith("cuota-total"))
            assert total.label.startswith("Subtotal parcial:")
            assert "sin correcciones" in total.label


@pytest.mark.parametrize("scheme", ["exterior", "union", "importacion"])
def test_taxpayer_identity_is_bound_to_its_own_scheme_header(scheme: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/369")).revisions[f"esquema-{scheme}"]
    identity = revision.form_layouts[0].pages[0].sections[0]
    assert identity.id == "declarante"
    context_fields = [block for block in identity.blocks if isinstance(block, FormContextFieldBlock)]
    assert len(context_fields) == 2
    actual = set()
    for block in context_fields:
        layout = next(item for item in revision.export_layouts if item.id == block.export_layout_id)
        record = next(item for item in layout.records if item.id == block.export_record_id)
        field = next(item for item in record.fields if item.id == block.export_field_id)
        actual.add(field.producer_key)
        assert f"-{scheme}-" in str(record.id)
    assert actual == {"taxpayer.tax_id", "taxpayer.full_name"}


@pytest.mark.parametrize("scheme", ["exterior", "union", "importacion"])
def test_identity_period_and_payment_have_separate_reading_sections(scheme: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/369")).revisions[f"esquema-{scheme}"]
    (layout,) = revision.form_layouts
    assert [section.id for section in layout.pages[0].sections[:2]] == ["declarante", "ejercicio-periodo"]
    sections = {section.id: section for page in layout.pages for section in page.sections}

    def suffixes(section_id: str) -> set[str]:
        return {
            str(block.binding_id).split(".", 1)[1]
            for block in sections[section_id].blocks
            if isinstance(block, FormFieldBlock) and block.binding_id is not None
        }

    assert all(field.startswith("1-") for field in suffixes("declarante"))
    assert all(field.startswith("2-ejercicio-y-periodo-") for field in suffixes("ejercicio-periodo"))
    assert "2-ejercicio-y-periodo-tipo-de-periodo" not in suffixes("ejercicio-periodo")
    assert suffixes("pago") == {"tipo-de-pago", "nrc-pago", "importe-pagado"}
    assert suffixes("presentacion") == {"regimen", "categoria", "2-ejercicio-y-periodo-tipo-de-periodo"}
    assert [section.id for section in layout.pages[-1].sections[-2:]] == ["pago", "presentacion"]
    placed = [
        block.binding_id
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormFieldBlock)
    ]
    assert len(placed) == len(set(placed)), "A field must not become editable in two sections"


@pytest.mark.parametrize("scheme,count", [("exterior", 2), ("union", 5), ("importacion", 2)])
def test_detail_grids_preserve_all_declared_export_bindings(scheme: str, count: int) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/369")).revisions[f"esquema-{scheme}"]
    (layout,) = revision.form_layouts
    assert form_layout_failures(revision) == ()
    grids = [
        block
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormGridBlock) and block.id != "resultado-estados"
    ]
    assert len(grids) == count
    assert all(len(grid.rows) == 28 for grid in grids)
    assert all([row.key for row in grid.rows] == [f"fila-{i}" for i in range(1, 29)] for grid in grids)
    expected = {
        field.binding
        for export in revision.export_layouts
        for record in export.records
        for field in record.fields
        if field.binding
    }
    actual = {cell.binding_id for grid in grids for row in grid.rows for cell in row.cells}
    actual.update(
        block.binding_id
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormFieldBlock) and block.binding_id is not None
    )
    assert actual == expected
    assert layout.review.state == "generated"
    if scheme == "exterior":
        assert "Additional-payment page remains unimplemented" in (layout.review.notes or "")
    elif scheme == "importacion":
        assert "Additional-payment form remains unimplemented" in (layout.review.notes or "")
        assert len(layout.pages) == 3
    else:
        assert "settlement" in (layout.review.notes or "")


def test_union_establishment_and_dispatch_rows_never_interleave() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/369")).revisions["esquema-union"]
    grids = {
        block.id: block
        for page in revision.form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormGridBlock)
    }
    for name, prefix in (("union-ep", "5-prestaciones"), ("union-envio", "6-entregas")):
        grid = grids[name]
        assert [column.key for column in grid.columns] == [
            "pais-origen",
            "niva",
            "pais-consumo",
            "tipo",
            "clase",
            "base",
            "cuota",
        ]
        # AEAT T36907 row 27 labels its NIVA, base and quota fields "76.". Their
        # source-derived identities retain that typo; they still belong to goods.
        allowed = (f".{prefix}", ".76-entregas") if name == "union-envio" else (f".{prefix}",)
        assert all(any(token in str(cell.binding_id) for token in allowed) for row in grid.rows for cell in row.cells)
    assert [column.key for column in grids["correcciones"].columns] == [
        "pais-consumo",
        "ejercicio",
        "tipo-periodo",
        "periodo",
        "correccion",
    ]
