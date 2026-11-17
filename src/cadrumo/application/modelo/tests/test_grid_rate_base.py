"""A grid row serves its one rate box and whether the amount that rate applies to, in the declared base column, is empty."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..work_form_models import ModeloFormGridBlock, ModeloFormGridRow, ModeloWorkForm
from .work_form_fixture import built_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _form_303(operation: PinnedAuthorityOperation, held: dict[str, Decimal | str] | None = None) -> ModeloWorkForm:
    return built_form(operation, "303", operation.supported_filing_years().horizon, "1T", held=held, calculated=True)


def _row_with(form: ModeloWorkForm, box: str) -> tuple[ModeloFormGridBlock, ModeloFormGridRow]:
    return next(
        (block, row)
        for page in form.pages
        for section in page.sections
        for block in section.blocks
        if isinstance(block, ModeloFormGridBlock)
        for row in block.rows
        if any(cell.field is not None and cell.field.box == box for cell in row.cells)
    )


def test_a_rate_row_names_its_rate_box_and_says_its_base_is_empty_until_the_base_holds_an_amount(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    block, empty = _row_with(_form_303(authority_operation), "165")
    _block, held = _row_with(_form_303(authority_operation, {"165": Decimal("100.00")}), "165")

    assert empty.rate_cell is not None
    rate = empty.cells[empty.rate_cell].field
    assert rate is not None
    assert rate.box == "166"
    assert [column.key for column in block.columns][empty.rate_cell] == "tipo"
    assert empty.rate_base_empty is True
    assert held.rate_base_empty is False


def test_a_held_zero_base_is_still_an_empty_base(authority_operation: PinnedAuthorityOperation) -> None:
    _block, row = _row_with(_form_303(authority_operation, {"165": Decimal("0.00")}), "165")

    assert row.rate_base_empty is True


def test_a_rate_beside_a_column_that_is_no_base_has_no_base(authority_operation: PinnedAuthorityOperation) -> None:
    block, row = _row_with(_form_303(authority_operation), "500")

    assert row.rate_cell is not None
    assert [column.key for column in block.columns][row.rate_cell - 1] == "tipo_prorrata"
    assert row.rate_base_empty is None


def test_a_row_without_a_rate_names_no_rate_box(authority_operation: PinnedAuthorityOperation) -> None:
    _block, row = _row_with(_form_303(authority_operation), "28")

    assert row.rate_cell is None
    assert row.rate_base_empty is None
