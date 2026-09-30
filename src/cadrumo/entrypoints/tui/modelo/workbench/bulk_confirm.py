"""Confirm several assumed values at once, only after reading every one of them.

An assumed value is one the calculation holds that nobody is recorded as
having entered. The dialog lists every such box it can confirm by its number,
its concept and the value it holds, and confirms nothing until the filer ticks
that these values are right for them. Confirming keeps each value as the
filer's own for review; nothing is applied from here.

Only a box the filer types into can be confirmed. A box a source fills is left
out, and the dialog says so, because keeping a value over a source would
replace the source rather than confirm it.
"""

from __future__ import annotations

from typing import ClassVar, override

from rich.table import Table
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static

from .....application.modelo.work_form_models import (
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    edit_address,
)
from .....core.external_constants import OutputLanguage
from .....core.i18n.render import output_language, tr
from ...components.theme import tokenised
from .casilla_list import CasillaListEntry, value_text
from .dialog_width import fit_dialog_width


def confirmable(field: ModeloFormField) -> bool:
    """Whether ``field`` holds an assumed value the filer can confirm as their own."""
    return (
        field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM
        and field.value is not None
        and field.editability is ModeloFormEditability.EDITABLE_VALUE
        and edit_address(field) == field.address
    )


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
        BulkConfirmScreen #bulk-title {
            text-style: bold;
            color: $primary;
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

    def __init__(self, fields: tuple[ModeloFormField, ...], *, language: OutputLanguage | None = None) -> None:
        """Hold the assumed boxes offered for confirmation.

        Every box passed is considered; the ones a source fills, or that hold no
        assumed value, are left out of the list, and the dialog says so.
        ``language`` formats the values, and defaults to the filer's language.
        """
        super().__init__()
        self._fields = tuple(field for field in fields if confirmable(field))
        self._left_out = len(fields) - len(self._fields)
        self._language = language if language is not None else OutputLanguage(output_language())

    @property
    def fields(self) -> tuple[ModeloFormField, ...]:
        """The boxes the dialog lists and would confirm."""
        return self._fields

    @override
    def compose(self) -> ComposeResult:
        with Container(id="bulk-backdrop"), Vertical(id="bulk-panel"):
            yield Static(tr("tui.modelo.workbench.bulk_confirm.title"), id="bulk-title", markup=False)
            yield Static(tr("tui.modelo.workbench.bulk_confirm.intro"), id="bulk-intro", markup=False)
            yield Static(
                tr("tui.modelo.workbench.bulk_confirm.count", count=len(self._fields)), id="bulk-count", markup=False
            )
            with VerticalScroll(id="bulk-body", can_focus=True):
                yield Static(confirmation_table(self._fields, self._language), id="bulk-table")
                if self._left_out:
                    yield Static(
                        tr("tui.modelo.workbench.bulk_confirm.sourced_left_out"), id="bulk-left-out", markup=False
                    )
            yield Checkbox(
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


__all__ = ["BulkConfirmScreen", "confirmable", "confirmation_table"]
