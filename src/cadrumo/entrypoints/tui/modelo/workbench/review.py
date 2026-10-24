"""Review every staged change before anything is applied.

The review lists each change with its box, its concept, how it read before,
how it will read after, and what the change does in words: a new value, a value
that replaces what a source or the calculation produced, a value removed, or a
source restored. Each change is a wrapped line rather than a table row, so a
narrow terminal wraps the words instead of cutting them. Changes that displace
a source or a calculated figure are warned about, because the filer's value
will keep winning until they restore it. Nothing is saved until the filer
chooses to apply; the scrolling list has the focus on arrival so Enter cannot
apply by accident, and the acknowledgement and the buttons stay in view however
long the list grows.

What the application found when it checked the changes is listed under them;
a finding that would make it refuse the changes keeps Apply unavailable until
the filer resolves it, its mark drawn in the error colour as every blocker's
is. Two situations ask the filer to acknowledge before
applying: a declaration that does not record which of its values the filer
typed, where applying recalculates every value not listed without anything
typed elsewhere, and a declaration that changed after the changes were staged,
whose changed boxes are marked. The acknowledgement reads "[ ]" until it is
ticked, so an unticked box never looks ticked.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Final, override

from rich.cells import cell_len
from rich.console import Console
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Static

from .....application.modelo.work_form_typing_effect import (
    CLEAR_EFFECT_LOCALE_KEY,
    RESTORE_EFFECT_LOCALE_KEY,
    ModeloFormDisplacement,
    typing_effect_key,
    typing_effect_words,
)
from .....core.i18n.render import tr
from ...components.language import localized, refresh_localized_widgets
from ...components.theme import tokenised
from .bulk_confirm import TickBox
from .dialog_width import fit_dialog_width
from .issue_scale import blocks_marked
from .ports import WorkbenchChangeKind
from .session import StagedChange
from .sources import BOX_LIST_LINES
from .status_bar import StatusBar
from .vocabulary import BLOCKS_MARK, CHECK_MARK, WorkbenchMark

if TYPE_CHECKING:
    from .header import StatusLine


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


_FRAME: Final[int] = 4
"""Cells a dialog's border and padding take on each side, for a first estimate of its paragraph width."""
_NOTE_MARKS: Final[Mapping[bool, WorkbenchMark]] = {True: BLOCKS_MARK, False: CHECK_MARK}
"""A finding that refuses the changes blocks; any other is worth checking, marked as every surface marks it."""
_AND_MORE_LOCALE_KEY: Final[str] = "workspace.modelo.review.and_more"
_NAMED_BOXES_UP_TO: Final[int] = 20
"""Past this many boxes a list of their numbers stops helping; the sections that hold them are named instead."""


def change_effect_key(change: StagedChange) -> str:
    """The catalogue key saying in words what one change does; a typed value's is its field's."""
    if change.kind is WorkbenchChangeKind.CLEAR:
        return CLEAR_EFFECT_LOCALE_KEY
    if change.kind is WorkbenchChangeKind.RESTORE:
        return RESTORE_EFFECT_LOCALE_KEY
    return typing_effect_key(change.field)


def change_effect_text(change: StagedChange) -> str:
    """Say in words what one change does, naming the source a replaced value came from."""
    if change.kind is WorkbenchChangeKind.SET:
        return typing_effect_words(change.field)
    return tr(change_effect_key(change))


@dataclass(frozen=True, slots=True)
class UnattributedBoxes:
    """The boxes holding a value nobody is recorded as having typed, and the part of the form each sits in.

    ``boxes`` names each by its box number in brackets, or by its words when no
    box prints it; ``sections`` gives, in the same order, the heading of the
    section it sits in.
    """

    boxes: tuple[str, ...]
    sections: tuple[str, ...]


def _lines(text: str, console: Console, width: int) -> int:
    return len(Text(text).wrap(console, max(width, 1)))


def _fitted(parts: tuple[str, ...], console: Console, width: int) -> str:
    """``parts`` joined in at most two lines at ``width``; those that do not fit give way to how many more there are."""
    whole = ", ".join(parts)
    if _lines(whole, console, width) <= BOX_LIST_LINES:
        return whole
    room = BOX_LIST_LINES * max(width, 1)
    shown = 1
    while shown < len(parts) and cell_len(", ".join(parts[: shown + 1])) <= room:
        shown += 1
    while True:
        text = tr(_AND_MORE_LOCALE_KEY, shown=", ".join(parts[:shown]), count=len(parts) - shown)
        if shown == 1 or _lines(text, console, width) <= BOX_LIST_LINES:
            return text
        shown -= 1


