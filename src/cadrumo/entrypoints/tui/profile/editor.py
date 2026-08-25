"""The dialog that edits one profile field, and how it decides its editor.

Split from the manager page because the two answer different questions. The
page answers "what does my profile hold"; this answers "how do I change one
of those values" — and the second question has an answer per declared field
type, which is what the page had been getting wrong.

Which editor appears is decided by what the schema says the field HOLDS. A
field with a closed answer set is picked from; everything else is typed into
a box that states the shape it accepts and refuses a bad value where it was
typed, while the operator is still looking at it.

The screen owns no profile logic. It is handed a projected field and, from
its host, the judge that says whether a typed value may be stored — the same
form-presentation arrangement, for the same
reason: an adapter renders and reports intent, and the entry point composes.

See Also:
    :class:`~cadrumo.application.user_profile.ProfileFieldView`
        The projection this dialog edits, carrying the declared type and the
        closed answer set the editor is chosen from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static

from ....core.i18n import tr
from ....domain.user_profile import ProfileFieldType

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from ....application.user_profile import ProfileFieldView


def accepted_shape_hint(field_type: ProfileFieldType) -> str:
    """What a typed box accepts, or empty for a type that needs no saying.

    Deliberately partial. A ``string`` field's shape is whatever its label
    already says — a name, a NIF, an address — and a line under every such
    row reading "text" would be noise. The types answered here are the ones
    a box cannot state for itself: nothing about a date box says WHICH
    layout, and nothing about a decimal box says the separator is a point.

    ``enum`` and ``boolean`` return nothing because they are never typed
    into; they are picked from
    :func:`~cadrumo.application.user_profile.profile_field_choices`.
    ``object`` and ``array`` return nothing because they name a namespace
    rather than a slot, and the projection renders their indexed leaves
    instead of the bare path.

    Written as a match over literal keys rather than as a type-to-key table
    because the locale scaffold reads ``tr()`` call sites: a key assembled
    into a variable first is invisible to it, and the catalogues would be
    scaffolded without the entries this function then asks for.
    """
    match field_type:
        case ProfileFieldType.DATE:
            return tr("flows.manager.edit.shape.date")
        case ProfileFieldType.EMAIL:
            return tr("flows.manager.edit.shape.email")
        case ProfileFieldType.INTEGER:
            return tr("flows.manager.edit.shape.integer")
        case ProfileFieldType.DECIMAL:
            return tr("flows.manager.edit.shape.decimal")
        case ProfileFieldType.MONEY:
            return tr("flows.manager.edit.shape.money")
        case _:
            return ""


_EDIT_DIALOG_CSS = """
#edit-dialog {
    border: thick $accent;
    background: $surface;
    padding: 0 1;
    width: 100%;
    height: auto;
}
#edit-label { text-style: bold; }
#edit-hint { color: $text-muted; }
#edit-refusal { color: $error; text-style: bold; }
#edit-masked-note { color: $text-muted; }
#edit-dialog Input { margin: 0; }
#edit-actions { height: auto; align-horizontal: right; margin: 0; }
#edit-actions Button { margin: 0 0 0 1; }
"""
"""Styling carried by the dialog itself rather than by whichever page opened it.

