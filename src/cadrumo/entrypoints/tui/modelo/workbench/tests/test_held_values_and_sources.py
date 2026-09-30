"""A box says what it holds, and where it comes from, the same way on every surface.

A zero nobody entered is a value: the row, a grid cell, the panel, the help
band's words and a search hit show it as a figure and never call the box empty,
while a box holding nothing shows no figure. A value the official form sets
draws one mark on its row and in the sources map. A box fed by the filer's own
entries that none of them can reach, and that holds nothing, names no source
the filer cannot use. A value taken from imported AEAT tax data names the day
it was imported in the panel, the help band's words, search and the sources
map. The panel says what a box affects before the new value, and on a filed
declaration how to change it. The filters narrow a page to values from the
filer's records, calculated values or boxes holding an amount.

Driven through the real list, panel, search and sources code over synthetic
fields and forms; only the parser is a stand-in, which no test here reaches.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, override

import pytest
from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widgets import Static

from ......application.modelo.source_policy import SourceFamily
from ......application.modelo.value_presentation import absent_value_text
from ......application.modelo.work_form_models import (
    ModeloFormAeatData,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormOrigin,
    ModeloFormValueSource,
    ModeloWorkForm,
)
from ......core.aggregation import BindingSourceKind
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import lookup_translation, tr
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList, CasillaListEntry, grid_value_text, row_value_text, stated_value_text
from ..editor import CasillaEditorScreen, EditorOutcome, read_only_reason, where_from_text
from ..page_items import StagedDisplay, WorkbenchFilter, WorkbenchPage, page_items, workbench_pages
from ..search import search_entries
from ..sources import SOURCE_GROUP_MARKS, SourceGroupKind, group_prompt, group_words, source_group_kind, source_groups
from ..vocabulary import (
    FORM_SET_MARK,
    ORIGIN_MARKS,
    aeat_imported_on,
    origin_glyph,
    origin_text,
    origin_words,
)
from ..wording import date_text
from .workbench_fixture import FakeActions, fed_by, form_field, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LANGUAGES = tuple(OutputLanguage)
_EMPTY_KEY = "tui.modelo.workbench.origin.optional_empty"
_HELD_ZERO_KEY = "tui.modelo.workbench.origin_held_zero.optional_empty"
_FORM_SET_KEY = "tui.modelo.workbench.origin_source.imported.fixed_by_design"
_ZERO = "0.00\u00a0€"
_IMPORTED_AT = datetime(2026, 4, 2, 10, 30, tzinfo=UTC)


def _empty() -> ModeloFormField:
    return form_field("150", "Taxable base", ModeloFormOrigin.OPTIONAL_EMPTY)


def _held_zero() -> ModeloFormField:
    return form_field("152", "Tax amount", ModeloFormOrigin.OPTIONAL_EMPTY, Decimal("0.00"))


def _form_set() -> ModeloFormField:
    return form_field(
        "40",
        "Coefficient",
        ModeloFormOrigin.IMPORTED,
        Decimal("1.00"),
        editability=ModeloFormEditability.DESIGN_CONSTANT,
        bindings=(fed_by("m.coefficient", BindingSourceKind.DESIGN_CONSTANT),),
    ).model_copy(update={"source": ModeloFormValueSource(family=SourceFamily.FIXED_BY_DESIGN)})


def _from_aeat() -> ModeloFormField:
    return form_field(
        "01",
        "Income",
        ModeloFormOrigin.IMPORTED,
        Decimal("24000.00"),
        editability=ModeloFormEditability.LOCKED_SOURCE,
        bindings=(fed_by("m.income", BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION),),
    ).model_copy(
        update={
            "source": ModeloFormValueSource(
                family=SourceFamily.AEAT_DRAFT, source_kind=BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION
            )
        }
    )


def _unreachable_entry() -> ModeloFormField:
    """A binding input the filer's entries feed but that no entry can reach here, holding nothing."""
    return form_field(
        "900",
        "Unnamed box",
        ModeloFormOrigin.OPTIONAL_EMPTY,
        bindings=(fed_by("m.manual", BindingSourceKind.MANUAL_INPUT),),
    ).model_copy(
        update={
            "box": None,
            "editability": ModeloFormEditability.NOT_WRITABLE,
            "not_writable_reason": "absent_from_admission",
            "source": ModeloFormValueSource(
                family=SourceFamily.YOUR_ENTRIES, source_kind=BindingSourceKind.MANUAL_INPUT
            ),
        }
    )


