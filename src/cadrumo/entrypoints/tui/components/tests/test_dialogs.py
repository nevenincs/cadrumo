"""Pilot-driven proofs for reusable form-field dialogs."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, SelectionList, Static

from .....core.presentation import FormField, FormFieldKind, form_choices
from ..dialogs import ChoiceEditScreen, ConfirmScreen, OneChoiceEditScreen, TextEditScreen

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TERMINAL_SIZE = (140, 60)


class _Host(App[None]):
    """A running application that supplies a screen stack to one dialog."""


@pytest.mark.asyncio
async def test_confirmation_dialog_defaults_to_decline_and_requires_explicit_acceptance() -> None:
    app = _Host()
    dismissed: list[bool | None] = []

    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        app.push_screen(
            ConfirmScreen(
                title="Restart?", message="Answers will be cleared.", confirm_label="Restart", cancel_label="Keep"
            ),
            dismissed.append,
        )
        await pilot.pause()

        assert app.focused is app.screen.query_one("#btn-confirm-cancel")
        await pilot.press("y")
        await pilot.pause()
        assert dismissed == [True]
        app.exit(None)


@pytest.mark.asyncio
async def test_text_dialog_refuses_an_invalid_value_before_dismissing() -> None:
    app = _Host()
    dismissed: list[str | None] = []
    field = FormField(key="name", label="Name", validate=lambda value: "NO" if value == "bad" else None)

    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        app.push_screen(TextEditScreen(field, cancel_label="Cancel", save_label="Save"), dismissed.append)
        await pilot.pause()

        dialog = app.screen
        dialog.query_one("#edit-input", Input).value = "bad"
        await pilot.click("#btn-edit-save")
        await pilot.pause()

        assert dismissed == []
        assert str(dialog.query_one("#edit-refusal", Static).content) == "NO"

        accepted_input = dialog.query_one("#edit-input", Input)
        accepted_input.value = "accepted"
        accepted_input.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert dismissed == ["accepted"]
        app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dialog",
    (
        TextEditScreen(FormField(key="name", label="Name"), cancel_label="Cancel", save_label="Save"),
        ChoiceEditScreen(
            FormField(
                key="scopes",
                label="Scopes",
                kind=FormFieldKind.MULTI_CHOICE,
                choices=form_choices([("READ", "Read")]),
            ),
            cancel_label="Cancel",
            save_label="Save",
        ),
        OneChoiceEditScreen(
            FormField(
                key="route",
                label="Route",
                kind=FormFieldKind.SINGLE_CHOICE,
                choices=form_choices([("qr", "QR code")]),
            ),
            cancel_label="Cancel",
            save_label="Save",
        ),
    ),
    ids=("text", "multi-choice", "one-choice"),
)
async def test_edit_dialog_escape_dismisses_without_saving(dialog: ModalScreen[str | None]) -> None:
    app = _Host()
    dismissed: list[str | None] = []

    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        app.push_screen(dialog, dismissed.append)
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert dismissed == [None]
        app.exit(None)


@pytest.mark.asyncio
async def test_multi_choice_dialog_preserves_selected_storage_tokens() -> None:
    app = _Host()
    dismissed: list[str | None] = []
    field = FormField(
        key="scopes",
        label="Scopes",
        value="READ",
        kind=FormFieldKind.MULTI_CHOICE,
        choices=form_choices([("READ", "Read"), ("WRITE", "Write")]),
    )

    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        app.push_screen(ChoiceEditScreen(field, cancel_label="Cancel", save_label="Save"), dismissed.append)
        await pilot.pause()

        app.screen.query_one("#edit-choices", SelectionList).select_all()
        await pilot.click("#btn-edit-save")
        await pilot.pause()
        assert dismissed == ["READ,WRITE"]
        app.exit(None)


@pytest.mark.asyncio
async def test_one_choice_dialog_keeps_the_declared_value_highlighted() -> None:
    app = _Host()
    dismissed: list[str | None] = []
    field = FormField(
        key="route",
        label="Route",
        value="app_request",
        kind=FormFieldKind.SINGLE_CHOICE,
        choices=form_choices([("qr", "QR code"), ("app_request", "Request in app")]),
    )

    async with app.run_test(size=_TERMINAL_SIZE) as pilot:
        await pilot.pause()
        app.push_screen(OneChoiceEditScreen(field, cancel_label="Cancel", save_label="Save"), dismissed.append)
        await pilot.pause()

        assert app.screen.query_one("#edit-options", OptionList).highlighted == 1
        await pilot.click("#btn-edit-save")
        await pilot.pause()
        assert dismissed == ["app_request"]
        app.exit(None)
