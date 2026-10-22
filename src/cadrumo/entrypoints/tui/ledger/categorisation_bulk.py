"""Classify a filtered page of entries at once, after reviewing exactly the rows that will change.

The entries are read one page at a time through the list operation's own
filters, sort and paging. The operator chooses one classification; the review
lists only the rows on the page whose classification differs from it, and
only those rows go into the classification table the bulk operation receives.
A batch is not atomic: the result reports the rows applied, skipped and
refused, each refusal with its own reason.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from typing import Final, cast, override

from textual.widget import Widget
from textual.widgets import DataTable, Input, Select, Static

from ....application.ledger.bulk_classify_operation import LedgerBulkClassifyProjection, LedgerBulkClassifyRequest
from ....application.ledger.list_operation import LedgerListRequest
from ....application.ledger.transaction_projection import LedgerTransactionReviewProjection
from ....application.review.filter import LedgerReviewStatus
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language, tr
from ....core.ledger_sort import LedgerSortField, LedgerSortOrder
from ....domain.transactions.enums import BusinessClassification
from ..components.widgets import ContentDataTable
from .categorisation_common import (
    CategorisationScreen,
    StagedChangeV1,
    action,
    action_row,
    blank_to_none,
    classification_label,
    field,
    heading,
    page_label,
    short_id,
)
from .categorisation_doors import LedgerBulkClassifyDoorV1, LedgerSelectionDoorV1
from .controller import LedgerWorkspaceController

BULK_PAGE_SIZE: Final = 200
"""The most entries the screen reads and renders at once."""

BULK_CLASSIFICATIONS: Final[tuple[BusinessClassification, ...]] = (
    BusinessClassification.BUSINESS,
    BusinessClassification.PERSONAL,
    BusinessClassification.MIXED,
    BusinessClassification.REVIEWED_EXCLUDED,
)
"""The decisions a bulk classification can record."""

_ANY_STATUS: Final = "any"


def bulk_csv(
    rows: tuple[LedgerTransactionReviewProjection, ...],
    classification: BusinessClassification,
    *,
    business_pct: str | None,
    category_id: str | None,
) -> str:
    """The classification table for the reviewed rows, in the columns the bulk operation reads."""
    columns = ["transaction_id", "classification"]
    if business_pct is not None:
        columns.append("business_pct")
    if category_id is not None:
        columns.append("category_id")
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        values = [row.transaction.transaction_id, classification.value]
        if business_pct is not None:
            values.append(business_pct)
        if category_id is not None:
            values.append(category_id)
        writer.writerow(values)
    return buffer.getvalue()


def bulk_result_text(projection: LedgerBulkClassifyProjection) -> str:
    """Say what a batch did, row refusals included."""
    if projection.outcome == "validation_error" or projection.result is None:
        return tr("tui.ledger.categorisation.bulk.refused", messages="; ".join(projection.validation_messages))
    result = projection.result
    lines = [
        tr(
            "tui.ledger.categorisation.bulk.done",
            applied=result.applied,
            skipped=result.skipped,
            failed=len(result.failures),
        )
    ]
    lines.extend(
        tr(
            "tui.ledger.categorisation.bulk.failure",
            row=failure.row_index,
            entry=short_id(failure.transaction_id),
            reason=failure.reason,
        )
        for failure in result.failures
    )
    return "\n".join(lines)


class LedgerBulkClassifyScreen(CategorisationScreen):
    """Classify the entries of one filtered page that differ from the chosen classification."""

    TITLE_KEY = "tui.ledger.categorisation.bulk.title"
    PROMPT_KEY = "tui.ledger.categorisation.bulk.prompt"

    def __init__(
        self,
        controller: LedgerWorkspaceController,
        *,
        selection_door: LedgerSelectionDoorV1,
        bulk_door: LedgerBulkClassifyDoorV1,
    ) -> None:
        """Keep the page-reading door and the bulk classification door."""
        super().__init__(controller, id="ledger-categorisation-bulk-screen")
        self.selection_door = selection_door
        self.bulk_door = bulk_door
        self.rows: tuple[LedgerTransactionReviewProjection, ...] = ()
        self.total = 0
        self.page_offset = 0
        self.filters: tuple[str, ...] = ()
        self.changing: tuple[LedgerTransactionReviewProjection, ...] = ()

    @override
    def compose_body(self) -> Iterator[Widget]:
        yield heading("tui.ledger.categorisation.bulk.filter_heading")
        yield Select[str](
            (
                (tr("tui.ledger.categorisation.bulk.status_any"), _ANY_STATUS),
                *((tr(f"tui.ledger.review_status.{status.value}"), status.value) for status in LedgerReviewStatus),
            ),
            value=_ANY_STATUS,
            allow_blank=False,
            id="categorisation-bulk-status",
        )
        yield field("tui.ledger.categorisation.bulk.year", id="categorisation-bulk-year", max_length=4)
        yield field("tui.ledger.categorisation.bulk.period", id="categorisation-bulk-period", max_length=2)
        yield field("tui.ledger.categorisation.bulk.text", id="categorisation-bulk-text")
        yield action_row(action("tui.ledger.categorisation.bulk.read", id="categorisation-bulk-read"))
        yield ContentDataTable[str](id="categorisation-bulk-entries", cursor_type="row", zebra_stripes=True)
        yield Static("", id="categorisation-bulk-page", markup=False)
        yield action_row(
            action("tui.ledger.categorisation.page.previous", id="categorisation-bulk-previous"),
            action("tui.ledger.categorisation.page.next", id="categorisation-bulk-next"),
        )
        yield heading("tui.ledger.categorisation.bulk.target_heading")
        yield Select[str](
            tuple((classification_label(item.value), item.value) for item in BULK_CLASSIFICATIONS),
            value=BusinessClassification.BUSINESS.value,
            allow_blank=False,
            id="categorisation-bulk-classification",
        )
        yield field("tui.ledger.categorisation.bulk.business_pct", id="categorisation-bulk-pct", max_length=32)
        yield field("tui.ledger.categorisation.bulk.category", id="categorisation-bulk-category")
        yield action_row(action("tui.ledger.categorisation.bulk.review", id="categorisation-bulk-review"))
        yield ContentDataTable[str](id="categorisation-bulk-changing", cursor_type="row", zebra_stripes=True)

    @override
    def staged_controls(self) -> tuple[str, ...]:
        return (
            "#categorisation-bulk-status",
            "#categorisation-bulk-year",
            "#categorisation-bulk-period",
            "#categorisation-bulk-text",
            "#categorisation-bulk-read",
            "#categorisation-bulk-previous",
            "#categorisation-bulk-next",
            "#categorisation-bulk-classification",
            "#categorisation-bulk-pct",
            "#categorisation-bulk-category",
            "#categorisation-bulk-review",
        )

    @override
    def mount_body(self) -> None:
        self.query_one("#categorisation-bulk-changing", DataTable).display = False
        self.run_read(self._read_page)

    @override
    def paint_tables(self) -> None:
        entries = cast("DataTable[str]", self.query_one("#categorisation-bulk-entries", DataTable))
        changing = cast("DataTable[str]", self.query_one("#categorisation-bulk-changing", DataTable))
        for table in (entries, changing):
            if not table.columns:
                table.add_columns(
                    tr("tui.ledger.categorisation.column.entry"),
                    tr("tui.ledger.categorisation.bulk.column.date"),
                    tr("tui.ledger.categorisation.bulk.column.amount"),
                    tr("tui.ledger.categorisation.column.description"),
                    tr("tui.ledger.categorisation.column.classification"),
                )
        for table, rows in ((entries, self.rows), (changing, self.changing)):
            table.clear()
            for row in rows:
                transaction = row.transaction
                table.add_row(
                    short_id(transaction.transaction_id),
                    transaction.date,
                    f"{transaction.amount} {transaction.currency}",
                    transaction.description,
                    classification_label(transaction.business_classification),
                    key=transaction.transaction_id,
                )
        self.query_one("#categorisation-bulk-page", Static).update(
            page_label(self.page_offset, len(self.rows), self.total)
        )

    def _typed_filters(self) -> tuple[str, ...]:
        clauses: list[str] = []
        status = str(cast("Select[str]", self.query_one("#categorisation-bulk-status", Select)).value)
        if status != _ANY_STATUS:
            clauses.append(f"status={status}")
        for key, selector in (
            ("year", "#categorisation-bulk-year"),
            ("period", "#categorisation-bulk-period"),
            ("text", "#categorisation-bulk-text"),
        ):
            value = blank_to_none(self.query_one(selector, Input).value)
            if value is not None:
                clauses.append(f"{key}={value}")
        return tuple(clauses)

    def _page_request(self, offset: int) -> LedgerListRequest:
        return LedgerListRequest(
            profile_id=self.selection_door.profile_id,
            filters=self.filters,
            limit=BULK_PAGE_SIZE,
            offset=offset,
            sort_by=LedgerSortField.DATE,
            sort_order=LedgerSortOrder.ASC,
        )

    async def _read_page(self, offset: int = 0) -> None:
        result = await self.selection_door(self._page_request(offset))
        self.rows = result.rows
        self.total = result.total
        self.page_offset = result.offset
        self.changing = ()
        self.query_one("#categorisation-bulk-changing", DataTable).display = False
        self.paint_tables()
        if not self.rows:
            self.show_outcome(lambda: tr("tui.ledger.categorisation.bulk.empty"))
        else:
            self.show_outcome(None)

    @override
    def on_tool_button(self, button_id: str) -> None:
        if button_id == "categorisation-bulk-read":
            try:
                filters = self._typed_filters()
                LedgerListRequest(profile_id=self.selection_door.profile_id, filters=filters)
            except ValueError as error:
                self.refuse_error(error)
                return
            self.filters = filters
            self.run_read(self._read_page)
        elif button_id == "categorisation-bulk-previous":
            self._turn(self.page_offset - BULK_PAGE_SIZE)
        elif button_id == "categorisation-bulk-next":
            self._turn(self.page_offset + BULK_PAGE_SIZE)
        elif button_id == "categorisation-bulk-review":
            self.stage_from(self._stage)

    def _turn(self, offset: int) -> None:
        if offset < 0 or offset >= self.total:
            self.status("tui.ledger.categorisation.page.none")
            return
        self.run_read(lambda: self._read_page(offset))

    def _stage(self) -> StagedChangeV1:
        classification = BusinessClassification(
            str(cast("Select[str]", self.query_one("#categorisation-bulk-classification", Select)).value)
        )
        business_pct = blank_to_none(self.query_one("#categorisation-bulk-pct", Input).value)
        if (classification is BusinessClassification.MIXED) != (business_pct is not None):
            raise ValueError(tr("tui.ledger.categorisation.bulk.share_mixed_only"))
        category_id = blank_to_none(self.query_one("#categorisation-bulk-category", Input).value)
        changing = tuple(row for row in self.rows if row.transaction.business_classification != classification.value)
        if not changing:
            raise ValueError(tr("tui.ledger.categorisation.bulk.nothing_changes"))
        language = output_language()
        request = LedgerBulkClassifyRequest(
            profile_id=self.bulk_door.profile_id,
            csv_text=bulk_csv(changing, classification, business_pct=business_pct, category_id=category_id),
            output_language=OutputLanguage(language) if language in set(OutputLanguage) else OutputLanguage.ES,
        )
        self.changing = changing
        self.paint_tables()
        self.query_one("#categorisation-bulk-changing", DataTable).display = True
        offset = self.page_offset

        async def write() -> bool:
            projection = await self.bulk_door(request)
            self.show_outcome(lambda: bulk_result_text(projection))
            outcome = projection.result
            await self._read_page(offset)
            self.show_outcome(lambda: bulk_result_text(projection))
            return outcome is not None and outcome.applied > 0

        count = len(changing)
        return StagedChangeV1(
            summary=lambda: tr(
                "tui.ledger.categorisation.bulk.stage",
                count=count,
                classification=classification_label(classification.value),
                category=category_id or "-",
            ),
            write=write,
            refreshes_workspace=True,
        )

    @override
    def unstage(self) -> None:
        super().unstage()
        if self.changing:
            self.changing = ()
            self.query_one("#categorisation-bulk-changing", DataTable).display = False
            self.paint_tables()

    @override
    def clear_private_view(self) -> None:
        super().clear_private_view()
        self.rows = ()
        self.total = 0
        self.page_offset = 0
        self.paint_tables()


__all__ = ["BULK_CLASSIFICATIONS", "BULK_PAGE_SIZE", "LedgerBulkClassifyScreen", "bulk_csv", "bulk_result_text"]
