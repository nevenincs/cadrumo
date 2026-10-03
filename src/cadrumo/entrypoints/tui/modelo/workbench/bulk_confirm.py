"""Confirm several assumed values at once, only after reading every one of them.

An assumed value is one the calculation holds that nobody is recorded as
having entered. The dialog lists every such box it can confirm by its number,
its concept and the value it holds, and confirms nothing until the filer ticks
that these values are right for them. Confirming keeps each value as the
filer's own for review; nothing is applied from here.

Only a value the filer types can be confirmed, and only where it can be typed
here. An assumed box left out is counted under its reason: a source fills it,
so keeping a value over it would replace the source rather than confirm it; or
its kind of value cannot be changed here, which its own panel explains.

The dialog covers the header, so it can repeat the header's result line as its
first line.

The tick reads "[ ]" until the filer ticks it and "[✓]" once they have, so an
unticked box never looks ticked, in colour or without it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final, override

from rich.table import Table
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static

from .....application.modelo.work_form_models import (
    ModeloFormField,
    ModeloFormOrigin,
    confirmable,
    typed_by_the_filer,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language, tr
from ...components.theme import tokenised
from .casilla_list_models import CasillaListEntry
from .casilla_list_values import value_text
from .dialog_width import fit_dialog_width
from .status_bar import StatusBar

if TYPE_CHECKING:
    from .header import StatusLine

_LEFT_OUT_SOURCED_KEY = "tui.modelo.workbench.bulk_confirm.left_out.sourced"
_LEFT_OUT_NOT_CHANGEABLE_KEY = "tui.modelo.workbench.bulk_confirm.left_out.not_changeable"
_UNTICKED: Final[str] = "[ ]"
_TICKED: Final[str] = "[✓]"


class TickBox(Checkbox):
    """A checkbox that reads as ticked only once it is: "[ ]", then "[✓]"."""

    @property
    @override
    def _button(self) -> Content:
        return Content.styled(_TICKED if self.value else _UNTICKED, self.get_visual_style("toggle--button"))


def left_out_notes(fields: tuple[ModeloFormField, ...]) -> tuple[str, ...]:
    """Say, by reason, how many assumed boxes among ``fields`` cannot be confirmed here."""
    assumed = [
        field for field in fields if field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM and not confirmable(field)
    ]
    sourced = sum(1 for field in assumed if not typed_by_the_filer(field))
    not_changeable = len(assumed) - sourced
    notes: list[str] = []
    if sourced:
        notes.append(tr(_LEFT_OUT_SOURCED_KEY, count=sourced))
    if not_changeable:
        notes.append(tr(_LEFT_OUT_NOT_CHANGEABLE_KEY, count=not_changeable))
    return tuple(notes)


def confirmation_table(fields: tuple[ModeloFormField, ...], language: OutputLanguage) -> Table:
    """The boxes to confirm as rows of box, concept and assumed value; long concepts wrap."""
    table = Table(box=None, expand=True, pad_edge=False, show_edge=False)
    table.add_column(tr("tui.modelo.workbench.review.column.box"), no_wrap=True)
    table.add_column(tr("tui.modelo.workbench.review.column.concept"), ratio=1, overflow="fold")
    table.add_column(tr("tui.modelo.workbench.bulk_confirm.column.value"), no_wrap=True, justify="right")
    for field in fields:
        table.add_row(
            f"[{field.box}]" if field.box else "",
            field.label.text,
            value_text(CasillaListEntry(field), language),
        )
    return table


class BulkConfirmScreen(ModalScreen[tuple[ModeloFormField, ...] | None]):
    """List assumed values and confirm them together once the filer ticks that they are right."""

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        BulkConfirmScreen #bulk-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        BulkConfirmScreen #bulk-panel {
            width: $cadrumo-modal-width;
            height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        BulkConfirmScreen.-narrow #bulk-panel {
            width: 100%;
        }
        BulkConfirmScreen #bulk-status {
            height: auto;
        }
        BulkConfirmScreen #bulk-title {
            text-style: bold;
            color: $foreground;
        }
        BulkConfirmScreen #bulk-intro, BulkConfirmScreen #bulk-left-out {
            color: $secondary;
            height: auto;
        }
        BulkConfirmScreen #bulk-count {
            margin-top: $cadrumo-stack;
            height: auto;
        }
        BulkConfirmScreen #bulk-body {
            height: 1fr;
        }
        BulkConfirmScreen #bulk-body:focus {
            background-tint: $foreground 4%;
        }
        BulkConfirmScreen #bulk-table {
            height: auto;
        }
        BulkConfirmScreen #bulk-tick {
            margin-top: $cadrumo-stack;
        }
        BulkConfirmScreen #bulk-tick > .toggle--button {
            color: $foreground;
        }
        BulkConfirmScreen #bulk-tick.-on > .toggle--button {
            color: $text-success;
        }
        BulkConfirmScreen #bulk-actions {
            height: auto;
            margin-top: $cadrumo-stack;
            align-horizontal: right;
        }
        BulkConfirmScreen #bulk-actions Button {
            margin-left: $cadrumo-control-gap;
        }
        """
    )

    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(
        self,
        fields: tuple[ModeloFormField, ...],
        *,
        language: OutputLanguage | None = None,
        status_line: StatusLine | None = None,
    ) -> None:
        """Hold the assumed boxes offered for confirmation.

        Every box passed is considered. One that holds no assumed value is not
        listed; an assumed one that cannot be confirmed here is not listed
        either, and the dialog counts it under its reason.
        ``language`` formats the values, and defaults to the filer's language.
        ``status_line`` is the header's result line, shown first because the
        dialog covers it.
        """
        super().__init__()
        self._fields = tuple(field for field in fields if confirmable(field))
        self._left_out = left_out_notes(fields)
        self._language = language if language is not None else OutputLanguage(output_language())
        self._status_line = status_line

    @property
    def fields(self) -> tuple[ModeloFormField, ...]:
        """The boxes the dialog lists and would confirm."""
        return self._fields

    @override
    def compose(self) -> ComposeResult:
        with Container(id="bulk-backdrop"), Vertical(id="bulk-panel"):
            if self._status_line is not None:
                yield StatusBar(self._status_line, id="bulk-status")
            yield Static(tr("tui.modelo.workbench.bulk_confirm.title"), id="bulk-title", markup=False)
            yield Static(tr("tui.modelo.workbench.bulk_confirm.intro"), id="bulk-intro", markup=False)
            yield Static(
                tr("tui.modelo.workbench.bulk_confirm.count", count=len(self._fields)), id="bulk-count", markup=False
            )
            with VerticalScroll(id="bulk-body", can_focus=True):
                yield Static(confirmation_table(self._fields, self._language), id="bulk-table")
                if self._left_out:
                    yield Static("\n".join(self._left_out), id="bulk-left-out", markup=False)
            yield TickBox(
                tr("tui.modelo.workbench.bulk_confirm.tick"),
                id="bulk-tick",
                compact=True,
                disabled=not self._fields,
            )
            with Horizontal(id="bulk-actions"):
                yield Button(tr("tui.modelo.workbench.editor.cancel"), id="bulk-cancel")
                yield Button(
                    tr("tui.modelo.workbench.bulk_confirm.confirm"), id="bulk-confirm", variant="primary", disabled=True
                )

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def on_mount(self) -> None:
        """Fit the terminal and give the list the focus, so nothing is confirmed by a stray key."""
        fit_dialog_width(self, self.app.size.width)
        self.query_one("#bulk-body", VerticalScroll).focus()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Offer Confirm only once the filer has ticked that the values are right."""
        self.query_one("#bulk-confirm", Button).disabled = not (event.value and self._fields)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close with the boxes to confirm, or with nothing."""
        if event.button.id == "bulk-confirm" and self.query_one("#bulk-tick", Checkbox).value and self._fields:
            self.dismiss(self._fields)
            return
        self.dismiss(None)

    def action_cancel(self) -> None:
        """Close without confirming anything."""
        self.dismiss(None)


__all__ = ["BulkConfirmScreen", "TickBox", "confirmation_table", "left_out_notes"]
