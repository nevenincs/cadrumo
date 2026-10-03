"""Official grids read as the paper form's tables, and stack only when the table does not fit.

Every form is built by the real read model from the published authority, and
the lines come from the workbench's own page layout drawn by the real list.
The expected row and column order is read from the published layout's grid
block, not from what the list draws, so the table is checked against the
official order rather than against itself.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from decimal import Decimal
from typing import Final, override

import pytest
from rich.style import Style
from textual.app import App, ComposeResult
from textual.widgets import Static

from ......application.modelo.work_form import build_modelo_work_form
from ......application.modelo.work_form_models import (
    ModeloFormBlocker,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormGridBlock,
    ModeloFormGridCell,
    ModeloFormOrigin,
    ModeloFormRepeatingBlock,
    ModeloFormRepeatingRow,
    ModeloWorkForm,
    address_key,
)
from ......application.modelo.work_form_service import modelo_form_snapshot
from ......application.modelo.work_review import (
    ModeloWorkProgress,
    ModeloWorkReview,
    build_modelo_work_review_casillas,
)
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import lookup_translation
from ......core.modelo_work_progress_state import ModeloWorkProgressState
from ......core.period import Period
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ......domain.calculations.registry.schema_form_layouts import FormCellKind
from ......domain.modelos.codes import ModeloCode
from ....components.host import ScreenHostApp
from ....components.theme import install_cadrumo_themes
from ..casilla_list import (
    CasillaList,
)
from ..casilla_list_models import (
    CasillaListEntry,
    CasillaListHeading,
    CasillaListItem,
)
from ..casilla_list_values import (
    grid_cell_title,
    grid_value_text,
    row_value_text,
    value_text,
)
from ..page_items import StagedDisplay, WorkbenchPage, page_items, workbench_pages
from ..screen import ModeloWorkbenchScreen
from ..vocabulary import (
    ATTENTION_GLYPHS,
    BLOCKS_MARK,
    MISSING_MARK,
    NEEDS_ATTENTION,
    NOT_CALCULATED_MARK,
    NOT_IMPORTED_MARK,
    ORIGIN_STANDINGS,
    Attention,
    Standing,
)
from .workbench_fixture import FakeReader, form_field, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _in_english() -> Iterator[None]:
    """Every text the page lays out, and every line the list draws, in English."""
    with override_settings(cadrumo_output_language="en"):
        yield


_WIDTHS: Final[tuple[int, ...]] = (80, 120, 200)
_NBSP: Final[str] = chr(0xA0)
_ACCRUED_PAGE: Final[str] = "dp30301"
_PRORRATAS_PAGE: Final[str] = "dp30305"


def _form(
    operation: PinnedAuthorityOperation, modelo: str = "303", year: int = 2026, code: str = "1T"
) -> ModeloWorkForm:
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    snapshot = modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000457",
        modelo=modelo,
        filing_year=year,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id="f" * 64,
        calculation_revision_id=None,
        lifecycle_state=None,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation),
        findings=(),
        blockers=(),
    )
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout(modelo, snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=OutputLanguage.EN,
    )


def _page(form: ModeloWorkForm, page_id: str) -> WorkbenchPage:
    return next(page for page in workbench_pages(form) if page.id == page_id)


def _grids(page: WorkbenchPage) -> list[ModeloFormGridBlock]:
    return [block for section in page.sections for block in section.blocks if isinstance(block, ModeloFormGridBlock)]


def _boxes(row_cells: tuple[ModeloFormGridCell, ...]) -> list[str]:
    return [f"[{cell.field.box}]" for cell in row_cells if cell.field is not None and cell.field.box]


def _with_field(form: ModeloWorkForm, box: str, update: Mapping[str, object]) -> ModeloWorkForm:
    """The form with one box's field changed, everything else as the read model built it."""

    def changed(field: ModeloFormField) -> ModeloFormField:
        return field.model_copy(update=dict(update)) if field.box == box else field

    pages = []
    for page in form.pages:
        sections = []
        for section in page.sections:
            blocks = []
            for block in section.blocks:
                if isinstance(block, ModeloFormGridBlock):
                    rows = tuple(
                        row.model_copy(
                            update={
                                "cells": tuple(
                                    cell
                                    if cell.field is None
                                    else cell.model_copy(update={"field": changed(cell.field)})
                                    for cell in row.cells
                                )
                            }
                        )
                        for row in block.rows
                    )
                    blocks.append(block.model_copy(update={"rows": rows}))
                elif isinstance(block, ModeloFormFieldBlock):
                    blocks.append(block.model_copy(update={"field": changed(block.field)}))
                else:
                    blocks.append(block)
            sections.append(section.model_copy(update={"blocks": tuple(blocks)}))
        pages.append(page.model_copy(update={"sections": tuple(sections)}))
    return form.model_copy(update={"pages": tuple(pages)})


