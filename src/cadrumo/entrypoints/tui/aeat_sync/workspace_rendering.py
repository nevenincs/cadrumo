"""Render source availability and settled notification summaries without changing admission."""

from textual.widgets import DataTable

from ....application.aeat_sync.workspace import (
    AeatSyncWorkspaceAvailability,
    AeatSyncWorkspaceZone,
    AeatSyncWorkspaceZoneStateV1,
)
from ....application.live.notifications_read_operation import NotificationsListPublicResultV1
from ....core.i18n.render import tr
from ..components.cell_text import ellipsize
from .controller import AeatSyncWorkspaceController
from .screen_presentation import status_label


def render_navigation(navigation: DataTable[str], controller: AeatSyncWorkspaceController) -> None:
    """Render every zone with its independent source axes."""
    navigation.clear(columns=False)
    for zone in AeatSyncWorkspaceZone:
        state = controller.state_for(zone)
        navigation.add_row(
            status_label(zone),
            status_label(state.availability),
            tr(
                "tui.aeat_sync.sources.joined",
                entries=", ".join(
                    ellipsize(
                        tr(
                            "tui.aeat_sync.sources.entry",
                            source=status_label(source.source),
                            availability=status_label(source.availability),
                        ),
                        42,
                    )
                    for source in state.sources
                ),
            ),
            key=zone.value,
        )


def notifications_list_summary(result: NotificationsListPublicResultV1) -> str:
    """Render only snapshot capture times and public notification-row counts."""
    lines = [f"{tr('tui.aeat_sync.notifications.title')} · {tr('tui.aeat_sync.status.items', count=result.count)}"]
    lines.extend(
        f"{row.captured_at.isoformat()} · {tr('tui.aeat_sync.status.items', count=row.row_count)}"
        for row in result.rows
    )
    return "\n".join(lines)


def closed_zone_copy(state: AeatSyncWorkspaceZoneStateV1) -> str:
    """Name the sources a closed zone is still waiting for.

    The zone carries no reason of its own, but its sources say which of
    them could not be observed, and that is what the operator needs to
    know: which data has to arrive before the area can open.
    """
    missing = [
        tr(
            "tui.aeat_sync.sources.entry",
            source=status_label(source.source),
            availability=status_label(source.availability),
        )
        for source in state.sources
        if source.availability not in {AeatSyncWorkspaceAvailability.AVAILABLE, AeatSyncWorkspaceAvailability.STALE}
    ]
    if not missing:
        return tr("tui.aeat_sync.refusal.source")
    return tr("tui.aeat_sync.refusal.sources_missing", sources=", ".join(missing))
