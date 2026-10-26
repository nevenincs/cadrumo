"""The navigator fits headings to the cells a terminal gives them, not to their code-point count."""

from __future__ import annotations

import pytest
from rich.cells import cell_len

from ......application.modelo.work_form_models import ModeloFormText, ModeloFormTextDisclosure
from ..navigator import NavigatorState, navigator_rows
from ..page_items import WorkbenchPage

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_WIDTH = 24


def _page(heading: str) -> WorkbenchPage:
    return WorkbenchPage(
        id="page-1",
        heading=ModeloFormText(text=heading, disclosure=ModeloFormTextDisclosure.LOCALIZED),
        sections=(),
    )


def _row(heading: str) -> str:
    rows = navigator_rows(
        (_page(heading),), current=0, state=NavigatorState(), checked={}, width=_WIDTH, show_attention=False
    )
    return rows[0].prompt.plain


def test_a_wide_character_heading_is_cut_to_the_navigator_width() -> None:
    line = _row("漢字" * 12)

    assert cell_len(line) <= _WIDTH
    assert line.endswith("…")


def test_a_heading_of_combining_marks_is_not_cut_while_it_fits_the_cells() -> None:
    heading = "é" * 18

    assert _row(heading).endswith(heading)
