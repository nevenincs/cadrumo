"""The profile's record groups, read-only: each served group with the rows that name it and its linked ledger rows.

Every kind the record-group read serves is read and drawn the same way, in the
kinds' served order, so a new kind needs no code here. A group shows its served
kind and summary words, each member indented under the row its served
``parent_ref`` names with its served relation words, and the ledger rows linked
to the group with the served words of their expense concept. A lease also shows
its served art. 23.2 reduction: the title, each fact it reads with its stated mark,
and each ejercicio's outcome words. A door the read serves on a field of a member
(the way out of a missing fact, ending a lease) is a button under its served label;
pressing it closes the screen with that door, and the page that owns the row opens
its field editor. The screen authors only chrome and edits nothing itself.

The read is paged. The next page of a kind continues at the first page's
revision; a refused page shows the read's own words, and reading again starts
every kind over.
"""

from __future__ import annotations

from typing import ClassVar, Final, NamedTuple, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static
from textual.worker import Worker, WorkerState

from ....application.user_profile.record_group_contracts import (
    ProfileRecordGroupKind,
    ProfileRecordLedgerRowItem,
    ProfileRecordMemberItem,
)
from ....core.i18n.render import tr
from ..components.language import localized
from ..components.theme import tokenised
from ..components.widgets import ContentScroll
from ..ledger.entries_common import DIRECTION_LOCALE_KEYS
from .record_groups import RecordGroupBlock, RecordGroupDoor, RecordGroupsPort, RecordGroupStream, field_doors

RECORD_GROUPS_TITLE_LOCALE_KEY: Final = "tui.profile.record_groups.title"
_READING_LOCALE_KEY: Final = "tui.profile.record_groups.reading"
_READ_FAILED_LOCALE_KEY: Final = "tui.profile.record_groups.read_failed"
_READ_AGAIN_LOCALE_KEY: Final = "tui.profile.record_groups.read_again"
_EMPTY_LOCALE_KEY: Final = "tui.profile.record_groups.empty"
_MORE_LOCALE_KEY: Final = "tui.profile.record_groups.more"
_CLOSE_LOCALE_KEY: Final = "tui.profile.record_groups.close"
_LINKED_ROWS_LOCALE_KEY: Final = "tui.profile.record_groups.linked_rows"
_LINKED_NONE_LOCALE_KEY: Final = "tui.profile.record_groups.linked_rows_none"
_LINKED_SHOWN_LOCALE_KEY: Final = "tui.profile.record_groups.linked_rows_shown"
_LEDGER_ROW_LOCALE_KEY: Final = "tui.profile.record_groups.ledger_row"
_FACT_STATED_LOCALE_KEY: Final = "tui.profile.record_groups.fact_stated"
_FACT_UNSTATED_LOCALE_KEY: Final = "tui.profile.record_groups.fact_unstated"

_WORDS_SEPARATOR: Final = " · "
"""Joins two served texts on one line; layout only, no words of its own."""
_INDENT: Final = "  "

_CSS: Final = tokenised("""
#record-groups-dialog {
    border: $cadrumo-radius-overlay $accent;
    background: $surface;
    padding: $cadrumo-space-0 $cadrumo-space-1;
    width: 100%;
    height: auto;
    max-height: 100%;
}
#record-groups-body { height: auto; max-height: $cadrumo-modal-max-height; }
#record-groups-title { text-style: bold; }
#record-groups-status { color: $text-muted; }
.record-group { height: auto; margin-top: $cadrumo-space-1; }
.record-group-summary { text-style: bold; }
.record-group-note { color: $text-muted; }
.record-group-reduction-title { text-style: bold; }
#record-groups-actions { height: auto; align-horizontal: right; margin: $cadrumo-space-0; }
#record-groups-actions Button { margin: $cadrumo-space-0 $cadrumo-space-0 $cadrumo-space-0 $cadrumo-control-gap; }
""")


def ledger_row_text(row: ProfileRecordLedgerRowItem) -> str:
    """One linked ledger row as a line: its date, direction, amount and description, then its served concept words."""
    line = tr(
        _LEDGER_ROW_LOCALE_KEY,
        date=row.booked_date.isoformat(),
        direction=tr(DIRECTION_LOCALE_KEYS[row.direction]),
        amount=row.amount.decimal,
        currency=row.currency,
        description=row.description,
    )
    return line if row.concept_words is None else f"{line}{_WORDS_SEPARATOR}{row.concept_words}"