def unattributed_words(unattributed: UnattributedBoxes, *, console: Console, width: int) -> str:
    """Name the boxes in at most two lines at ``width``; past twenty, the sections holding them, with counts.

    Every box is still counted: words that do not fit give way to how many
    more there are.
    """
    if len(unattributed.boxes) <= _NAMED_BOXES_UP_TO:
        return _fitted(unattributed.boxes, console, width)
    counts = Counter(unattributed.sections)
    return _fitted(tuple(f"{section} ({counts[section]})" for section in counts), console, width)


def at_risk_text(unattributed: UnattributedBoxes, *, console: Console, width: int) -> str:
    """Say what applying does to values nobody is recorded as having typed, naming their boxes at ``width``."""
    if not unattributed.boxes:
        return tr("workspace.modelo.review.operator_entries_unknown")
    return tr(
        "workspace.modelo.review.operator_entries_at_risk",
        count=len(unattributed.boxes),
        boxes=unattributed_words(unattributed, console=console, width=width),
    )


def recalculation_risk_text(unattributed: UnattributedBoxes, *, console: Console, width: int) -> str:
    """Say what recalculating does to values nobody is recorded as having typed, naming their boxes at ``width``."""
    if not unattributed.boxes:
        return tr("workspace.modelo.calculate.operator_entries_unknown")
    return tr(
        "workspace.modelo.calculate.operator_entries_at_risk",
        count=len(unattributed.boxes),
        boxes=unattributed_words(unattributed, console=console, width=width),
    )


def change_line(change: StagedChange) -> str:
    """One change as a line of words: its box and concept, how it read before and after, and its effect."""
    field = change.field
    box = f"[{field.box}] " if (field.box is not None and field.box) else ""
    effect = change_effect_text(change)
    if change.before_changed:
        effect = f"{effect} · {tr('workspace.modelo.review.before_changed')}"
    return tr(
        "workspace.modelo.review.change_line",
        box=box,
        concept=field.label.text,
        before=change.previous_text,
        after=change.text,
        effect=effect,
    )