class _ListHarness(App[None]):
    def __init__(self, items: tuple[CasillaListItem, ...]) -> None:
        super().__init__()
        self._items = items

    @override
    def compose(self) -> ComposeResult:
        yield CasillaList(self._items, language=OutputLanguage.EN)

    def on_mount(self) -> None:
        install_cadrumo_themes(self, appearance="dark")
        self.query_one(CasillaList).focus()


async def _drawn(items: tuple[CasillaListItem, ...], width: int) -> list[str]:
    with override_settings(cadrumo_output_language="en"):
        app = _ListHarness(items)
        async with app.run_test(size=(width, 300)) as pilot:
            await pilot.pause()
            widget = app.query_one(CasillaList)
            return [widget.render_line(y).text for y in range(widget.size.height)]


async def _walk(items: tuple[CasillaListItem, ...], width: int, keys: tuple[str, ...]) -> list[str | None]:
    """The box under the cursor after each key, from the first box of the page."""
    visited: list[str | None] = []
    with override_settings(cadrumo_output_language="en"):
        app = _ListHarness(items)
        async with app.run_test(size=(width, 300)) as pilot:
            await pilot.pause()
            widget = app.query_one(CasillaList)
            for key in keys:
                await pilot.press(key)
                entry = widget.highlighted
                visited.append(None if entry is None else entry.field.box)
    return visited


def _line_with(lines: list[str], box: str) -> str:
    """The line that draws a box, never a stacked row's heading that only names it."""
    return next(
        line for line in lines if f"[{box}]" in line and f"[{box}] to [" not in line and f"to [{box}]" not in line
    )


# ── the table ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [120, 200])
async def test_the_303_accrued_iva_grid_is_the_official_table_in_the_published_order(
    operation: PinnedAuthorityOperation, width: int
) -> None:
    page = _page(_form(operation), _ACCRUED_PAGE)
    grid = _grids(page)[0]
    lines = await _drawn(page_items(page, staged={}), width)

    header = next(line for line in lines if "Taxable base" in line and "Rate %" in line)
    assert header.index("Taxable base") < header.index("Rate %") < header.index("Tax amount")
    row_lines: list[int] = []
    for row in grid.rows:
        boxes = _boxes(row.cells)
        line = _line_with(lines, boxes[0][1:-1])
        positions = [line.index(box) for box in boxes]
        # A row's boxes share one line, in the official column order.
        assert positions == sorted(positions), line
        row_lines.append(lines.index(line))
    assert row_lines == sorted(row_lines), "rows follow the published order"
    # Every row carries its own label, as the stacked grid names it: its heading, and its rate when it has one.
    for row in grid.rows:
        # The cursor and level marks lead the line; the label follows them, its first line on the row's own line.
        label = _line_with(lines, _boxes(row.cells)[0][1:-1])[3:].split("[")[0].strip()
        assert label and row.heading.text.startswith(label.split(" · ")[0]), (label, row.heading.text)
    for box, label, rate in (
        ("02", "General regime", "4"), ("05", "General regime", "10"),
        ("08", "General regime", "21"), ("166", "General regime", "2"),
        ("157", "Equivalence surcharge", "1.75"),
        ("20", "Equivalence surcharge", "1.4"), ("23", "Equivalence surcharge", "5.2"),
    ):  # fmt: skip
        assert f"{label} · {rate}{_NBSP}%" in _line_with(lines, box), box
    # Only a rate the design fixes stands in its cell; a rate box the calculation fills shows its own value.
    for box, following, rate in (
        ("02", "03", "4"), ("05", "06", "10"), ("08", "09", "21"),
        ("157", "158", "1.75"), ("20", "21", "1.4"),
        ("23", "24", "5.2"), ("166", "167", None),
    ):  # fmt: skip
        line = _line_with(lines, box)
        slot = line[line.index(f"[{box}]") + len(box) + 2 : line.index(f"[{following}]")]
        if rate is None:
            assert "·" in slot and "%" not in slot, slot
        else:
            assert f"{rate}{_NBSP}%" in slot, slot
    # No rate where the design prints zeros, no base grounds one, or the design's literal declares no scale.
    for box, following in {"151": "152", "154": "155", "17": "18"}.items():
        line = _line_with(lines, box)
        slot = line[line.index(f"[{box}]") + len(box) + 2 : line.index(f"[{following}]")]
        assert "·" in slot and "%" not in slot, slot
    # Where the paper form has no rate box the slot stays empty and the columns stay aligned.
    intra = _line_with(lines, "10")
    assert "%" not in intra and intra.index("[11]") == _line_with(lines, "09").index("[09]")
    # Origin words stay out of the table; the help band says them.
    assert "Not calculated yet" not in _line_with(lines, "09")


