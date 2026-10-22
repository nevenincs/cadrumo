"""Allocate the selected entry's business use: share, category, usage ratio and prorrata reference.

The share is a decimal fraction from 0 to 1; the operation derives the
classification it implies. The allocation is staged and written only after
the operator confirms the reviewed values.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import override

from textual.widget import Widget
from textual.widgets import Input

from ....application.ledger.allocate_operation import LedgerAllocateRequest
from ....core.i18n.render import tr
from .categorisation_common import (
    CategorisationScreen,
    StagedChangeV1,
    action,
    action_row,
    blank_to_none,
    classification_label,
    field,
    heading,
)
from .categorisation_doors import LedgerAllocateDoorV1
from .controller import LedgerWorkspaceController


class LedgerAllocateScreen(CategorisationScreen):
    """Allocate the business share of the selected entry."""

    TITLE_KEY = "tui.ledger.categorisation.allocate.title"
    PROMPT_KEY = "tui.ledger.categorisation.allocate.prompt"
    ENTRY_SCOPED = True

    def __init__(self, controller: LedgerWorkspaceController, *, door: LedgerAllocateDoorV1) -> None:
        """Keep the profile-bound allocation door."""
        super().__init__(controller, id="ledger-categorisation-allocate-screen")
        self.door = door

    @override
    def compose_body(self) -> Iterator[Widget]:
        yield heading("tui.ledger.categorisation.allocate.heading")
        yield field("tui.ledger.categorisation.allocate.business_pct", id="categorisation-allocate-pct", max_length=32)
        yield field("tui.ledger.categorisation.allocate.category", id="categorisation-allocate-category")
        yield field("tui.ledger.categorisation.allocate.usage_ratio", id="categorisation-allocate-ratio")
        yield field("tui.ledger.categorisation.allocate.prorrata", id="categorisation-allocate-prorrata")
        yield action_row(action("tui.ledger.categorisation.allocate.review", id="categorisation-allocate-review"))

    @override
    def staged_controls(self) -> tuple[str, ...]:
        return (
            "#categorisation-allocate-pct",
            "#categorisation-allocate-category",
            "#categorisation-allocate-ratio",
            "#categorisation-allocate-prorrata",
            "#categorisation-allocate-review",
        )

    @override
    def on_tool_button(self, button_id: str) -> None:
        if button_id == "categorisation-allocate-review":
            self.stage_from(self._stage)

    def _stage(self) -> StagedChangeV1:
        request = LedgerAllocateRequest(
            profile_id=self.door.profile_id,
            transaction_id=self.target,
            business_pct=self.query_one("#categorisation-allocate-pct", Input).value.strip(),
            category_id=blank_to_none(self.query_one("#categorisation-allocate-category", Input).value),
            usage_ratio_id=blank_to_none(self.query_one("#categorisation-allocate-ratio", Input).value),
            prorrata_reference=blank_to_none(self.query_one("#categorisation-allocate-prorrata", Input).value),
        )

        async def write() -> bool:
            result = await self.door(request)
            transaction = result.transaction
            classification = classification_label(transaction.business_classification)
            share = transaction.business_pct or "-"
            self.show_outcome(
                lambda: tr(
                    "tui.ledger.categorisation.allocate.done",
                    classification=classification,
                    share=share,
                    category=transaction.category_id or "-",
                )
            )
            return True

        return StagedChangeV1(
            summary=lambda: tr(
                "tui.ledger.categorisation.allocate.stage",
                share=request.business_pct,
                category=request.category_id or "-",
                ratio=request.usage_ratio_id or "-",
                prorrata=request.prorrata_reference or "-",
            ),
            write=write,
            refreshes_workspace=True,
        )


__all__ = ["LedgerAllocateScreen"]
