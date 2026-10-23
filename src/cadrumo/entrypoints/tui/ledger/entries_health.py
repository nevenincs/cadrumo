"""Ledger status and checks: ``ledger.status``, ``ledger.check`` and ``ledger.preflight`` for a chosen period.

Every finding is read-only and stated in words. Readiness says ready, not
ready, or not measured; it is never a colour alone, and a period without a
measurement is not reported as ready.
"""

from __future__ import annotations

from typing import ClassVar, Final, override

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, DataTable, Input, Select, Static

from ....application.ledger.check_operation import LedgerCheckProjection, LedgerCheckRequest
from ....application.ledger.preflight_operation import LedgerPreflightProjection, LedgerPreflightRequest
from ....application.ledger.status_operation import LedgerStatusProjection, LedgerStatusRequest
from ....application.operations.public_period import PublicPeriod
from ....core.errors.hierarchy import CadrumoError
from ....core.i18n.render import tr
from ....core.invoice_link import LinkInconsistencyDirection
from ..account import AccountSessionExpiredError
from ..components.language import localized
from ..components.theme import tokenised
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from .entries_common import joined, period_label, period_options, read_period, selected_value, short_id
from .entries_doors import LedgerEntriesDoorsV1
from .workspace_presentation import door_refusal_text, ledger_workspace_page

_LINK_DIRECTION_LOCALE_KEYS: Final[dict[LinkInconsistencyDirection, str]] = {
    LinkInconsistencyDirection.INVOICE_ONLY: "tui.ledger.entry_tools.health.link.invoice_only",
    LinkInconsistencyDirection.TRANSACTION_ONLY: "tui.ledger.entry_tools.health.link.transaction_only",
}


def _readiness(ready: bool | None, *, findings: int, checked: int) -> str:
    if ready is None:
        return tr("tui.ledger.entry_tools.health.not_measured")
    if ready:
        return tr("tui.ledger.entry_tools.health.ready", checked=checked)
    return tr("tui.ledger.entry_tools.health.not_ready", findings=findings, checked=checked)


def status_lines(status: LedgerStatusProjection) -> tuple[str, ...]:
    """State the ledger's counts, money totals, readiness and stale filings."""
    lines = [
        tr("tui.ledger.entry_tools.health.status_heading", period=period_label(status.period)),
        tr(
            "tui.ledger.entry_tools.health.totals",
            income=status.business_income_total,
            expense=status.business_expense_total,
            net=status.business_net_total,
        ),
        tr(
            "tui.ledger.entry_tools.health.counts",
            total=status.total_count,
            active=status.active_count,
            archived=status.archived_count,
            stashed=status.stashed_count,
            split=status.split_count,
        ),
        tr(
            "tui.ledger.entry_tools.health.review_counts",
            pending=status.pending_review_count,
            reviewed=status.reviewed_count,
            skipped=status.skipped_count,
        ),
        _readiness(status.ready, findings=status.readiness_issue_count, checked=status.checked_transaction_count),
    ]
    if status.unconverted_currency_count:
        lines.append(tr("tui.ledger.entry_tools.health.unconverted", count=status.unconverted_currency_count))
    lines.extend(f"{short_id(issue.transaction_id)}: {issue.detail}" for issue in status.readiness_issues)
    lines.extend(
        tr(
            "tui.ledger.entry_tools.health.stale_filing",
            modelo=filing.modelo,
            year=filing.filing_year,
            period=filing.period,
            changed=filing.changed_count,
            removed=filing.removed_count,
        )
        for filing in status.stale_filings
    )
    return tuple(lines)


def check_lines(check: LedgerCheckProjection) -> tuple[str, ...]:
    """State the preflight sweep and the one-sided invoice links the check found."""
    lines = [
        tr("tui.ledger.entry_tools.health.check_heading", period=period_label(check.period)),
        _readiness(
            check.ready,
            findings=len(check.issues) + len(check.link_inconsistencies),
            checked=check.checked_transaction_count,
        ),
    ]
    lines.extend(f"{short_id(issue.transaction_id)}: {issue.detail}" for issue in check.issues)
    lines.extend(
        tr(
            _LINK_DIRECTION_LOCALE_KEYS[item.direction],
            invoice=short_id(item.invoice_id),
            entry=short_id(item.transaction_id),
        )
        for item in check.link_inconsistencies
    )
    return tuple(lines)


def preflight_lines(preflight: LedgerPreflightProjection) -> tuple[str, ...]:
    """State the facts missing before a declaration for the chosen period can be calculated."""
    return (
        tr("tui.ledger.entry_tools.health.preflight_heading", period=period_label(preflight.period)),
        _readiness(preflight.ready, findings=len(preflight.issues), checked=preflight.checked_transaction_count),
        *(f"{short_id(issue.transaction_id)}: {issue.detail}" for issue in preflight.issues),
    )