def _with_fields(form: ModeloWorkForm, replacements: dict[str, ModeloFormField]) -> ModeloWorkForm:
    """The form with each listed box's field replaced where it stands."""

    def block(item: Any) -> Any:
        if isinstance(item, ModeloFormFieldBlock) and item.field.box in replacements:
            return item.model_copy(update={"field": replacements[item.field.box]})
        return item

    pages = tuple(
        page.model_copy(
            update={
                "sections": tuple(
                    section.model_copy(update={"blocks": tuple(block(item) for item in section.blocks)})
                    for section in page.sections
                )
            }
        )
        for page in form.pages
    )
    return form.model_copy(update={"pages": pages})


async def _settle(pilot: Pilot[EditorOutcome | None]) -> None:
    for _ in range(3):
        await pilot.pause()


def _text(screen: CasillaEditorScreen, widget_id: str) -> str:
    return str(screen.query_one(widget_id, Static).render())


class _RowHarness(App[None]):
    def __init__(self, entries: tuple[CasillaListEntry, ...]) -> None:
        super().__init__()
        self._entries = entries

    @override
    def compose(self) -> ComposeResult:
        yield CasillaList(self._entries, language=OutputLanguage.EN)


async def _rows(*fields: ModeloFormField) -> list[str]:
    app = _RowHarness(tuple(CasillaListEntry(field) for field in fields))
    async with app.run_test(size=(140, 10)) as pilot:
        await pilot.pause()
        widget = app.query_one(CasillaList)
        return [widget.render_line(y).text for y in range(widget.size.height)]


# ── a held zero is not an empty box ──────────────────────────────────────


@pytest.mark.parametrize("language", _LANGUAGES)
def test_a_held_zero_and_an_empty_box_have_their_own_words_in_every_language(language: OutputLanguage) -> None:
    held = lookup_translation(_HELD_ZERO_KEY, locale=language.value)
    empty = lookup_translation(_EMPTY_KEY, locale=language.value)
    assert held and empty and held != empty
    assert "0" in held and "0" not in empty
    with override_settings(cadrumo_output_language=language.value):
        assert origin_words(_held_zero()) == held
        assert origin_words(_empty()) == empty


@pytest.mark.asyncio
async def test_every_surface_shows_a_held_zero_and_no_figure_for_an_empty_box() -> None:
    held, empty = _held_zero(), _empty()
    with override_settings(cadrumo_output_language="en"):
        rows = await _rows(empty, held)
        held_row = next(line for line in rows if "[152]" in line)
        empty_row = next(line for line in rows if "[150]" in line)
        # The row: a held zero is a figure beside words that never say "empty"; nothing held is a dot.
        assert f"{_ZERO} ○ Optional, left at 0" in held_row
        assert "empty" not in held_row
        assert empty_row.rstrip().endswith("· ○ Optional, empty")
        assert not any(character.isdigit() for character in empty_row.split("]", 1)[1])
        # A grid cell draws the same figure, or the same dot.
        assert grid_value_text(CasillaListEntry(held), OutputLanguage.EN) == _ZERO
        assert grid_value_text(CasillaListEntry(empty), OutputLanguage.EN) == "·"
        # The help band's words, through the one origin text.
        assert origin_text(held) == "○ Optional, left at 0"
        assert origin_text(empty) == "○ Optional, empty"
        # The panel and search state the zero, and state no figure for nothing.
        assert stated_value_text(CasillaListEntry(held), OutputLanguage.EN) == _ZERO
        assert stated_value_text(CasillaListEntry(empty), OutputLanguage.EN) is None
        pages = workbench_pages(_with_fields(synthetic_form(), {"06": held.model_copy(update={"box": "06"})}))
        hit = next(item for item in search_entries(pages, staged={}, language=OutputLanguage.EN) if item.box == "06")
        assert hit.value == _ZERO
        assert hit.text().endswith(f"{_ZERO} · ○ Optional, left at 0")

        panels = {}
        for field in (held, empty):
            panel = CasillaEditorScreen(field, parse=FakeActions().parse, language=OutputLanguage.EN)
            async with ScreenHostApp(panel).run_test(size=(140, 40)) as pilot:
                await _settle(pilot)
                panels[field.box] = _text(panel, "#editor-now-text")
    assert panels["152"] == f"{_ZERO} · ○ Optional, left at 0"
    assert panels["150"] == "○ Optional, empty"
    assert absent_value_text(OutputLanguage.EN) not in panels["150"]


