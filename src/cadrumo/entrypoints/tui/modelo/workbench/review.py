"""Review every staged change before anything is applied.

The review lists each change with its box, its concept, how it read before,
how it will read after, and what the change does in words: a new value, a value
that replaces what a source or the calculation produced, a value removed, or a
source restored. Changes that displace a source or a calculated figure are
warned about, because the filer's value will keep winning until they restore
it. Nothing is saved until the filer chooses to apply; the table has the focus
on arrival so Enter cannot apply by accident.

What the application found when it checked the changes is listed under them;
a finding that would make it refuse the changes keeps Apply unavailable until
the filer resolves it. Two situations ask the filer to acknowledge before
applying: a declaration that does not record which of its values the filer
typed, where applying returns every value not listed to what its source says,
and a declaration that changed after the changes were staged, whose changed
boxes are marked.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final, override

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static

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


@dataclass(frozen=True, slots=True)
class ReviewNote:
    """One finding of the check before applying, with the box it concerns."""

    box: str | None
    message: str
    blocking: bool


REVIEW_EFFECTS: Final[tuple[str, ...]] = ("clear", "restore", *(f"set_{item.value}" for item in Displacement))
"""Every effect the review can state for a change."""
_COLUMN_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "box": "tui.modelo.workbench.review.column.box",
    "concept": "tui.modelo.workbench.review.column.concept",
    "before": "tui.modelo.workbench.review.column.before",
    "after": "tui.modelo.workbench.review.column.after",
    "effect": "tui.modelo.workbench.review.column.effect",
}
_NOTE_MARKS: Final[Mapping[bool, str]] = {True: "▲", False: "!"}
_AT_RISK_SHOWN: Final[int] = 12


def change_effect_key(change: StagedChange) -> str:
    """The catalogue key saying in words what one change does."""
    if change.kind is WorkbenchChangeKind.CLEAR:
        effect = "clear"
    elif change.kind is WorkbenchChangeKind.RESTORE:
        effect = "restore"
    else:
        effect = f"set_{change.displaces.value}"
    return f"tui.modelo.workbench.review.effect.{effect}"


def at_risk_text(boxes: tuple[str, ...]) -> str:
    """Say what applying does to values nobody is recorded as having typed, naming their boxes."""
    if not boxes:
        return tr("tui.modelo.workbench.review.operator_entries_unknown")
    shown = ", ".join(boxes[:_AT_RISK_SHOWN])
    if len(boxes) > _AT_RISK_SHOWN:
        shown = tr("tui.modelo.workbench.review.and_more", shown=shown, count=len(boxes) - _AT_RISK_SHOWN)
    return tr("tui.modelo.workbench.review.operator_entries_at_risk", count=len(boxes), boxes=shown)


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
        EditReviewScreen #review-warning, EditReviewScreen #review-at-risk, EditReviewScreen #review-rebased {
            color: $warning;
            text-style: bold;
            height: auto;
            margin-top: $cadrumo-stack;
        }
        EditReviewScreen #review-findings {
            height: auto;
            max-height: $cadrumo-help-max-height;
            overflow-y: auto;
            margin-top: $cadrumo-stack;
        }
        EditReviewScreen #review-acknowledge {
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

    def __init__(
        self,
        changes: tuple[StagedChange, ...],
        *,
        notes: tuple[ReviewNote, ...] = (),
        at_risk: tuple[str, ...] | None = None,
    ) -> None:
        """Hold the changes under review, what the check found, and the boxes applying could return to source.

        ``at_risk`` is ``None`` when the declaration records which values the
        filer typed; otherwise it names the boxes holding values nobody is
        recorded as having typed, which applying returns to their source.
        """
        super().__init__()
        self._changes = changes
        self._notes = notes
        self._at_risk = at_risk
        self._rebased = sum(1 for change in changes if change.before_changed)

    @property
    def _needs_acknowledgement(self) -> bool:
        return self._at_risk is not None or self._rebased > 0

    @property
    def _blocked(self) -> bool:
        return any(note.blocking for note in self._notes)

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
            if self._rebased:
                yield Static(
                    tr("tui.modelo.workbench.review.rebased", count=self._rebased), id="review-rebased", markup=False
                )
            if self._at_risk is not None:
                yield Static(at_risk_text(self._at_risk), id="review-at-risk", markup=False)
            if self._notes:
                yield Static(self._notes_text(), id="review-findings", markup=False)
            if self._needs_acknowledgement:
                yield Checkbox(tr("tui.modelo.workbench.review.acknowledge"), id="review-acknowledge")
            with Horizontal(id="review-actions"):
                yield Button(tr("tui.modelo.workbench.review.back"), id="review-back")
                yield Button(tr("tui.modelo.workbench.review.discard"), id="review-discard", variant="error")
                yield Button(
                    tr("tui.modelo.workbench.review.apply"),
                    id="review-apply",
                    variant="primary",
                    disabled=not self._may_apply(acknowledged=False),
                )

    def _notes_text(self) -> str:
        lines = [tr("tui.modelo.workbench.review.findings_heading")]
        for note in self._notes:
            box = f"[{note.box}] " if note.box else ""
            lines.append(f"{_NOTE_MARKS[note.blocking]} {box}{note.message}")
        if self._blocked:
            lines.append(tr("tui.modelo.workbench.review.blocked"))
        return "\n".join(lines)

    def _may_apply(self, *, acknowledged: bool) -> bool:
        return not self._blocked and (acknowledged or not self._needs_acknowledgement)

    def _acknowledged(self) -> bool:
        boxes = self.query("#review-acknowledge").results(Checkbox)
        return any(box.value for box in boxes)

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
            effect = tr(change_effect_key(change))
            if change.before_changed:
                effect = f"{effect} · {tr('tui.modelo.workbench.review.before_changed')}"
            table.add_row(
                field.box or "·",
                field.label.text,
                change.previous_text,
                change.text,
                effect,
                key=f"change-{index}",
            )
        table.focus()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Offer Apply once the filer has acknowledged what applying does."""
        self.query_one("#review-apply", Button).disabled = not self._may_apply(acknowledged=event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close with the filer's choice."""
        choice = {"review-apply": ReviewDecision.APPLY, "review-discard": ReviewDecision.DISCARD}.get(
            str(event.button.id)
        )
        self.dismiss(choice)

    def action_apply(self) -> None:
        """Apply the changes, once nothing blocks them and anything to acknowledge was acknowledged."""
        if self._may_apply(acknowledged=self._acknowledged()):
            self.dismiss(ReviewDecision.APPLY)

    def action_back(self) -> None:
        """Return to editing with every change kept."""
        self.dismiss(None)


__all__ = ["REVIEW_EFFECTS", "EditReviewScreen", "ReviewDecision", "ReviewNote", "at_risk_text", "change_effect_key"]
