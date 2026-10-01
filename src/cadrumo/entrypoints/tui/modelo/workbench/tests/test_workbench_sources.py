"""The sources view maps every box to where its value comes from and leads back to the box or its source.

The grouping runs over synthetic forms with the product's real source
policies: every box lands in exactly one group, counted per box; a source that
was read and gave nothing reads "none found", distinct from a source not read
yet and from a zero it did give. Driven through the standalone host, the view
opens on the group of the box under the cursor, opens another group on Enter,
returns to a chosen box, and opens the owning product area only after the filer
has decided about staged changes. One run maps a real declaration read from the
bundled registry.
"""

from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal

import pytest
from rich.console import Console
from textual.pilot import Pilot
from textual.widgets import OptionList, Static

from ......application.modelo.source_policy import SourceFamily, SourceSurface, source_policy
from ......application.modelo.work_form_models import (
    ModeloFormEarlierFiling,
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormValueSource,
    ModeloWorkForm,
    address_key,
)
from ......core.aggregation import BindingSourceKind
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......core.period import Period
from ....components.dialogs import ConfirmScreen
from ....components.host import ScreenHostApp
from ....navigation import TuiNavigationTargetV1, declared_destination_ids
from ..casilla_list import CasillaList, CasillaListEntry
from ..screen import ModeloWorkbenchScreen
from ..sources import (
    SourceGroup,
    SourceGroupKind,
    SourceState,
    WorkbenchSourcesScreen,
    group_boxes,
    group_items,
    group_prompt,
    group_summary,
    source_groups,
    surface_target,
)
from .declaration_states import recorded_as_filed
from .editor_panel import open_panel
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, fed_by, form_field, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SIZE = (140, 40)


