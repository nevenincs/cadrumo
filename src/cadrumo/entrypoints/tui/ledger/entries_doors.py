"""Injected doors the Records entry tools submit through, one per registered operation.

Each door is bound to one admitted profile and submits exactly the typed
request it is given, returning the operation's own receipt-correlated result.
A door is awaited on the event loop and owns its own off-loop work: its session
checks and transport exchanges run on worker threads, so a screen never blocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ....application.ledger.check_operation import LedgerCheckProjection, LedgerCheckRequest
from ....application.ledger.export_operation import LedgerExportProjection, LedgerExportRequest
from ....application.ledger.history_operation import (
    LedgerHistoryProjection,
    LedgerHistoryRequest,
    LedgerHistoryTypedProjection,
)
from ....application.ledger.ledger_add_contracts import LedgerAddOperationResult, LedgerAddRequest
from ....application.ledger.lifecycle_contracts import (
    LedgerLifecycleMutationRequest,
    LedgerLifecycleOperationId,
    LedgerLifecycleOperationResult,
)
from ....application.ledger.list_operation import LedgerListProjection, LedgerListRequest
from ....application.ledger.merge_operation import LedgerMergeOperationResult, LedgerMergeRequest
from ....application.ledger.preflight_operation import LedgerPreflightProjection, LedgerPreflightRequest
from ....application.ledger.remove_operation import LedgerRemoveOperationResult, LedgerRemoveRequest
from ....application.ledger.reset_operation import LedgerResetOperationResult, LedgerResetRequest
from ....application.ledger.status_operation import LedgerStatusProjection, LedgerStatusRequest
from ....application.ledger.track_operation import LedgerTrackProjection, LedgerTrackRequest


class _ProfileDoor(Protocol):
    @property
    def profile_id(self) -> UUID:
        """The profile every request through this door must name."""
        ...


class LedgerListDoorV1(_ProfileDoor, Protocol):
    """Injected door to ``ledger.list`` for one admitted profile."""

    async def __call__(self, request: LedgerListRequest) -> LedgerListProjection:
        """Read one page of entries."""
        ...


class LedgerAddDoorV1(_ProfileDoor, Protocol):
    """Injected door to ``ledger.add`` for one admitted profile."""

    async def __call__(self, request: LedgerAddRequest) -> LedgerAddOperationResult:
        """Record one entry, or return the operation's own validation refusal."""
        ...


class LedgerRemoveDoorV1(_ProfileDoor, Protocol):
    """Injected door to ``ledger.remove`` for one admitted profile."""

    async def __call__(self, request: LedgerRemoveRequest) -> LedgerRemoveOperationResult:
        """Preview or remove one entry."""
        ...


class LedgerLifecycleDoorV1(_ProfileDoor, Protocol):
    """Injected door to one lifecycle operation: archive, stash, restore or exclude."""

    @property
    def operation_id(self) -> LedgerLifecycleOperationId:
        """The lifecycle operation this door submits."""
        ...

    async def __call__(self, request: LedgerLifecycleMutationRequest) -> LedgerLifecycleOperationResult:
        """Move one entry, or return the operation's own validation refusal."""
        ...


class LedgerMergeDoorV1(_ProfileDoor, Protocol):
    """Injected door to ``ledger.merge`` for one admitted profile."""

    async def __call__(self, request: LedgerMergeRequest) -> LedgerMergeOperationResult:
        """Merge the children of one split back into a single entry."""
        ...


class LedgerHistoryDoorV1(_ProfileDoor, Protocol):
    """Injected door to ``ledger.history`` for one admitted profile."""

    async def __call__(self, request: LedgerHistoryRequest) -> LedgerHistoryProjection:
        """Read one entry's complete event record."""
        ...


class LedgerHistoryTypedDoorV1(_ProfileDoor, Protocol):
    """Injected door to ``ledger.history.typed`` for one admitted profile."""

    async def __call__(self, request: LedgerHistoryRequest) -> LedgerHistoryTypedProjection:
        """Read one entry's history with only its declared facts."""
        ...


