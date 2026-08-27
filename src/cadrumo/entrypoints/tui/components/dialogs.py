"""Reusable, state-local dialogs for immutable form fields."""

from __future__ import annotations

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, SelectionList, Static

from ....core.presentation import FormField
from ..components.theme import tokenised

_MULTI_CHOICE_SEPARATOR = ","

_EDIT_DIALOG_CSS = tokenised("""
#edit-dialog {
    border: $cadrumo-radius-overlay $accent;
    background: $surface;
    padding: $cadrumo-space-0 $cadrumo-space-1;
    width: 100%;
    height: auto;
}
#edit-label { text-style: bold; }
#edit-path { color: $text-muted; margin: $cadrumo-space-0; }
#edit-refusal { color: $error; }
#edit-dialog Input { margin: $cadrumo-space-0; }
#edit-actions { height: auto; align-horizontal: right; margin: $cadrumo-space-0; }
#edit-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
""")
"""Styling carried by each dialog so every host renders it consistently."""

_CONFIRM_DIALOG_CSS = tokenised("""
#confirm-dialog {
    border: $cadrumo-radius-overlay $warning;
    background: $surface;
    padding: $cadrumo-space-0 $cadrumo-space-1;
    width: 100%;
    height: auto;
}
#confirm-title { text-style: bold; margin: $cadrumo-space-0; }
#confirm-message { color: $text; margin: $cadrumo-space-0; }
#confirm-actions { height: auto; align-horizontal: right; margin: $cadrumo-space-0; }
#confirm-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
""")


