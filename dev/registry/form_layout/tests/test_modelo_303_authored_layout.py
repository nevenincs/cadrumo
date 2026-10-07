"""303 presentation follows the printed annex while retaining typed value owners."""

from functools import cache
from pathlib import Path

import pytest

from cadrumo.core.i18n.render import lookup_translation
from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormContextFieldBlock,
    FormFieldBlock,
    FormGridBlock,
    FormLayoutDefinition,
    FormRepeatingGroupBlock,
)

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _revision() -> ModeloRevision:
    return load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/303")).revisions["2026-y-siguientes"]


def test_2022_form_keeps_single_record_and_historical_bank_owners() -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/303")).revisions["2022"]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert len(layout.pages) == 6
    assert all(str(75943 + n) in (page.official_ref or "") for n, page in enumerate(layout.pages))
    assert len(layout.placements) == len(revision.casillas) == 208
    blocks = [block for page in layout.pages for section in page.sections for block in section.blocks]
    activities = [block for block in blocks if isinstance(block, FormRepeatingGroupBlock)]
    assert len(activities) == 4
    assert sum(len(block.columns) for block in activities) == 70
    assert all(block.max_rows == 1 for block in activities)
    for page in (layout.pages[2], layout.pages[5]):
        bank_fields = [
            resolve_form_context_field(revision, block)
            for section in page.sections
            for block in section.blocks
            if isinstance(block, FormContextFieldBlock)
        ]
        assert any(field.producer_key == "selected_account.iban" for field in bank_fields)
    assert layout.review.state == "generated"


def test_annual_volume_formula_is_inherited_only_in_grounded_editions() -> None:
    revisions = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/303")).revisions
    expressions = []
    for revision_id in revisions:
        revision = revisions[revision_id]
        box = next(c for c in revision.casillas if c.id == "88")
        assert box.input_kind == "computed"
        formula = next(f for f in revision.formulas if f.id == box.formula)
        expressions.append(formula.expression)
        source = {
            "2022": "boe-modelo-303-2021-form-pdf",
            "2023": "boe-modelo-303-2023-form-pdf",
            "2024-hasta-08-y-2t": "boe-modelo-303-2023-form-pdf",
            "2024-desde-09-y-3t": "boe-modelo-303-2024-form-pdf",
            "2025": "boe-modelo-303-2024-form-pdf",
            "2026-y-siguientes": "boe-modelo-303-2026-form-pdf",
        }[revision_id]
        assert source in formula.source_refs
    assert all(expression == expressions[0] for expression in expressions)


@pytest.mark.parametrize("revision_id", ["2024-desde-09-y-3t", "2025"])
def test_historical_rectificativa_form_preserves_its_own_field_owners(revision_id: str) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/303")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert len(layout.pages) == 6
    assert all(str(99216 + n) in (page.official_ref or "") for n, page in enumerate(layout.pages))
    assert len(layout.placements) == len(revision.casillas) == 228
    assert {source.source_ref for source in layout.design_sources} >= {"boe-modelo-303-2024-form-pdf"}
    blocks = [block for page in layout.pages for section in page.sections for block in section.blocks]
    assert not any(block.id in {"gasolinas", "c-112"} for block in blocks)
    contexts = {block.id: block for block in blocks if isinstance(block, FormContextFieldBlock)}
    assert resolve_form_context_field(revision, contexts["nif"]).producer_key == "taxpayer.tax_id"
    assert resolve_form_context_field(revision, contexts["iban"]).producer_key == "selected_account.iban"
    assert all("m303-2026" not in block.export_field_id for block in contexts.values())
    activities = [block for block in blocks if isinstance(block, FormRepeatingGroupBlock)]
    assert len(activities) == 4
    assert sum(len(block.columns) for block in activities) == 70
    assert all(
        column.export_field_id and "m303-2026" not in column.export_field_id
        for block in activities
        for column in block.columns
    )
    refund = layout.pages[5].sections[0].blocks[0]
    assert isinstance(refund, FormFieldBlock) and refund.casilla_id == "111"
    assert layout.pages[3].condition_periods == ("4T", "12")
    assert layout.review.state == "generated"

    # A visually identical field from another year's export is not a valid owner.
    first_context = contexts["nif"]
    foreign_field = next(
        block.export_field_id
        for section in _revision().form_layouts[0].pages[0].sections
        for block in section.blocks
        if isinstance(block, FormContextFieldBlock) and block.id == "nif"
    )
    corrupted = FormLayoutDefinition.model_validate_json(
        layout.model_dump_json().replace(first_context.export_field_id, foreign_field)
    )
    assert form_layout_failures(revision.model_copy(update={"form_layouts": (corrupted,)}))


