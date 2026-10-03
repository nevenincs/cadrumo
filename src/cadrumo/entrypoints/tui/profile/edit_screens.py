"""Profile field and repeatable-row editors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static

from ....application.user_profile.presentation import profile_field_shape_hint
from ....core.i18n.render import tr
from ..components.widgets import ContentScroll, DisclosureGroup
from .overview_contracts import _EDIT_DIALOG_CSS, _REQUIRED_MARK

if TYPE_CHECKING:
    from ....application.user_profile.overview import ProfileFieldView, ProfileSectionView


def field_help_text(field: ProfileFieldView) -> str:
    """Explain one field: what it is, why it is asked, where to find it.

    A field without catalogue help is explained by its schema description,
    so no question is ever asked without saying what it is about.
    """
    if field.help:
        headings = (
            tr("flows.manager.help.what"),
            tr("flows.manager.help.why"),
            tr("flows.manager.help.where"),
        )
        return "\n".join(f"{heading} {part}" for heading, part in zip(headings, field.help, strict=True))
    if field.about:
        return f"{tr('flows.manager.help.about')} {field.about}"
    return ""


class FieldEditScreen(ModalScreen[str | None]):
    """Edit one projected profile field without owning profile policy."""

    DEFAULT_CSS = _EDIT_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(
        self,
        field: ProfileFieldView,
        *,
        prompt: str | None = None,
        choice_labels: Mapping[str, str] | None = None,
        validate: Callable[[str], str | None] | None = None,
        context: str | None = None,
    ) -> None:
        """Initialize the modal from one already-projected profile field.

        ``context`` is shown above the question: where the operator is in
        the setup walk and what the section being asked about is for.
        """
        super().__init__()
        self._field = field
        self._question_context = context
        self._prompt = prompt if prompt is not None else field.label
        self._choice_labels: dict[str, str] = dict(choice_labels) if choice_labels is not None else {}
        self._validate = validate

    def _label_for(self, value: str) -> str:
        """Return the operator label for one stored choice token."""
        override = self._choice_labels.get(value)
        if override is not None:
            return override
        return next(
            (choice.label for choice in self._field.choices if choice.value == value),
            tr("flows.manager.choice_unavailable"),
        )

    @property
    def _box_hides_a_value(self) -> bool:
        """Whether an empty box conceals an existing masked value."""
        return self._field.masked and self._field.present and not self._field.choices

    @property
    def _offers_clear(self) -> bool:
        """Whether the masked optional value can be explicitly cleared."""
        return self._field.masked and self._field.present and not self._field.required

    @override
    def compose(self) -> ComposeResult:
        """Lay out the choice or typed editor without exposing masked values."""
        yield from _field_edit_dialog(self)

    def on_mount(self) -> None:
        """Focus the editor and restore an exact current choice only."""
        if not self._field.choices:
            self.query_one("#edit-input", Input).focus()
            return
        options = self.query_one("#edit-options", OptionList)
        current = next(
            (index for index, choice in enumerate(self._field.choices) if choice.value == self._field.value),
            None,
        )
        options.focus()
        options.highlighted = current

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Translate one editor button into a value, clear, or cancellation."""
        if event.button.id == "btn-edit-save":
            if self._field.choices:
                self._dismiss_highlighted_option()
            else:
                self._submit_typed(self.query_one("#edit-input", Input).value)
        elif event.button.id == "btn-edit-clear":
            self.dismiss("")
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Validate and submit the typed value."""
        self._submit_typed(event.value)

    def _submit_typed(self, value: str) -> None:
        """Dismiss with a valid value while preserving an untouched mask."""
        if self._box_hides_a_value and not value.strip():
            self.dismiss(None)
            return
        if self._field.required and not value.strip():
            self.query_one("#edit-refusal", Static).update(
                tr("flows.manager.edit.required_blank", field=self._field.label)
            )
            self.query_one("#edit-refusal", Static).scroll_visible()
            return
        refusal = self._validate(value) if (self._validate is not None and value.strip()) else None
        if refusal is not None:
            self.query_one("#edit-refusal", Static).update(refusal)
            return
        self.dismiss(value)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Submit the option explicitly selected by the operator."""
        self._dismiss_highlighted_option()

    def _dismiss_highlighted_option(self) -> None:
        highlighted = self.query_one("#edit-options", OptionList).highlighted
        if highlighted is None:
            if self._field.masked and self._field.present:
                # A hidden answer pre-selects nothing, so an empty save is how
                # the operator keeps it.
                self.dismiss(None)
                return
            # Otherwise nothing chosen is not a cancellation: say what is
            # missing and keep the question open, rather than closing it as
            # though the operator had asked to leave the value alone.
            self.query_one("#edit-refusal", Static).update(tr("flows.manager.edit.choose_one"))
            return
        self.dismiss(self._field.choices[highlighted].value)

    def action_cancel(self) -> None:
        """Dismiss without requesting a profile change."""
        self.dismiss(None)


