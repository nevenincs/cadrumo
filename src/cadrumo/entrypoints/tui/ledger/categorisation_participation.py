"""Which finalised declarations the selected entry took part in, and rebuilding that index.

The participation read lists every finalised declaration revision that used
the entry. The index behind it is derived from the finalised declarations, so
rebuilding replaces it as a whole; the rebuild is staged and confirmed first.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast, override

from textual.widget import Widget
from textual.widgets import DataTable, Static

from ....application.ledger.participation_operation import LedgerParticipationRequest
from ....application.ledger.participation_rebuild_operation import LedgerParticipationRebuildRequest
from ....application.ledger.tracking_projection import LedgerParticipationProjection
from ....core.i18n.render import tr
from ..components.widgets import ContentDataTable
from .categorisation_common import CategorisationScreen, StagedChangeV1, action, action_row, heading, line
from .categorisation_doors import LedgerParticipationDoorV1, LedgerParticipationRebuildDoorV1
from .controller import LedgerWorkspaceController


class LedgerParticipationScreen(CategorisationScreen):
    """List the declarations the selected entry took part in, and rebuild their index."""

    ENTRY_SCOPED = True

    @override
    def banner(self) -> Static:
        return line("tui.ledger.categorisation.participation.title", classes="cadrumo-banner")

    @override
    def prompt(self) -> Static:
        return line("tui.ledger.categorisation.participation.prompt")

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        *,
        read_door: LedgerParticipationDoorV1,
        rebuild_door: LedgerParticipationRebuildDoorV1,
    ) -> None:
        """Keep the participation read and rebuild doors."""
        super().__init__(controller, id="ledger-categorisation-participation-screen")
        self.read_door = read_door
        self.rebuild_door = rebuild_door
        self.participations: tuple[LedgerParticipationProjection, ...] = ()

    @override
    def compose_body(self) -> Iterator[Widget]:
        yield heading("tui.ledger.categorisation.participation.heading")
        yield ContentDataTable[str](id="categorisation-participations", cursor_type="row", zebra_stripes=True)
        yield heading("tui.ledger.categorisation.participation.rebuild_heading")
        yield action_row(
            action("tui.ledger.categorisation.participation.review_rebuild", id="categorisation-participation-rebuild")
        )

    @override
    def staged_controls(self) -> tuple[str, ...]:
        return ("#categorisation-participation-rebuild",)

    @override
    def mount_body(self) -> None:
        self.run_read(self._read)

    @override
    def paint_tables(self) -> None:
        table = cast("DataTable[str]", self.query_one("#categorisation-participations", DataTable))
        if not table.columns:
            table.add_columns(
                tr("tui.ledger.categorisation.participation.column.modelo"),
                tr("tui.ledger.categorisation.participation.column.period"),
                tr("tui.ledger.categorisation.participation.column.state"),
                tr("tui.ledger.categorisation.participation.column.receipt"),
            )
        table.clear()
        for item in self.participations:
            table.add_row(
                item.modelo,
                f"{item.period.filing_year} {item.period.code}",
                item.revision_state,
                item.justificante_reference or "-",
                key=item.calculation_revision_id,
            )

    async def _read(self) -> None:
        result = await self.read_door(
            LedgerParticipationRequest(profile_id=self.read_door.profile_id, transaction_prefix=self.target)
        )
        self.participations = result.participations
        self.paint_tables()
        if not self.participations:
            self.show_outcome(lambda: tr("tui.ledger.categorisation.participation.empty"))

    @override
    def on_tool_button(self, button_id: str) -> None:
        if button_id == "categorisation-participation-rebuild":
            self.stage_from(self._stage_rebuild)

    def _stage_rebuild(self) -> StagedChangeV1:
        request = LedgerParticipationRebuildRequest(profile_id=self.rebuild_door.profile_id)

        async def write() -> bool:
            result = await self.rebuild_door(request)
            self.show_outcome(
                lambda: tr(
                    "tui.ledger.categorisation.participation.rebuilt",
                    transactions=result.transaction_count,
                    participations=result.participation_count,
                    revisions=result.revision_count,
                    removed=result.stale_removed_count,
                )
            )
            await self._read_after_rebuild()
            return True

        return StagedChangeV1(
            summary=lambda: tr("tui.ledger.categorisation.participation.stage_rebuild"),
            write=write,
            destructive=True,
        )

    async def _read_after_rebuild(self) -> None:
        result = await self.read_door(
            LedgerParticipationRequest(profile_id=self.read_door.profile_id, transaction_prefix=self.target)
        )
        self.participations = result.participations
        self.paint_tables()

    @override
    def clear_private_view(self) -> None:
        super().clear_private_view()
        self.participations = ()
        self.paint_tables()


__all__ = ["LedgerParticipationScreen"]
