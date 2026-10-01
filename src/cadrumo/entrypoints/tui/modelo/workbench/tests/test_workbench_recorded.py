"""A declaration recorded as filed opens read only and says so, without asking the filer for anything.

Driven through the workbench over the synthetic form recorded as filed: the
journey says when it was recorded, once, even on a small terminal; no deadline, attention chip,
navigator count or row blocker mark asks for anything; every box opens its panel read only; and
recording the filing again, confirming values or recalculating is refused with
the same words. Its help and its legend name no key that would change it.
"""

from __future__ import annotations

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, OptionList, Static

from ......application.modelo.work_form_models import ModeloFormBlocker
from ......core.config import override_settings
from ......core.i18n.render import lookup_translation, tr
from ....components.host import ScreenHostApp
from ..casilla_list import CasillaList, CasillaListEntry
from ..screen import ModeloWorkbenchScreen
from .declaration_states import recorded_as_filed, with_deadline, with_findings
from .editor_panel import open_panel
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
            panel = open_panel(app.screen)
            assert panel is not None
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
async def test_a_small_terminal_says_recorded_as_filed_once() -> None:
    form = recorded_as_filed(synthetic_form(needs_input=False))
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form, verified=True, filed=True), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await _settle(pilot)
            # The notice surfaces: the header and the journey line, and whatever else states the declaration.
            notices = "\n".join(
                str(widget.render())
                for widget in screen.query(Static)
                if widget.display and widget.region.area and widget.id != "wb-help"
            )
            band = str(screen.query_one("#wb-help", Static).render())
            correction = tr("tui.modelo.workbench.editor.can_change.recorded")
            app.exit(None)

    assert notices.lower().count("recorded as filed") == 1, notices
    # The help band answers "can I change it" for the box under the cursor, with the way to correct it.
    assert correction in band


_CHANGE_KEY_WORDS = (
    "tui.modelo.workbench.bulk_confirm.title",
    "tui.modelo.workbench.key.next_step",
    "tui.modelo.workbench.key.review",
    "tui.modelo.workbench.key.calculate",
    "tui.modelo.workbench.key.next_attention",
)
"""What the keys that change a declaration, or lead to something left to do, are called."""


@pytest.mark.asyncio
async def test_the_help_and_the_legend_of_a_recorded_declaration_name_no_key_that_asks_for_anything() -> None:
    form = recorded_as_filed(synthetic_form())
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(FakeReader(form=form, verified=True, filed=True), actions=FakeActions())
        app = ScreenHostApp(screen)
        async with app.run_test(size=(160, 48)) as pilot:
            await _settle(pilot)
            await pilot.press("question_mark")
            await _settle(pilot)
            band = str(screen.query_one("#wb-help", Static).render())
            await pilot.press("question_mark")
            await _settle(pilot)
            legend = str(screen.query_one("#wb-legend-text", Static).render())
            app.exit(None)

    words = [lookup_translation(key, locale="en") for key in _CHANGE_KEY_WORDS]
    open_box = lookup_translation("tui.modelo.workbench.sources.key.go", locale="en")
    edit = lookup_translation("tui.modelo.workbench.key.edit", locale="en")
    assert all(words)
    assert open_box is not None and edit is not None
    assert open_box in band, "the help band still names the keys a reader uses"
    assert f"⏎ {edit}" not in band, "Enter opens a box to read, not to edit"
    for text in (band, legend):
        named = [segment.strip() for line in text.splitlines() for segment in line.split(" · ")]
        for word in words:
            assert not [segment for segment in named if segment.endswith(f" {word}")], (
                f"a recorded declaration's help names the key for {word!r}"
            )


@pytest.mark.asyncio
async def test_on_a_recorded_declaration_enter_is_named_for_opening_the_box_not_editing_it() -> None:
    with override_settings(cadrumo_output_language="en"):
        draft = ModeloWorkbenchScreen(FakeReader(form=synthetic_form()), actions=FakeActions())
        draft_app = ScreenHostApp(draft)
        async with draft_app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            draft_enter = draft.query_one(CasillaList).binding_for("enter")
            draft_app.exit(None)
        filed = ModeloWorkbenchScreen(
            FakeReader(form=recorded_as_filed(synthetic_form()), verified=True, filed=True), actions=FakeActions()
        )
        filed_app = ScreenHostApp(filed)
        async with filed_app.run_test(size=(140, 40)) as pilot:
            await _settle(pilot)
            filed_enter = filed.query_one(CasillaList).binding_for("enter")
            filed_app.exit(None)

    assert draft_enter is not None and draft_enter.description == tr("tui.modelo.workbench.key.edit", locale="en")
    assert filed_enter is not None and filed_enter.description == tr("tui.modelo.workbench.sources.key.go", locale="en")