class RepeatableRowAddScreen(ModalScreen[dict[str, str] | None]):
    """Collect one new repeatable row without deciding what may be stored.

    Blank boxes are omitted rather than interpreted as clears: a new row has
    no prior value to clear.  The application row door remains the authority
    for required fields, value shape, and relationship rules.
    """

    DEFAULT_CSS = _EDIT_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, section: ProfileSectionView) -> None:
        """Build one row form from the section's declared field order."""
        super().__init__()
        self._section = section
        # The blank projection for an empty section and every extant row both
        # carry the declaration in display order.  Keep one field per key for
        # the new row; repeated extant rows must not duplicate form controls.
        self._fields = tuple(
            field
            for index, field in enumerate(section.fields)
            if field.path.rsplit(".", 1)[-1]
            not in {earlier.path.rsplit(".", 1)[-1] for earlier in section.fields[:index]}
        )

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="edit-dialog"):
            yield Label(tr("flows.manager.rows.add"), id="edit-label")
            for index, field in enumerate(self._fields):
                yield Label(f"{field.label}{_REQUIRED_MARK if field.required else ''}")
                if field.choices:
                    yield OptionList(*(choice.label for choice in field.choices), id=f"row-option-{index}")
                else:
                    yield Input(
                        placeholder=profile_field_shape_hint(field.field_type) or "",
                        id=f"row-input-{index}",
                    )
            with Horizontal(id="edit-actions"):
                yield Button(tr("flows.manager.edit.cancel"), id="btn-row-cancel")
                yield Button(tr("flows.manager.edit.save"), id="btn-row-save", classes="-primary")

    def on_mount(self) -> None:
        """Focus the first available row input."""
        if self._fields:
            first = self._fields[0]
            self.query_one("#row-option-0", OptionList).focus() if first.choices else self.query_one(
                "#row-input-0", Input
            ).focus()

    def _submitted_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for index, field in enumerate(self._fields):
            field_key = field.path.rsplit(".", 1)[-1]
            if field.choices:
                highlighted = self.query_one(f"#row-option-{index}", OptionList).highlighted
                if highlighted is not None:
                    values[field_key] = field.choices[highlighted].value
                continue
            value = self.query_one(f"#row-input-{index}", Input).value
            if value.strip():
                values[field_key] = value
        return values

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit the row values or dismiss without adding a row."""
        if event.button.id == "btn-row-save":
            self.dismiss(self._submitted_values())
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        """Dismiss without adding a row."""
        self.dismiss(None)


class RepeatableRowRemoveScreen(ModalScreen[bool]):
    """Require an explicit confirmation before clearing an identified row."""

    DEFAULT_CSS = _EDIT_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, section_key: str, row_key: str) -> None:
        """Keep the stable section and row identities awaiting confirmation."""
        super().__init__()
        self._section_key = section_key
        self._row_key = row_key or "base"

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="edit-dialog"):
            yield Label(
                tr("flows.manager.rows.remove_confirm", section=self._section_key, row=self._row_key),
                id="edit-label",
            )
            with Horizontal(id="edit-actions"):
                yield Button(tr("flows.manager.edit.cancel"), id="btn-row-cancel")
                yield Button(tr("flows.confirm.yes"), id="btn-row-remove", classes="-error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Return whether the operator confirmed removal."""
        self.dismiss(event.button.id == "btn-row-remove")

    def action_cancel(self) -> None:
        """Decline removal."""
        self.dismiss(False)


def _field_edit_dialog(screen: FieldEditScreen) -> ComposeResult:
    """Compose the modal's fixed shell around its editor and actions."""
    with Vertical(id="edit-dialog"):
        with ContentScroll(id="edit-body"):
            yield from _field_edit_content(screen)
        with Horizontal(id="edit-actions"):
            yield Button(tr("flows.manager.edit.cancel"), id="btn-edit-cancel")
            yield from _field_edit_actions(screen)


def _field_edit_content(screen: FieldEditScreen) -> ComposeResult:
    """Compose the prompt, input, refusal, and optional help disclosure."""
    if screen._question_context:
        yield Static(screen._question_context, id="edit-context", markup=False)
    yield Label(screen._prompt, id="edit-label")
    yield Static(
        tr("flows.progress.required" if screen._field.required else "flows.progress.optional"),
        id="edit-requirement",
    )
    yield from _field_editor_input(screen)
    yield Static(id="edit-refusal")
    if screen._box_hides_a_value:
        yield Static(tr("flows.manager.edit.masked_kept"), id="edit-masked-note")
    help_text = field_help_text(screen._field)
    if help_text:
        yield DisclosureGroup(
            Static(help_text, id="edit-help", markup=False),
            title=tr("flows.manager.help.about"),
            id="edit-help-fold",
        )


def _field_editor_input(screen: FieldEditScreen) -> ComposeResult:
    """Compose exactly one choice list or masked/typed input control."""
    if screen._field.choices:
        yield OptionList(
            *[screen._label_for(choice.value) for choice in screen._field.choices],
            id="edit-options",
        )
        return
    yield Input(
        value="" if screen._field.masked else (screen._field.value or ""),
        password=screen._field.masked,
        id="edit-input",
    )
    hint = profile_field_shape_hint(screen._field.field_type)
    if hint:
        yield Static(hint, id="edit-hint")


def _field_edit_actions(screen: FieldEditScreen) -> ComposeResult:
    """Offer clear only when the existing masked optional answer allows it."""
    if screen._offers_clear:
        yield Button(tr("flows.manager.edit.clear"), id="btn-edit-clear")
    yield Button(tr("flows.manager.edit.save"), id="btn-edit-save", classes="-primary")
