"""Split the selected entry into children that add up to it, or review a suggested split.

A manual split is staged child by child. The children are amounts of the same
direction and currency as the entry, so the screen refuses to review a split
whose children do not add up to the entry's own amount; the operation refuses
it too, but the operator hears it before anything is sent. A suggested split
is a proposal the operation modal shows, and only Apply writes it.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Final, cast, override

from textual.widget import Widget
from textual.widgets import DataTable, Input, Static

from ....application.ledger.actions_common import display_decimal
from ....application.ledger.llm_review_contracts import LedgerLlmReviewRequest
from ....application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from ....application.ledger.split_operation import LedgerSplitChildRequest, LedgerSplitRequest
from ....application.ledger.workspace import LedgerWorkspaceEntryRefV1
from ....core.decimal.grammar import try_parse_canonical_decimal
from ....core.i18n.render import tr
from ..components.widgets import ContentDataTable
from .categorisation_common import StagedChangeV1, action, action_row, classification_label, field, heading, line
from .categorisation_doors import LedgerSplitDoorV1, LedgerSuggestionReviewDoorV1
from .categorisation_review import ReviewingCategorisationScreen
from .controller import LedgerWorkspaceController

SPLIT_MAX_CHILDREN: Final = 128
"""The most children one split may have, as the operation declares."""


def parse_child_amount(raw: str) -> Decimal:
    """Read one child amount as a positive magnitude in canonical decimal form."""
    parsed = try_parse_canonical_decimal(raw.strip(), signed=False, max_fraction_digits=2)
    if parsed is None or parsed <= 0:
        raise ValueError(tr("tui.ledger.categorisation.split.amount_invalid"))
    return parsed


class LedgerSplitScreen(ReviewingCategorisationScreen):
    """Split the selected entry by hand, or decide on a suggested split in the modal."""

    ENTRY_SCOPED = True

    @override
    def banner(self) -> Static:
        return line("tui.ledger.categorisation.split.title", classes="cadrumo-banner")

    @override
    def prompt(self) -> Static:
        return line("tui.ledger.categorisation.split.prompt")

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        *,
        split_door: LedgerSplitDoorV1,
        review_door: LedgerSuggestionReviewDoorV1,
    ) -> None:
        """Keep the manual split door and the suggested-split review door."""
        super().__init__(controller, id="ledger-categorisation-split-screen")
        self.split_door = split_door
        self.review_door = review_door
        self.children_staged: list[tuple[Decimal, str]] = []

    def parent_entry(self) -> LedgerWorkspaceEntryRefV1:
        """The selected entry as the workspace shows it."""
        target = self.target
        return next(row for row in self.controller.projection.entries if row.transaction_id == target)

    def parent_amount(self) -> Decimal:
        """The selected entry's own amount, which the children must add up to."""
        parsed = try_parse_canonical_decimal(self.parent_entry().amount, signed=False)
        if parsed is None:
            raise ValueError(tr("tui.ledger.categorisation.split.parent_unreadable"))
        return parsed

    def children_total(self) -> Decimal:
        """The sum of the children staged so far."""
        return sum((amount for amount, _description in self.children_staged), Decimal(0))

    @override
    def compose_body(self) -> Iterator[Widget]:
        yield heading("tui.ledger.categorisation.split.children_heading")
        yield ContentDataTable[str](id="categorisation-split-children", cursor_type="row", zebra_stripes=True)
        yield Static("", id="categorisation-split-total", markup=False)
        yield field("tui.ledger.categorisation.split.amount", id="categorisation-split-amount", max_length=32)
        yield field("tui.ledger.categorisation.split.description", id="categorisation-split-description")
        yield action_row(
            action("tui.ledger.categorisation.split.add_child", id="categorisation-split-add"),
            action("tui.ledger.categorisation.split.remove_child", id="categorisation-split-remove"),
        )
        yield field("tui.ledger.categorisation.split.reason", id="categorisation-split-reason", max_length=500)
        yield action_row(action("tui.ledger.categorisation.split.review", id="categorisation-split-review"))
        yield heading("tui.ledger.categorisation.split.suggestion_heading")
        yield action_row(action("tui.ledger.categorisation.split.ask", id="categorisation-split-ask"))

    @override
    def staged_controls(self) -> tuple[str, ...]:
        return (
            "#categorisation-split-amount",
            "#categorisation-split-description",
            "#categorisation-split-add",
            "#categorisation-split-remove",
            "#categorisation-split-reason",
            "#categorisation-split-review",
            "#categorisation-split-ask",
        )

    @override
    def paint_tables(self) -> None:
        table = cast("DataTable[str]", self.query_one("#categorisation-split-children", DataTable))
        if not table.columns:
            table.add_columns(
                tr("tui.ledger.categorisation.split.column.child"),
                tr("tui.ledger.categorisation.split.column.amount"),
                tr("tui.ledger.categorisation.column.description"),
            )
        table.clear()
        for index, (amount, description) in enumerate(self.children_staged, start=1):
            table.add_row(str(index), display_decimal(amount), description, key=f"child-{index}")
        self._show_total()

    def _show_total(self) -> None:
        if self.controller.classification_target is None:
            # The split entry has left the workspace after the write; there is nothing left to balance.
            self.query_one("#categorisation-split-total", Static).update("")
            return
        parent = self.parent_entry()
        total = self.children_total()
        self.query_one("#categorisation-split-total", Static).update(
            tr(
                "tui.ledger.categorisation.split.total",
                children=display_decimal(total),
                parent=parent.amount,
                currency=parent.currency,
                remaining=display_decimal(self.parent_amount() - total),
            )
        )

    @override
    def on_tool_button(self, button_id: str) -> None:
        if button_id == "categorisation-split-add":
            self._stage_child()
        elif button_id == "categorisation-split-remove":
            if self.children_staged:
                self.children_staged.pop()
            self.paint_tables()
        elif button_id == "categorisation-split-review":
            self.stage_from(self._stage_split)
        elif button_id == "categorisation-split-ask":
            self.ask_for_review(
                self.review_door,
                LedgerLlmReviewRequest(
                    profile_id=self.review_door.profile_id,
                    transaction_id=self.target,
                    mode="split",
                    origin=LlmReviewInvocationOrigin.SPLIT_LLM,
                ),
            )

    def _stage_child(self) -> None:
        amount_input = self.query_one("#categorisation-split-amount", Input)
        description_input = self.query_one("#categorisation-split-description", Input)
        try:
            amount = parse_child_amount(amount_input.value)
        except ValueError as error:
            self.refuse(str(error))
            return
        description = description_input.value.strip()
        if not description:
            self.refuse(tr("tui.ledger.categorisation.split.description_required"))
            return
        if len(self.children_staged) >= SPLIT_MAX_CHILDREN:
            self.refuse(tr("tui.ledger.categorisation.split.too_many", limit=SPLIT_MAX_CHILDREN))
            return
        self.refuse("")
        self.children_staged.append((amount, description))
        amount_input.value = ""
        description_input.value = ""
        self.paint_tables()
        amount_input.focus()

    def _stage_split(self) -> StagedChangeV1:
        if len(self.children_staged) < 2:
            raise ValueError(tr("tui.ledger.categorisation.split.too_few"))
        parent = self.parent_entry()
        total = self.children_total()
        if total != self.parent_amount():
            raise ValueError(
                tr(
                    "tui.ledger.categorisation.split.unbalanced",
                    children=display_decimal(total),
                    parent=parent.amount,
                    currency=parent.currency,
                )
            )
        request = LedgerSplitRequest(
            profile_id=self.split_door.profile_id,
            transaction_id=self.target,
            children=tuple(
                LedgerSplitChildRequest(amount=display_decimal(amount), description=description)
                for amount, description in self.children_staged
            ),
            reason=self.query_one("#categorisation-split-reason", Input).value,
        )

        async def write() -> bool:
            result = await self.split_door(request)
            count = len(result.child_transaction_ids)
            parent_keeps = classification_label(result.parent_business_classification.value)
            self.children_staged = []
            self.paint_tables()
            self.show_outcome(lambda: tr("tui.ledger.categorisation.split.done", count=count, parent=parent_keeps))
            return True

        return StagedChangeV1(
            summary=lambda: tr(
                "tui.ledger.categorisation.split.stage",
                count=len(request.children),
                parent=parent.amount,
                currency=parent.currency,
            ),
            write=write,
            refreshes_workspace=True,
        )

    @override
    def clear_private_view(self) -> None:
        super().clear_private_view()
        self.children_staged = []
        self.paint_tables()


__all__ = ["SPLIT_MAX_CHILDREN", "LedgerSplitScreen", "parse_child_amount"]
