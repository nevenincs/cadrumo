"""The disagreements dialog: what the form states, the answers held for it, and the two answers an operator can give.

The dialog lists each source disagreement the declaration states, in the form's
order, followed by any answer the form no longer states. The highlighted entry
shows the application's own sentences: the line's message, action and detail,
what answering records, and, where an answer is held, what it covers, whether it
stands and why it could not be taken back. Accepting needs the operator's
reason; revoking is offered only for an answer the application says it will
take back. A refusal is drawn by the shared refusal slot in the words the
application served. An answer whose outcome is unknown is never sent again from
this dialog.

The dialog reads and answers through a door off the event loop and changes
nothing itself. Closing after an answer returns the application's sentence for
it, and the workbench reads the declaration again.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import ClassVar, Final, Literal, override

from rich.console import Group, RenderableType
from rich.padding import Padding
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from ....application.modelo.credit_resolution_contracts import CreditResolutionRowProjection
from ....application.modelo.work_form_issue_lines import ModeloFormIssueLine
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language, tr
from ....core.logging import get_logger
from ....domain.modelos.credit_resolution import CREDIT_RESOLUTION_REASON_MAX_LENGTH
from ..components.language import localized, refresh_localized_widgets
from ..components.theme import tokenised
from ..refusal.panel import RefusalSlot
from .disagreements import (
    DisagreementEntryV1,
    ModeloDisagreementsDoorV1,
    committed,
    disagreement_entries,
    refusal_to_show,
)
from .workbench.dialog_width import fit_dialog_height, fit_dialog_width
from .workbench.keys import describe_bindings

_INDENT: Final[int] = 2
_ENTRY_PREFIX: Final[str] = "entry-"

#: The dialog's own words, written once for the catalogue; every other sentence on it is served.
TITLE_LOCALE_KEY: Final[str] = "tui.modelo.disagreements.title"
READING_LOCALE_KEY: Final[str] = "tui.modelo.disagreements.reading"
READ_FAILED_LOCALE_KEY: Final[str] = "tui.modelo.disagreements.read_failed"
NONE_LOCALE_KEY: Final[str] = "tui.modelo.disagreements.none"
REASON_LOCALE_KEY: Final[str] = "tui.modelo.disagreements.reason_label"
YOUR_REASON_LOCALE_KEY: Final[str] = "tui.modelo.disagreements.your_reason"
ACCEPT_LOCALE_KEY: Final[str] = "tui.modelo.disagreements.accept"
REVOKE_LOCALE_KEY: Final[str] = "tui.modelo.disagreements.revoke"
SENDING_LOCALE_KEY: Final[str] = "tui.modelo.disagreements.sending"
UNKNOWN_LOCALE_KEY: Final[str] = "tui.modelo.disagreements.outcome_unknown"
REFUSED_LOCALE_KEY: Final[str] = "tui.modelo.disagreements.refused"
CLOSE_LOCALE_KEY: Final[str] = "workspace.modelo.result_diff.close"
BACK_LOCALE_KEY: Final[str] = "workspace.modelo.key.back"

_KEY_DESCRIPTIONS: Final[dict[str, str]] = {"escape": BACK_LOCALE_KEY, "a": ACCEPT_LOCALE_KEY, "r": REVOKE_LOCALE_KEY}

type _Phase = Literal["reading", "ready", "failed"]
type _Kind = Literal["accept", "revoke"]


@dataclass(frozen=True, slots=True)
class DisagreementsChangedV1:
    """What the dialog closes with when an answer may have been stored: the sentence to say, then read again."""

    words: str


def _paragraph(text: str | None, style: str = "") -> Text | None:
    return None if text is None or text == "" else Text(text, style=style)


def _entry(*parts: RenderableType | None) -> RenderableType:
    return Padding(Group(*(part for part in parts if part is not None)), (0, 0, 0, _INDENT))


def _place(line: ModeloFormIssueLine) -> str | None:
    if line.box is None:
        return line.where
    return f"[{line.box}]" if line.where is None else f"[{line.box}] {line.where}"


def _answer_parts(answer: CreditResolutionRowProjection) -> tuple[Text | None, ...]:
    """What the application served about an answer held: what it covers, whether it stands, whether it applies."""
    return (
        _paragraph(answer.answer_words),
        _paragraph(answer.state_words, "italic"),
        _paragraph(answer.current_words, "dim"),
    )


def entry_prompt(entry: DisagreementEntryV1) -> RenderableType:
    """The line a disagreement takes in the list."""
    line, answer = entry.line, entry.answer
    if line is None:
        return _entry(*(() if answer is None else _answer_parts(answer)))
    return _entry(
        _paragraph(_place(line), "bold"),
        _paragraph(line.message),
        _paragraph(None if answer is None else answer.state_words, "italic"),
    )


def entry_detail(entry: DisagreementEntryV1) -> RenderableType:
    """Everything the application served about the highlighted disagreement."""
    line, answer = entry.line, entry.answer
    parts: list[Text | None] = []
    if line is not None:
        parts += [
            _paragraph(_place(line), "bold"),
            _paragraph(line.message),
            _paragraph(line.action, "italic"),
            _paragraph(line.detail),
            _paragraph(line.answer_lead_words),
        ]
    if answer is not None:
        parts += [*_answer_parts(answer), _paragraph(tr(YOUR_REASON_LOCALE_KEY, reason=answer.reason))]
        if not answer.revocable:
            parts.append(_paragraph(answer.revoke_refusal_words))
    return Group(*(part for part in parts if part is not None))


class ModeloDisagreementsScreen(ModalScreen[DisagreementsChangedV1 | None]):
    """List one declaration's disagreements and send the operator's answer to the one highlighted."""

    SCOPED_CSS: ClassVar[bool] = False
    DEFAULT_CSS: ClassVar[str] = tokenised(
        """
        ModeloDisagreementsScreen #disagreements-backdrop {
            width: 1fr;
            height: 1fr;
            align: center middle;
        }
        ModeloDisagreementsScreen #disagreements-panel {
            width: $cadrumo-modal-width;
            height: $cadrumo-modal-height;
            border: $cadrumo-radius-overlay $primary;
            background: $surface;
            padding: $cadrumo-gutter-y $cadrumo-gutter;
        }
        ModeloDisagreementsScreen.-narrow #disagreements-panel {
            width: 100%;
        }
        ModeloDisagreementsScreen.-short #disagreements-panel {
            height: 100%;
        }
        ModeloDisagreementsScreen #disagreements-title {
            text-style: bold;
            color: $foreground;
        }
        ModeloDisagreementsScreen #disagreements-status {
            height: auto;
            color: $secondary;
        }
        ModeloDisagreementsScreen #disagreements-list {
            height: 1fr;
        }
        ModeloDisagreementsScreen #disagreements-detail {
            height: auto;
            max-height: $cadrumo-dialog-detail-max-height;
            margin-top: $cadrumo-stack;
        }
        ModeloDisagreementsScreen #disagreements-note {
            height: auto;
            color: $warning;
        }
        ModeloDisagreementsScreen #disagreements-actions {
            height: auto;
            margin-top: $cadrumo-stack;
            align-horizontal: right;
        }
        """
    )

    BINDINGS: ClassVar = [
        Binding("escape", "close", "", show=False),
        Binding("a", "accept", "", show=False),
        Binding("r", "revoke", "", show=False),
    ]

    def __init__(
        self,
        door: ModeloDisagreementsDoorV1,
        *,
        calculation_revision_id: str,
        lines_for: Callable[[OutputLanguage], tuple[ModeloFormIssueLine, ...]],
    ) -> None:
        """Bind the door, the calculation answered, and how the form states its disagreements in a language."""
        super().__init__()
        self._door = door
        self._revision = calculation_revision_id
        self._lines_for = lines_for
        self._language = OutputLanguage(output_language())
        self._lines = lines_for(self._language)
        self._answers: tuple[CreditResolutionRowProjection, ...] = ()
        self._phase: _Phase = "reading"
        self._entries: tuple[DisagreementEntryV1, ...] = disagreement_entries(self._lines, ())
        self._busy = False
        self._held = False
        self._said = ""
        self._reads = 0

    @override
    def compose(self) -> ComposeResult:
        with Container(id="disagreements-backdrop"), Vertical(id="disagreements-panel"):
            yield localized(Static(tr(TITLE_LOCALE_KEY), id="disagreements-title", markup=False), TITLE_LOCALE_KEY)
            yield Static(id="disagreements-status", markup=False)
            yield OptionList(id="disagreements-list")
            yield Static(id="disagreements-detail", markup=False)
            yield localized(
                Input(
                    placeholder=tr(REASON_LOCALE_KEY),
                    id="disagreements-reason",
                    max_length=CREDIT_RESOLUTION_REASON_MAX_LENGTH,
                ),
                REASON_LOCALE_KEY,
            )
            yield Static(id="disagreements-note", markup=False)
            yield RefusalSlot(id="disagreements-refusal")
            with Horizontal(id="disagreements-actions"):
                yield localized(
                    Button(tr(ACCEPT_LOCALE_KEY), id="disagreements-accept", variant="primary"), ACCEPT_LOCALE_KEY
                )
                yield localized(Button(tr(REVOKE_LOCALE_KEY), id="disagreements-revoke"), REVOKE_LOCALE_KEY)
                yield localized(Button(tr(CLOSE_LOCALE_KEY), id="disagreements-close"), CLOSE_LOCALE_KEY)
        yield Footer(compact=True)

    def on_mount(self) -> None:
        """Draw what the form states, then read the answers held."""
        fit_dialog_width(self, self.app.size.width)
        fit_dialog_height(self, self.app.size.height)
        describe_bindings(self._bindings.key_to_bindings, _KEY_DESCRIPTIONS)
        self.refresh_bindings()
        self._redraw()
        self.query_one(OptionList).focus()
        self._read_answers()

    def on_resize(self, event: events.Resize) -> None:
        """Take the whole width on a narrow terminal and the whole height on a short one."""
        fit_dialog_width(self, event.size.width)
        fit_dialog_height(self, event.size.height)

    async def refresh_language(self) -> None:
        """Reword the open dialog: the form's lines at once, the served answers once they are read again."""
        refresh_localized_widgets(self)
        describe_bindings(self._bindings.key_to_bindings, _KEY_DESCRIPTIONS)
        self._language = OutputLanguage(output_language())
        self._lines = self._lines_for(self._language)
        self._redraw()
        self._read_answers()

    # -- reading ---------------------------------------------------------------

    def _read_answers(self) -> None:
        self._reads += 1
        self.run_worker(partial(self._read, self._reads, self._language), group="disagreements-read", exclusive=True)

    async def _read(self, ticket: int, language: OutputLanguage) -> None:
        try:
            projection = await asyncio.to_thread(self._door.list_answers, self._revision, language)
        except Exception as failure:
            get_logger(__name__).warning("the disagreements could not be read: %s", type(failure).__qualname__)
            if ticket == self._reads:
                self._phase = "failed"
                self._redraw()
            return
        if ticket != self._reads:
            return
        self._answers = projection.resolutions
        self._phase = "ready"
        self._redraw()

    # -- drawing ---------------------------------------------------------------

    def _highlighted(self) -> DisagreementEntryV1 | None:
        listing = self.query_one(OptionList)
        index = listing.highlighted
        if index is None or index >= len(self._entries):
            return None
        return self._entries[index]

    def _redraw(self) -> None:
        held_on = self._highlighted()
        self._entries = disagreement_entries(self._lines, self._answers)
        listing = self.query_one(OptionList)
        listing.clear_options()
        listing.add_options(
            [
                Option(entry_prompt(entry), id=f"{_ENTRY_PREFIX}{position}")
                for position, entry in enumerate(self._entries)
            ]
        )
        if self._entries:
            keep = 0
            if held_on is not None:
                keep = next(
                    (
                        position
                        for position, entry in enumerate(self._entries)
                        if entry.finding_id == held_on.finding_id
                    ),
                    0,
                )
            listing.highlighted = keep
        status = self.query_one("#disagreements-status", Static)
        if self._phase == "reading":
            said = tr(READING_LOCALE_KEY)
        elif self._phase == "failed":
            said = tr(READ_FAILED_LOCALE_KEY)
        else:
            said = "" if self._entries else tr(NONE_LOCALE_KEY)
        status.update(said)
        status.display = bool(said)
        self._show_selection()

    def _show_selection(self) -> None:
        entry = self._highlighted()
        self.query_one("#disagreements-detail", Static).update("" if entry is None else entry_detail(entry))
        note = self.query_one("#disagreements-note", Static)
        note.update(tr(SENDING_LOCALE_KEY) if self._busy else tr(UNKNOWN_LOCALE_KEY) if self._held else self._said)
        reason = self.query_one("#disagreements-reason", Input)
        reason.display = entry is not None and entry.offers_accept
        self.query_one("#disagreements-accept", Button).disabled = not self._may("accept")
        self.query_one("#disagreements-revoke", Button).disabled = not self._may("revoke")
        self.refresh_bindings()

    def on_option_list_option_highlighted(self, _event: OptionList.OptionHighlighted) -> None:
        """Show everything served about the entry now under the cursor."""
        self._show_selection()

    # -- answering -------------------------------------------------------------

    def _may(self, kind: _Kind) -> bool:
        entry = self._highlighted()
        if entry is None or self._busy or self._held:
            return False
        if kind == "accept":
            return entry.offers_accept and bool(self.query_one("#disagreements-reason", Input).value.strip())
        return entry.offers_revoke

    @override
    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Offer an answer's key only where that answer can be sent now."""
        if action in ("accept", "revoke"):
            return self._may("accept" if action == "accept" else "revoke")
        return True

    def on_input_changed(self, _event: Input.Changed) -> None:
        """Offer accepting once the operator has given a reason."""
        self._show_selection()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Accept on Enter in the reason box."""
        event.stop()
        self.action_accept()

    def action_accept(self) -> None:
        """Send the operator's acceptance of the highlighted disagreement, with their reason."""
        if self._may("accept"):
            self._send("accept")
        elif (entry := self._highlighted()) is not None and entry.offers_accept and not (self._busy or self._held):
            self.query_one("#disagreements-reason", Input).focus()

    def action_revoke(self) -> None:
        """Send the taking back of the highlighted disagreement's answer."""
        if self._may("revoke"):
            self._send("revoke")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route the dialog's three buttons."""
        event.stop()
        if event.button.id == "disagreements-accept":
            self.action_accept()
        elif event.button.id == "disagreements-revoke":
            self.action_revoke()
        else:
            self.action_close()

    def _send(self, kind: _Kind) -> None:
        entry = self._highlighted()
        if entry is None:
            return
        reason = self.query_one("#disagreements-reason", Input).value.strip()
        stored_at = None if entry.answer is None else entry.answer.revision_id
        if kind == "revoke" and stored_at is None:
            return
        self._busy = True
        self._said = ""
        self.query_one(RefusalSlot).show(None)
        self._show_selection()
        self.run_worker(
            partial(self._answer, kind, entry.finding_id, reason, stored_at, self._language), group="disagreements-send"
        )

    async def _answer(
        self, kind: _Kind, finding_id: str, reason: str, stored_at: str | None, language: OutputLanguage
    ) -> None:
        try:
            if kind == "revoke" and stored_at is not None:
                projection = await asyncio.to_thread(self._door.revoke, self._revision, finding_id, stored_at, language)
            else:
                projection = await asyncio.to_thread(self._door.accept, self._revision, finding_id, reason, language)
        except Exception as failure:
            # The answer may have been stored: say so, and send nothing more from here.
            get_logger(__name__).warning("a disagreement answer's outcome is unknown: %s", type(failure).__qualname__)
            self._busy = False
            self._held = True
            self._show_selection()
            return
        self._busy = False
        resolution = projection.resolution
        if committed(projection) and resolution is not None:
            self.dismiss(DisagreementsChangedV1(words=resolution.state_words))
            return
        refusal = refusal_to_show(projection)
        slot = self.query_one(RefusalSlot)
        if refusal is None:
            self._said = tr(REFUSED_LOCALE_KEY)
        else:
            slot.show(refusal)
        # What it was refused against may have moved: show the answers as they stand.
        self._show_selection()
        self._read_answers()

    # -- leaving ---------------------------------------------------------------

    def action_close(self) -> None:
        """Close, saying the answer may have been stored when its outcome is unknown; never while one is being sent."""
        if self._busy:
            return
        self.dismiss(DisagreementsChangedV1(words=tr(UNKNOWN_LOCALE_KEY)) if self._held else None)


__all__ = ["DisagreementsChangedV1", "ModeloDisagreementsScreen", "entry_detail", "entry_prompt"]
