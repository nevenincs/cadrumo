"""Classifier diagnostics: model usage, cost and confidence over an optional date range.

A read-only report. Usage counts each provider's calls, cache hits and tokens;
confidence counts the classifications each provider proposed and how many fell
below the chosen threshold. An unpriced call is counted, never priced at zero.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import cast, override

from textual.widget import Widget
from textual.widgets import DataTable, Input, Static

from ....application.ledger.llm_diagnostics import DEFAULT_LOW_CONFIDENCE_THRESHOLD
from ....application.ledger.llm_diagnostics_operation import (
    LedgerLlmDiagnosticsProjection,
    LedgerLlmDiagnosticsRequest,
)
from ....application.operations.public_scalar import PublicDecimal
from ....core.i18n.render import tr
from ....core.parsing.dates import require_iso8601_date_unless_blank
from ..components.widgets import ContentDataTable
from .categorisation_common import CategorisationScreen, action, action_row, field, heading
from .categorisation_doors import LedgerLlmDiagnosticsDoorV1
from .controller import LedgerWorkspaceController


def _decimal(value: PublicDecimal | None) -> str:
    return "-" if value is None else value.decimal


def totals_text(report: LedgerLlmDiagnosticsProjection) -> str:
    """Summarise the whole report in one line per measure."""
    snapshot = report.report
    return "\n".join(
        (
            tr(
                "tui.ledger.categorisation.diagnostics.usage_totals",
                calls=snapshot.total_calls,
                cache_hits=snapshot.total_cache_hits,
                input_tokens=snapshot.total_input_tokens,
                output_tokens=snapshot.total_output_tokens,
                cost=_decimal(snapshot.total_cost_estimate_usd),
                unpriced=snapshot.total_unpriced_calls,
            ),
            tr(
                "tui.ledger.categorisation.diagnostics.confidence_totals",
                classified=snapshot.total_classified,
                low=snapshot.total_low_confidence,
                threshold=snapshot.low_confidence_threshold.decimal,
            ),
        )
    )


class LedgerDiagnosticsScreen(CategorisationScreen):
    """Read the classifier's usage, cost and confidence report."""

    TITLE_KEY = "tui.ledger.categorisation.diagnostics.title"
    PROMPT_KEY = "tui.ledger.categorisation.diagnostics.prompt"

    def __init__(self, controller: LedgerWorkspaceController, *, door: LedgerLlmDiagnosticsDoorV1) -> None:
        """Keep the profile-bound diagnostics door."""
        super().__init__(controller, id="ledger-categorisation-diagnostics-screen")
        self.door = door
        self.report: LedgerLlmDiagnosticsProjection | None = None

    @override
    def compose_body(self) -> Iterator[Widget]:
        yield field("tui.ledger.categorisation.diagnostics.since", id="categorisation-diagnostics-since", max_length=10)
        yield field("tui.ledger.categorisation.diagnostics.until", id="categorisation-diagnostics-until", max_length=10)
        yield field(
            "tui.ledger.categorisation.diagnostics.threshold", id="categorisation-diagnostics-threshold", max_length=8
        )
        yield action_row(action("tui.ledger.categorisation.diagnostics.read", id="categorisation-diagnostics-read"))
        yield Static("", id="categorisation-diagnostics-totals", markup=False)
        yield heading("tui.ledger.categorisation.diagnostics.usage_heading")
        yield ContentDataTable[str](id="categorisation-diagnostics-usage", cursor_type="row", zebra_stripes=True)
        yield heading("tui.ledger.categorisation.diagnostics.confidence_heading")
        yield ContentDataTable[str](id="categorisation-diagnostics-confidence", cursor_type="row", zebra_stripes=True)

    @override
    def mount_body(self) -> None:
        self.query_one("#categorisation-diagnostics-threshold", Input).value = str(DEFAULT_LOW_CONFIDENCE_THRESHOLD)
        self.run_read(self._read_typed)

    @override
    def paint_tables(self) -> None:
        usage = cast("DataTable[str]", self.query_one("#categorisation-diagnostics-usage", DataTable))
        if not usage.columns:
            usage.add_columns(
                tr("tui.ledger.categorisation.diagnostics.column.provider"),
                tr("tui.ledger.categorisation.diagnostics.column.calls"),
                tr("tui.ledger.categorisation.diagnostics.column.cache_hits"),
                tr("tui.ledger.categorisation.diagnostics.column.tokens"),
                tr("tui.ledger.categorisation.diagnostics.column.cost"),
                tr("tui.ledger.categorisation.diagnostics.column.unpriced"),
            )
        confidence = cast("DataTable[str]", self.query_one("#categorisation-diagnostics-confidence", DataTable))
        if not confidence.columns:
            confidence.add_columns(
                tr("tui.ledger.categorisation.diagnostics.column.provider"),
                tr("tui.ledger.categorisation.diagnostics.column.classified"),
                tr("tui.ledger.categorisation.diagnostics.column.low"),
                tr("tui.ledger.categorisation.diagnostics.column.medium"),
                tr("tui.ledger.categorisation.diagnostics.column.high"),
                tr("tui.ledger.categorisation.diagnostics.column.mean"),
            )
        usage.clear()
        confidence.clear()
        totals = self.query_one("#categorisation-diagnostics-totals", Static)
        report = self.report
        if report is None:
            totals.update("")
            return
        totals.update(totals_text(report))
        for row in report.report.usage_providers:
            usage.add_row(
                row.provider,
                str(row.calls),
                str(row.cache_hits),
                f"{row.input_tokens} / {row.output_tokens}",
                _decimal(row.cost_estimate_usd),
                str(row.unpriced_calls),
                key=row.provider,
            )
        for row in report.report.confidence_providers:
            confidence.add_row(
                row.provider,
                str(row.classified_count),
                str(row.low_confidence_count),
                str(row.medium_confidence_count),
                str(row.high_confidence_count),
                _decimal(row.mean_confidence),
                key=row.provider,
            )

    def _request(self) -> LedgerLlmDiagnosticsRequest:
        since: date | None = require_iso8601_date_unless_blank(
            self.query_one("#categorisation-diagnostics-since", Input).value
        )
        until: date | None = require_iso8601_date_unless_blank(
            self.query_one("#categorisation-diagnostics-until", Input).value
        )
        threshold = self.query_one("#categorisation-diagnostics-threshold", Input).value.strip()
        return LedgerLlmDiagnosticsRequest(
            profile_id=self.door.profile_id,
            since=since,
            until=until,
            low_confidence_threshold=PublicDecimal(decimal=threshold or str(DEFAULT_LOW_CONFIDENCE_THRESHOLD)),
        )

    async def _read_typed(self) -> None:
        await self._read(self._request())

    async def _read(self, request: LedgerLlmDiagnosticsRequest) -> None:
        self.report = await self.door(request)
        self.paint_tables()
        snapshot = self.report.report
        if not snapshot.usage_providers and not snapshot.confidence_providers:
            self.show_outcome(lambda: tr("tui.ledger.categorisation.diagnostics.empty"))
        else:
            self.show_outcome(None)

    @override
    def on_tool_button(self, button_id: str) -> None:
        if button_id != "categorisation-diagnostics-read":
            return
        try:
            request = self._request()
        except ValueError as error:
            self.refuse_error(error)
            return
        self.run_read(lambda: self._read(request))

    @override
    def clear_private_view(self) -> None:
        super().clear_private_view()
        self.report = None
        self.paint_tables()


__all__ = ["LedgerDiagnosticsScreen", "totals_text"]