class ConfirmScreen(ModalScreen[bool]):
    """Ask before an irreversible action and default to declining it."""

    DEFAULT_CSS = _CONFIRM_DIALOG_CSS
    BINDINGS: ClassVar = [
        Binding("escape", "decline", "", show=False),
        Binding("y", "confirm", "", show=False),
    ]

    def __init__(self, *, title: str, message: str, confirm_label: str, cancel_label: str) -> None:
        """Store already-localized copy for one irreversible-action prompt."""
        super().__init__()
        self._title = title
        self._message = message
        self._confirm_label = confirm_label
        self._cancel_label = cancel_label

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(self._title, id="confirm-title")
            yield Static(self._message, id="confirm-message")
            with Horizontal(id="confirm-actions"):
                yield Button(self._cancel_label, id="btn-confirm-cancel")
                yield Button(self._confirm_label, id="btn-confirm-accept", classes="-primary", variant="error")

    def on_mount(self) -> None:
        """Focus the declining action as the safe default."""
        self.query_one("#btn-confirm-cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismiss with the boolean represented by the pressed button."""
        self.dismiss(event.button.id == "btn-confirm-accept")

    def action_decline(self) -> None:
        """Dismiss without approving the guarded intent."""
        self.dismiss(False)

    def action_confirm(self) -> None:
        """Dismiss with explicit approval."""
        self.dismiss(True)


class TextEditScreen(ModalScreen[str | None]):
    """Type one text value. Dismisses with the new value, or ``None``."""

    DEFAULT_CSS = _EDIT_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, field: FormField, *, cancel_label: str, save_label: str) -> None:
        """Store the immutable field descriptor that supplies this dialog."""
        super().__init__()
        self._field = field
        self._cancel_label = cancel_label
        self._save_label = save_label

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="edit-dialog"):
            yield Label(self._field.label, id="edit-label")
            if self._field.hint:
                yield Static(self._field.hint, id="edit-path")
            yield Input(value=self._field.value, password=self._field.secret, id="edit-input")
            yield Static(id="edit-refusal")
            with Horizontal(id="edit-actions"):
                yield Button(self._cancel_label, id="btn-edit-cancel")
                yield Button(self._save_label, id="btn-edit-save", classes="-primary")

    def on_mount(self) -> None:
        """Focus the text input as soon as the dialog opens."""
        self.query_one("#edit-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Save through the local validator or cancel the edit."""
        if event.button.id == "btn-edit-save":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Treat the text input's submit gesture as a save."""
        self._submit()

    def _submit(self) -> None:
        """Accept the typed value, or hold the dialog open showing why not."""
        candidate = self.query_one("#edit-input", Input).value
        refusal = self._field.validate(candidate) if self._field.validate is not None else None
        if refusal is not None:
            self.query_one("#edit-refusal", Static).update(refusal)
            return
        self.dismiss(candidate)

    def action_cancel(self) -> None:
        """Dismiss without changing the field value."""
        self.dismiss(None)


class ChoiceEditScreen(ModalScreen[str | None]):
    """Pick any number of options. Dismisses with a comma-joined token list."""

    DEFAULT_CSS = _EDIT_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, field: FormField, *, cancel_label: str, save_label: str) -> None:
        """Store the immutable field descriptor that supplies this dialog."""
        super().__init__()
        self._field = field
        self._cancel_label = cancel_label
        self._save_label = save_label

    @override
    def compose(self) -> ComposeResult:
        selected = {token for token in self._field.value.split(_MULTI_CHOICE_SEPARATOR) if token}
        with Vertical(id="edit-dialog"):
            yield Label(self._field.label, id="edit-label")
            if self._field.hint:
                yield Static(self._field.hint, id="edit-path")
            yield SelectionList[str](
                *[(choice.label, choice.value, choice.value in selected) for choice in self._field.choices],
                id="edit-choices",
            )
            with Horizontal(id="edit-actions"):
                yield Button(self._cancel_label, id="btn-edit-cancel")
                yield Button(self._save_label, id="btn-edit-save", classes="-primary")

    def on_mount(self) -> None:
        """Focus the selectable choices as soon as the dialog opens."""
        self.query_one("#edit-choices", SelectionList).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Save the selected values or cancel the edit."""
        if event.button.id != "btn-edit-save":
            self.dismiss(None)
            return
        picked = self.query_one("#edit-choices", SelectionList).selected
        self.dismiss(_MULTI_CHOICE_SEPARATOR.join(str(token) for token in picked))


class OneChoiceEditScreen(ModalScreen[str | None]):
    """Pick exactly one option. Dismisses with its token."""

    DEFAULT_CSS = _EDIT_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, field: FormField, *, cancel_label: str, save_label: str) -> None:
        """Store the immutable field descriptor that supplies this dialog."""
        super().__init__()
        self._field = field
        self._cancel_label = cancel_label
        self._save_label = save_label

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="edit-dialog"):
            yield Label(self._field.label, id="edit-label")
            if self._field.hint:
                yield Static(self._field.hint, id="edit-path")
            yield OptionList(*[choice.label for choice in self._field.choices], id="edit-options")
            with Horizontal(id="edit-actions"):
                yield Button(self._cancel_label, id="btn-edit-cancel")
                yield Button(self._save_label, id="btn-edit-save", classes="-primary")

    def on_mount(self) -> None:
        """Focus the options and restore the declared current value."""
        options = self.query_one("#edit-options", OptionList)
        current = next(
            (index for index, choice in enumerate(self._field.choices) if choice.value == self._field.value),
            None,
        )
        if current is not None:
            options.highlighted = current
        options.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Save the highlighted option or cancel the edit."""
        if event.button.id != "btn-edit-save":
            self.dismiss(None)
            return
        self._dismiss_highlighted()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Dismiss with the option selected directly from the list."""
        self._dismiss_highlighted()

    def _dismiss_highlighted(self) -> None:
        highlighted = self.query_one("#edit-options", OptionList).highlighted
        if highlighted is None:
            self.dismiss(None)
            return
        self.dismiss(self._field.choices[highlighted].value)

    def action_cancel(self) -> None:
        """Dismiss without changing the field value."""
        self.dismiss(None)


__all__ = ["ChoiceEditScreen", "ConfirmScreen", "OneChoiceEditScreen", "TextEditScreen"]