It used to live on the manager application's ``CSS``, which was invisible
while the manager was the only host and the dialog was declared in the same
module. Now that it is its own screen, a host that did not happen to carry
these rules would render it unstyled -- the failure
:mod:`~cadrumo.adapters.inbound.tui._form_screen` already documents having
met, and the reason its dialogs carry their own rules too.
"""


class FieldEditScreen(ModalScreen[str | None]):
    """Edit one field's value. Dismisses with the new value, or ``None``.

    Which editor appears is decided by what the schema says the field HOLDS,
    not by whether it happens to declare an enum. A field with a closed
    answer set — an enum's tokens, a boolean's yes and no — is picked from a
    list, so an unanswerable value is not typeable. Everything else is typed
    into a box that states the shape it accepts and refuses a bad value where
    it was typed.

    Both halves used to be missing for every non-enum field. A boolean got a
    free-text box with nothing saying what a boolean is spelled like, so the
    operator guessed: ``on`` was refused with "profile facts failed schema
    validation" — the write door's own words, naming neither the field nor
    anything acceptable — and ``yes`` was ACCEPTED and stored as the literal
    word, leaving the record carrying a token no other writer produces. A
    date and a percentage were the same box with the same silence.
    """

    DEFAULT_CSS = _EDIT_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(
        self,
        field: ProfileFieldView,
        *,
        prompt: str | None = None,
        choice_labels: Mapping[str, str] | None = None,
        validate: Callable[[str], str | None] | None = None,
    ) -> None:
        """Initialize the modal from one already-projected profile field."""
        super().__init__()
        self._field = field
        self._prompt = prompt if prompt is not None else field.label
        """What to call the field here, when the schema's own name is not
        the one the operator knows it by."""
        self._choice_labels: dict[str, str] = dict(choice_labels or {})
        """How to show one token, for a field whose stored tokens are not
        words the operator reads.

        A language is stored as ``es`` and read as "Spanish", and an
        operator picking their own language cannot be asked to recognise
        the token — least of all in a language they do not read. The token
        is still what gets dismissed and written; only its presentation
        changes.

        An override, not the source: the projection already carries a label
        per choice, and this replaces it for a caller that knows better."""
        self._validate = validate
        """Why the write door would refuse a typed value, or ``None``.

        Injected rather than imported, like the write door itself, and for
        the stronger reason: the ANSWER must come from the one authority
        that admits the value, or the dialog closes on a value storage then
        rejects. ``None`` leaves the box unchecked, which is the honest
        behaviour for a host that supplied no judge — the write door still
        refuses, just later and less usefully."""

    def _label_for(self, value: str) -> str:
        """Show one token the way the operator should read it."""
        override = self._choice_labels.get(value)
        if override is not None:
            return override
        return next(
            (choice.label for choice in self._field.choices if choice.value == value),
            tr("flows.manager.choice_unavailable"),
        )

    @property
    def _box_hides_a_value(self) -> bool:
        """Whether an empty box here is hiding a value rather than describing one.

        The single authority for both halves of the withheld-value
        reading: whether the dialog explains that an empty box keeps the
        value, and whether saving on one actually keeps it. Those were
        once decided separately, and the operator met the behaviour
        without the explanation on a masked field holding nothing — where
        the behaviour was also wrong. One predicate keeps a promise the
        dialog makes and the rule it acts on from parting again.
        """
        return self._field.masked and self._field.present and not self._field.choices

    @property
    def _offers_clear(self) -> bool:
        """Whether this dialog must carry its own way to delete the value.

        Only a masked field needs one. Its box opens empty because the
        value is withheld, so emptying the box cannot mean "delete this" —
        the box was already empty, and the operator never saw what they
        would be deleting. Every other field says it by being emptied,
        which is a gesture they took deliberately against a value they
        could read.

        Offered only where the deletion would actually happen: a field
        holding nothing has none to remove, and a required field's
        deletion is refused downstream, so a button for either would
        promise an outcome the dialog then has to take back.
        """
        return self._field.masked and self._field.present and not self._field.required

    @override
    def compose(self) -> ComposeResult:
        """Lay out the dialog for one field.

        A masked field's box starts EMPTY, and both halves of why are
        worth stating because neither is visible from here. The overview
        this dialog is handed never carries a masked value — the
        projection substitutes the mask placeholder, deliberately, so
        that a page held open on screen cannot leak a secret — which
        means there is no real value available to pre-fill with. And the
        placeholder itself must not be used in its place: it is an
        ordinary string, so it would be submitted back as the literal new
        value the moment the operator pressed save, overwriting the
        secret with a row of dots.

        The emptiness is therefore not the field's state, and the rest of
        this screen exists to stop it being read as one.
        """
        with Vertical(id="edit-dialog"):
            yield Label(self._prompt, id="edit-label")
            if self._field.choices:
                yield OptionList(
                    *[self._label_for(choice.value) for choice in self._field.choices],
                    id="edit-options",
                )
            else:
                yield Input(value="" if self._field.masked else (self._field.value or ""), id="edit-input")
                # What shape this box takes, stated before the operator
                # guesses at it. Only for a type whose shape is not evident
                # from the field's own name: a NIF box explains itself, a
                # date box does not say WHICH date layout it wants.
                hint = accepted_shape_hint(self._field.field_type)
                if hint:
                    yield Static(hint, id="edit-hint")
                # Empty until the operator submits something the schema will
                # not take. Mounted regardless so the refusal has somewhere
                # to land without rebuilding the dialog under them.
                yield Static(id="edit-refusal")
            # An empty box that means "unset" needs no explaining. One that
            # means "withheld" does, or the operator reads the emptiness as
            # the field's state and saves it back.
            if self._box_hides_a_value:
                yield Static(tr("flows.manager.edit.masked_kept"), id="edit-masked-note")
            with Horizontal(id="edit-actions"):
                yield Button(tr("flows.manager.edit.cancel"), id="btn-edit-cancel")
                if self._offers_clear:
                    yield Button(tr("flows.manager.edit.clear"), id="btn-edit-clear")
                yield Button(tr("flows.manager.edit.save"), id="btn-edit-save", classes="-primary")

    def on_mount(self) -> None:
        """Focus the typed field or safely initialize the choice selection."""
        if not self._field.choices:
            self.query_one("#edit-input", Input).focus()
            return
        options = self.query_one("#edit-options", OptionList)
        current = next(
            (index for index, choice in enumerate(self._field.choices) if choice.value == self._field.value),
            None,
        )
        options.focus()
        # Taking focus highlights the first row on its own, and enter on an
        # untouched list would then write whatever happens to be first — a
        # choice the operator never made. So the highlight is assigned after
        # focus and only where it is TRUE, which clears it when the field
        # holds no token of this list. Masking is what makes that
        # destructive rather than merely wrong: the lookup above compares
        # against the mask placeholder, so it can never match, and the write
        # would replace a value the dialog was not allowed to show. Nothing
        # is lost in reach — the first arrow key highlights the first row,
        # exactly where focus used to leave it.
        options.highlighted = current

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Translate an editor button into a typed value, clear, or cancellation."""
        if event.button.id == "btn-edit-save":
            if self._field.choices:
                self._dismiss_highlighted_option()
            else:
                self._submit_typed(self.query_one("#edit-input", Input).value)
        elif event.button.id == "btn-edit-clear":
            # The one gesture that means "delete this". It dismisses the
            # empty string rather than a marker of its own so the write
            # door keeps a single reading of blank: blank is already a
            # clear everywhere else, and this is how a field whose box
            # cannot be emptied meaningfully still reaches it.
            self.dismiss("")
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Validate and submit the value typed into the text editor."""
        self._submit_typed(event.value)

    def _submit_typed(self, value: str) -> None:
        """Dismiss with what the operator typed, or with nothing to do.

        An empty box that is HIDING a value is not a clear. The operator
        was shown a mask instead of the value, so an empty box is what "I
        typed nothing" looks like and saving on it reads as leaving the
        field alone — they were never offered the chance to delete
        something they could see. Writing the blank through would destroy
        a value they cannot even watch go, so it dismisses as a
        no-change, exactly as cancelling does, and deletion is left to
        the button that says so.

        The condition is that the box conceals something, not merely that
        the field is masked, and the two part on a masked field holding
        NOTHING. There the emptiness is the field's own state rather than
        a withholding, the operator is looking at the truth, and the
        reasoning above has nothing to bite on — so a blank means what it
        means everywhere else. That matters on a required field: reading
        it as a no-change answered an operator who opened an empty
        required field to fill it in with silence, leaving them a field
        still counted as missing and no account of why saving changed
        nothing. Handing the blank on lets the write door refuse it and
        say so.

        This is deliberately the same predicate that decides whether the
        dialog EXPLAINS the no-change reading. Behaviour the operator is
        not told about is the failure being closed here, so the note and
        the rule it describes are read from one place and cannot drift
        apart again.

        Every other field keeps the old reading, because there an empty
        box is one the operator emptied.

        A value the schema will not take holds the dialog OPEN with the
        reason, rather than closing and letting the write door answer. The
        operator is then still looking at the box they typed into and can
        correct it in place; the door's refusal arrives after a storage
        round trip, on a page that has already moved on, and says only that
        the profile does not match the schema. A blank is exempt because it
        is a clear rather than an answer, and the two guards above already
        decide what a blank means here.
        """
        if self._box_hides_a_value and not value.strip():
            self.dismiss(None)
            return
        refusal = self._validate(value) if (self._validate is not None and value.strip()) else None
        if refusal is not None:
            self.query_one("#edit-refusal", Static).update(refusal)
            return
        self.dismiss(value)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Submit the option that the operator explicitly selected."""
        self._dismiss_highlighted_option()

    def _dismiss_highlighted_option(self) -> None:
        highlighted = self.query_one("#edit-options", OptionList).highlighted
        if highlighted is None:
            self.dismiss(None)
            return
        self.dismiss(self._field.choices[highlighted].value)

    def action_cancel(self) -> None:
        """Dismiss the editor without requesting a profile change."""
        self.dismiss(None)


__all__ = [
    "FieldEditScreen",
    "accepted_shape_hint",
]
