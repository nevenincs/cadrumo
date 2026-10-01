"""Registry-backed creation stays a keyboard-confirmed, two-step decision."""

from __future__ import annotations

import pytest
from textual.widgets import Button, DataTable, Input, Static

from .....application.modelo.declaration_targets import DeclarationTarget, declaration_targets
from .....core.config import override_settings
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import tr
from .....core.period import Period
from .....domain.calculations.registry.authority import bundled_indexed_authority
from ...components.host import ScreenHostApp
from ...tests.frame import geometry_band
from ..picker import NewDeclarationPicker

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", tuple(OutputLanguage))
@pytest.mark.parametrize("theme", ("cadrumo-dark", "cadrumo-light"))
@pytest.mark.parametrize("size", ((80, 24), (120, 40)))
async def test_picker_requires_modelo_period_and_confirmation_in_every_locale_and_theme(
    locale: OutputLanguage, theme: str, size: tuple[int, int]
) -> None:
    with bundled_indexed_authority().operation() as operation:
        admitted = declaration_targets(operation)
    selected = DeclarationTarget("111", Period.from_year_and_code(2025, "2T"))
    targets = (
        DeclarationTarget("111", Period.from_year_and_code(2025, "1T")),
        selected,
        DeclarationTarget("130", Period.from_year_and_code(2025, "1T")),
    )
    assert all(target in admitted for target in targets)
    with override_settings(cadrumo_output_language=locale.value):
        picker = NewDeclarationPicker(targets, frozenset({"130"}))
        app = ScreenHostApp(picker)
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            await pilot.pause()
            table = picker.query_one("#declaration-picker-table", DataTable)
            create = picker.query_one("#declaration-picker-create", Button)
            assert app.focused is table
            assert tuple(row.key.value for row in table.ordered_rows) == ("130",)
            assert create.disabled and picker.selected is None
            assert not create.display
            assert str(picker.query_one("#declaration-picker-cancel", Button).label) == tr(
                "tui.modelo.workbench.editor.cancel"
            )
            assert not picker.query(Input)
            assert geometry_band(app, size[0]) == []
            assert table.max_scroll_x == 0
            await pilot.press("tab", "enter")
            await pilot.pause()
            assert tuple(row.key.value for row in table.ordered_rows) == ("111", "130")
            assert app.focused is table
            assert geometry_band(app, size[0]) == []
            assert table.max_scroll_x == 0
            await pilot.press("enter")
            await pilot.pause()
            assert picker.modelo == "111"
            assert table.row_count == 2
            assert create.disabled and picker.selected is None
            assert create.display
            assert "2025" in str(table.get_row_at(0)[0])
            assert "2025" in str(table.get_row_at(1)[0])
            await pilot.press("escape")
            await pilot.pause()
            assert picker.modelo is None and picker.selected is None
            assert create.disabled
            assert not create.display
            await pilot.press("enter", "down", "enter")
            await pilot.pause()
            assert picker.selected == selected
            assert app.focused is create
            assert not create.disabled
            assert "2025" in str(picker.query_one("#declaration-picker-selection", Static).render())
            rendered = "\n".join(str(item.render()) for item in picker.query(Static))
            assert "tui." not in rendered
            assert geometry_band(app, size[0]) == []
            assert table.max_scroll_x == 0
            await pilot.press("enter")
        assert app.return_value == selected


@pytest.mark.asyncio
async def test_cancel_and_escape_never_create_an_unselected_declaration() -> None:
    target = DeclarationTarget("130", Period.from_year_and_code(2026, "1T"))
    picker = NewDeclarationPicker((target,), frozenset({"130"}))
    app = ScreenHostApp(picker)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("enter", "escape")
        await pilot.pause()
        assert picker.modelo is None and picker.selected is None
        await pilot.press("escape")
    assert app.return_value is None
