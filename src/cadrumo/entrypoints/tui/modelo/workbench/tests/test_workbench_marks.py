"""Every mark the workbench draws means one thing, and a section shows the most severe one it holds.

The registry refuses, at import and for any set handed to it, a glyph that
means two things or a meaning drawn two ways; the navigator's section mark
ranks a blocker above a missing value above an assumed one.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final, override

import pytest
from textual.app import App, ComposeResult

from ......application.modelo.work_form_models import (
    ModeloFormBlocker,
    ModeloFormCounts,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
    ModeloFormGridCell,
    ModeloFormGridColumn,
    ModeloFormGridRow,
    ModeloFormOrigin,
    ModeloFormPage,
    ModeloFormSection,
    ModeloFormText,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
)
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import lookup_translation
from ......domain.calculations.registry.schema_form_layouts import FormCellKind, FormPageCondition
from ....components.theme import install_cadrumo_themes
from ..casilla_list import CasillaList, CasillaListEntry, CasillaListHeading, CasillaListItem
from ..header import ChipLevel, attention_chips
from ..navigator import NavigatorState, navigator_rows
from ..page_items import (
    WorkbenchPage,
    page_items,
    section_heading_text,
    section_mark,
    section_nav_text,
    workbench_pages,
)
from ..vocabulary import (
    BLOCKS_MARK,
    CHECK_MARK,
    CONFIRM_MARK,
    DONE_MARK,
    HERE_MARK,
    MISSING_MARK,
    ORIGIN_MARKS,
    ORIGIN_STANDINGS,
    WORKBENCH_MARKS,
    Standing,
    WorkbenchMark,
    origin_words,
    require_one_meaning_per_glyph,
)
from .workbench_fixture import form_field, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_the_shipped_marks_give_each_glyph_one_meaning_and_each_meaning_one_glyph() -> None:
    require_one_meaning_per_glyph(WORKBENCH_MARKS)

    # A glyph repeats across surfaces only as the same meaning: the row's blocker is the stepper's.
    assert BLOCKS_MARK.translation_key == "tui.modelo.workbench.level.blocks"
    # The marks that used to mean two things now mean one.
    by_glyph = {mark.glyph: mark.translation_key for mark in WORKBENCH_MARKS}
    assert by_glyph["●"] == "tui.modelo.workbench.origin.entered"
    assert by_glyph["○"] == "tui.modelo.workbench.origin.optional_empty"
    assert by_glyph["!"] == "tui.modelo.workbench.origin.needs_input"
    assert HERE_MARK.glyph == "▸"
    assert CHECK_MARK.glyph == "◆"


def test_every_mark_has_words_in_every_language() -> None:
    for mark in WORKBENCH_MARKS:
        for locale in ("es", "en", "ca", "hu"):
            assert lookup_translation(mark.translation_key, locale=locale), (mark, locale)


def test_a_glyph_given_a_second_meaning_is_refused() -> None:
    entered = ORIGIN_MARKS[ModeloFormOrigin.ENTERED]
    current_step = WorkbenchMark(entered.glyph, translation_key="tui.modelo.workbench.legend.name.here")

    with pytest.raises(ValueError, match="means more than one thing"):
        require_one_meaning_per_glyph((*WORKBENCH_MARKS, current_step))


def test_a_meaning_drawn_with_a_second_glyph_is_refused() -> None:
    second_done = WorkbenchMark("✔", translation_key=DONE_MARK.translation_key)

    with pytest.raises(ValueError, match="more than one glyph"):
        require_one_meaning_per_glyph((*WORKBENCH_MARKS, second_done))


def test_repeating_a_mark_with_its_own_meaning_is_allowed() -> None:
    require_one_meaning_per_glyph((*WORKBENCH_MARKS, BLOCKS_MARK, DONE_MARK))


def _section(*fields: ModeloFormField) -> ModeloFormSection:
    return ModeloFormSection(
        id="s1",
        heading=ModeloFormText(text="I. Activities", disclosure=ModeloFormTextDisclosure.LOCALIZED),
        official_heading=None,
        blocks=tuple(ModeloFormFieldBlock(id=f"f{item.box}", field=item) for item in fields),
        counts=ModeloFormCounts(
            total=len(fields),
            needs_input=sum(1 for item in fields if item.origin is ModeloFormOrigin.NEEDS_INPUT),
            entered=0,
            imported=0,
            calculated=0,
            overridden=0,
            default_to_confirm=sum(1 for item in fields if item.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM),
            not_applicable=0,
            blocked=sum(1 for item in fields if item.blockers),
        ),
    )


def test_a_section_shows_the_most_severe_thing_it_still_holds() -> None:
    entered = form_field("01", "Income", ModeloFormOrigin.ENTERED, Decimal("1"))
    assumed = form_field("02", "Expenses", ModeloFormOrigin.DEFAULT_TO_CONFIRM, Decimal("0"))
    missing = form_field("03", "Withholdings", ModeloFormOrigin.NEEDS_INPUT)
    blocked = form_field("04", "Payments", ModeloFormOrigin.ENTERED, Decimal("2")).model_copy(
        update={"blockers": (ModeloFormBlocker(code="synthetic_blocker"),)}
    )

    assert section_mark(_section(entered)) == DONE_MARK
    assert section_mark(_section(entered, assumed)) == CONFIRM_MARK
    assert section_mark(_section(assumed, missing)) == MISSING_MARK
    assert section_mark(_section(assumed, missing, blocked)) == BLOCKS_MARK
    with override_settings(cadrumo_output_language="en"):
        assert section_nav_text(_section(assumed, missing, blocked), 40) == "▲ I. Activities (3)"
        assert section_nav_text(_section(entered, assumed), 40) == "◐ I. Activities (1)"
        assert section_nav_text(_section(entered), 40) == "✓ I. Activities"
        assert section_heading_text(_section(entered, missing)).startswith("! ")


def test_an_informational_value_reads_as_a_reference_value() -> None:
    reference = form_field("99", "Rate", ModeloFormOrigin.INFORMATIONAL, Decimal("21"))

    with override_settings(cadrumo_output_language="en"):
        assert origin_words(reference) == "Reference value"
    with override_settings(cadrumo_output_language="es"):
        assert origin_words(reference) == "Valor de referencia"


_EXPECTED_LEVELS: Final[dict[ModeloFormOrigin, str]] = {
    ModeloFormOrigin.NEEDS_INPUT: "!",
    ModeloFormOrigin.DEFAULT_TO_CONFIRM: "◐",
    ModeloFormOrigin.CALCULATION_FAILED: "×",
    ModeloFormOrigin.NOT_IMPORTED_YET: "…",
    ModeloFormOrigin.NOT_CALCULATED_YET: "◌",
}
"""The mark each origin that is not done shows wherever a section, a page or a grid row is marked."""
_ACTIONABLE: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {ModeloFormOrigin.NEEDS_INPUT, ModeloFormOrigin.DEFAULT_TO_CONFIRM, ModeloFormOrigin.CALCULATION_FAILED}
)
"""The origins the filer can act on; a box waiting on an import or a calculation is not one."""
_HELD: Final[frozenset[ModeloFormOrigin]] = frozenset(
    {
        ModeloFormOrigin.DEFAULT_TO_CONFIRM,
        ModeloFormOrigin.ENTERED,
        ModeloFormOrigin.IMPORTED,
        ModeloFormOrigin.CALCULATED,
        ModeloFormOrigin.OVERRIDES_SOURCE,
        ModeloFormOrigin.INFORMATIONAL,
    }
)


def _one_box_per_origin() -> dict[ModeloFormOrigin, ModeloFormField]:
    return {
        origin: form_field(f"{number:02d}", origin.value, origin, Decimal("5") if origin in _HELD else None)
        for number, origin in enumerate(ModeloFormOrigin, start=1)
    }


def _form_with(sections: tuple[ModeloFormSection, ...], fields: list[ModeloFormField]) -> ModeloWorkForm:
    page = ModeloFormPage(
        id="p1",
        heading=ModeloFormText(text="Liquidación", disclosure=ModeloFormTextDisclosure.LOCALIZED),
        official_ref=None,
        condition=FormPageCondition.ALWAYS,
        applies=True,
        sections=sections,
        counts=_section(*fields).counts,
    )
    return synthetic_form().model_copy(
        update={
            "pages": (page,),
            "working_figures": (),
            "unplaced": (),
            "result_addresses": (),
            "issues": (),
            "counts": page.counts,
        }
    )


class _GridHarness(App[None]):
    def __init__(self, items: tuple[CasillaListItem, ...]) -> None:
        super().__init__()
        self._items = items

    @override
    def compose(self) -> ComposeResult:
        yield CasillaList(self._items, language=OutputLanguage.EN)

    def on_mount(self) -> None:
        install_cadrumo_themes(self, appearance="dark")


@pytest.mark.asyncio
async def test_the_navigator_the_list_a_grid_row_n_and_the_header_class_every_origin_alike() -> None:
    boxes = _one_box_per_origin()
    sections = tuple(
        _section(field).model_copy(
            update={
                "id": f"s{field.box}",
                "heading": ModeloFormText(text=f"Part {field.box}", disclosure=ModeloFormTextDisclosure.LOCALIZED),
            }
        )
        for field in boxes.values()
    )
    grid = ModeloFormGridBlock(
        id="grid",
        columns=(
            ModeloFormGridColumn(
                key="base", heading=ModeloFormText(text="Base", disclosure=ModeloFormTextDisclosure.LOCALIZED)
            ),
        ),
        rows=tuple(
            ModeloFormGridRow(
                key=f"r{field.box}",
                heading=ModeloFormText(text=f"Row {field.box}", disclosure=ModeloFormTextDisclosure.LOCALIZED),
                cells=(ModeloFormGridCell(kind=FormCellKind.CASILLA, field=field),),
            )
            for field in boxes.values()
        ),
    )
    form = _form_with(sections, list(boxes.values()))
    page = workbench_pages(form)[0]
    grid_page = WorkbenchPage(
        id="grid",
        heading=page.heading,
        sections=(sections[0].model_copy(update={"blocks": (grid,)}),),
    )
    with override_settings(cadrumo_output_language="en"):
        navigator = navigator_rows(
            (page,), current=0, state=NavigatorState(), checked={}, width=80, show_attention=True
        )
        items = page_items(page, staged={})
        chips = {chip.level: chip.count for chip in attention_chips(form, recorded=False)}
        app = _GridHarness(page_items(grid_page, staged={}))
        async with app.run_test(size=(120, 60)) as pilot:
            await pilot.pause()
            widget = app.query_one(CasillaList)
            drawn = [widget.render_line(y).text for y in range(widget.size.height)]

    by_heading = {row.prompt.plain.split()[1] + " " + row.prompt.plain.split()[2]: row for row in navigator[1:]}
    headings = {
        item.text.split(" ", 1)[1].split(" · ")[0]: item for item in items if isinstance(item, CasillaListHeading)
    }
    entries = {item.field.origin: item for item in items if isinstance(item, CasillaListEntry)}
    for origin, field in boxes.items():
        expected = _EXPECTED_LEVELS.get(origin, DONE_MARK.glyph)
        title = f"Part {field.box}"
        navigator_mark = by_heading[title].prompt.plain.split()[0]
        heading = headings[title]
        row_line = next(line for line in drawn if f"[{field.box}]" in line)
        assert navigator_mark == expected, origin
        assert heading.mark is not None and heading.mark.glyph == expected, origin
        assert row_line[1] == (" " if expected == DONE_MARK.glyph else expected), origin
        # "Needs your input" is only ever a missing value, and done never sits over a value not imported or calculated.
        assert (expected == MISSING_MARK.glyph) is (origin is ModeloFormOrigin.NEEDS_INPUT)
        assert (expected == DONE_MARK.glyph) is (ORIGIN_STANDINGS[origin] is Standing.DONE)
        # Only what the filer can act on counts as to do in the heading, and is where n goes.
        needs_you = origin in _ACTIONABLE
        assert (ORIGIN_STANDINGS[origin] is Standing.NEEDS_YOU) is needs_you, origin
        assert entries[origin].needs_filer is needs_you, origin
        assert ("to do: 1" in heading.text) is needs_you, heading.text
    # The page reads as not done, and the header counts exactly what the list and the navigator call missing and assumed.
    assert DONE_MARK.glyph not in navigator[0].prompt.plain
    assert chips == {ChipLevel.MISSING: 1, ChipLevel.CONFIRM: 1}