# ── a value the form sets draws one mark ─────────────────────────────────


def test_a_value_the_form_sets_draws_the_same_mark_on_its_row_and_in_the_sources_map() -> None:
    field = _form_set()
    with override_settings(cadrumo_output_language="en"):
        words = origin_words(field)
    kind = source_group_kind(field)
    assert kind is SourceGroupKind.SET_BY_FORM
    assert origin_glyph(field) == SOURCE_GROUP_MARKS[kind].glyph == FORM_SET_MARK.glyph
    assert origin_glyph(field) != ORIGIN_MARKS[ModeloFormOrigin.IMPORTED].glyph
    assert words == lookup_translation(_FORM_SET_KEY, locale="en")
    # A design constant the layout places reads the same way, not as a bare reference value.
    constant = form_field(
        "98", "Clave fija", ModeloFormOrigin.INFORMATIONAL, editability=ModeloFormEditability.DESIGN_CONSTANT
    ).model_copy(update={"source": ModeloFormValueSource(family=SourceFamily.FIXED_BY_DESIGN)})
    with override_settings(cadrumo_output_language="en"):
        assert origin_text(constant) == f"{FORM_SET_MARK.glyph} {words}"
        # Its value column is a dot beside those words, never the word "fixed".
        assert row_value_text(CasillaListEntry(constant), OutputLanguage.EN) == "·"
    # A figure shown only for information draws the mark its row draws, in the map too.
    information = form_field("99", "Reference", ModeloFormOrigin.INFORMATIONAL, Decimal("5.00")).model_copy(
        update={"editability": ModeloFormEditability.INFORMATIONAL}
    )
    assert source_group_kind(information) is SourceGroupKind.INFORMATION
    assert SOURCE_GROUP_MARKS[SourceGroupKind.INFORMATION].glyph == origin_glyph(information)


# ── a source the filer cannot use is not named ───────────────────────────


@pytest.mark.asyncio
async def test_a_box_no_entry_can_reach_names_no_source_and_says_it_is_empty_once() -> None:
    field = _unreachable_entry()
    with override_settings(cadrumo_output_language="en"):
        assert where_from_text(field) is None
        # The same box holding a value still says where that value came from.
        held = field.model_copy(update={"value": Decimal("12.00"), "origin": ModeloFormOrigin.ENTERED})
        assert where_from_text(held) is not None
        reason = read_only_reason(field, OutputLanguage.EN)
        assert reason is not None
        panel = CasillaEditorScreen(
            field, parse=FakeActions().parse, language=OutputLanguage.EN, read_only_reason=reason
        )
        async with ScreenHostApp(panel).run_test(size=(80, 24)) as pilot:
            await _settle(pilot)
            now = _text(panel, "#editor-now-text")
            has_where = bool(panel.query("#editor-where"))
    assert not has_where
    assert now == "○ Optional, empty"
    assert tr("tui.modelo.workbench.origin_source.imported.your_entries") not in now


# ── AEAT data names the day it was imported ──────────────────────────────


def _aeat_form() -> ModeloWorkForm:
    form = _with_fields(synthetic_form(), {"01": _from_aeat()})
    return form.model_copy(update={"aeat_data": ModeloFormAeatData(snapshot_id="snapshot-1", imported_at=_IMPORTED_AT)})


@pytest.mark.asyncio
@pytest.mark.parametrize("language", _LANGUAGES)
async def test_a_value_from_aeat_data_names_the_day_it_was_imported_on_every_surface(language: OutputLanguage) -> None:
    form = _aeat_form()
    imported = aeat_imported_on(form)
    assert imported is not None
    assert imported == _IMPORTED_AT.astimezone().date()
    field = _from_aeat()
    with override_settings(cadrumo_output_language=language.value):
        written = date_text(imported, language)
        dated = tr("tui.modelo.workbench.origin_source.aeat_imported_on", date=written)
        undated = tr("tui.modelo.workbench.origin_source.imported.aeat_draft")
        assert written in dated
        # The help band's words and search.
        assert origin_text(field, aeat_imported=imported, language=language).endswith(dated)
        assert origin_text(field).endswith(undated)
        hit = next(
            item
            for item in search_entries(workbench_pages(form), staged={}, language=language, aeat_imported=imported)
            if item.box == "01"
        )
        assert hit.origin.endswith(dated)
        # The sources map's group heading, closed and open.
        group = next(item for item in source_groups(form) if item.kind is SourceGroupKind.AEAT_DATA)
        assert group.imported_on == imported
        heading = tr("tui.modelo.workbench.sources.group.aeat_data_imported_on", date=written)
        assert written in heading
        assert str(group_prompt(group, expanded=True)).startswith(f"▿ {SOURCE_GROUP_MARKS[group.kind].glyph} {heading}")
        assert group_words(SourceGroupKind.AEAT_DATA).endswith(tr("tui.modelo.workbench.sources.group.aeat_data"))
        # The panel's "Now" line and where the value comes from.
        panel = CasillaEditorScreen(
            field,
            parse=FakeActions().parse,
            language=language,
            read_only_reason=read_only_reason(field, language),
            aeat_imported=imported,
        )
        async with ScreenHostApp(panel).run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            now = _text(panel, "#editor-now-text")
            where = _text(panel, "#editor-where-text")
    assert now.endswith(dated)
    assert where == dated
    # Without an import date the words stay undated.
    assert aeat_imported_on(synthetic_form()) is None


