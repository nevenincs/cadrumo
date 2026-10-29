"""Shared shell, paging and door handling for the evidence and attachment tools.

Each tool reads through its injected doors from a worker, shows a refusal on
screen in the operator's language, and discards every private fact it holds
once the admitted session is lost.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator, Sequence
from typing import Protocol, override

from pydantic import ValidationError
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Button, Static

from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ..account import AccountSessionExpiredError
from ..components.language import localized
from ..components.theme import tokenised
from .controller import LedgerWorkspaceController
from .evidence_files_doors import LEDGER_EVIDENCE_FILES_PAGE_SIZE, LedgerEvidenceFilesDoorsV1
from .workspace_presentation import door_refusal_text
from .workspace_screen import LedgerWorkspaceScreen

EVIDENCE_FILES_CSS = tokenised(
    """
    .evidence-files-actions { height: auto; margin-bottom: $cadrumo-stack; }
    .evidence-files-actions Button { margin-right: $cadrumo-space-1; }
    .evidence-files-detail { height: auto; }
    """
)


def blank_to_none(value: str) -> str | None:
    """Read a field left blank as absent rather than as an empty value."""
    stripped = value.strip()
    return stripped or None


def short_identity(value: str) -> str:
    """The leading characters of an identifier, enough to tell rows apart."""
    return value[:12]


def shown(value: object | None) -> str:
    """A value as text, or a dash for one the record does not hold."""
    return "-" if value is None or value == "" else str(value)


class EvidenceFilesPager[ItemT]:
    """One page of an operation's rows; the table holds that page and nothing more."""

    def __init__(self, page_size: int = LEDGER_EVIDENCE_FILES_PAGE_SIZE) -> None:
        """Start empty at the first page."""
        if not 0 < page_size <= LEDGER_EVIDENCE_FILES_PAGE_SIZE:
            raise ValueError("an evidence page holds between one and the page-size limit of rows")
        self.page_size = page_size
        self.items: tuple[ItemT, ...] = ()
        self.offset = 0

    def load(self, items: Sequence[ItemT]) -> None:
        """Take a fresh read, staying on the current page while it still exists."""
        self.items = tuple(items)
        if self.offset >= len(self.items):
            self.offset = 0

    def clear(self) -> None:
        """Forget every row."""
        self.items = ()
        self.offset = 0

    def page(self) -> tuple[ItemT, ...]:
        """The rows of the current page."""
        return self.items[self.offset : self.offset + self.page_size]

    @property
    def has_previous(self) -> bool:
        """Whether an earlier page exists."""
        return self.offset > 0

    @property
    def has_next(self) -> bool:
        """Whether a later page exists."""
        return self.offset + self.page_size < len(self.items)

    def next(self) -> None:
        """Move to the following page, if there is one."""
        if self.has_next:
            self.offset += self.page_size

    def previous(self) -> None:
        """Move to the preceding page, if there is one."""
        if self.has_previous:
            self.offset = max(0, self.offset - self.page_size)

    def position_text(self) -> str:
        """Which rows of how many the page shows, or nothing for an empty read."""
        if not self.items:
            return ""
        return tr(
            "tui.ledger.evidence_files.page.position",
            first=self.offset + 1,
            last=self.offset + len(self.page()),
            total=len(self.items),
        )


class EvidenceFilesPaging(Protocol):
    """What a paged table's controls read from its pager."""

    @property
    def has_previous(self) -> bool:
        """Whether an earlier page exists."""
        ...

    @property
    def has_next(self) -> bool:
        """Whether a later page exists."""
        ...

    def position_text(self) -> str:
        """Which rows of how many the page shows."""
        ...


def paint_paging(scope: Widget, prefix: str, pager: EvidenceFilesPaging) -> None:
    """Enable only the page moves that exist and say which rows are shown."""
    scope.query_one(f"#{prefix}-previous", Button).disabled = not pager.has_previous
    scope.query_one(f"#{prefix}-next", Button).disabled = not pager.has_next
    scope.query_one(f"#{prefix}-position", Static).update(pager.position_text())


def paging_controls(prefix: str) -> Iterator[Widget]:
    """Yield the previous and next buttons and the position line of one paged table."""
    with Horizontal(id=f"{prefix}-paging", classes="evidence-files-actions"):
        yield localized(
            Button(tr("tui.ledger.evidence_files.page.previous"), id=f"{prefix}-previous", disabled=True),
            "tui.ledger.evidence_files.page.previous",
        )
        yield localized(
            Button(tr("tui.ledger.evidence_files.page.next"), id=f"{prefix}-next", disabled=True),
            "tui.ledger.evidence_files.page.next",
        )
    yield Static("", id=f"{prefix}-position", markup=False)


class EvidenceFilesToolScreen(LedgerWorkspaceScreen):
    """A Records tool over the evidence doors: one worker at a time, refusals on screen."""

    CSS = LedgerWorkspaceScreen.CSS + EVIDENCE_FILES_CSS

    def __init__(self, controller: LedgerWorkspaceController, doors: LedgerEvidenceFilesDoorsV1, *, id: str) -> None:
        """Keep the injected profile-bound doors for every request this tool submits."""
        super().__init__(controller, id=id)
        self.doors = doors
        self.busy = False
        """Whether a door call is out; a second request waits for it."""

    @property
    @override
    def in_flight(self) -> bool:
        """A door call is out."""
        return self.busy

    @staticmethod
    def banner(title: str, key: str) -> Static:
        """The tool's title line, ``title`` being ``tr(key)``, reworded on a language change."""
        return localized(Static(title, classes="cadrumo-banner"), key)

    def status(self, text: str) -> None:
        """Say what the tool is doing."""
        self.query_one("#ledger-flow-status", Static).update(text)

    def refuse(self, text: str) -> None:
        """Say why the last request did not go through."""
        self.query_one("#ledger-refusal", Static).update(text)

    def start(self, work: Callable[[], Awaitable[None]]) -> bool:
        """Run one door call off the event loop, unless another is still out."""
        if self.busy:
            self.status(tr("tui.ledger.flow.in_flight_refusal"))
            return False
        self.busy = True
        self.refuse("")
        self.run_worker(self._guarded(work), exclusive=True)
        return True

    async def _guarded(self, work: Callable[[], Awaitable[None]]) -> None:
        try:
            await work()
        finally:
            self.busy = False

    async def ask[ResultT](self, call: Awaitable[ResultT]) -> ResultT | None:
        """Await one door call, rendering a refusal or a lost session instead of raising it."""
        try:
            return await call
        except AccountSessionExpiredError as error:
            self.clear_private_view()
            self.refuse(door_refusal_text(error))
        except CadrumoError as error:
            self.refuse(door_refusal_text(error))
        except ValidationError as error:
            self.refuse(door_refusal_text(error))
        self.status(tr("tui.ledger.evidence_files.failed"))
        return None

    def clear_private_view(self) -> None:
        """Discard every evidence fact the tool shows once the admitted session is lost."""
        raise NotImplementedError


__all__ = [
    "EVIDENCE_FILES_CSS",
    "EvidenceFilesPager",
    "EvidenceFilesPaging",
    "EvidenceFilesToolScreen",
    "blank_to_none",
    "paging_controls",
    "paint_paging",
    "short_identity",
    "shown",
]
