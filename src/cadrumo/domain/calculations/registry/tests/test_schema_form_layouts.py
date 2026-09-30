"""Structural invariants of the declared form layout family.

Each refusal is exercised beside the accepted shape it departs from, so a test
proves the model rejects exactly the defect and not the whole family.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import TypeAdapter, ValidationError

from ..schema_form_layouts import (
    FormAliasPosition,
    FormBindingInputsBlock,
    FormBlockDefinition,
    FormCell,
    FormCellKind,
    FormFieldBlock,
    FormGridBlock,
    FormGridColumn,
    FormGridRow,
    FormLayoutDefinition,
    FormLayoutReview,
    FormLayoutReviewState,
    FormPageCondition,
    FormPageDefinition,
    FormPlacementDefinition,
    FormPlacementKind,
    FormRepeatingGroupBlock,
    FormRepeatingRowSource,
    FormSectionDefinition,
    FormUnplacedReason,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DIGEST = "a" * 64


def _columns() -> tuple[FormGridColumn, ...]:
    return (
        FormGridColumn(key="base_imponible", heading_key="modelo.form.column.base_imponible"),
        FormGridColumn(key="tipo", heading_key="modelo.form.column.tipo"),
        FormGridColumn(key="cuota", heading_key="modelo.form.column.cuota"),
    )


def _row(*cells: FormCell) -> FormGridRow:
    return FormGridRow(key="r1", heading_key="modelo.schema.303.form.p1.s1.row.r1.heading", cells=cells)


def _layout(**overrides: object) -> FormLayoutDefinition:
    section = FormSectionDefinition(
        id="s1",
        heading_key="modelo.schema.303.form.p1.s1.heading",
        official_heading="Liquidación (3) - Régimen General - IVA Devengado",
        blocks=(FormFieldBlock(id="b1", casilla_id="01"),),
    )
    page = FormPageDefinition(
        id="p1", official_ref="DP30301", heading_key="modelo.schema.303.form.p1.heading", sections=(section,)
    )
    payload: dict[str, object] = {
        "id": "form-layout",
        "revision_id": "2025",
        "seed_source": "export_record_design",
        "generator_version": 1,
        "source_state_digest": _DIGEST,
        "pages": (page,),
        "placements": (FormPlacementDefinition(casilla_id="01", kind=FormPlacementKind.ON_FORM, box_number="01"),),
        "legal_refs": ("ley-37-1992:art-164",),
        "source_refs": ("aeat-dr-303-2025",),
    }
    payload.update(overrides)
    return FormLayoutDefinition.model_validate(payload)


def test_a_complete_layout_validates_and_round_trips_through_its_serialised_form() -> None:
    layout = _layout()
    assert layout.review.state is FormLayoutReviewState.GENERATED
    assert FormLayoutDefinition.model_validate(layout.model_dump(mode="json"), strict=False) == layout


def test_a_grid_row_narrower_than_its_columns_is_refused() -> None:
    cells = (FormCell(kind=FormCellKind.CASILLA, casilla_id="01"), FormCell(kind=FormCellKind.BLANK))
    with pytest.raises(ValidationError, match="has 2 cells for 3 columns"):
        FormGridBlock(id="g1", columns=_columns(), rows=(_row(*cells),))
    full = (*cells, FormCell(kind=FormCellKind.CASILLA, casilla_id="03"))
    assert len(FormGridBlock(id="g1", columns=_columns(), rows=(_row(*full),)).rows[0].cells) == 3


def test_a_design_constant_cell_must_carry_its_literal() -> None:
    with pytest.raises(ValidationError, match="must carry the design's literal"):
        FormCell(kind=FormCellKind.DESIGN_CONSTANT)
    assert FormCell(kind=FormCellKind.DESIGN_CONSTANT, literal="00400").literal == "00400"


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "casilla"},
        {"kind": "casilla", "binding_id": "b"},
        {"kind": "binding_input", "casilla_id": "01"},
        {"kind": "blank", "casilla_id": "01"},
        {"kind": "blank", "literal": "x"},
    ],
)
def test_a_cell_whose_address_disagrees_with_its_kind_is_refused(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        FormCell.model_validate(payload, strict=False)


def test_a_repeating_group_names_the_address_its_row_source_declares() -> None:
    accepted = FormRepeatingGroupBlock(
        id="r1", row_source=FormRepeatingRowSource.ROW_SET_BINDING, binding_id="perceptores", max_rows=10
    )
    assert accepted.binding_id == "perceptores"
    with pytest.raises(ValidationError, match="names the wrong address"):
        FormRepeatingGroupBlock(id="r1", row_source=FormRepeatingRowSource.ROW_SET_BINDING, export_record_id="x")
    with pytest.raises(ValidationError, match="max_rows below min_rows"):
        FormRepeatingGroupBlock(
            id="r1", row_source=FormRepeatingRowSource.EXPORT_RECORD, export_record_id="x", min_rows=3, max_rows=2
        )


def test_blocks_decode_through_the_kind_discriminator() -> None:
    adapter: TypeAdapter[FormBlockDefinition] = TypeAdapter(FormBlockDefinition)
    block = adapter.validate_python({"kind": "binding_inputs", "id": "b", "binding_ids": ["x", "y"]}, strict=False)
    assert isinstance(block, FormBindingInputsBlock)
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "unknown", "id": "b"}, strict=False)


def test_a_field_block_addresses_exactly_one_target() -> None:
    with pytest.raises(ValidationError, match="exactly one casilla or binding"):
        FormFieldBlock(id="b1", casilla_id="01", binding_id="x")
    with pytest.raises(ValidationError, match="exactly one casilla or binding"):
        FormFieldBlock(id="b1")


def test_placement_detail_belongs_to_its_arm() -> None:
    unplaced = FormPlacementDefinition(
        casilla_id="x", kind=FormPlacementKind.UNPLACED, unplaced_reason=FormUnplacedReason.NO_OFFICIAL_ANCHOR
    )
    assert unplaced.unplaced_reason is FormUnplacedReason.NO_OFFICIAL_ANCHOR
    with pytest.raises(ValidationError, match="unplaced arm"):
        FormPlacementDefinition(casilla_id="x", kind=FormPlacementKind.UNPLACED)
    with pytest.raises(ValidationError, match="unplaced arm"):
        FormPlacementDefinition(
            casilla_id="x", kind=FormPlacementKind.ON_FORM, unplaced_reason=FormUnplacedReason.PENDING_REVIEW
        )
    with pytest.raises(ValidationError, match="only an on-form placement"):
        FormPlacementDefinition(
            casilla_id="x",
            kind=FormPlacementKind.WORKING_FIGURE,
            aliases=(FormAliasPosition(page_id="p1", section_id="s1"),),
        )


def test_page_conditions_carry_exactly_their_declared_operand() -> None:
    section = _layout().pages[0].sections[0]
    gated = FormPageDefinition(
        id="p2",
        heading_key="modelo.schema.303.form.p2.heading",
        condition=FormPageCondition.REQUIRES_POSITIVE_CASILLA,
        condition_casilla_id="01",
        sections=(section,),
    )
    assert gated.condition_casilla_id == "01"
    with pytest.raises(ValidationError, match="disagrees with its casilla"):
        FormPageDefinition(
            id="p2",
            heading_key="modelo.schema.303.form.p2.heading",
            condition=FormPageCondition.REQUIRES_POSITIVE_CASILLA,
            sections=(section,),
        )
    with pytest.raises(ValidationError, match="disagrees with its periods"):
        FormPageDefinition(
            id="p2", heading_key="modelo.schema.303.form.p2.heading", condition_periods=("4T",), sections=(section,)
        )


def test_review_state_binds_a_reviewer_to_a_review_claim() -> None:
    reviewed = FormLayoutReview(state=FormLayoutReviewState.REVIEWED, reviewer="reviewer", reviewed_at=date(2026, 9, 1))
    assert reviewed.reviewer == "reviewer"
    with pytest.raises(ValidationError, match="names its reviewer"):
        FormLayoutReview(state=FormLayoutReviewState.REVIEWED, reviewer="reviewer")
    with pytest.raises(ValidationError, match="carries no reviewer"):
        FormLayoutReview(reviewer="reviewer")


def test_a_layout_refuses_duplicate_placements_and_dangling_aliases() -> None:
    duplicate = (
        FormPlacementDefinition(casilla_id="01", kind=FormPlacementKind.ON_FORM),
        FormPlacementDefinition(casilla_id="01", kind=FormPlacementKind.WORKING_FIGURE),
    )
    with pytest.raises(ValidationError, match="duplicate placements"):
        _layout(placements=duplicate)
    dangling = (
        FormPlacementDefinition(
            casilla_id="01",
            kind=FormPlacementKind.ON_FORM,
            aliases=(FormAliasPosition(page_id="p9", section_id="s1"),),
        ),
    )
    with pytest.raises(ValidationError, match="aliases unknown section"):
        _layout(placements=dangling)
    with pytest.raises(ValidationError, match="not a lowercase SHA-256"):
        _layout(source_state_digest="A" * 64)


def test_a_design_constant_may_name_the_casilla_printed_at_its_box() -> None:
    cell = FormCell(kind=FormCellKind.DESIGN_CONSTANT, casilla_id="02", literal="00400")
    assert (cell.casilla_id, cell.literal) == ("02", "00400")
    with pytest.raises(ValidationError, match="names the wrong address"):
        FormCell(kind=FormCellKind.DESIGN_CONSTANT, binding_id="b", literal="00400")


def test_a_field_fixes_a_design_constant_only_on_a_casilla() -> None:
    assert FormFieldBlock(id="f", casilla_id="02", design_constant="00400").design_constant == "00400"
    with pytest.raises(ValidationError, match="fixes a design constant on no casilla"):
        FormFieldBlock(id="f", binding_id="b", design_constant="00400")


def test_casilla_sections_lists_every_shown_casilla_at_its_section() -> None:
    assert _layout().casilla_sections() == {"01": ("p1", "s1")}