@pytest.mark.asyncio
async def test_at_80_columns_the_303_grid_is_stacked_with_each_row_told_apart(
    operation: PinnedAuthorityOperation,
) -> None:
    page = _page(_form(operation), _ACCRUED_PAGE)
    lines = await _drawn(page_items(page, staged={}), 80)
    text = "\n".join(lines)

    assert f"General regime · 4{_NBSP}%" in text
    assert f"General regime · 21{_NBSP}%" in text
    assert "General regime · [150] to [152]" in text
    assert "Equivalence surcharge · [168] to [170]" in text
    # Each box is its own line under the row heading, labelled by its column.
    assert "Rate %" in _line_with(lines, "02") and f"4{_NBSP}%" in _line_with(lines, "02")
    assert f"21{_NBSP}%" in _line_with(lines, "08")
    assert f"1.75{_NBSP}%" in _line_with(lines, "157")
    assert f"5.2{_NBSP}%" in _line_with(lines, "23")
    assert "[09]" not in _line_with(lines, "07")
    # Descriptions are off inside a stacked grid, and still on for a box outside it.
    after_07 = lines[lines.index(_line_with(lines, "07")) + 1]
    assert "[08]" in after_07
    after_27 = lines[lines.index(_line_with(lines, "27")) + 1]
    assert "[" not in after_27 and after_27.strip()


@pytest.mark.asyncio
@pytest.mark.parametrize(("width", "table"), [(110, False), (200, True)])
async def test_the_prorratas_grid_is_a_table_only_where_it_fits(
    operation: PinnedAuthorityOperation, width: int, table: bool
) -> None:
    page = _page(_form(operation), _PRORRATAS_PAGE)
    lines = await _drawn(page_items(page, staged={}), width)

    first = next(line for line in lines if "[500]" in line and "Line 1 ·" not in line)
    assert ("[504]" in first) is table
    assert any("Line 1 · [500] to [504]" in line for line in lines) is not table


@pytest.mark.asyncio
async def test_390_page_2_draws_each_group_as_its_own_base_and_tax_table(operation: PinnedAuthorityOperation) -> None:
    page = _page(_form(operation, "390", 2025, "0A"), "pag-2")
    grids = _grids(page)
    lines = await _drawn(page_items(page, staged={}), 120)

    headers = [line for line in lines if "Taxable base" in line and "Tax amount" in line and "[" not in line]
    assert len(headers) == len(grids)
    for grid in grids:
        for row in grid.rows:
            boxes = _boxes(row.cells)
            line = _line_with(lines, boxes[0][1:-1])
            assert all(box in line for box in boxes)
            assert row.heading.text.split()[0] in line
            assert "%" not in line.replace(row.heading.text, ""), "the rate is in the row heading, not a column"
    # A casilla keyed by a semantic id is never shown by that id.
    assert not any("iva.anual" in line for line in lines)