async def _settle[ResultT](pilot: Pilot[ResultT], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _lines(widget: CasillaList) -> list[str]:
    return [widget.render_line(y).text.rstrip() for y in range(widget.size.height)]


def _group_lines(groups: OptionList) -> list[str]:
    return [groups.render_line(y).text.strip() for y in range(groups.size.height)]


def _unread_expenses(form: ModeloWorkForm) -> ModeloWorkForm:
    """Box 02's source gave nothing; box 01's source gave a genuine zero."""
    return replace_fields(
        form,
        {
            "01": {"value": Decimal("0.00")},
            "02": {
                "origin": ModeloFormOrigin.NOT_IMPORTED_YET,
                "value": None,
                "bindings": (
                    fed_by(
                        "m130.gastos",
                        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
                        resolved=False,
                    ),
                ),
            },
        },
    )


def test_every_box_sits_in_exactly_one_group_and_groups_count_boxes() -> None:
    form = synthetic_form()
    groups = source_groups(form)

    assert [(group.kind, [field.box for field in group.fields]) for group in groups] == [
        (SourceGroupKind.RECORDS, ["01", "02"]),
        (SourceGroupKind.YOURS, ["07"]),
        (SourceGroupKind.NEEDS_YOU, ["06"]),
        (SourceGroupKind.CALCULATED, ["03", "09", "19", "99"]),
    ]
    placed = Counter(address_key(field.address) for group in groups for field in group.fields)
    assert placed == Counter(address_key(field.address) for field in form.fields())
    assert set(placed.values()) == {1}


def test_a_source_that_found_nothing_differs_from_one_not_read_yet_and_from_a_zero() -> None:
    calculated = _unread_expenses(synthetic_form())
    not_calculated = _unread_expenses(synthetic_form(calculated=False))
    with override_settings(cadrumo_output_language="en"):
        after = source_groups(calculated)[0]
        before = source_groups(not_calculated)[0]
        after_summary = group_summary(after)
        before_summary = group_summary(before)

    assert after.kind is before.kind is SourceGroupKind.RECORDS
    assert [reading.state for reading in after.readings] == [SourceState.PRODUCED, SourceState.NONE_FOUND]
    assert [reading.state for reading in before.readings] == [SourceState.PRODUCED, SourceState.NOT_YET]
    assert after_summary.endswith(": none found")
    assert before_summary.endswith(": not read yet")
    assert "none found" not in after_summary.split(" · ")[0]
    assert after.fields[0].value == Decimal("0.00")


def test_a_value_taken_from_aeat_data_reads_as_aeat_data_not_as_the_source_its_binding_names() -> None:
    form = replace_fields(
        synthetic_form(),
        {"02": {"source": ModeloFormValueSource(family=SourceFamily.AEAT_DRAFT)}},
    )
    groups = {group.kind: group for group in source_groups(form)}
    with override_settings(cadrumo_output_language="en"):
        records = group_summary(groups[SourceGroupKind.RECORDS])
        items = group_items(groups[SourceGroupKind.AEAT_DATA], staged={})
        texts = [
            item.field.box if isinstance(item, CasillaListEntry) else getattr(item, "text", None) for item in items
        ]

    assert [field.box for field in groups[SourceGroupKind.RECORDS].fields] == ["01"]
    assert [field.box for field in groups[SourceGroupKind.AEAT_DATA].fields] == ["02"]
    assert groups[SourceGroupKind.AEAT_DATA].readings == ()
    assert "expenses" not in records.casefold()
    assert texts == ["↓ AEAT data", "02"]


def test_assumed_replaced_fixed_and_blank_boxes_each_have_their_own_group() -> None:
    form = replace_fields(
        synthetic_form(),
        {
            "07": {"origin": ModeloFormOrigin.DEFAULT_TO_CONFIRM, "value": Decimal("0")},
            "02": {"origin": ModeloFormOrigin.OVERRIDES_SOURCE},
            "09": {"origin": ModeloFormOrigin.INFORMATIONAL, "editability": ModeloFormEditability.DESIGN_CONSTANT},
            "99": {"origin": ModeloFormOrigin.NOT_APPLICABLE, "value": None},
        },
    )
    groups = {group.kind: group for group in source_groups(form)}
    with override_settings(cadrumo_output_language="en"):
        assumed = group_summary(groups[SourceGroupKind.ASSUMED])
        replaced = group_summary(groups[SourceGroupKind.REPLACED])

    assert [field.box for field in groups[SourceGroupKind.ASSUMED].fields] == ["07"]
    assert [field.box for field in groups[SourceGroupKind.REPLACED].fields] == ["02"]
    assert [field.box for field in groups[SourceGroupKind.SET_BY_FORM].fields] == ["09"]
    assert [field.box for field in groups[SourceGroupKind.BLANK].fields] == ["99"]
    assert (assumed, group_boxes(groups[SourceGroupKind.ASSUMED])) == ("", ("07",))
    assert (replaced, group_boxes(groups[SourceGroupKind.REPLACED])) == ("", ("02",))


def test_a_group_lists_its_boxes_under_each_of_its_sources() -> None:
    with override_settings(cadrumo_output_language="es"):
        items = group_items(source_groups(synthetic_form())[0], staged={})
        texts = [
            item.field.box if isinstance(item, CasillaListEntry) else getattr(item, "text", None) for item in items
        ]
        income = tr(source_policy(BindingSourceKind.LEDGER_RENTA_INCOME_AGGREGATION).label_key)
        expenses = tr(source_policy(BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION).label_key)

    assert texts == ["↓ Tus registros", income, "01", expenses, "02"]


def _prompt_lines(group: SourceGroup, *, expanded: bool, width: int = 60) -> list[str]:
    console = Console(width=width)
    with console.capture() as captured:
        console.print(group_prompt(group, expanded=expanded))
    return [line.rstrip() for line in captured.get().splitlines()]


def test_a_group_opens_with_the_open_mark_and_drops_the_summary_its_list_repeats() -> None:
    form = replace_fields(
        synthetic_form(),
        {
            "07": {"origin": ModeloFormOrigin.DEFAULT_TO_CONFIRM, "value": Decimal("0")},
            "99": {"origin": ModeloFormOrigin.NOT_APPLICABLE, "value": None},
        },
    )
    groups = {group.kind: group for group in source_groups(form)}
    with override_settings(cadrumo_output_language="en"):
        closed = _prompt_lines(groups[SourceGroupKind.ASSUMED], expanded=False)
        opened = _prompt_lines(groups[SourceGroupKind.ASSUMED], expanded=True)
        records_closed = _prompt_lines(groups[SourceGroupKind.RECORDS], expanded=False)
        records_opened = _prompt_lines(groups[SourceGroupKind.RECORDS], expanded=True)
        blank = _prompt_lines(groups[SourceGroupKind.BLANK], expanded=False)

    assert closed == ["▹ ◐ Assumed, please confirm · Boxes: 1", "  [07]"]
    assert opened == ["▿ ◐ Assumed, please confirm · Boxes: 1"]
    assert records_closed[0] == "▹ ↓ Your records · Boxes: 2"
    assert len(records_closed) == 2
    assert records_opened == ["▿ ↓ Your records · Boxes: 2"]
    assert blank == ["▹ - Left blank or do not apply · Boxes: 1"]


def test_a_closed_group_lists_its_boxes_in_two_lines_then_counts_the_rest() -> None:
    fields = tuple(
        form_field(str(number), "Importe", ModeloFormOrigin.DEFAULT_TO_CONFIRM, Decimal("5.00"))
        for number in range(1000, 1030)
    )
    group = SourceGroup(kind=SourceGroupKind.ASSUMED, fields=fields)
    with override_settings(cadrumo_output_language="en"):
        lines = _prompt_lines(group, expanded=False, width=40)

    listed = lines[1:]
    rest = re.search(r"and (\d+) more", listed[-1])
    assert len(listed) == 2
    assert rest is not None
    assert len(re.findall(r"\[\d+\]", " ".join(listed))) + int(rest.group(1)) == len(fields)


def test_a_value_carried_from_an_earlier_declaration_names_that_declaration() -> None:
    earlier = ModeloFormEarlierFiling(modelo="130", period=Period.from_year_and_code(2025, "4T"))
    carried = ModeloFormValueSource(family=SourceFamily.EARLIER_FILINGS, earlier_filings=(earlier,))
    bound = replace_fields(
        synthetic_form(),
        {"02": {"source": carried, "bindings": (fed_by("m130.anterior", BindingSourceKind.PREVIOUS_FILING),)}},
    )
    unbound = replace_fields(synthetic_form(), {"02": {"source": carried, "bindings": ()}})
    with override_settings(cadrumo_output_language="en"):
        group = {group.kind: group for group in source_groups(bound)}[SourceGroupKind.EARLIER_DECLARATIONS]
        summary = group_summary(group)
        headings = [getattr(item, "text", None) for item in group_items(group, staged={})]
        unbound_group = {group.kind: group for group in source_groups(unbound)}[SourceGroupKind.EARLIER_DECLARATIONS]
        unbound_summary = group_summary(unbound_group)
        generic = tr(source_policy(BindingSourceKind.PREVIOUS_FILING).label_key)

    assert summary == "Modelo 130 · 4th quarter 2025"
    assert headings[:2] == ["« Earlier declarations", "Modelo 130 · 4th quarter 2025"]
    assert unbound_group.readings == ()
    assert unbound_summary == "Modelo 130 · 4th quarter 2025"
    assert generic not in summary


def test_a_filed_declaration_keeps_its_unentered_values_in_their_own_groups_and_asks_for_nothing() -> None:
    unentered = replace_fields(
        synthetic_form(needs_input=True), {"07": {"origin": ModeloFormOrigin.DEFAULT_TO_CONFIRM}}
    )
    filed = recorded_as_filed(unentered)
    open_groups = {group.kind: group for group in source_groups(unentered)}
    recorded_groups = {group.kind: group for group in source_groups(filed)}
    with override_settings(cadrumo_output_language="en"):
        open_names = [str(group_prompt(open_groups[kind], expanded=True)) for kind in _ASKING_GROUPS]
        filed_names = [str(group_prompt(recorded_groups[kind], expanded=True)) for kind in _ASKING_GROUPS]
        filed_rows = [
            item.origin_words
            for kind in _ASKING_GROUPS
            for item in group_items(recorded_groups[kind], staged={})
            if isinstance(item, CasillaListEntry)
        ]
        needs_you = tr("tui.modelo.workbench.sources.group.needs_you")

    # A value nobody entered was held, never calculated, so filing does not move it to the calculated group.
    for kind, box in zip(_ASKING_GROUPS, ("07", "06"), strict=True):
        assert [field.box for field in open_groups[kind].fields] == [box]
        assert [field.box for field in recorded_groups[kind].fields] == [box]
    assert "07" not in [field.box for field in recorded_groups[SourceGroupKind.CALCULATED].fields]
    assert open_names == ["▿ ◐ Assumed, please confirm · Boxes: 1", f"▿ ! {needs_you} · Boxes: 1"]
    assert filed_names == ["▿   Assumed, nobody entered them · Boxes: 1", "▿   Empty, nobody filled them in · Boxes: 1"]
    assert filed_rows == ["Assumed, nobody entered it", "Empty, nobody filled it in"]


_ASKING_GROUPS = (SourceGroupKind.ASSUMED, SourceGroupKind.NEEDS_YOU)


def test_every_owning_surface_opens_a_declared_destination_and_none_opens_nothing() -> None:
    for surface in SourceSurface:
        target = surface_target(surface)
        if surface is SourceSurface.NONE:
            assert target is None
        else:
            assert target is not None
            assert target.destination in declared_destination_ids()


@pytest.mark.asyncio
async def test_the_map_opens_on_the_group_of_the_box_under_the_cursor_and_enter_opens_another() -> None:
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            await pilot.press("s")
            await _settle(pilot)
            sources = app.screen
            assert isinstance(sources, WorkbenchSourcesScreen)
            title = str(sources.query_one("#sources-title", Static).render())
            groups = sources.query_one("#sources-groups", OptionList)
            opened_group = groups.highlighted
            opened_on = sources.query_one(CasillaList).highlighted
            first_listing = _lines(sources.query_one(CasillaList))
            first_groups = _group_lines(groups)
            await pilot.press("shift+tab", "home", "enter")
            await _settle(pilot)
            records_listing = _lines(sources.query_one(CasillaList))
            records_groups = _group_lines(groups)
            focused_list = sources.focused is sources.query_one(CasillaList)
            await pilot.press("enter")
            await _settle(pilot)
            back = app.screen is screen
            landed_on = screen.query_one(CasillaList).highlighted

    assert title.endswith("Casillas: 8")
    assert [line[:1] for line in first_groups if line[:1] in "▹▿"] == ["▹", "▹", "▿", "▹"]
    assert not any("[06]" in line for line in first_groups)
    assert [line[:1] for line in records_groups if line[:1] in "▹▿"] == ["▿", "▹", "▹", "▹"]
    assert any(line.strip() == "[06]" for line in records_groups)
    assert opened_group == 2
    assert opened_on is not None
    assert opened_on.field.box == "06"
    assert not any("[01]" in line for line in first_listing)
    assert any("[01]" in line for line in records_listing)
    assert focused_list
    assert back
    assert landed_on is not None
    assert landed_on.field.box == "01"


@pytest.mark.asyncio
async def test_opening_a_source_shows_staged_changes_and_asks_before_leaving_them() -> None:
    navigated: list[TuiNavigationTargetV1] = []
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions(), navigate=navigated.append)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            await pilot.press("enter")
            await _settle(pilot)
            await pilot.press(*"10", "enter")
            await _settle(pilot)
            await pilot.press("s")
            await _settle(pilot)
            staged_line = next(
                line for line in _lines(app.screen.query_one(CasillaList)) if "Retenciones e ingresos" in line
            )
            await pilot.press("o")
            await _settle(pilot)
            asked = isinstance(app.screen, ConfirmScreen)
            navigated_before_answer = list(navigated)
            await pilot.press("y")
            await _settle(pilot)

    assert "Δ" in staged_line
    assert asked
    assert navigated_before_answer == []
    assert [target.destination for target in navigated] == ["workbench.withholding"]