# ── the panel's order and a filed declaration ────────────────────────────


@pytest.mark.asyncio
async def test_the_panel_says_what_a_box_affects_before_the_new_value_and_a_filed_one_how_to_change_it() -> None:
    field = form_field("06", "Withholdings", ModeloFormOrigin.DEFAULT_TO_CONFIRM, Decimal("0.00"))
    with override_settings(cadrumo_output_language="en"):
        panel = CasillaEditorScreen(field, parse=FakeActions().parse, language=OutputLanguage.EN, feeds=("[07]",))
        async with ScreenHostApp(panel).run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            affects = panel.query_one("#editor-affects").region
            entry = panel.query_one("#editor-entry").region
        filed = CasillaEditorScreen(
            field,
            parse=FakeActions().parse,
            language=OutputLanguage.EN,
            read_only_reason=read_only_reason(field, OutputLanguage.EN, recorded=True),
            recorded=True,
        )
        async with ScreenHostApp(filed).run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            can_change = _text(filed, "#editor-can-change-text")
        correction = tr("tui.modelo.workbench.filed.read_only")
    assert affects.bottom <= entry.y
    assert can_change == correction


# ── filters ──────────────────────────────────────────────────────────────


def _shown(page: WorkbenchPage, mode: WorkbenchFilter) -> set[str | None]:
    return {item.field.box for item in page_items(page, staged={}, mode=mode) if isinstance(item, CasillaListEntry)}


def test_the_filters_narrow_a_page_to_records_calculated_values_or_amounts() -> None:
    records = form_field(
        "01", "Income", ModeloFormOrigin.IMPORTED, Decimal("10.00"), editability=ModeloFormEditability.LOCKED_SOURCE
    ).model_copy(update={"source": ModeloFormValueSource(family=SourceFamily.RECORDS)})
    profile = records.model_copy(update={"box": "02", "source": ModeloFormValueSource(family=SourceFamily.PROFILE)})
    calculated = form_field("03", "Net", ModeloFormOrigin.CALCULATED, Decimal("0.00"))
    pending = form_field("09", "Quota", ModeloFormOrigin.NOT_CALCULATED_YET, Decimal("7.00"))
    held_zero = form_field("06", "Withholdings", ModeloFormOrigin.OPTIONAL_EMPTY, Decimal("0.00"))
    empty = form_field("07", "Base", ModeloFormOrigin.OPTIONAL_EMPTY)
    fields = (records, profile, calculated, pending, held_zero, empty)
    form = synthetic_form()
    section = form.pages[0].sections[0]
    blocks = tuple(ModeloFormFieldBlock(id=f"f{field.box}", field=field) for field in fields)
    page = WorkbenchPage(
        id="p", heading=form.pages[0].heading, sections=(section.model_copy(update={"blocks": blocks}),)
    )

    assert _shown(page, WorkbenchFilter.RECORDS) == {"01"}
    assert _shown(page, WorkbenchFilter.CALCULATED) == {"03"}
    # An amount is a figure other than zero that is there: not a held zero, nothing, or a value not calculated yet.
    assert _shown(page, WorkbenchFilter.AMOUNT) == {"01", "02"}
    # A staged change is always shown, whatever the filter.
    change = {CasillaListEntry(empty).key: StagedDisplay(text="5,00 €", previous_text="·")}
    staged = {
        item.field.box
        for item in page_items(page, staged=change, mode=WorkbenchFilter.AMOUNT)
        if isinstance(item, CasillaListEntry)
    }
    assert "07" in staged