# ── moving through a table ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_cursor_moves_cell_by_cell_and_keeps_its_column(operation: PinnedAuthorityOperation) -> None:
    items = page_items(_page(_form(operation), _ACCRUED_PAGE), staged={})
    keys = (
        "down", "right", "l", "right", "j", "h",
        "down", "down", "down", "down", "down", "down", "down",
        "home", "end", "k",
    )  # fmt: skip
    visited = await _walk(items, 120, keys)

    assert visited == [
        "165", "166", "167", "167", "03", "02",
        # Down the rate column: the blank rate slots send the cursor to the nearest box, and it
        # comes back to the rate column on the first row that has one.
        "154", "05", "08", "10", "12", "14", "157",
        "156", "158", "15",
    ]  # fmt: skip


@pytest.mark.asyncio
async def test_past_the_last_row_the_cursor_leaves_the_table_and_side_arrows_are_the_screens_again(
    operation: PinnedAuthorityOperation,
) -> None:
    items = page_items(_page(_form(operation), _ACCRUED_PAGE), staged={})
    with override_settings(cadrumo_output_language="en"):
        app = _ListHarness(items)
        async with app.run_test(size=(120, 300)) as pilot:
            await pilot.pause()
            widget = app.query_one(CasillaList)
            assert widget.focus_address(("casilla", "26"))
            on_grid = widget.on_grid_row
            await pilot.press("down")
            after = widget.highlighted
            left_taken = widget.check_action("cell", (-1,))
            await pilot.press("left")
            still = widget.highlighted
            await pilot.press("up")
            back = widget.highlighted

    assert on_grid
    assert after is not None and after.field.box == "27"
    assert not left_taken
    assert still is not None and still.field.box == "27"
    assert back is not None and back.field.box == "25"


@pytest.mark.asyncio
async def test_n_walks_the_boxes_needing_the_filer_row_by_row(operation: PinnedAuthorityOperation) -> None:
    form = _form(operation)
    for box, update in (
        ("165", {"origin": ModeloFormOrigin.NEEDS_INPUT}),
        ("03", {"origin": ModeloFormOrigin.CALCULATION_FAILED}),
        ("19", {"origin": ModeloFormOrigin.DEFAULT_TO_CONFIRM, "value": Decimal("5.00")}),
    ):
        form = _with_field(form, box, update)
    page = _page(form, _ACCRUED_PAGE)
    grid = _grids(page)[0]
    expected = [
        cell.field.box
        for row in grid.rows
        for cell in row.cells
        if cell.field is not None and cell.field.origin in NEEDS_ATTENTION
    ]
    waiting = {
        cell.field.box
        for row in grid.rows
        for cell in row.cells
        if cell.field is not None and ORIGIN_STANDINGS[cell.field.origin] is Standing.WAITING
    }
    visited = await _walk(page_items(page, staged={}), 120, ("n",) * (len(expected) + 1))

    assert expected == ["165", "03", "19"]
    # The boxes waiting on an import or a calculation are many, and n passes every one of them.
    assert len(waiting) > 10
    assert visited[: len(expected)] == expected
    assert not waiting & set(filter(None, visited))


@pytest.mark.asyncio
async def test_a_side_arrow_moves_between_cells_in_the_workbench_and_folds_elsewhere() -> None:
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader())
        async with ScreenHostApp(screen).run_test(size=(140, 40)) as pilot:
            for _ in range(3):
                await pilot.pause()
            casilla_list = screen.query_one(CasillaList)
            await pilot.press("g", *"07", "enter")
            for _ in range(4):
                await pilot.pause()
            on_grid = casilla_list.on_grid_row
            await pilot.press("right")
            moved = casilla_list.highlighted
            await pilot.press("g", *"01", "enter")
            for _ in range(4):
                await pilot.pause()
            await pilot.press("left")
            kept = casilla_list.highlighted
            off_grid = casilla_list.on_grid_row

    assert on_grid
    # The design's literal between them is not a box, so the cursor passes it.
    assert moved is not None and moved.field.box == "09"
    assert not off_grid
    assert kept is not None and kept.field.box == "01"