class BlockLine(NamedTuple):
    """One line of a group: its style class, its text and the door it offers, when it is a door."""

    css: str
    text: str
    door: RecordGroupDoor | None = None


def fact_text(words: str, *, stated: bool) -> str:
    """One fact of a lease as served, behind a mark of whether the lease states it."""
    return tr(_FACT_STATED_LOCALE_KEY if stated else _FACT_UNSTATED_LOCALE_KEY, words=words)


def _reduction_lines(item: ProfileRecordMemberItem, indent: str) -> list[BlockLine]:
    """The served reduction of a lease: its title, the facts it reads and each ejercicio's outcome."""
    reduction = item.reduction
    if reduction is None:
        return []
    inner = indent + _INDENT
    lines = [BlockLine("record-group-reduction-title", f"{indent}{reduction.title_words}")]
    lines.extend(
        BlockLine("record-group-fact", f"{inner}{fact_text(fact.fact_words, stated=fact.stated)}")
        for fact in reduction.facts
    )
    lines.extend(BlockLine("record-group-outcome", f"{inner}{year.outcome_words}") for year in reduction.years)
    return lines


def block_rows(block: RecordGroupBlock) -> tuple[BlockLine, ...]:
    """The lines of one group in served order, each text served or chrome and each door as served."""
    group = block.group
    lines = [BlockLine("record-group-summary", f"{group.kind_words}{_WORDS_SEPARATOR}{group.summary_words}")]
    for member in block.members:
        indent = _INDENT * member.depth
        item = member.item
        lines.append(
            BlockLine("record-group-member", f"{indent}{item.kind_words}{_WORDS_SEPARATOR}{item.summary_words}")
        )
        lines.append(BlockLine("record-group-note", f"{indent}{item.relation_words}"))
        lines.extend(_reduction_lines(item, indent))
        lines.extend(
            BlockLine("record-group-door", f"{indent}{_INDENT}{door.action.label_words}", door)
            for door in field_doors(item)
        )
    if group.ledger_row_count == 0:
        lines.append(BlockLine("record-group-note", f"{_INDENT}{tr(_LINKED_NONE_LOCALE_KEY)}"))
        return tuple(lines)
    lines.append(BlockLine("record-group-note", f"{_INDENT}{tr(_LINKED_ROWS_LOCALE_KEY)}"))
    lines.extend(
        BlockLine("record-group-ledger-row", f"{_INDENT * 2}{ledger_row_text(row)}") for row in block.ledger_rows
    )
    if len(block.ledger_rows) < group.ledger_row_count:
        shown = tr(_LINKED_SHOWN_LOCALE_KEY, shown=len(block.ledger_rows), total=group.ledger_row_count)
        lines.append(BlockLine("record-group-note", f"{_INDENT}{shown}"))
    return tuple(lines)


def block_lines(block: RecordGroupBlock) -> tuple[tuple[str, str], ...]:
    """The lines of one group as ``(class, text)``, in served order, each text served or chrome."""
    return tuple((line.css, line.text) for line in block_rows(block))


