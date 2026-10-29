"""Compose the paged entry browser's controls."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Final

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, Input, Select, Static

from ....application.ledger.list_operation import LedgerListProjection
from ....application.ledger.transaction_projection import LedgerTransactionReviewProjection
from ....application.review.filter import LedgerReviewStatus
from ....application.transactions.diagnostics import LedgerImportDiagnosticKind
from ....core.i18n.render import tr
from ....core.ledger_sort import LedgerSortField, LedgerSortOrder
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ..components.language import localized
from ..components.widgets import ContentDataTable
from .controller import review_status_label
from .entries_common import (
    CLASSIFICATION_LOCALE_KEYS,
    DIRECTION_LOCALE_KEYS,
    classification_label,
    direction_label,
    lifecycle_label,
    period_options,
)
from .workspace_presentation import ledger_workspace_page

_ISSUE_LOCALE_KEYS: Final[dict[LedgerImportDiagnosticKind, str]] = {
    LedgerImportDiagnosticKind.ORIGINAL_FILE: "tui.ledger.entry_tools.issue.original_file",
    LedgerImportDiagnosticKind.GAP: "tui.ledger.entry_tools.issue.gap",
    LedgerImportDiagnosticKind.DUPLICATE: "tui.ledger.entry_tools.issue.duplicate",
    LedgerImportDiagnosticKind.PARSER: "tui.ledger.entry_tools.issue.parser",
}
_SORT_LOCALE_KEYS: Final[dict[LedgerSortField, str]] = {
    LedgerSortField.DATE: "tui.ledger.entry_tools.sort.date",
    LedgerSortField.VALUE_DATE: "tui.ledger.entry_tools.sort.value_date",
    LedgerSortField.AMOUNT: "tui.ledger.entry_tools.sort.amount",
    LedgerSortField.DESCRIPTION: "tui.ledger.entry_tools.sort.description",
    LedgerSortField.CREATED_AT: "tui.ledger.entry_tools.sort.created_at",
    LedgerSortField.MODIFIED_AT: "tui.ledger.entry_tools.sort.modified_at",
    LedgerSortField.CLASSIFIED_AT: "tui.ledger.entry_tools.sort.classified_at",
    LedgerSortField.LIFECYCLE_STATE: "tui.ledger.entry_tools.sort.lifecycle_state",
    LedgerSortField.CLASSIFICATION: "tui.ledger.entry_tools.sort.classification",
}
_ORDER_LOCALE_KEYS: Final[dict[LedgerSortOrder, str]] = {
    LedgerSortOrder.ASC: "tui.ledger.entry_tools.order.asc",
    LedgerSortOrder.DESC: "tui.ledger.entry_tools.order.desc",
}


def options[TokenT: str](keys: Mapping[TokenT, str]) -> list[tuple[str, str]]:
    """Translate option labels in declaration order."""
    return [(tr(key), str(token)) for token, key in keys.items()]


def status_options() -> list[tuple[str, str]]:
    """Return translated browser choices."""
    return [(review_status_label(status.value), status.value) for status in LedgerReviewStatus]


def direction_options() -> list[tuple[str, str]]:
    """Return translated browser choices."""
    return [(tr(DIRECTION_LOCALE_KEYS[member]), member.value.lower()) for member in TransactionDirection]


def classification_options() -> list[tuple[str, str]]:
    """Return translated browser choices."""
    return [(tr(CLASSIFICATION_LOCALE_KEYS[member]), member.value) for member in BusinessClassification]


def issue_options() -> list[tuple[str, str]]:
    """Return translated browser choices."""
    return [(tr(key), member.value) for member, key in _ISSUE_LOCALE_KEYS.items()]


#: Table columns in priority order; narrow terminals drop from the end rather than overflow.
_COLUMNS: Final[tuple[tuple[str, str, int], ...]] = (
    ("date", "tui.ledger.column.date", 10),
    ("description", "tui.ledger.column.description", 16),
    ("amount", "tui.ledger.column.amount", 12),
    ("review_status", "tui.ledger.column.review_status", 9),
    ("lifecycle", "tui.ledger.entry_tools.column.lifecycle", 9),
    ("marked", "tui.ledger.entry_tools.column.marked", 7),
    ("classification", "tui.ledger.column.classification", 12),
    ("direction", "tui.ledger.column.direction", 10),
)


def visible_columns(width: int) -> tuple[tuple[str, str, int], ...]:
    """Take columns in priority order while their headers and floors still fit the terminal."""
    taken: list[tuple[str, str, int]] = []
    used = 0
    for column in _COLUMNS:
        cost = max(column[2], len(tr(column[1]))) + 2
        if used + cost > width - 1:
            break
        taken.append(column)
        used += cost
    return tuple(taken)


def row_cells(row: LedgerTransactionReviewProjection, marked: Mapping[str, str]) -> dict[str, str]:
    """Render each visible entry fact under its column key."""
    transaction = row.transaction
    return {
        "date": transaction.date,
        "description": transaction.description,
        "amount": f"{transaction.amount} {transaction.currency}",
        "review_status": review_status_label(row.review_status.value),
        "lifecycle": lifecycle_label(transaction.lifecycle_state),
        "marked": tr("tui.ledger.entry_tools.browse.marked") if transaction.transaction_id in marked else "",
        "classification": classification_label(transaction.business_classification),
        "direction": direction_label(transaction.direction),
    }


def compose_browse(
    *,
    mark_label: Callable[[], str],
    merge_label: Callable[[], str],
) -> ComposeResult:
    """Build the browser controls in their established order."""
    yield localized(
        Static(tr("tui.ledger.entry_tools.browse.title"), classes="cadrumo-banner"),
        "tui.ledger.entry_tools.browse.title",
    )
    with ledger_workspace_page() as navigation:
        yield navigation
        yield localized(
            Static(tr("tui.ledger.entry_tools.browse.prompt"), markup=False),
            "tui.ledger.entry_tools.browse.prompt",
        )
        with Horizontal(classes="entries-browse-row"):
            yield Select[str](
                status_options(), prompt=tr("tui.ledger.entry_tools.browse.any_status"), id="entries-browse-status"
            )
            yield Select[str](
                direction_options(),
                prompt=tr("tui.ledger.entry_tools.browse.any_direction"),
                id="entries-browse-direction",
            )
            yield Select[str](
                classification_options(),
                prompt=tr("tui.ledger.entry_tools.browse.any_classification"),
                id="entries-browse-classification",
            )
        with Horizontal(classes="entries-browse-row"):
            yield Select[str](
                issue_options(), prompt=tr("tui.ledger.entry_tools.browse.any_issue"), id="entries-browse-issue"
            )
            yield localized(
                Input(placeholder=tr("tui.ledger.entry_tools.field.year"), max_length=4, id="entries-browse-year"),
                "tui.ledger.entry_tools.field.year",
            )
            yield Select[str](
                period_options(), prompt=tr("tui.ledger.entry_tools.period.any"), id="entries-browse-period"
            )
        with Horizontal(classes="entries-browse-row"):
            yield localized(
                Input(placeholder=tr("tui.ledger.entry_tools.browse.text"), id="entries-browse-text"),
                "tui.ledger.entry_tools.browse.text",
            )
            yield localized(
                Input(placeholder=tr("tui.ledger.entry_tools.browse.import"), id="entries-browse-import"),
                "tui.ledger.entry_tools.browse.import",
            )
            yield localized(
                Input(placeholder=tr("tui.ledger.entry_tools.browse.account"), id="entries-browse-account"),
                "tui.ledger.entry_tools.browse.account",
            )
        with Horizontal(classes="entries-browse-row"):
            yield localized(
                Input(placeholder=tr("tui.ledger.entry_tools.browse.group"), id="entries-browse-group"),
                "tui.ledger.entry_tools.browse.group",
            )
            yield Select[str](
                options(_SORT_LOCALE_KEYS),
                prompt=tr("tui.ledger.entry_tools.browse.ledger_order"),
                id="entries-browse-sort",
            )
            yield Select[str](
                options(_ORDER_LOCALE_KEYS),
                value=LedgerSortOrder.ASC.value,
                allow_blank=False,
                id="entries-browse-order",
            )
        with Horizontal(classes="entries-browse-row"):
            yield Checkbox(tr("tui.ledger.entry_tools.browse.by_group"), id="entries-browse-by-group")
            yield Checkbox(tr("tui.ledger.entry_tools.browse.hide_rejected"), id="entries-browse-hide-rejected")
            yield localized(
                Button(tr("tui.ledger.entry_tools.browse.apply"), id="entries-browse-apply", variant="primary"),
                "tui.ledger.entry_tools.browse.apply",
            )
        yield Static("", id="entries-browse-window", markup=False)
        yield ContentDataTable[str](id="entries-browse", cursor_type="row", zebra_stripes=True)
        with Horizontal(classes="entries-browse-row"):
            yield localized(
                Button(tr("tui.ledger.entry_tools.browse.previous"), id="entries-browse-previous", disabled=True),
                "tui.ledger.entry_tools.browse.previous",
            )
            yield localized(
                Button(tr("tui.ledger.entry_tools.browse.next"), id="entries-browse-next", disabled=True),
                "tui.ledger.entry_tools.browse.next",
            )
        yield Static("", id="entries-browse-selected", markup=False)
        yield localized(
            Input(placeholder=tr("tui.ledger.entry_tools.field.reason"), max_length=500, id="entries-browse-reason"),
            "tui.ledger.entry_tools.field.reason",
        )
        with Horizontal(classes="entries-browse-row"):
            yield localized(
                Button(tr("tui.ledger.entry_tools.browse.open"), id="entries-browse-open"),
                "tui.ledger.entry_tools.browse.open",
            )
            yield localized(
                Button(tr("tui.ledger.entry_tools.browse.trace"), id="entries-browse-trace"),
                "tui.ledger.entry_tools.browse.trace",
            )
            yield Button(mark_label(), id="entries-browse-mark")
        with Horizontal(classes="entries-browse-row"):
            yield localized(
                Button(tr("tui.ledger.entry_tools.browse.action.archive"), id="entries-browse-archive"),
                "tui.ledger.entry_tools.browse.action.archive",
            )
            yield localized(
                Button(tr("tui.ledger.entry_tools.browse.action.stash"), id="entries-browse-stash"),
                "tui.ledger.entry_tools.browse.action.stash",
            )
            yield localized(
                Button(tr("tui.ledger.entry_tools.browse.action.restore"), id="entries-browse-restore"),
                "tui.ledger.entry_tools.browse.action.restore",
            )
        with Horizontal(classes="entries-browse-row"):
            yield localized(
                Button(tr("tui.ledger.entry_tools.browse.action.exclude"), id="entries-browse-exclude"),
                "tui.ledger.entry_tools.browse.action.exclude",
            )
            yield localized(
                Button(tr("tui.ledger.entry_tools.browse.action.remove"), id="entries-browse-remove"),
                "tui.ledger.entry_tools.browse.action.remove",
            )
            yield Button(merge_label(), id="entries-browse-merge")
        yield Static("", id="ledger-flow-status", markup=False)
        yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)


def sort_options() -> list[tuple[str, str]]:
    """Return translated sort choices."""
    return options(_SORT_LOCALE_KEYS)


def order_options() -> list[tuple[str, str]]:
    """Return translated ordering choices."""
    return options(_ORDER_LOCALE_KEYS)


def show_browse_window(
    window: Static, previous: Button, following: Button, page: LedgerListProjection | None, busy: bool
) -> None:
    """Show the loaded page range and whether adjacent pages can be read."""
    if page is None:
        window.update("")
        previous.disabled = following.disabled = True
        return
    if not page.rows:
        window.update(tr("tui.ledger.entry_tools.browse.window_empty", total=page.total))
    else:
        window.update(
            tr(
                "tui.ledger.entry_tools.browse.window",
                first=page.offset + 1,
                last=page.offset + len(page.rows),
                total=page.total,
            )
        )
    previous.disabled = busy or page.offset == 0
    following.disabled = busy or page.offset + len(page.rows) >= page.total


_ACTION_BUTTONS: Final[tuple[str, ...]] = (
    "entries-browse-open",
    "entries-browse-trace",
    "entries-browse-mark",
    "entries-browse-archive",
    "entries-browse-stash",
    "entries-browse-restore",
    "entries-browse-exclude",
    "entries-browse-remove",
)


def set_browse_controls(
    button: Callable[[str], Button], *, busy: bool, chosen: bool, marked_count: int, page: LedgerListProjection | None
) -> None:
    """Hold navigation and action controls while the selected page is busy."""
    for button_id in _ACTION_BUTTONS:
        button(f"#{button_id}").disabled = busy or not chosen
    button("#entries-browse-merge").disabled = busy or marked_count < 2
    button("#entries-browse-apply").disabled = busy
    button("#entries-browse-previous").disabled = busy or page is None or page.offset == 0
    button("#entries-browse-next").disabled = busy or page is None or page.offset + len(page.rows) >= page.total
