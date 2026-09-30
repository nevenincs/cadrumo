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

from collections import Counter
from decimal import Decimal

import pytest
from textual.pilot import Pilot
from textual.widgets import OptionList, Static

from ......application.modelo.source_policy import SourceFamily, SourceSurface
from ......application.modelo.work_form_models import (
    ModeloFormEditability,
    ModeloFormOrigin,
    ModeloFormValueSource,
    ModeloWorkForm,
    address_key,
)
from ......core.aggregation import BindingSourceKind
from ......core.config import override_settings
from ....components.dialogs import ConfirmScreen
from ....components.host import ScreenHostApp
from ....navigation import TuiNavigationTargetV1, declared_destination_ids
from ..casilla_list import CasillaList, CasillaListEntry
from ..editor import CasillaEditorScreen
from ..screen import ModeloWorkbenchScreen
from ..sources import (
    SourceGroupKind,
    SourceState,
    WorkbenchSourcesScreen,
    group_items,
    group_summary,
    source_groups,
    surface_target,
)
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, fed_by, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SIZE = (140, 40)


async def _settle(pilot: Pilot[None], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


def _lines(widget: CasillaList) -> list[str]:
    return [widget.render_line(y).text.rstrip() for y in range(widget.size.height)]


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
    assert assumed == "[07]"
    assert replaced == "[02]"


def test_a_group_lists_its_boxes_under_each_of_its_sources() -> None:
    with override_settings(cadrumo_output_language="es"):
        items = group_items(source_groups(synthetic_form())[0], staged={})
        texts = [
            item.field.box if isinstance(item, CasillaListEntry) else getattr(item, "text", None) for item in items
        ]

    assert texts == [
        "↓ Tus registros",
        "Totales de ingresos",
        "01",
        "Totales de gastos en estimación directa",
        "02",
    ]


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
            await pilot.press("shift+tab", "home", "enter")
            await _settle(pilot)
            records_listing = _lines(sources.query_one(CasillaList))
            focused_list = sources.focused is sources.query_one(CasillaList)
            await pilot.press("enter")
            await _settle(pilot)
            back = app.screen is screen
            landed_on = screen.query_one(CasillaList).highlighted

    assert title.endswith("Casillas: 8")
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
            editor = app.screen
            landed_on = screen.query_one(CasillaList).highlighted

    assert chosen is not None
    assert chosen.field.box == "06"
    assert isinstance(editor, CasillaEditorScreen)
    assert landed_on is not None
    assert landed_on.field.box == "06"