class RecordGroupsScreen(ModalScreen[RecordGroupDoor | None]):
    """Read every served kind of record group and draw it a page at a time; a pressed door closes it."""

    DEFAULT_CSS = _CSS
    BINDINGS: ClassVar = [Binding("escape", "close", "", show=False)]

    def __init__(self, port: RecordGroupsPort) -> None:
        """Bind the host's read; nothing is read until the screen is mounted."""
        super().__init__()
        self._port = port
        self._streams: list[RecordGroupStream] = []
        self._job: Worker[None] | None = None
        self._doors: dict[Button, RecordGroupDoor] = {}

    @property
    def streams(self) -> tuple[RecordGroupStream, ...]:
        """Each kind's groups as read so far, in the kinds' served order."""
        return tuple(self._streams)

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="record-groups-dialog"):
            yield localized(
                Label(tr(RECORD_GROUPS_TITLE_LOCALE_KEY), id="record-groups-title"), RECORD_GROUPS_TITLE_LOCALE_KEY
            )
            yield Static(id="record-groups-status", markup=False)
            with ContentScroll(id="record-groups-body"):
                yield Vertical(id="record-groups-list")
            with Horizontal(id="record-groups-actions"):
                yield localized(Button(tr(_MORE_LOCALE_KEY), id="record-groups-more"), _MORE_LOCALE_KEY)
                yield localized(Button(tr(_READ_AGAIN_LOCALE_KEY), id="record-groups-read"), _READ_AGAIN_LOCALE_KEY)
                yield localized(Button(tr(_CLOSE_LOCALE_KEY), id="record-groups-close"), _CLOSE_LOCALE_KEY)

    def on_mount(self) -> None:
        """Read the first page of every kind."""
        self._read_again()

    def _status(self, text: str) -> None:
        self.query_one("#record-groups-status", Static).update(text)

    def _lock(self) -> None:
        busy = self._job is not None
        self.query_one("#record-groups-read", Button).disabled = busy
        more = self.query_one("#record-groups-more", Button)
        more.display = self._continuing() is not None
        more.disabled = busy

    def _continuing(self) -> RecordGroupStream | None:
        """The first kind whose read names a next page, which the next-page control continues."""
        return next((stream for stream in self._streams if stream.next_cursor is not None), None)

    def _start(self, streams: list[RecordGroupStream]) -> None:
        if self._job is not None:
            return
        self._status(tr(_READING_LOCALE_KEY))
        self._job = self.run_worker(
            self._read_pages(streams), name="profile-record-groups", group="profile-record-groups", exit_on_error=False
        )
        self._lock()

    async def _read_pages(self, streams: list[RecordGroupStream]) -> None:
        for stream in streams:
            cursor = stream.next_cursor
            if cursor is not None:
                stream.accept(await self._port.read(stream.kind, cursor=cursor, pin=stream.pin))

    def _read_again(self) -> None:
        if self._job is not None:
            return
        self._streams = [RecordGroupStream(kind) for kind in ProfileRecordGroupKind]
        self._start(list(self._streams))

    async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Draw what was read once the read finishes, or say it could not be read."""
        if self._job is None or event.worker is not self._job:
            return
        if event.state not in {WorkerState.SUCCESS, WorkerState.ERROR, WorkerState.CANCELLED}:
            return
        self._job = None
        refusal = next((stream.refusal_words for stream in self._streams if stream.refusal_words is not None), None)
        if event.state is not WorkerState.SUCCESS:
            self._status(tr(_READ_FAILED_LOCALE_KEY))
        elif refusal is not None:
            self._status(refusal)
        elif not any(stream.blocks for stream in self._streams):
            self._status(tr(_EMPTY_LOCALE_KEY))
        else:
            self._status("")
        await self._draw()
        self._lock()

    async def _draw(self) -> None:
        body = self.query_one("#record-groups-list", Vertical)
        await body.remove_children()
        self._doors = {}
        for stream in self._streams:
            for block in stream.blocks:
                lines = [self._line_widget(line) for line in block_rows(block)]
                await body.mount(Vertical(*lines, classes="record-group"))

    def _line_widget(self, line: BlockLine) -> Static | Button:
        if line.door is None:
            return Static(line.text, classes=line.css, markup=False)
        # The served label is drawn as it is served, brackets and all.
        button = Button(Content(line.door.action.label_words), classes=line.css, compact=True)
        self._doors[button] = line.door
        return button

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Continue the next kind with a next page, read every kind again, or close."""
        door = self._doors.get(event.button)
        if door is not None:
            event.stop()
            self.dismiss(door)
            return
        button_id = event.button.id
        if button_id == "record-groups-close":
            event.stop()
            self.dismiss(None)
        elif button_id == "record-groups-read":
            event.stop()
            self._read_again()
        elif button_id == "record-groups-more":
            event.stop()
            stream = self._continuing()
            if stream is not None:
                self._start([stream])

    def action_close(self) -> None:
        """Close the screen."""
        self.dismiss(None)


__all__ = [
    "RECORD_GROUPS_TITLE_LOCALE_KEY",
    "BlockLine",
    "RecordGroupsScreen",
    "block_lines",
    "block_rows",
    "fact_text",
    "ledger_row_text",
]
