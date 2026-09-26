"""Collect one calendar year's average workforce, or the year to withdraw.

The dialog parses what the operator typed into typed values and nothing more.
Which years, amounts and states may be stored is the shared application
service's decision: a year out of range, a negative workforce or one with more
than two decimal places reaches that service and comes back as its refusal, so
this surface and the command line refuse exactly the same values.

The average workforce is read as a ``Decimal`` from the text itself. A float
would already have lost the two decimal places the figure is counted in before
any rule could look at them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import ClassVar, Final, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static

from ....core.i18n.render import tr
from ....domain.user_profile.plantilla_media import PlantillaMediaState, PlantillaMediaYear
from ..components.theme import tokenised

_STATE_LOCALE_KEYS: Final[dict[PlantillaMediaState, str]] = {
    PlantillaMediaState.OBSERVED: "flows.manager.plantilla_media.state_observed",
    PlantillaMediaState.COMMITTED: "flows.manager.plantilla_media.state_committed",
}

_STATES: Final[tuple[PlantillaMediaState, ...]] = tuple(PlantillaMediaState)
"""The state choices in the order the dialog offers them."""

_DECLARED_SEPARATOR: Final[str] = " · "
"""Sits between a declared year, its workforce and its state in the listing.

Punctuation rather than copy: the year and the figure are stored values and
the state beside them is already translated, so nothing here is written in a
language.
"""

_PLANTILLA_MEDIA_DIALOG_CSS = tokenised("""
#plantilla-dialog {
    border: $cadrumo-radius-overlay $accent;
    background: $surface;
    padding: $cadrumo-space-0 $cadrumo-space-1;
    width: 100%;
    height: auto;
}
#plantilla-title { text-style: bold; }
#plantilla-none-declared { color: $text-muted; }
#plantilla-refusal { color: $error; text-style: bold; }
#plantilla-dialog Input { margin: $cadrumo-space-0; }
#plantilla-actions { height: auto; align-horizontal: right; margin: $cadrumo-space-0; }
#plantilla-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
""")


@dataclass(frozen=True, slots=True)
class PlantillaMediaSetRequest:
    """Declare one year's average workforce, replacing the year if it is declared."""

    year: int
    average_workforce: Decimal
    state: PlantillaMediaState


@dataclass(frozen=True, slots=True)
class PlantillaMediaRemoveRequest:
    """Withdraw one declared year."""

    year: int


type PlantillaMediaRequest = PlantillaMediaSetRequest | PlantillaMediaRemoveRequest


def plantilla_media_state_label(state: PlantillaMediaState) -> str:
    """Return the operator wording for one stored state token."""
    return tr(_STATE_LOCALE_KEYS[state])


def _parse_year(raw: str) -> int | None:
    """Return the typed year as a whole number, or ``None`` when it is not one.

    Only ASCII digits count: ``int`` would also accept a sign, underscores
    and other scripts' digits, none of which is a year an operator means.
    """
    text = raw.strip()
    if not text or not text.isascii() or not text.isdigit():
        return None
    return int(text)


def _parse_average_workforce(raw: str) -> Decimal | None:
    """Return the typed workforce as a finite ``Decimal``, or ``None``."""
    try:
        value = Decimal(raw.strip())
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


class PlantillaMediaScreen(ModalScreen[PlantillaMediaRequest | None]):
    """Show the declared years and collect one year to declare, replace or withdraw."""

    DEFAULT_CSS = _PLANTILLA_MEDIA_DIALOG_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, declared: Sequence[PlantillaMediaYear]) -> None:
        """Initialise the dialog from the years the profile declares now."""
        super().__init__()
        self._declared = tuple(declared)

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="plantilla-dialog"):
            yield Label(tr("profile.schema.field.irpf.plantilla_media.label"), id="plantilla-title")
            if self._declared:
                yield OptionList(
                    *(
                        _DECLARED_SEPARATOR.join(
                            (str(item.year), str(item.average_workforce), plantilla_media_state_label(item.state))
                        )
                        for item in self._declared
                    ),
                    id="plantilla-declared",
                )
            else:
                yield Static(tr("flows.manager.plantilla_media.none_declared"), id="plantilla-none-declared")
            yield Label(tr("flows.manager.plantilla_media.year"))
            yield Input(id="plantilla-year")
            yield Label(tr("flows.manager.plantilla_media.average_workforce"))
            yield Input(placeholder=tr("flows.manager.edit.shape.decimal"), id="plantilla-workforce")
            yield Label(tr("flows.manager.plantilla_media.state"))
            yield OptionList(*(plantilla_media_state_label(state) for state in _STATES), id="plantilla-state")
            yield Static(id="plantilla-refusal")
            with Horizontal(id="plantilla-actions"):
                yield Button(tr("flows.manager.edit.cancel"), id="btn-plantilla-cancel")
                yield Button(tr("flows.manager.plantilla_media.remove"), id="btn-plantilla-remove", classes="-error")
                yield Button(tr("flows.manager.edit.save"), id="btn-plantilla-save", classes="-primary")

    def on_mount(self) -> None:
        """Start with no state chosen, so the state is always the operator's answer."""
        self.query_one("#plantilla-state", OptionList).highlighted = None
        self.query_one("#plantilla-year", Input).focus()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Fill the boxes from a declared year, so replacing or withdrawing it starts from its values."""
        if event.option_list.id != "plantilla-declared":
            return
        item = self._declared[event.option_index]
        self.query_one("#plantilla-year", Input).value = str(item.year)
        self.query_one("#plantilla-workforce", Input).value = str(item.average_workforce)
        self.query_one("#plantilla-state", OptionList).highlighted = _STATES.index(item.state)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Translate one button into a declaration, a withdrawal, or a cancellation."""
        if event.button.id == "btn-plantilla-save":
            self._submit_set()
        elif event.button.id == "btn-plantilla-remove":
            self._submit_remove()
        else:
            self.dismiss(None)

    def _year(self) -> int | None:
        year = _parse_year(self.query_one("#plantilla-year", Input).value)
        if year is None:
            self._refuse(tr("flows.manager.plantilla_media.year_not_whole"))
        return year

    def _submit_set(self) -> None:
        year = self._year()
        if year is None:
            return
        average_workforce = _parse_average_workforce(self.query_one("#plantilla-workforce", Input).value)
        if average_workforce is None:
            self._refuse(tr("flows.manager.plantilla_media.workforce_not_number"))
            return
        highlighted = self.query_one("#plantilla-state", OptionList).highlighted
        if highlighted is None:
            self._refuse(tr("flows.manager.plantilla_media.state_required"))
            return
        self.dismiss(
            PlantillaMediaSetRequest(year=year, average_workforce=average_workforce, state=_STATES[highlighted])
        )

    def _submit_remove(self) -> None:
        year = self._year()
        if year is None:
            return
        self.dismiss(PlantillaMediaRemoveRequest(year=year))

    def _refuse(self, message: str) -> None:
        self.query_one("#plantilla-refusal", Static).update(message)

    def action_cancel(self) -> None:
        """Dismiss without requesting a profile change."""
        self.dismiss(None)


__all__ = [
    "PlantillaMediaRemoveRequest",
    "PlantillaMediaRequest",
    "PlantillaMediaScreen",
    "PlantillaMediaSetRequest",
    "plantilla_media_state_label",
]