# ── marks and names ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_rows_left_edge_carries_its_most_severe_cell_and_a_cell_its_own_change(
    operation: PinnedAuthorityOperation,
) -> None:
    form = _with_field(_form(operation), "09", {"blockers": (ModeloFormBlocker(code="synthetic"),)})
    form = _with_field(form, "12", {"origin": ModeloFormOrigin.NEEDS_INPUT})
    page = _page(form, _ACCRUED_PAGE)
    base = next(field for field in page.fields() if field.box == "07")
    staged = {address_key(base.address): StagedDisplay(text="7,000.00 €", previous_text="·")}
    lines = await _drawn(page_items(page, staged=staged), 120)

    blocked = _line_with(lines, "07")
    assert blocked[1] == BLOCKS_MARK.glyph, "a blocker outranks what the row's other boxes wait on"
    assert blocked[blocked.index("[07]") - 2] == ATTENTION_GLYPHS[Attention.STAGED]
    assert blocked[blocked.index("[09]") - 2] == ATTENTION_GLYPHS[Attention.BLOCKED]
    assert _line_with(lines, "12")[1] == MISSING_MARK.glyph
    # A row whose boxes wait on an import is marked as waiting, never as missing input nor as done. The reduced
    # transitional row's base waits on an import while its rate and cuota wait on the calculation, so its mark
    # also says that what a row waits on first is the import.
    waiting = next(row for grid in _grids(page) for row in grid.rows if "[153]" in _boxes(row.cells))
    assert {cell.field.origin for cell in waiting.cells if cell.field is not None} == {
        ModeloFormOrigin.NOT_IMPORTED_YET,
        ModeloFormOrigin.NOT_CALCULATED_YET,
    }
    assert _line_with(lines, "153")[1] == NOT_IMPORTED_MARK.glyph
    assert _line_with(lines, "10")[1] == NOT_CALCULATED_MARK.glyph
    assert _line_with(lines, "14")[1] == " ", "a row with nothing to do and nothing waiting has no mark"


def test_a_grid_cell_is_named_by_its_row_its_column_and_its_own_label(operation: PinnedAuthorityOperation) -> None:
    with override_settings(cadrumo_output_language="en"):
        items = page_items(_page(_form(operation), _ACCRUED_PAGE), staged={})
    entry = next(item for item in items if isinstance(item, CasillaListEntry) and item.field.box == "07")
    outside = next(item for item in items if isinstance(item, CasillaListEntry) and item.field.box == "27")

    assert grid_cell_title(entry) == f"General regime · Taxable base · {entry.field.label.text}"
    assert grid_cell_title(outside) is None


@pytest.mark.asyncio
async def test_section_headings_take_the_colour_of_their_most_severe_level(operation: PinnedAuthorityOperation) -> None:
    form = _with_field(_form(operation), "40", {"blockers": (ModeloFormBlocker(code="synthetic"),)})
    form = _with_field(form, "150", {"origin": ModeloFormOrigin.NEEDS_INPUT})
    form = _with_field(form, "27", {"origin": ModeloFormOrigin.CALCULATED, "value": Decimal("210.00")})
    items = page_items(_page(form, _ACCRUED_PAGE), staged={})
    with override_settings(cadrumo_output_language="en"):
        app = _ListHarness(items)
        async with app.run_test(size=(120, 300)) as pilot:
            await pilot.pause()
            widget = app.query_one(CasillaList)
            styles: dict[str, Style | None] = {}
            for y in range(widget.size.height):
                strip = widget.render_line(y)
                text = strip.text
                if text.startswith(" ") and text[1:2] in {"!", "▲", "✓"} and text[2:3] == " " and "[" not in text:
                    styles.setdefault(text[1], next(iter(strip)).style)
            warning = widget.get_component_rich_style("casilla-list--heading-warning")
            error = widget.get_component_rich_style("casilla-list--heading-error")
            plain = widget.get_component_rich_style("casilla-list--heading")
            primary = app.theme_variables["primary"]

    assert set(styles) == {"!", "▲", "✓"}
    to_do, blocked, done = styles["!"], styles["▲"], styles["✓"]
    assert to_do is not None and to_do.color == warning.color and to_do.bold
    assert blocked is not None and blocked.color == error.color and blocked.bold
    assert done is not None and done.color == plain.color and done.bold
    assert len({to_do.color, blocked.color, done.color}) == 3
    for style in (to_do, blocked, done):
        assert style.color is not None and style.color.triplet is not None
        assert style.color.triplet.hex.lower() != primary.lower()


