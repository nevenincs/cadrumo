"""The profile's record groups as the record-group read serves them, page by page.

The read serves one stream per group kind: each group's head row, then the rows
that name it, then the ledger rows that name any of them, each item carrying its
group's key and its words. This module only collects the pages in served order
and checks that each page continues the one before. It never reads a member's
field to place it, never composes a summary and never works out a relation: a
member sits under the row its served ``parent_ref`` names.

A continuation names the profile revision and the digests the first page was
read at, so a page from a profile or ledger that moved since is refused by the
read, with served words, rather than spliced onto the earlier pages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ....application.user_profile.record_group_contracts import (
    ProfileRecordGroupItem,
    ProfileRecordGroupKind,
    ProfileRecordGroupsResult,
    ProfileRecordLedgerRowItem,
    ProfileRecordMemberItem,
)


@dataclass(frozen=True, slots=True)
class RecordGroupsPin:
    """The profile revision and digests a stream's first page was read at; every continuation names them."""

    record_revision: int
    content_digest: str
    ledger_digest: str


class RecordGroupsPort(Protocol):
    """The host's read of one page of one kind's groups, bound to one exact profile session.

    The page is read in the host's current output language.
    """

    async def read(
        self, group_kind: ProfileRecordGroupKind, *, cursor: int, pin: RecordGroupsPin | None
    ) -> ProfileRecordGroupsResult:
        """Read the page starting at ``cursor``; a continuation passes the first page's ``pin``."""
        ...


class MalformedRecordGroupPageError(ValueError):
    """A page that does not continue the stream it was read for."""


@dataclass(frozen=True, slots=True)
class RecordGroupMember:
    """One member row and how many rows lie between it and its group's head row."""

    item: ProfileRecordMemberItem
    depth: int


@dataclass(slots=True)
class RecordGroupBlock:
    """One group as read so far: its head row, its members and its linked ledger rows, in served order."""

    group: ProfileRecordGroupItem
    members: list[RecordGroupMember] = field(default_factory=list)
    ledger_rows: list[ProfileRecordLedgerRowItem] = field(default_factory=list)

    def _depth_of(self, parent_ref: str) -> int:
        if parent_ref == self.group.group_key:
            return 1
        parent = next((member for member in self.members if member.item.row_ref == parent_ref), None)
        if parent is None:
            raise MalformedRecordGroupPageError("a member names a row its group has not served before it")
        return parent.depth + 1

    def add_member(self, item: ProfileRecordMemberItem) -> None:
        """Place a member under the row it names, which the group served before it."""
        self.members.append(RecordGroupMember(item=item, depth=self._depth_of(item.parent_ref)))

    def add_ledger_row(self, item: ProfileRecordLedgerRowItem) -> None:
        """Append a ledger row at the place among the group's ledger rows the read serves it at."""
        if item.ledger_row_index != len(self.ledger_rows) or item.ledger_row_total != self.group.ledger_row_count:
            raise MalformedRecordGroupPageError("a ledger row is not the next of its group's ledger rows")
        self.ledger_rows.append(item)


@dataclass(slots=True)
class RecordGroupStream:
    """The groups of one kind as read so far, and whether and where the read continues."""

    kind: ProfileRecordGroupKind
    blocks: list[RecordGroupBlock] = field(default_factory=list)
    pin: RecordGroupsPin | None = None
    next_cursor: int | None = 0
    refusal_words: str | None = None
    _read: int = 0

    @property
    def read_started(self) -> bool:
        """Whether a page of this stream has been accepted."""
        return self.pin is not None

    def accept(self, result: ProfileRecordGroupsResult) -> None:
        """Take the next page, or the read's refusal of it, after checking that it continues this stream.

        Raises:
            MalformedRecordGroupPageError: When the page is not the next page of this kind at this pin.
        """
        if result.group_kind is not self.kind:
            raise MalformedRecordGroupPageError("a page of another kind")
        if result.outcome == "refused":
            self.refusal_words = result.refusal_words
            self.next_cursor = None
            return
        pin = RecordGroupsPin(result.record_revision, result.content_digest, result.ledger_digest)
        if (self.pin is not None and pin != self.pin) or result.cursor != self._read:
            raise MalformedRecordGroupPageError("a page that does not continue the pages read before it")
        for item in result.items:
            self._place(item)
        self.pin = pin
        self._read = result.cursor + len(result.items)
        self.next_cursor = result.next_cursor

    def _place(self, item: ProfileRecordGroupItem | ProfileRecordMemberItem | ProfileRecordLedgerRowItem) -> None:
        if isinstance(item, ProfileRecordGroupItem):
            if item.payload_kind is not self.kind or any(
                block.group.group_key == item.group_key for block in self.blocks
            ):
                raise MalformedRecordGroupPageError("a group served twice, or of another kind")
            self.blocks.append(RecordGroupBlock(group=item))
            return
        # The read serves every item of a group straight after its head row.
        if not self.blocks or self.blocks[-1].group.group_key != item.group_key:
            raise MalformedRecordGroupPageError("an item served outside its group")
        if isinstance(item, ProfileRecordMemberItem):
            self.blocks[-1].add_member(item)
        else:
            self.blocks[-1].add_ledger_row(item)


__all__ = [
    "MalformedRecordGroupPageError",
    "RecordGroupBlock",
    "RecordGroupMember",
    "RecordGroupStream",
    "RecordGroupsPin",
    "RecordGroupsPort",
]
