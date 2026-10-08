"""Pending intent cannot export or record a different saved declaration."""

from __future__ import annotations

from decimal import Decimal

import pytest
from textual.widgets import Input, Static

from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ....components.dialogs import ConfirmScreen
from ....components.host import ScreenHostApp
from ..export import WorkbenchExportScreen
from ..screen import ModeloWorkbenchScreen
from .workbench_fixture import FakeActions, FakeReader, synthetic_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _stage(screen: ModeloWorkbenchScreen, intent: str, *, refresh: bool = True) -> None:
    assert screen.form is not None
    field = next(field for field in screen.form.fields() if field.box == "06")
    if intent == "clear":
        assert screen._session.stage_clear(field) is None
    else:
        value = {"true": True, "false": False, "zero": Decimal(0)}[intent]
        assert screen._session.stage_value(field, value, str(value)) is None
    if refresh:
        screen._refresh_after_staging()


@pytest.mark.asyncio
@pytest.mark.parametrize("language", list(OutputLanguage))
@pytest.mark.parametrize("intent", ["true", "false", "zero", "clear"])
async def test_verified_saved_values_cannot_bypass_pending_intent_at_either_output_boundary(
    language: OutputLanguage, intent: str
) -> None:
    actions = FakeActions()
    with override_settings(cadrumo_output_language=language.value):
        screen = ModeloWorkbenchScreen(
            FakeReader(form=synthetic_form(needs_input=False), verified=True), actions=actions
        )
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert screen._load is not None
            saved_progress = screen._progress(screen._load)
            assert not saved_progress.filing_withheld and screen._load.verified
            _stage(screen, intent)
            staged = screen.staged_changes
            await pilot.press("e")
            await pilot.pause()
            assert app.screen is screen and screen.staged_changes == staged
            assert "[R]" in str(screen.query_one("#wb-notice", Static).render())
            assert screen.active_bindings["R"].binding.show
            screen._confirm_file(actions.file)
            await pilot.pause()
            assert app.screen is screen and screen.staged_changes == staged
            assert actions.exports == [] and actions.requested == []
            assert screen.form is not None
            assert next(field for field in screen.form.fields() if field.box == "06").value == Decimal("300.00")
            app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["export", "record"])
async def test_output_dialog_submission_rechecks_new_pending_intent(boundary: str) -> None:
    actions = FakeActions()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(
            FakeReader(form=synthetic_form(needs_input=False), verified=True), actions=actions
        )
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            if boundary == "export":
                await pilot.press("e")
                await pilot.pause()
                assert isinstance(app.screen, WorkbenchExportScreen)
                path = app.screen.query_one("#export-path", Input)
                path.value = "pending-output-test.boe"
            else:
                screen._confirm_file(actions.file)
                await pilot.pause()
                assert isinstance(app.screen, ConfirmScreen)
            _stage(screen, "false", refresh=False)
            staged = screen.staged_changes
            if boundary == "export":
                await pilot.click("#export-submit")
            else:
                await pilot.click("#btn-confirm-accept")
            await pilot.pause()
            await pilot.pause()
            assert app.screen is screen and screen.staged_changes == staged
            assert actions.exports == [] and actions.requested == []
            assert "[R]" in str(screen.query_one("#wb-notice", Static).render())
            app.exit(None)
