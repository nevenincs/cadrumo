"""Visible guidance follows admitted row actions without changing filing facts."""

from __future__ import annotations

import pytest
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Input, Static

from .....application.modelo.declaration_summary import DeclarationSummary, DeclarationSummaryState
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.period import Period
from ...components.host import ScreenHostApp
from ...modelo.lifecycle import ModeloLifecycleActionUnavailableError
from ...navigation import TuiScreenContextV1
from ...tests.frame import geometry_band
from ..controller import DeclarationsWorkspaceController
from ..models import DeclarationsWorkspaceWiringV1, ModeloWorkCreateResultV1
from ..overview import DeclarationsOverviewScreen
from .portfolio_fixtures import portfolio_projection

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _refuse_creation(modelo: str, year: int, period: Period) -> ModeloWorkCreateResultV1:
    raise ModeloLifecycleActionUnavailableError(
        translated_message="tui.declarations.refusal.handoff",
        context={"modelo": modelo, "year": year, "period": period.registry_token},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", tuple(OutputLanguage))
@pytest.mark.parametrize("theme", ("cadrumo-dark", "cadrumo-light"))
@pytest.mark.parametrize("size", ((80, 24), (120, 40)))
async def test_group_and_row_guidance_stays_visible_and_local_recording_stays_separate(
    locale: OutputLanguage, theme: str, size: tuple[int, int]
) -> None:
    workspace, calendar = portfolio_projection()
    draft = workspace.declarations[1].model_copy(
        update={"has_current_calculation": False, "summary": DeclarationSummary(state=DeclarationSummaryState.DRAFT)}
    )
    workspace = workspace.model_copy(
        update={"declarations": (workspace.declarations[0], draft, *workspace.declarations[2:])}
    )
    controller = DeclarationsWorkspaceController(
        TuiScreenContextV1(destination="workbench.declarations"),
        workspace,
        DeclarationsWorkspaceWiringV1(
            work_action=ActionReference(action_id=lookup_action("operator.modelo.work.list").action_id),
            revisions_action=ActionReference(action_id=lookup_action("operator.modelo.work.revisions").action_id),
            filing_action=ActionReference(action_id=lookup_action("operator.modelo.filing_record.list").action_id),
            calendar_projection=calendar,
            modelo_workspace_factory=lambda declaration: Screen(),
            work_create_handoff=_refuse_creation,
        ),
    )
    with override_settings(cadrumo_output_language=locale.value):
        screen = DeclarationsOverviewScreen(controller)
        app = ScreenHostApp(screen)
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            await pilot.pause()
            table = screen.query_one("#declarations-list", DataTable)
            guidance = screen.query_one("#declarations-keys", Static)
            page = screen.query_one("#declarations-page", VerticalScroll)
            assert "Enter " + tr("tui.declarations.list.key.toggle_group") in str(guidance.render())
            assert "+ " + tr("tui.declarations.list.key.new") in str(guidance.render())
            for key, label in (("/", "search"), ("f", "filter"), ("s", "sort")):
                assert key + " " + tr("tui.modelo.workbench.key." + label) in str(guidance.render())
            assert "t " + tr("tui.modelo.workbench.issues.technical") in str(guidance.render())
            assert guidance.region.bottom <= page.region.y
            original_region = guidance.region
            page.scroll_end(animate=False)
            await pilot.pause()
            assert guidance.region == original_region and screen.region.contains_region(guidance.region)
            assert geometry_band(app, size[0]) == []
            assert table.max_scroll_y == 0, (
                table.styles.max_height,
                table.styles.height,
                table.size,
                table.virtual_size,
                table.styles.css,
            )

            await pilot.press("down", "ctrl+home")
            await pilot.pause()
            assert table.cursor_row == 0
            await pilot.press("down", "down", "down", "down")
            await pilot.pause()
            assert table.cursor_row == 4
            assert table.max_scroll_y == 0

            def selected_row_is_visible() -> None:
                row_top = (
                    table.region.y
                    + (table.header_height if table.show_header else 0)
                    + sum(row.height for row in table.ordered_rows[: table.cursor_row])
                )
                row_bottom = row_top + table.ordered_rows[table.cursor_row].height
                viewport = page.scrollable_content_region
                assert viewport.y <= row_top < row_bottom <= viewport.bottom
                assert table.max_scroll_y == 0 and table.scroll_y == 0

            selected_row_is_visible()
            for key in ("ctrl+end", "up", "home", "end", "ctrl+home"):
                await pilot.press(key)
                await pilot.pause()
                selected_row_is_visible()

            def select(key: str) -> None:
                index = next(index for index, row in enumerate(table.ordered_rows) if row.key.value == key)
                table.move_cursor(row=index)

            select(str(draft.work_unit_id))
            await pilot.pause()
            assert "Enter " + tr("tui.declarations.list.next.open_local_draft") in str(guidance.render())
            assert tr("tui.modelo.workbench.origin.not_calculated_yet") in str(table.get_row_at(table.cursor_row)[1])
            external = next(row for row in screen.rows if row.state == "aeat_unlinked")
            select(external.key)
            await pilot.pause()
            assert "Enter " + tr("tui.declarations.calendar.action.open") in str(guidance.render())
            select("group:aeat_unlinked")
            await pilot.pause()
            selected_row_is_visible()
            assert tr("tui.declarations.list.state.aeat_unlinked") in str(
                table.get_row_at(table.cursor_row)[0]
            ).replace("\n", " ")
            await pilot.press("enter")
            await pilot.pause()
            selected_row_is_visible()
            assert external.key not in {row.key.value for row in table.ordered_rows}
            await pilot.press("enter")
            await pilot.pause()
            selected_row_is_visible()
            assert external.key in {row.key.value for row in table.ordered_rows}
            due = next(row for row in screen.rows if row.state == "not_started")
            select(due.key)
            await pilot.pause()
            assert "Enter " + tr("tui.declarations.list.next.start") in str(guidance.render())

            await pilot.press("f", "f", "f")
            keys = {row.key.value for row in table.ordered_rows if not str(row.key.value).startswith("group:")}
            assert keys == {"d" * 64}
            assert external.key not in keys
            await pilot.press("/")
            await pilot.pause()
            assert app.focused is screen.query_one("#declarations-search", Input)
            assert "Enter" not in str(guidance.render())
            await pilot.press("tab")
            await pilot.pause()
            assert table.has_focus
            selected_row_is_visible()
            controller.modelo_workspace_factory = None
            controller.work_create_handoff = None
            screen.filter_index = 0
            screen._populate()
            select(str(draft.work_unit_id))
            await pilot.pause()
            assert "Enter" not in str(guidance.render())
            assert "+ " not in str(guidance.render())
            assert geometry_band(app, size[0]) == [] and table.max_scroll_x == 0, (
                table.size,
                table.container_size,
                table.virtual_size,
                table.scrollbar_size_vertical,
                [(column.width, column.label) for column in table.columns.values()],
                page.size,
                guidance.region,
            )
            assert table.max_scroll_y == 0