class LedgerHealthScreen(LedgerWorkspaceScreen):
    """Read the ledger's status, check and preflight for one period, or for all of it."""

    CSS: ClassVar[str] = LedgerWorkspaceScreen.CSS + tokenised(
        """
        .entries-health-row { height: auto; width: 100%; }
        .entries-health-row > * { width: 1fr; min-width: 0; }
        .entries-health-findings { height: auto; margin-bottom: $cadrumo-stack; }
        """
    )

    def __init__(self, controller: LedgerWorkspaceController, doors: LedgerEntriesDoorsV1) -> None:
        """Keep the injected doors; nothing has been read yet."""
        super().__init__(controller, id="ledger-health-screen")
        self.doors = doors
        self.status: LedgerStatusProjection | None = None
        self.check: LedgerCheckProjection | None = None
        self.preflight: LedgerPreflightProjection | None = None
        self.busy = False

    @property
    @override
    def in_flight(self) -> bool:
        """A health read is out through a door."""
        return self.busy

    @override
    def compose(self) -> ComposeResult:
        yield localized(
            Static(tr("tui.ledger.entry_tools.health.title"), classes="cadrumo-banner"),
            "tui.ledger.entry_tools.health.title",
        )
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(tr("tui.ledger.entry_tools.health.prompt"), markup=False),
                "tui.ledger.entry_tools.health.prompt",
            )
            with Horizontal(classes="entries-health-row"):
                yield localized(
                    Input(placeholder=tr("tui.ledger.entry_tools.field.year"), max_length=4, id="entries-health-year"),
                    "tui.ledger.entry_tools.field.year",
                )
                yield Select[str](
                    period_options(), prompt=tr("tui.ledger.entry_tools.period.any"), id="entries-health-period"
                )
                yield localized(
                    Button(tr("tui.ledger.entry_tools.health.read"), id="entries-health-read", variant="primary"),
                    "tui.ledger.entry_tools.health.read",
                )
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield Static("", id="entries-health-status", classes="entries-health-findings", markup=False)
            yield Static("", id="entries-health-check", classes="entries-health-findings", markup=False)
            yield Static("", id="entries-health-preflight", classes="entries-health-findings", markup=False)

    def on_mount(self) -> None:
        """Show navigation; findings are read when the operator asks."""
        self.populate_navigation()

    @override
    async def refresh_language(self) -> None:
        """Reword the findings already read."""
        await super().refresh_language()
        self._paint()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Route the area navigation."""
        self.handle_navigation_selection(event)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Read the findings for the chosen period off the loop."""
        if event.button.id != "entries-health-read":
            return
        if self.busy:
            self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.flow.in_flight_refusal"))
            return
        refusal = self.query_one("#ledger-refusal", Static)
        try:
            period = read_period(
                self.query_one("#entries-health-year", Input).value,
                selected_value(self.query_one("#entries-health-period", Select)),
            )
        except ValueError as error:
            refusal.update(str(error))
            return
        refusal.update("")
        self.busy = True
        event.button.disabled = True
        self.query_one("#ledger-flow-status", Static).update(tr("tui.ledger.records.loading"))
        self.run_worker(self._read(period), exclusive=True)

    async def _read(self, period: PublicPeriod | None) -> None:
        profile_id = self.doors.profile_id
        try:
            status = await self.doors.status(LedgerStatusRequest(profile_id=profile_id, period=period))
            check = await self.doors.check(LedgerCheckRequest(profile_id=profile_id, period=period))
            preflight: LedgerPreflightProjection | None = None
            if period is not None:
                preflight_request = LedgerPreflightRequest(profile_id=profile_id, period=period)
                preflight = await self.doors.preflight(preflight_request)
        except AccountSessionExpiredError as error:
            self.status = self.check = self.preflight = None
            self._settle(error)
            return
        except CadrumoError as error:
            self._settle(error)
            return
        self.status, self.check, self.preflight = status, check, preflight
        self._settle()

    def _settle(self, error: CadrumoError | None = None) -> None:
        self.busy = False
        self.query_one("#entries-health-read", Button).disabled = False
        self.query_one("#ledger-flow-status", Static).update("")
        if error is not None:
            self.query_one("#ledger-refusal", Static).update(door_refusal_text(error))
        self._paint()

    def _paint(self) -> None:
        self.query_one("#entries-health-status", Static).update(
            "" if self.status is None else joined(status_lines(self.status))
        )
        self.query_one("#entries-health-check", Static).update(
            "" if self.check is None else joined(check_lines(self.check))
        )
        preflight = self.query_one("#entries-health-preflight", Static)
        if self.preflight is not None:
            preflight.update(joined(preflight_lines(self.preflight)))
        elif self.status is not None:
            preflight.update(tr("tui.ledger.entry_tools.health.preflight_needs_period"))
        else:
            preflight.update("")


__all__ = ["LedgerHealthScreen", "check_lines", "preflight_lines", "status_lines"]
