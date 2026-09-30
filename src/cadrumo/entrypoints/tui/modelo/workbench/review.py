"""Review every staged change before anything is applied.

The review lists each change with its box, its concept, how it read before,
how it will read after, and what the change does in words: a new value, a value
that replaces what a source or the calculation produced, a value removed, or a
source restored. Changes that displace a source or a calculated figure are
warned about, because the filer's value will keep winning until they restore
it. Nothing is saved until the filer chooses to apply; the table has the focus
on arrival so Enter cannot apply by accident.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import ClassVar, Final, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from .....core.i18n.render import tr
from ...components.theme import tokenised
from ...components.widgets import ContentDataTable
from .dialog_width import fit_dialog_width
from .ports import WorkbenchChangeKind
from .session import Displacement, StagedChange


class ReviewDecision(StrEnum):
    """What the filer chose on the review."""

    APPLY = "apply"
    DISCARD = "discard"


REVIEW_EFFECTS: Final[tuple[str, ...]] = ("clear", "restore", *(f"set_{item.value}" for item in Displacement))
"""Every effect the review can state for a change."""
_COLUMN_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "box": "tui.modelo.workbench.review.column.box",
    "concept": "tui.modelo.workbench.review.column.concept",
    "before": "tui.modelo.workbench.review.column.before",
    "after": "tui.modelo.workbench.review.column.after",
    "effect": "tui.modelo.workbench.review.column.effect",
}


def change_effect_key(change: StagedChange) -> str:
    """The catalogue key saying in words what one change does."""
    if change.kind is WorkbenchChangeKind.CLEAR:
        effect = "clear"
    elif change.kind is WorkbenchChangeKind.RESTORE:
        effect = "restore"
    else:
        effect = f"set_{change.displaces.value}"
    return f"tui.modelo.workbench.review.effect.{effect}"


class EditReviewScreen(ModalScreen[ReviewDecision | None]):
    """The mandatory review of staged changes."""

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        EditReviewScreen #review-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        EditReviewScreen #review-panel {
            width: $cadrumo-modal-width;
            height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        EditReviewScreen.-narrow #review-panel {
            width: 100%;
        }
        EditReviewScreen #review-title {
            text-style: bold;
            color: $primary;
        }
        EditReviewScreen #review-subtitle {
            color: $secondary;
            margin-bottom: $cadrumo-stack;
        }
        EditReviewScreen #review-table {
            height: 1fr;
        }
        EditReviewScreen #review-warning {
            color: $warning;
            text-style: bold;
            height: auto;
            margin-top: $cadrumo-stack;
        }
        EditReviewScreen #review-actions {
            height: auto;
            margin-top: $cadrumo-stack;
            align-horizontal: right;
        }
        EditReviewScreen #review-actions Button {
            margin-left: $cadrumo-control-gap;
        }
        """
    )

    BINDINGS: ClassVar = [
        Binding("escape", "back", "", show=False),
        Binding("a", "apply", "", show=False),
    ]

    def __init__(self, changes: tuple[StagedChange, ...]) -> None:
        """Hold the changes under review."""
        super().__init__()
        self._changes = changes

    @override
    def compose(self) -> ComposeResult:
        displacing = sum(
            1
            for change in self._changes
            if change.kind is WorkbenchChangeKind.SET
            and change.displaces in {Displacement.SOURCE, Displacement.CALCULATION}
        )
        with Container(id="review-backdrop"), Vertical(id="review-panel"):
            yield Static(
                tr("tui.modelo.workbench.review.title", count=len(self._changes)), id="review-title", markup=False
            )
            yield Static(tr("tui.modelo.workbench.review.nothing_saved"), id="review-subtitle", markup=False)
            yield ContentDataTable[str](id="review-table", cursor_type="row", zebra_stripes=True)
            if displacing:
                yield Static(
                    tr("tui.modelo.workbench.review.displacing", count=displacing), id="review-warning", markup=False
                )
            with Horizontal(id="review-actions"):
                yield Button(tr("tui.modelo.workbench.review.back"), id="review-back")
                yield Button(tr("tui.modelo.workbench.review.discard"), id="review-discard", variant="error")
                yield Button(tr("tui.modelo.workbench.review.apply"), id="review-apply", variant="primary")

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)

    def on_mount(self) -> None:
        """List the changes and give the table the focus."""
        fit_dialog_width(self, self.app.size.width)
        table = self.query_one("#review-table", ContentDataTable)
        for key, label_key in _COLUMN_LOCALE_KEYS.items():
            table.add_column(tr(label_key), key=key)
        for index, change in enumerate(self._changes):
            field = change.field
            table.add_row(
                field.box or "·",
                field.label.text,
                change.previous_text,
                change.text,
                tr(change_effect_key(change)),
                key=f"change-{index}",
            )
        table.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close with the filer's choice."""
        choice = {"review-apply": ReviewDecision.APPLY, "review-discard": ReviewDecision.DISCARD}.get(
            str(event.button.id)
        )
        self.dismiss(choice)

    def action_apply(self) -> None:
        """Apply the changes."""
        self.dismiss(ReviewDecision.APPLY)

    def action_back(self) -> None:
        """Return to editing with every change kept."""
        self.dismiss(None)


__all__ = ["REVIEW_EFFECTS", "EditReviewScreen", "ReviewDecision", "change_effect_key"]
