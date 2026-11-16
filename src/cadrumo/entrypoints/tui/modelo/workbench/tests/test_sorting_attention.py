"""Ordering the declaration by attention follows the rank the form serves on each field.

The form decides where a box sorts (``ModeloFormField.attention_rank``); the
workbench only orders by it, a staged change breaking a tie ahead of an
unstaged box and form order breaking every other tie.
"""

from __future__ import annotations

import pytest

from ......application.modelo.work_form_field_vocabulary import ModeloFormOrigin, address_key
from ......application.modelo.work_form_models import ModeloFormField
from ..page_items import StagedDisplay, WorkbenchPage
from ..sorting import SortOrder, sorted_items
from .workbench_fixture import form_field, form_section, form_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _page(*fields: ModeloFormField) -> WorkbenchPage:
    return WorkbenchPage(id="p1", heading=form_text("Page"), sections=(form_section("s1", "Section", list(fields)),))


def _order(page: WorkbenchPage, *staged: ModeloFormField) -> list[str | None]:
    change = StagedDisplay(text="10,00", previous_text="5,00")
    entries = sorted_items(
        (page,),
        order=SortOrder.ATTENTION,
        staged={address_key(field.address): change for field in staged},
    )
    return [entry.field.box for entry in entries]


def test_a_staged_change_breaks_a_tie_in_served_rank_and_form_order_breaks_the_rest() -> None:
    first = form_field("01", "First", ModeloFormOrigin.CALCULATED)
    second = form_field("02", "Second", ModeloFormOrigin.CALCULATED)
    third = form_field("03", "Third", ModeloFormOrigin.CALCULATED)

    assert {item.attention_rank for item in (first, second, third)} == {first.attention_rank}
    assert _order(_page(first, second, third), third) == ["03", "01", "02"]