class LedgerTrackDoorV1(_ProfileDoor, Protocol):
    """Injected door to ``ledger.track`` for one admitted profile."""

    async def __call__(self, request: LedgerTrackRequest) -> LedgerTrackProjection:
        """Read one entry's lineage and filing participation."""
        ...


class LedgerStatusDoorV1(_ProfileDoor, Protocol):
    """Injected door to ``ledger.status`` for one admitted profile."""

    async def __call__(self, request: LedgerStatusRequest) -> LedgerStatusProjection:
        """Read the ledger's counts, totals and readiness."""
        ...


class LedgerCheckDoorV1(_ProfileDoor, Protocol):
    """Injected door to ``ledger.check`` for one admitted profile."""

    async def __call__(self, request: LedgerCheckRequest) -> LedgerCheckProjection:
        """Read the preflight sweep and invoice link findings."""
        ...


class LedgerPreflightDoorV1(_ProfileDoor, Protocol):
    """Injected door to ``ledger.preflight`` for one admitted profile."""

    async def __call__(self, request: LedgerPreflightRequest) -> LedgerPreflightProjection:
        """Read the missing facts for one period."""
        ...


class LedgerResetDoorV1(_ProfileDoor, Protocol):
    """Injected door to ``ledger.reset`` for one admitted profile."""

    async def __call__(self, request: LedgerResetRequest) -> LedgerResetOperationResult:
        """Preview or reset the whole ledger."""
        ...


class LedgerExportDoorV1(_ProfileDoor, Protocol):
    """Injected door to ``ledger.export`` for one admitted profile."""

    async def __call__(self, request: LedgerExportRequest) -> LedgerExportProjection:
        """Write one export and report what was written.

        An export that failed after it may have published its file raises
        :class:`~cadrumo.entrypoints.tui.operations.outcome.OperationOutcomeUnknownError`
        with the receipt's effect, since the file can exist although the
        ledger does not record it.
        """
        ...


@dataclass(frozen=True, slots=True)
class LedgerEntriesDoorsV1:
    """Every door the entry tools need, all bound to the same admitted profile."""

    list_entries: LedgerListDoorV1
    add: LedgerAddDoorV1
    remove: LedgerRemoveDoorV1
    archive: LedgerLifecycleDoorV1
    stash: LedgerLifecycleDoorV1
    restore: LedgerLifecycleDoorV1
    exclude: LedgerLifecycleDoorV1
    merge: LedgerMergeDoorV1
    history: LedgerHistoryDoorV1
    history_typed: LedgerHistoryTypedDoorV1
    track: LedgerTrackDoorV1
    status: LedgerStatusDoorV1
    check: LedgerCheckDoorV1
    preflight: LedgerPreflightDoorV1
    reset: LedgerResetDoorV1
    export: LedgerExportDoorV1

    def __post_init__(self) -> None:
        """Refuse a bundle whose doors answer for different profiles."""
        doors: tuple[_ProfileDoor, ...] = (
            self.list_entries,
            self.add,
            self.remove,
            self.archive,
            self.stash,
            self.restore,
            self.exclude,
            self.merge,
            self.history,
            self.history_typed,
            self.track,
            self.status,
            self.check,
            self.preflight,
            self.reset,
            self.export,
        )
        if len({door.profile_id for door in doors}) != 1:
            raise ValueError("every entry door must answer for the same profile")

    @property
    def profile_id(self) -> UUID:
        """The one profile every door answers for."""
        return self.list_entries.profile_id


__all__ = [
    "LedgerAddDoorV1",
    "LedgerCheckDoorV1",
    "LedgerEntriesDoorsV1",
    "LedgerExportDoorV1",
    "LedgerHistoryDoorV1",
    "LedgerHistoryTypedDoorV1",
    "LedgerLifecycleDoorV1",
    "LedgerListDoorV1",
    "LedgerMergeDoorV1",
    "LedgerPreflightDoorV1",
    "LedgerRemoveDoorV1",
    "LedgerResetDoorV1",
    "LedgerStatusDoorV1",
    "LedgerTrackDoorV1",
]