@pytest.mark.parametrize(("revision_id", "count"), [("2023", 219), ("2024-hasta-08-y-2t", 220)])
def test_complementaria_editions_do_not_inherit_rectificativa_fields(revision_id: str, count: int) -> None:
    revision = load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/303")).revisions[revision_id]
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert len(layout.pages) == 6
    assert len(layout.placements) == len(revision.casillas) == count
    assert all(str(158996 + n) in (page.official_ref or "") for n, page in enumerate(layout.pages))
    assert {source.source_ref for source in layout.design_sources} >= {"boe-modelo-303-2023-form-pdf"}
    amendment = layout.pages[2].sections[-1]
    assert amendment.id == "complementaria"
    assert lookup_translation(amendment.heading_key, locale="es") == "Complementaria (5)"
    assert [block.id for block in amendment.blocks] == ["justificante"]
    assert not {p.casilla_id for p in layout.placements} & {
        "108",
        "111",
        "112",
        "165",
        "166",
        "167",
        "168",
        "169",
        "170",
    }
    rate = next(
        cell
        for section in layout.pages[0].sections
        for block in section.blocks
        if isinstance(block, FormGridBlock)
        for row in block.rows
        for cell in row.cells
        if cell.casilla_id == "17"
    )
    # Later editions fix this wire field to zero; the historical input remains editable.
    assert rate.kind == "casilla" and rate.literal is None
    contexts = [
        block
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormContextFieldBlock)
    ]
    assert all("m303-2025" not in block.export_field_id for block in contexts)
    assert all(resolve_form_context_field(revision, block) for block in contexts)
    assert layout.review.state == "generated"


def test_official_page_order_and_scalar_simplified_totals() -> None:
    revision = _revision()
    layout = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert len(layout.pages) == 6
    assert all(str(12129 + n) in (page.official_ref or "") for n, page in enumerate(layout.pages))
    simplified = layout.pages[1]
    assert [
        block.casilla_id
        for section in simplified.sections
        for block in section.blocks
        if isinstance(block, FormFieldBlock)
    ] == ["47", "48", "49", "50", "51", "52", "53", "54", "55", "56", "57", "58"]
    activities = [
        block
        for section in simplified.sections
        for block in section.blocks
        if isinstance(block, FormRepeatingGroupBlock)
    ]
    assert len(activities) == 4
    assert sum(len(block.columns) for block in activities) == 70
    assert all(block.max_rows == 3 for block in activities)
    assert all(column.export_field_id and column.casilla_id is None for block in activities for column in block.columns)
    annual = layout.pages[3]
    assert annual.condition_periods == ("4T", "12")
    assert annual.condition == "period_restricted"
    annual_context = [
        block for section in annual.sections for block in section.blocks if isinstance(block, FormContextFieldBlock)
    ]
    assert [block.export_field_id for block in annual_context] == [f"m303-2026.dp30304.f{n:03}" for n in range(6, 19)]
    assert all(resolve_form_context_field(revision, block).projection_ref is not None for block in annual_context)
    assert len(layout.placements) == len(revision.casillas) == 229
    assert not any(placement.kind == "unplaced" for placement in layout.placements)
    # Placement coverage is not a claim of full paper or temporal fidelity.
    assert layout.review.state == "generated"
    assert "January2026 and first-quarter2026" in (layout.review.notes or "")
    assert "extra electronic activity worksheets" in (layout.review.notes or "")


def test_context_uses_existing_filing_owners_and_exact_regime_codes() -> None:
    revision = _revision()
    contexts = {
        block.id: block
        for page in revision.form_layouts[0].pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormContextFieldBlock)
    }
    assert resolve_form_context_field(revision, contexts["nif"]).producer_key == "taxpayer.tax_id"
    assert resolve_form_context_field(revision, contexts["iban"]).producer_key == "selected_account.iban"
    assert (
        resolve_form_context_field(revision, contexts["justificante"]).producer_key
        == "amendment_evidence.original_aeat_receipt"
    )
    assert [
        (choice.value, lookup_translation(choice.heading_key, locale="es")) for choice in contexts["regimen"].choices
    ] == [
        ("1", "Solo régimen simplificado"),
        ("2", "Régimen general y simplificado"),
        ("3", "Solo régimen general"),
    ]
    assert {choice.value for choice in contexts["gasolinas"].choices} == {"0", "1", "2"}