# ── a box the form sets reads as its figure or a dot ─────────────────────


def test_a_box_the_form_sets_shows_its_figure_or_a_dot_and_never_a_word(operation: PinnedAuthorityOperation) -> None:
    forms = (_form(operation), _form(operation, "390", 2025, "0A"), _form(operation, "349", 2026, "1T"))
    checked = 0
    for language in OutputLanguage:
        with override_settings(cadrumo_output_language=language.value):
            for form in forms:
                for page in workbench_pages(form):
                    for item in page_items(page, staged={}):
                        if not isinstance(item, CasillaListEntry):
                            continue
                        field = item.field
                        if field.editability is not ModeloFormEditability.DESIGN_CONSTANT or field.value is not None:
                            continue
                        shown = (value_text(item, language), row_value_text(item, language))
                        if item.row_label is not None:
                            shown = (*shown, grid_value_text(item, language))
                        for text in shown:
                            # A figure the form prints, or a dot beside the words saying the form sets it.
                            assert text == "·" or text[0].isdigit(), (field.box, text)
                        checked += 1
    assert checked


@pytest.mark.asyncio
@pytest.mark.parametrize("width", _WIDTHS)
async def test_a_box_the_design_fixes_without_a_figure_reads_as_a_dot_in_a_grid(width: int) -> None:
    form = synthetic_form()
    page = workbench_pages(form)[0]
    fixed_box = form_field("98", "Clave fija", ModeloFormOrigin.INFORMATIONAL, None).model_copy(
        update={"editability": ModeloFormEditability.DESIGN_CONSTANT}
    )
    grid_section = page.sections[1]
    grid = grid_section.blocks[0]
    assert isinstance(grid, ModeloFormGridBlock)
    row = grid.rows[0]
    cells = (
        row.cells[0],
        ModeloFormGridCell(kind=FormCellKind.DESIGN_CONSTANT, field=fixed_box, literal="X"),
        row.cells[2],
    )
    grid = grid.model_copy(update={"rows": (row.model_copy(update={"cells": cells}),)})
    sections = (page.sections[0], grid_section.model_copy(update={"blocks": (grid,)}))
    page = WorkbenchPage(id=page.id, heading=page.heading, sections=sections)
    lines = await _drawn(page_items(page, staged={}), width)

    row_text = _line_with(lines, "98")
    assert "·" in row_text
    assert not any(character.isalpha() for character in row_text.split("[98]", 1)[1].split("[", 1)[0]), row_text


@pytest.mark.asyncio
@pytest.mark.parametrize("width", _WIDTHS)
async def test_the_303_grid_never_draws_the_word_fixed(operation: PinnedAuthorityOperation, width: int) -> None:
    lines = await _drawn(page_items(_page(_form(operation), _ACCRUED_PAGE), staged={}), width)

    assert lines
    assert not any("fixed" in line.lower() for line in lines)


# ── repeated records ─────────────────────────────────────────────────────


def _records_page(form: ModeloWorkForm, rows: tuple[ModeloFormRepeatingRow, ...] | None) -> WorkbenchPage:
    """The 349 operators page; with ``rows``, as if the records had been read from their source."""
    page = next(
        page
        for page in form.pages
        if any(isinstance(block, ModeloFormRepeatingBlock) for section in page.sections for block in section.blocks)
    )
    sections = []
    for section in page.sections:
        blocks = tuple(
            block.model_copy(update={"rows_known": True, "rows": rows})
            if rows is not None and isinstance(block, ModeloFormRepeatingBlock)
            else block
            for block in section.blocks
        )
        sections.append(section.model_copy(update={"blocks": blocks}))
    return WorkbenchPage(id=page.id, heading=page.heading, sections=tuple(sections))