def _displacing_count(changes: tuple[StagedChange, ...]) -> int:
    return sum(
        change.kind is WorkbenchChangeKind.SET
        and change.displaces in {ModeloFormDisplacement.SOURCE, ModeloFormDisplacement.CALCULATION}
        for change in changes
    )


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
        EditReviewScreen #review-status {
            color: $foreground;
            text-style: bold;
            height: auto;
            margin-bottom: $cadrumo-stack;
        }
        EditReviewScreen #review-title {
            text-style: bold;
            color: $primary;
        }
        EditReviewScreen #review-subtitle {
            color: $secondary;
            margin-bottom: $cadrumo-stack;
        }
        EditReviewScreen #review-body {
            height: 1fr;
        }
        EditReviewScreen #review-body:focus {
            background-tint: $foreground 4%;
        }
        EditReviewScreen .review-change {
            height: auto;
        }
        EditReviewScreen #review-warning, EditReviewScreen #review-at-risk, EditReviewScreen #review-rebased {
            color: $warning;
            text-style: bold;
            height: auto;
            margin-top: $cadrumo-stack;
        }
        EditReviewScreen #review-findings {
            height: auto;
            margin-top: $cadrumo-stack;
        }
        EditReviewScreen #review-acknowledge {
            margin-top: $cadrumo-stack;
        }
        EditReviewScreen #review-acknowledge > .toggle--button {
            color: $foreground;
        }
        EditReviewScreen #review-acknowledge.-on > .toggle--button {
            color: $text-success;
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
        at_risk: UnattributedBoxes | None = None,
        status_line: StatusLine | None = None,
    ) -> None:
        """Hold the changes under review, what the check found, and the boxes applying could return to source.

        ``at_risk`` is ``None`` when the declaration records which values the
        filer typed; otherwise it names the boxes holding values nobody is
        recorded as having typed, which applying returns to their source.
        ``status_line`` is the declaration's result line, shown first because
        the review dims the header that normally carries it.
        """
        super().__init__()
        self._changes = changes
        self._status_line = status_line
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
        displacing = _displacing_count(self._changes)
        with Container(id="review-backdrop"), Vertical(id="review-panel"):
            if self._status_line is not None:
                yield StatusBar(self._status_line, id="review-status")
            yield localized(
                Static(tr("workspace.modelo.review.title", count=len(self._changes)), id="review-title", markup=False),
                "workspace.modelo.review.title",
                count=len(self._changes),
            )
            yield localized(
                Static(tr("workspace.modelo.review.nothing_saved"), id="review-subtitle", markup=False),
                "workspace.modelo.review.nothing_saved",
            )
            with VerticalScroll(id="review-body", can_focus=True):
                for index, change in enumerate(self._changes):
                    yield Static(
                        change_line(change), id=f"review-change-{index}", classes="review-change", markup=False
                    )
                if displacing:
                    yield localized(
                        Static(
                            tr("workspace.modelo.review.displacing", count=displacing),
                            id="review-warning",
                            markup=False,
                        ),
                        "workspace.modelo.review.displacing",
                        count=displacing,
                    )
                if self._rebased:
                    yield localized(
                        Static(
                            tr("workspace.modelo.review.rebased", count=self._rebased),
                            id="review-rebased",
                            markup=False,
                        ),
                        "workspace.modelo.review.rebased",
                        count=self._rebased,
                    )
                if self._at_risk is not None:
                    yield Static(
                        self._at_risk_text(max(self.app.size.width - 2 * _FRAME, 1)),
                        id="review-at-risk",
                        markup=False,
                    )
                if self._notes:
                    yield Static(self._notes_text(), id="review-findings", markup=False)
            if self._needs_acknowledgement:
                yield TickBox(tr("workspace.modelo.review.acknowledge"), id="review-acknowledge", compact=True)
            with Horizontal(id="review-actions"):
                yield localized(
                    Button(tr("workspace.modelo.review.back"), id="review-back"), "workspace.modelo.review.back"
                )
                yield localized(
                    Button(tr("workspace.modelo.review.discard"), id="review-discard", variant="error"),
                    "workspace.modelo.review.discard",
                )
                yield localized(
                    Button(
                        tr("workspace.modelo.review.apply"),
                        id="review-apply",
                        variant="primary",
                        disabled=not self._may_apply(acknowledged=False),
                    ),
                    "workspace.modelo.review.apply",
                )

    def _notes_text(self) -> Content:
        lines = [tr("workspace.modelo.review.findings_heading")]
        for note in self._notes:
            box = f"[{note.box}] " if (note.box is not None and note.box) else ""
            lines.append(f"{_NOTE_MARKS[note.blocking].glyph} {box}{note.message}")
        if self._blocked:
            lines.append(tr("workspace.modelo.review.blocked"))
        return blocks_marked("\n".join(lines))

    def _may_apply(self, *, acknowledged: bool) -> bool:
        return not self._blocked and (acknowledged or not self._needs_acknowledgement)

    def _acknowledged(self) -> bool:
        boxes = self.query("#review-acknowledge").results(Checkbox)
        return any(box.value for box in boxes)

    def _at_risk_text(self, width: int) -> str:
        at_risk = self._at_risk
        return "" if at_risk is None else at_risk_text(at_risk, console=self.app.console, width=width)

    def _fit_at_risk(self) -> None:
        """Name the boxes applying could return to source in as many as fit the paragraph's width."""
        for widget in self.query("#review-at-risk").results(Static):
            width = widget.content_region.width
            if width:
                widget.update(self._at_risk_text(width))

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal."""
        fit_dialog_width(self, event.size.width)
        self.call_after_refresh(self._fit_at_risk)

    def on_mount(self) -> None:
        """Fit the terminal and give the list of changes the focus."""
        fit_dialog_width(self, self.app.size.width)
        self.query_one("#review-body", VerticalScroll).focus()
        self.call_after_refresh(self._fit_at_risk)

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

    async def refresh_language(self) -> None:
        """Reword the open dialog without changing its inputs or decision."""
        refresh_localized_widgets(self)


__all__ = [
    "EditReviewScreen",
    "ReviewDecision",
    "ReviewNote",
    "UnattributedBoxes",
    "at_risk_text",
    "change_effect_key",
    "change_effect_text",
    "change_line",
    "recalculation_risk_text",
    "unattributed_words",
]
