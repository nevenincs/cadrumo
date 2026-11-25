"""Safe labels, coordinates and paired-column sizing for AEAT Sync screens."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Final

from ....application.aeat_sync.workspace import (
    AeatSyncAeatObservationState,
    AeatSyncCensusCategory,
    AeatSyncCensusStatus,
    AeatSyncDiscrepancyKind,
    AeatSyncDocumentCustodyState,
    AeatSyncJustificanteState,
    AeatSyncLocalFilingState,
    AeatSyncNotificationCategory,
    AeatSyncNotificationReadState,
    AeatSyncOverviewArea,
    AeatSyncReconciliationState,
    AeatSyncSourceState,
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceNotificationRowV1,
    AeatSyncWorkspaceSource,
    AeatSyncWorkspaceZone,
)
from ....core.i18n.render import tr
from ..components.cell_text import ellipsize
from .screen_rows import DeclarationRow

if TYPE_CHECKING:
    from collections.abc import Mapping


#: Which catalogue prefix names each rendered enum's members.
#:
#: Keyed by the enum CLASS, not by its name as a string. The string form made a
#: rename silently unmappable: nothing referenced the class, so the name drifted
#: while the key stayed, and the first symptom was ``status_label`` raising at mount
#: and taking the whole workspace down. A class key is a real reference -- a
#: rename updates it, and a deletion fails the import here rather than a render
#: later.
LABEL_PREFIXES: Final[Mapping[type[Enum], str]] = {
    AeatSyncWorkspaceZone: "tui.aeat_sync.zone",
    AeatSyncWorkspaceAvailability: "tui.aeat_sync.availability",
    AeatSyncWorkspaceSource: "tui.aeat_sync.source",
    AeatSyncOverviewArea: "tui.aeat_sync.area",
    AeatSyncSourceState: "tui.aeat_sync.source_state",
    AeatSyncDiscrepancyKind: "tui.aeat_sync.discrepancy",
    AeatSyncCensusCategory: "tui.aeat_sync.census_category",
    AeatSyncCensusStatus: "tui.aeat_sync.census_status",
    AeatSyncLocalFilingState: "tui.aeat_sync.local_filing_state",
    AeatSyncAeatObservationState: "tui.aeat_sync.aeat_observation_state",
    AeatSyncJustificanteState: "tui.aeat_sync.justificante_state",
    AeatSyncNotificationCategory: "tui.aeat_sync.notification_category",
    AeatSyncNotificationReadState: "tui.aeat_sync.notification_read_state",
    AeatSyncDocumentCustodyState: "tui.aeat_sync.document_custody_state",
    AeatSyncReconciliationState: "tui.aeat_sync.reconciliation_state",
}


def status_label(value: Enum | None) -> str:
    """Render a public enum through its authored semantic catalogue key."""
    if value is None:
        return tr("tui.aeat_sync.value.none")
    prefix = LABEL_PREFIXES.get(type(value))
    if prefix is None:
        raise ValueError("unsupported AEAT Sync operator label")
    return tr(f"{prefix}.{value.value}")


def fit_columns(
    width: int,
    standalone: tuple[tuple[str, str, int], ...],
    pair: tuple[tuple[str, str, int], ...] = (),
) -> tuple[tuple[str, str, int], ...]:
    """Take columns in priority order, and a comparison pair whole or not at all.

    Shared by every AEAT Sync screen that compares two sides, because the rule
    is the same wherever a comparison is rendered and three copies of it would
    drift. `standalone` columns are taken while they fit; `pair` is taken only
    if BOTH fit after them.

    Dropping one half of a pair is the failure this exists to prevent: a column
    headed "Local value" beside nothing to compare against reads as a value
    AEAT does not hold, rather than a column the terminal had no room for.
    """
    taken: list[tuple[str, str, int]] = []
    used = 0

    def _sized(column: tuple[str, str, int]) -> tuple[str, str, int, int]:
        header = tr(column[1])
        size = max(column[2], len(header))
        return column[0], header, size, size + 2

    for name, header, size, cost in (_sized(column) for column in standalone):
        if used + cost > width - 1:
            break
        taken.append((name, header, size))
        used += cost

    sized_pair = [_sized(column) for column in pair]
    if sized_pair and used + sum(cost for *_, cost in sized_pair) <= width - 1:
        for name, header, size, _cost in sized_pair:
            taken.append((name, header, size))
    return tuple(taken)


def census_value(value: str | None) -> str:
    """Render one side of a census comparison, naming an unobserved side."""
    if value is None:
        return tr("tui.aeat_sync.value.unobserved")
    return ellipsize(value, 24)


def census_identity(path: str) -> str:
    """Derive a stable key from the safe canonical census path only."""
    return f"census:{' '.join(path.split()).casefold()}"


def natural_identity(row: DeclarationRow, *, prefix: str) -> str:
    """Derive a stable key from a public declaration coordinate."""
    return f"{prefix}:{row.modelo}|{row.filing_year}|{row.period.registry_token}"


def notification_identity(row: AeatSyncWorkspaceNotificationRowV1) -> str:
    """Use the application-projected opaque semantic notification identity."""
    if row.selection_key is None:
        raise ValueError("projected notification row requires a selection key")
    return row.selection_key


def declaration_address(row: DeclarationRow) -> str:
    """Render only the public Modelo/year/period natural coordinate."""
    return tr(
        "tui.aeat_sync.address.declaration",
        modelo=row.modelo,
        filing_year=row.filing_year,
        period=row.period.registry_token,
    )