_RECORDS: Final[tuple[ModeloFormRepeatingRow, ...]] = (
    ModeloFormRepeatingRow(
        index=1, values=(None, None, "FR", "FR00000000001", "Operador Uno", "E", Decimal("1500.00"))
    ),
    ModeloFormRepeatingRow(index=2, values=(None, None, "DE", "DE000000002", "Operador Dos", "A", Decimal("250.50"))),
)


@pytest.mark.asyncio
async def test_records_whose_number_is_not_known_are_never_counted_as_none(operation: PinnedAuthorityOperation) -> None:
    form = _form(operation, "349", 2026, "1T")
    lines = await _drawn(page_items(_records_page(form, None), staged={}), 120)
    unknown = lookup_translation("tui.modelo.workbench.grid.records_unknown", locale="en")
    counted = lookup_translation("tui.modelo.workbench.repeating", locale="en")

    assert unknown is not None and counted is not None
    assert any(unknown in line for line in lines), lines
    assert not any(counted.split("{")[0].strip() in line for line in lines)


@pytest.mark.asyncio
async def test_an_unknown_record_source_is_visible_content_in_the_screen_header_and_help(
    operation: PinnedAuthorityOperation,
) -> None:
    screen = ModeloWorkbenchScreen(FakeReader(form=_form(operation, "349", 2026, "1T")))
    async with ScreenHostApp(screen).run_test(size=(80, 24)) as pilot:
        for _ in range(3):
            await pilot.pause()
        await pilot.press("]")
        await pilot.pause()
        help_text = str(screen.query_one("#wb-help", Static).render())
        heading = str(screen.query_one("#wb-page", Static).render())
        unknown = lookup_translation("tui.modelo.workbench.grid.records_unknown", locale="en")
        empty_help = lookup_translation("tui.modelo.workbench.help.empty", locale="en")
        empty_page = lookup_translation("tui.modelo.workbench.filter.empty", locale="en")
        assert unknown is not None and unknown in help_text
        assert empty_help is not None and empty_help not in help_text
        assert empty_page is not None and empty_page not in heading
        assert screen.query_one(CasillaList).highlighted is None


@pytest.mark.asyncio
@pytest.mark.parametrize(("width", "table"), [(80, False), (200, True)])
async def test_known_records_are_a_read_only_table_with_an_index_column(
    operation: PinnedAuthorityOperation, width: int, table: bool
) -> None:
    form = _form(operation, "349", 2026, "1T")
    page = _records_page(form, _RECORDS)
    items = page_items(page, staged={})
    lines = await _drawn(items, width)
    text = "\n".join(lines)
    block = next(
        block for section in page.sections for block in section.blocks if isinstance(block, ModeloFormRepeatingBlock)
    )

    assert "Detail rows: 2" in text
    read_only = lookup_translation("tui.modelo.workbench.grid.records_read_only", locale="en")
    assert read_only is not None and read_only in text
    first = next(line for line in lines if "1,500.00" in line)
    second = next(line for line in lines if "250.50" in line)
    assert first.lstrip().startswith("1") and second.lstrip().startswith("2")
    assert ("Operador Uno" in first) is table
    if table:
        header = [line for line in lines if block.columns[-1].heading.text.split()[0] in line]
        assert header, "the columns carry the labels of their boxes"
    else:
        assert "Operador Uno" in text and "Operador Dos" in text
        assert "FR" in text and "DE" in text
        for column in block.columns:
            assert column.heading.text in text, "stacked records retain every declared column label"
    # Records are read, never edited here: none is a box the cursor can rest on.
    assert not any(isinstance(item, CasillaListEntry) for item in items)
    assert not any(isinstance(item, CasillaListHeading) and item.row is not None for item in items)
