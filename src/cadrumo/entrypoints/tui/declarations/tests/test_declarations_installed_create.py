"""The installed picker persists new work and opens its fresh admission."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Button, DataTable

from .....application.user_profile.login_interaction import ProfileLoginChoice
from .....core.period import Period
from ....tests.modelo_operator_work_storage import seeded_operator_work
from ...components.dialogs import ConfirmScreen
from ...components.host import ScreenHostApp
from ...installed_session import compose_authenticated_root_inputs_provider
from ...launcher import compose_installed_workbench_root, operation_services_scope
from ...modelo.workbench.screen import ModeloWorkbenchScreen
from ...navigation import TuiScreenContextV1
from ..overview import DeclarationsOverviewScreen
from ..picker import NewDeclarationPicker

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_installed_creation_opens_a_persisted_new_period_and_returns_to_that_row(tmp_path: Path) -> None:
    with seeded_operator_work(tmp_path) as persisted:
        provider = compose_authenticated_root_inputs_provider(
            profile_id=persisted.work_unit.bucket_id,
            profile_label="Synthetic operator",
            login_choices=(ProfileLoginChoice(persisted.work_unit.bucket_id, "Synthetic operator"),),
        )
        async with operation_services_scope() as runtime:
            root = compose_installed_workbench_root(provider(runtime))
            route = root.destination_catalogue.resolve("workbench.declarations")
            assert route.factory is not None
            screen = route.factory(TuiScreenContextV1(destination="workbench.declarations"))
            assert isinstance(screen, DeclarationsOverviewScreen)
            target = Period.from_year_and_code(2026, "2T")
            assert len(persisted.ports.work_unit_repository.load().work_units) == 1
            app = ScreenHostApp(screen)
            async with app.run_test(size=(100, 40)) as pilot:
                await pilot.pause()
                await pilot.press("plus")
                await pilot.pause()
                picker = app.screen
                assert isinstance(picker, NewDeclarationPicker)
                table = picker.query_one("#declaration-picker-table", DataTable)
                table.move_cursor(row=next(i for i, row in enumerate(table.ordered_rows) if row.key.value == "130"))
                table.focus()
                await pilot.press("enter")
                await pilot.pause()
                table.move_cursor(row=next(i for i, item in enumerate(picker.visible_targets) if item.period == target))
                await pilot.press("enter")
                await pilot.pause()
                assert app.focused is picker.query_one("#declaration-picker-create", Button)
                await pilot.press("enter")
                await app.workers.wait_for_complete()
                await pilot.pause()
                await app.workers.wait_for_complete()
                await pilot.pause()
                assert isinstance(app.screen, ModeloWorkbenchScreen)
                new_units = tuple(
                    unit
                    for unit in persisted.ports.work_unit_repository.load().work_units.values()
                    if unit.period == target
                )
                assert len(new_units) == 1
                created = new_units[0]
                assert created.modelo == "130" and created.filing_year == 2026
                assert created.work_unit_id != persisted.work_unit_id
                assert app.screen.form is not None
                assert app.screen.form.work_unit_id == created.work_unit_id
                assert app.screen.form.period == target
                app.screen.dismiss(None)
                await pilot.pause()
                assert app.screen is screen
                table = screen.query_one("#declarations-list", DataTable)
                assert app.focused is table
                assert table.ordered_rows[table.cursor_row].key.value == created.work_unit_id
                assert len(persisted.ports.work_unit_repository.load().work_units) == 2
                before_reopen = persisted.ports.work_unit_repository.load()
                for confirm in (False, True):
                    await pilot.press("plus")
                    await pilot.pause()
                    picker = app.screen
                    assert isinstance(picker, NewDeclarationPicker)
                    table = picker.query_one("#declaration-picker-table", DataTable)
                    table.move_cursor(row=next(i for i, row in enumerate(table.ordered_rows) if row.key.value == "130"))
                    table.focus()
                    await pilot.press("enter")
                    await pilot.pause()
                    table.move_cursor(
                        row=next(i for i, item in enumerate(picker.visible_targets) if item.period == target)
                    )
                    await pilot.press("enter", "enter")
                    await pilot.pause()
                    assert isinstance(app.screen, ConfirmScreen)
                    assert app.focused is app.screen.query_one("#btn-confirm-cancel", Button)
                    assert persisted.ports.work_unit_repository.load() == before_reopen
                    await pilot.press("y" if confirm else "escape")
                    await pilot.pause()
                    if confirm:
                        await app.workers.wait_for_complete()
                        await pilot.pause()
                        assert isinstance(app.screen, ModeloWorkbenchScreen)
                        assert app.screen.form is not None and app.screen.form.work_unit_id == created.work_unit_id
                        app.screen.dismiss(None)
                        await pilot.pause()
                    assert app.screen is screen
                    assert persisted.ports.work_unit_repository.load() == before_reopen