def test_refund_111_is_on_payment_page_and_deduction_rows_keep_their_meaning() -> None:
    layout = _revision().form_layouts[0]
    pages_for_111 = [
        n
        for n, page in enumerate(layout.pages, 1)
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormFieldBlock) and block.casilla_id == "111"
    ]
    assert pages_for_111 == [6]
    groups = layout.pages[4].sections[1:]
    for group, first in zip(groups, (700, 718), strict=True):
        grid = group.blocks[0]
        assert isinstance(grid, FormGridBlock)
        assert [[cell.casilla_id for cell in row.cells] for row in grid.rows] == [
            [str(first + offset), str(first + offset + 1)] for offset in range(0, 16, 2)
        ]
        # A current-goods row must still tell the reader whether it is domestic,
        # imported or intra-EU after combining the former fragmented sections.
        labels = [lookup_translation(row.heading_key, locale="es") for row in grid.rows]
        assert str(labels[0]).startswith("Operaciones interiores:")
        assert str(labels[2]).startswith("Importaciones:")
        assert str(labels[4]).startswith("Adquisiciones intracomunitarias:")


@pytest.mark.parametrize("locale", ["es", "en", "ca", "hu"])
def test_authored_headings_are_available_in_every_locale(locale: str) -> None:
    layout = _revision().form_layouts[0]
    keys = {page.heading_key for page in layout.pages}
    for page in layout.pages:
        for section in page.sections:
            keys.add(section.heading_key)
            for block in section.blocks:
                if isinstance(block, FormContextFieldBlock):
                    keys.add(block.heading_key)
                    keys.update(choice.heading_key for choice in block.choices)
                if isinstance(block, FormGridBlock):
                    keys.update(row.heading_key for row in block.rows)
                    keys.update(column.heading_key for column in block.columns)
                if isinstance(block, FormRepeatingGroupBlock):
                    keys.update(column.heading_key for column in block.columns)
    assert all(lookup_translation(key, locale=locale) for key in keys)


def test_lost_advance_payment_casilla_fails_layout_integrity() -> None:
    revision = _revision()
    layout = revision.form_layouts[0]
    broken = layout.model_copy(update={"placements": tuple(p for p in layout.placements if p.casilla_id != "112")})
    assert form_layout_failures(revision.model_copy(update={"form_layouts": (broken,)}))


def test_missing_context_owner_fails_layout_integrity() -> None:
    revision = _revision()
    layout = revision.form_layouts[0]
    page = layout.pages[0]
    identity = page.sections[0]
    broken_nif = identity.blocks[0].model_copy(update={"export_field_id": "missing-taxpayer-field"})
    identity = identity.model_copy(update={"blocks": (broken_nif, *identity.blocks[1:])})
    page = page.model_copy(update={"sections": (identity, *page.sections[1:])})
    layout = layout.model_copy(update={"pages": (page, *layout.pages[1:])})
    assert form_layout_failures(revision.model_copy(update={"form_layouts": (layout,)}))


def test_changed_activity_slot_invalidates_the_authored_source_digest() -> None:
    revision = _revision()
    export = revision.export_layouts[0]
    record = next(record for record in export.records if record.id == "m303-regimen-simplificado")
    field = next(field for field in record.fields if field.id == "m303-2026.dp30302.f024")
    assert field.projection_ref is not None
    changed = field.model_copy(update={"projection_ref": field.projection_ref.model_copy(update={"slot": 2})})
    record = record.model_copy(
        update={"fields": tuple(changed if item.id == field.id else item for item in record.fields)}
    )
    export = export.model_copy(
        update={"records": tuple(record if item.id == record.id else item for item in export.records)}
    )
    broken = revision.model_copy(update={"export_layouts": (export,)})
    assert any("stale" in failure for failure in form_layout_failures(broken))


def test_changed_annual_activity_slot_invalidates_the_authored_source_digest() -> None:
    revision = _revision()
    export = revision.export_layouts[0]
    record = next(record for record in export.records if record.id == "m303-exonerado-390")
    field = next(field for field in record.fields if field.id == "m303-2026.dp30304.f006")
    assert field.projection_ref is not None
    changed = field.model_copy(update={"projection_ref": field.projection_ref.model_copy(update={"slot": 2})})
    record = record.model_copy(
        update={"fields": tuple(changed if item.id == field.id else item for item in record.fields)}
    )
    export = export.model_copy(
        update={"records": tuple(record if item.id == record.id else item for item in export.records)}
    )
    broken = revision.model_copy(update={"export_layouts": (export,)})
    assert any("stale" in failure for failure in form_layout_failures(broken))