@pytest.mark.asyncio
async def test_a_box_no_other_area_fills_says_so_instead_of_opening_anything() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            await pilot.press("s")
            await _settle(pilot)
            sources = app.screen
            await pilot.press("shift+tab", "end", "enter")
            await _settle(pilot)
            await pilot.press("o")
            await _settle(pilot)
            still_open = app.screen is sources
            notice = str(sources.query_one("#sources-notice", Static).render())

    assert still_open
    assert notice == "This box is not filled from another area."


@pytest.mark.asyncio
async def test_without_a_way_to_open_other_areas_the_workbench_says_where_to_find_the_source() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            await pilot.press("s")
            await _settle(pilot)
            await pilot.press("o")
            await _settle(pilot)
            back = app.screen is screen
            notice = str(screen.query_one("#wb-notice", Static).render())

    assert back
    assert notice == "That area cannot be opened from here; open it from the main menu."


@pytest.mark.asyncio
async def test_choosing_a_box_the_filer_may_change_opens_its_editor_in_the_workbench() -> None:
    with override_settings(cadrumo_output_language="es"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            await pilot.press("s")
            await _settle(pilot)
            sources = app.screen
            assert isinstance(sources, WorkbenchSourcesScreen)
            chosen = sources.query_one(CasillaList).highlighted
            await pilot.press("enter")
            await _settle(pilot)
            on_top = app.screen
            editor = open_panel(on_top)
            landed_on = screen.query_one(CasillaList).highlighted

    assert chosen is not None
    assert chosen.field.box == "06"
    assert on_top is screen, "the sources view closed onto the workbench"
    assert editor is not None
    assert editor.field.box == "06"
    assert landed_on is not None
    assert landed_on.field.box == "06"


@pytest.mark.asyncio
async def test_the_declarations_status_line_leads_the_map_and_the_title_is_strong() -> None:
    status = "To pay 1,300.00 € · file by 20 Apr 2026"
    with override_settings(cadrumo_output_language="en"):
        screen = WorkbenchSourcesScreen(synthetic_form(), language=OutputLanguage.EN, staged={}, status_line=status)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            children = list(screen.query_one("#sources-panel").children)
            shown = str(children[0].render()) if isinstance(children[0], Static) else ""
            title = screen.query_one("#sources-title", Static).rich_style
            intro = screen.query_one("#sources-intro", Static).rich_style
            app.exit(None)
        plain = WorkbenchSourcesScreen(synthetic_form(), language=OutputLanguage.EN, staged={})
        plain_app = ScreenHostApp(plain)
        async with plain_app.run_test(size=_SIZE) as pilot:
            await _settle(pilot)
            without = [child.id for child in plain.query_one("#sources-panel").children]
            plain_app.exit(None)

    assert children[0].id == "sources-status"
    assert shown == status
    assert without[0] == "sources-title"
    assert "sources-status" not in without
    assert title.bold
    assert title.color != intro.color
