"""A declaration recorded as filed opens read only and says so, without asking the filer for anything.

Driven through the workbench over the synthetic form recorded as filed: the
banner says it can be looked at but not changed and that changing it starts a
correction; the journey says when it was recorded; no deadline, attention chip,
navigator count or row blocker mark asks for anything; every box opens its panel read only; and
recording the filing again, confirming values or recalculating is refused with
the same words.
"""

from __future__ import annotations

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, OptionList, Static

from ......application.modelo.work_form_models import ModeloFormBlocker
from ......core.config import override_settings
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList, CasillaListEntry
from ..editor import CasillaEditorScreen
from ..screen import ModeloWorkbenchScreen
from .declaration_states import recorded_as_filed, with_deadline, with_findings
from .form_edits import replace_fields
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_READ_ONLY = (
    "Recorded as filed: you can look at it but not change it. To change it, start a correction of this declaration."
)


async def _settle(pilot: Pilot[None], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


@pytest.mark.asyncio
async def test_a_recorded_declaration_is_read_only_and_asks_for_nothing() -> None:
    blocked = replace_fields(synthetic_form(), {"06": {"blockers": (ModeloFormBlocker(code="missing_required"),)}})
    form = recorded_as_filed(with_deadline(with_findings(blocked, blocking=("06",)), days_left=2))
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form, verified=True, filed=True), actions=actions)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            banner = screen.query_one("#wb-banner", Static)
            shown = (banner.display, str(banner.render()))
            next_line = str(screen.query_one("#wb-next", Static).render())
            stepper = str(screen.query_one("#wb-stepper", Static).render())
            deadline_shown = screen.query_one("#wb-deadline", Static).display
            chips = str(screen.query_one("#wb-chips", Static).render())
            navigator = screen.query_one("#wb-sections", OptionList)
            prompts = [str(navigator.get_option_at_index(i).prompt) for i in range(navigator.option_count)]
            overlays = [
                item.attention for item in screen.query_one(CasillaList).items if isinstance(item, CasillaListEntry)
            ]
            await pilot.press("enter")
            await _settle(pilot)
            panel = app.screen
            assert isinstance(panel, CasillaEditorScreen)
            panel_state = (panel.read_only, len(panel.query(Input)))
            reason = str(panel.query_one("#editor-can-change-text", Static).render())
            await pilot.press("escape")
            await _settle(pilot)
            await pilot.press("f8")
            await _settle(pilot)
            after_f8 = (app.screen is screen, str(screen.query_one("#wb-notice", Static).render()))
            await pilot.press("b")
            await _settle(pilot)
            after_b = (app.screen is screen, str(screen.query_one("#wb-notice", Static).render()))
            screen.query_one("#wb-notice", Static).update("")
            await pilot.press("c")
            await _settle(pilot)
            after_c = str(screen.query_one("#wb-notice", Static).render())
            app.exit(None)

    assert shown == (True, _READ_ONLY)
    assert next_line == "Recorded as filed on 15/04/2026"
    assert stepper == "✓ Fill in ── ✓ Calculate ── ✓ Check ── ✓ Record filing"
    assert not deadline_shown
    assert chips == ""
    assert all(not set(prompt) & set("▲!◐◆✓") for prompt in prompts)
    assert overlays and not any(overlays)
    assert panel_state == (True, 0)
    assert reason
    assert after_f8 == (True, _READ_ONLY)
    assert after_b == (True, _READ_ONLY)
    assert after_c == _READ_ONLY
    assert actions.requested == []


@pytest.mark.asyncio
async def test_a_declaration_not_recorded_hides_the_banner() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            shown = screen.query_one("#wb-banner", Static).display
            app.exit(None)

    assert not shown
