"""Modelo 353 preserves its official page split and each entity's row."""

from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.manual_input_selector import ManualInputProvider
from cadrumo.domain.calculations.registry.schema_form_layouts import FormContextFieldBlock, FormGridBlock

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("revision_id,pages", [("2021-hasta-2026-01", 1), ("2026-desde-02", 2)])
def test_official_page_count_and_complete_placement(revision_id: str, pages: int) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/353")).revisions[revision_id]
    (layout,) = revision.form_layouts
    assert layout.seed_source == "authored"
    assert len(layout.pages) == pages
    assert form_layout_failures(revision) == ()
    assert {p.casilla_id for p in layout.placements} == {c.id for c in revision.casillas}
    assert {"06", "07", "papel.importe-ingreso"} <= layout.casilla_sections().keys()
    assert not any(p.workbook_exclusion for p in layout.placements)
    assert layout.review.state == "generated"


@pytest.mark.parametrize("revision_id", ["2021-hasta-2026-01", "2026-desde-02"])
def test_entity_grid_keeps_identity_result_share_and_receipt_together(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/353")).revisions[revision_id]
    grid = next(
        block
        for page in revision.form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormGridBlock)
    )
    assert [column.key for column in grid.columns] == ["nif", "resultado-entidad", "participacion", "justificante"]
    assert len(grid.rows) == 21
    assert grid.rows[0].cells[2].kind == "blank"
    for number, row in enumerate(grid.rows[1:], 1):
        prefix = f"modelo-353.page_01.entidad-{number}-"
        assert [cell.binding_id for cell in row.cells] == [
            prefix + "entidades-dependientes-n-i-f",
            prefix + "entidades-dependientes-resultado",
            prefix + "ent-depndtes-de-participac-al-final-del",
            prefix + "entidades-dependientes-numero-de-justifi",
        ]


@pytest.mark.parametrize("revision_id", ["2021-hasta-2026-01", "2026-desde-02"])
def test_payment_amounts_are_explicit_paper_inputs_not_automatic_refund_elections(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/353")).revisions[revision_id]
    fields = {c.id: c for c in revision.casillas}
    for identifier in ("06", "07", "papel.importe-ingreso"):
        item = fields[identifier]
        assert item.input_kind == "manual"
        assert item.formula is None and item.binding is None
        assert item.data_type == "money" and not item.required
        assert not item.export_refs
        assert item.constraints is not None and item.constraints.sign == "non_negative"


def test_february_form_moves_payments_to_page_two_without_backdating_advance() -> None:
    modelo = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/353"))
    previous = modelo.revisions["2021-hasta-2026-01"].form_layouts[0]
    current = modelo.revisions["2026-desde-02"].form_layouts[0]
    assert "10" not in previous.casilla_sections()
    assert current.casilla_sections()["10"] == ("pagina-1", "liquidacion")
    for identifier in ("06", "07", "papel.importe-ingreso"):
        assert previous.casilla_sections()[identifier][0] == "pagina-1"
        assert current.casilla_sections()[identifier][0] == "pagina-2"
    assert [section.id for section in current.pages[1].sections] == [
        "identificacion",
        "compensacion",
        "ingreso",
        "devolucion",
    ]


@pytest.mark.parametrize("revision_id", ["2021-hasta-2026-01", "2026-desde-02"])
def test_account_and_no_activity_fields_use_the_existing_exact_producers(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/353")).revisions[revision_id]
    fields = {
        (layout.id, record.id, field.id): field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
    }
    contexts = {
        block.id: fields[(block.export_layout_id, block.export_record_id, block.export_field_id)]
        for page in revision.form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormContextFieldBlock)
    }
    assert contexts["iban--ingreso"].producer_key == "selected_account.iban"
    assert contexts["iban--devolucion"].producer_key == "selected_account.iban"
    assert contexts["bic"].producer_key == "selected_account.swift_bic"
    assert contexts["sin-actividad"].producer_key == "m353.sin_actividad"
    assert contexts["sin-actividad"].computed_key is None


@pytest.mark.parametrize("revision_id", ["2021-hasta-2026-01", "2026-desde-02"])
def test_entity_amounts_and_shares_are_numeric_but_identifiers_remain_text(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/353")).revisions[revision_id]
    manual = [binding for binding in revision.bindings if isinstance(binding.provider, ManualInputProvider)]
    assert sum(binding.value.data_type == "money" for binding in manual) == 21
    assert sum(binding.value.data_type == "decimal" for binding in manual) == 20
    assert sum(binding.value.data_type == "text" for binding in manual) == 42
    for binding in manual:
        assert isinstance(binding.provider, ManualInputProvider)
        if binding.value.data_type in ("money", "decimal"):
            assert binding.value.channel == "decimal"
        if binding.value.data_type == "money":
            assert binding.provider.signed is True
        if binding.value.data_type == "decimal":
            assert binding.provider.decimals == 2


@pytest.mark.parametrize("revision_id", ["2021-hasta-2026-01", "2026-desde-02"])
def test_human_numeric_values_retain_the_official_sign_and_decimal_wire_scale(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/353")).revisions[revision_id]
    fields = {
        field.binding: field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.binding is not None
    }
    prefix = "modelo-353.page_01."
    amount = fields[prefix + "entidad-dominante-entidad-dominante-resultado"]
    share = fields[prefix + "entidad-1-ent-depndtes-de-participac-al-final-del"]
    receipt = fields[prefix + "entidad-dominante-entidad-dominante-numero-de-justificante"]
    assert render_fixed_width_export_field(amount, Decimal("-150.25")) == "N0000000000015025"
    assert render_fixed_width_export_field(share, Decimal("75.25")) == "07525"
    assert render_fixed_width_export_field(receipt, "0001234567890") == "0001234567890"
