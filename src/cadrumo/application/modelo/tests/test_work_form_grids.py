"""The editor form reads an official grid's rate boxes and repeating columns as the published design states them.

Every form here is built by the real read model from the published authority.
The Modelo 303 accrued-IVA grid prints its rates in two ways: some rows' base
bindings declare exactly one rate, and some rate boxes are literals of the
official record design ("00400", "02100"). A literal is read as a rate only
where it states a percentage outright or its export field declares its scale;
nothing is inferred from neighbouring rows, and a literal of zeros is the
design's placeholder and never a rate. The fixtures that change a literal are
the published layout with that one literal replaced.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

import pytest

from ....core.external_constants import OutputLanguage
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_form_layouts import (
    FormCellKind,
    FormGridBlock,
    FormLayoutDefinition,
    FormRepeatingGroupBlock,
)
from ....domain.modelos.codes import ModeloCode
from ..work_form import build_modelo_work_form
from ..work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormGridBlock,
    ModeloFormRepeatingBlock,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    section_fields,
)
from ..work_form_service import modelo_form_snapshot
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LITERAL_RATES_303 = {
    "02": Decimal("0.04"),
    "05": Decimal("0.10"),
    "08": Decimal("0.21"),
    "157": Decimal("0.0175"),
    "20": Decimal("0.014"),
    "23": Decimal("0.052"),
}
"""Printed rate percentages independently stated by the official Modelo 303 instructions."""
_PLACEHOLDERS_303 = ("151", "17")
"""Fixed rate boxes whose literal is ``00000``: the design prints no rate there."""


def _layout(operation: PinnedAuthorityOperation, modelo: str, revision_id: str) -> FormLayoutDefinition:
    layout = operation.form_layout(modelo, revision_id)
    assert layout is not None
    return layout


def _form(
    operation: PinnedAuthorityOperation,
    modelo: str,
    year: int,
    code: str,
    *,
    literals: Mapping[str, str] | None = None,
    layout_override: FormLayoutDefinition | None = None,
) -> ModeloWorkForm:
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    snapshot = modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000451",
        modelo=modelo,
        filing_year=year,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id="c" * 64,
        calculation_revision_id=None,
        lifecycle_state=None,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation),
        findings=(),
        blockers=(),
    )
    layout = layout_override or _layout(operation, modelo, str(snapshot.revision.id))
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=layout if literals is None else _with_literals(layout, literals),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=OutputLanguage.EN,
    )


def _with_literals(layout: FormLayoutDefinition, literals: Mapping[str, str]) -> FormLayoutDefinition:
    """The published layout with the literal of some fixed boxes replaced, everything else untouched."""
    pages = []
    for page in layout.pages:
        sections = []
        for section in page.sections:
            blocks = []
            for block in section.blocks:
                if isinstance(block, FormGridBlock):
                    rows = tuple(
                        row.model_copy(
                            update={
                                "cells": tuple(
                                    cell.model_copy(update={"literal": literals[str(cell.casilla_id)]})
                                    if cell.kind is FormCellKind.DESIGN_CONSTANT and str(cell.casilla_id) in literals
                                    else cell
                                    for cell in row.cells
                                )
                            }
                        )
                        for row in block.rows
                    )
                    block = block.model_copy(update={"rows": rows})
                blocks.append(block)
            sections.append(section.model_copy(update={"blocks": tuple(blocks)}))
        pages.append(page.model_copy(update={"sections": tuple(sections)}))
    return layout.model_copy(update={"pages": tuple(pages)})


def _by_box(form: ModeloWorkForm) -> dict[str, ModeloFormField]:
    return {field.box: field for field in form.fields() if field.box is not None}


def _form_303(operation: PinnedAuthorityOperation, literals: Mapping[str, str] | None = None) -> ModeloWorkForm:
    return _form(operation, "303", 2026, "1T", literals=literals)


def test_published_literal_scales_print_the_official_rates(operation: PinnedAuthorityOperation) -> None:
    boxes = _by_box(_form_303(operation))

    for box, ratio in _LITERAL_RATES_303.items():
        printed = boxes[box].printed_rate
        assert printed is not None and printed.ratio == ratio, box
        assert boxes[box].value == ratio * 100, box
    # A rate the row's base binding declares is still shown, from the binding and never from the literal.
    for box, ratio in {"02": Decimal("0.04"), "05": Decimal("0.10")}.items():
        grounded = boxes[box].grounded_rate
        assert grounded is not None and grounded.ratio == ratio, box
    for box in ("08", "157", "20", "23"):
        assert boxes[box].grounded_rate is None, box
    for box in _PLACEHOLDERS_303:
        assert boxes[box].printed_rate is None, box
        assert boxes[box].grounded_rate is None, box


def test_a_numeric_literal_without_declared_scale_claims_no_printed_rate(operation: PinnedAuthorityOperation) -> None:
    revision = operation.revision_for_context("303", filing_year=2026, period="1T")
    published = _layout(operation, "303", str(revision.id))
    unscaled = published.model_copy(
        update={
            "pages": tuple(
                page.model_copy(
                    update={
                        "sections": tuple(
                            section.model_copy(
                                update={
                                    "blocks": tuple(
                                        block.model_copy(
                                            update={
                                                "rows": tuple(
                                                    row.model_copy(
                                                        update={
                                                            "cells": tuple(
                                                                cell.model_copy(update={"literal_decimals": None})
                                                                for cell in row.cells
                                                            )
                                                        }
                                                    )
                                                    for row in block.rows
                                                )
                                            }
                                        )
                                        if isinstance(block, FormGridBlock)
                                        else block
                                        for block in section.blocks
                                    )
                                }
                            )
                            for section in page.sections
                        )
                    }
                )
                for page in published.pages
            )
        }
    )
    boxes = _by_box(_form(operation, "303", 2026, "1T", layout_override=unscaled))
    assert all(boxes[box].printed_rate is None for box in _LITERAL_RATES_303)


def test_a_literal_that_states_its_percentage_is_printed_as_it_says(operation: PinnedAuthorityOperation) -> None:
    boxes = _by_box(_form_303(operation, {"23": "5,2 %", "08": "21%"}))

    for box, ratio in {"23": Decimal("0.052"), "08": Decimal("0.21")}.items():
        printed = boxes[box].printed_rate
        assert printed is not None and printed.ratio == ratio, box
    assert boxes["20"].printed_rate is not None
    assert boxes["20"].printed_rate.ratio == Decimal("0.014")
    # Only a box the design fixes prints a rate.
    assert all(
        field.printed_rate is None
        for field in boxes.values()
        if field.editability is not ModeloFormEditability.DESIGN_CONSTANT
    )


def test_a_placeholder_rate_box_claims_no_rate_even_where_its_base_declares_one(
    operation: PinnedAuthorityOperation,
) -> None:
    published = _by_box(_form_303(operation))["02"]
    zeroed = _by_box(_form_303(operation, {"02": "00000"}))["02"]

    assert published.grounded_rate is not None
    assert zeroed.grounded_rate is None
    assert zeroed.printed_rate is None


def test_every_390_grid_cell_shows_an_official_box_number_or_none(operation: PinnedAuthorityOperation) -> None:
    form = _form(operation, "390", 2025, "0A")
    cells = [
        cell.field
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormGridBlock)
        for row in block.rows
        for cell in row.cells
        if cell.field is not None
    ]
    named = [field for field in cells if isinstance(field.address, ModeloFormCasillaAddressV1)]

    assert named, "the 390 grids place casillas"
    # The page 2 casillas are keyed by ids such as iva.anual.repercutido.tipo-21.base; none is shown as a box.
    assert any(
        not str(field.address.casilla_id).isdigit()
        for field in named
        if isinstance(field.address, ModeloFormCasillaAddressV1)
    )
    for field in cells:
        assert field.box is None or field.box.isdigit(), field.box
    for field in named:
        address = field.address
        assert isinstance(address, ModeloFormCasillaAddressV1)
        assert field.box != str(address.casilla_id) or str(address.casilla_id).isdigit(), field.box


def test_a_repeating_column_the_design_leaves_unnamed_reads_as_the_label_of_its_box(
    operation: PinnedAuthorityOperation,
) -> None:
    revision = operation.revision_for_context("349", filing_year=2026, period="1T")
    published = _layout(operation, "349", str(revision.id))
    layout = published.model_copy(
        update={
            "pages": tuple(
                page.model_copy(
                    update={
                        "sections": tuple(
                            section.model_copy(
                                update={
                                    "blocks": tuple(
                                        block.model_copy(
                                            update={
                                                "columns": tuple(
                                                    column.model_copy(update={"official_heading": None})
                                                    for column in block.columns
                                                )
                                            }
                                        )
                                        if isinstance(block, FormRepeatingGroupBlock)
                                        else block
                                        for block in section.blocks
                                    )
                                }
                            )
                            for section in page.sections
                        )
                    }
                )
                for page in published.pages
            )
        }
    )
    form = _form(operation, "349", 2026, "1T", layout_override=layout)
    declared = {
        block.id: block
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, FormRepeatingGroupBlock)
    }
    shown = [
        block
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormRepeatingBlock)
    ]

    assert shown
    for block in shown:
        for column, source in zip(block.columns, declared[block.id].columns, strict=True):
            assert source.official_heading is None, "the design names this column; the fallback is not exercised"
            assert column.heading.disclosure is not ModeloFormTextDisclosure.TECHNICAL, column.key
            assert column.heading.text != column.key
    # The form stays total: the repeating columns are not also shown as single boxes.
    placed = {
        str(field.address.casilla_id)
        for page in form.pages
        for section in page.sections
        for field in section_fields(section)
        if isinstance(field.address, ModeloFormCasillaAddressV1)
    }
    assert not placed & {casilla for block in shown for casilla in block.column_casilla_ids if casilla is not None}
