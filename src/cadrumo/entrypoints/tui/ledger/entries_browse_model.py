"""Entry browse state and removal-preview wording."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from ....application.ledger.lifecycle_contracts import LedgerLifecycleOperationId
from ....application.ledger.list_operation import LedgerListRequest
from ....application.ledger.remove_operation import LedgerRemoveOperationResult
from ....core.i18n.render import tr
from .entries_common import joined

#: The most rows one page holds; the list never reads more than this at once.
BROWSE_PAGE_SIZE: Final = 200


@dataclass(frozen=True, slots=True)
class LedgerBrowseStateV1:
    """Where Browse entries stands: the request it reads, the chosen entry and the marked ones."""

    request: LedgerListRequest | None = None
    selected_id: str | None = None
    marked: tuple[tuple[str, str], ...] = field(default=())
    """Marked entries as ``(transaction id, label)``, in the order they were marked."""


_LIFECYCLE_ACTION_LOCALE_KEYS: Final[dict[LedgerLifecycleOperationId, str]] = {
    "ledger.archive": "tui.ledger.entry_tools.browse.action.archive",
    "ledger.stash": "tui.ledger.entry_tools.browse.action.stash",
    "ledger.restore": "tui.ledger.entry_tools.browse.action.restore",
    "ledger.exclude": "tui.ledger.entry_tools.browse.action.exclude",
}
_LIFECYCLE_CONSEQUENCE_LOCALE_KEYS: Final[dict[LedgerLifecycleOperationId, str]] = {
    "ledger.archive": "tui.ledger.entry_tools.browse.consequence.archive",
    "ledger.stash": "tui.ledger.entry_tools.browse.consequence.stash",
    "ledger.restore": "tui.ledger.entry_tools.browse.consequence.restore",
    "ledger.exclude": "tui.ledger.entry_tools.browse.consequence.exclude",
}
_LIFECYCLE_DONE_LOCALE_KEYS: Final[dict[LedgerLifecycleOperationId, str]] = {
    "ledger.archive": "tui.ledger.entry_tools.browse.done.archive",
    "ledger.stash": "tui.ledger.entry_tools.browse.done.stash",
    "ledger.restore": "tui.ledger.entry_tools.browse.done.restore",
    "ledger.exclude": "tui.ledger.entry_tools.browse.done.exclude",
}


def lifecycle_action(operation: LedgerLifecycleOperationId) -> str:
    """Name one lifecycle action in the current language."""
    return tr(_LIFECYCLE_ACTION_LOCALE_KEYS[operation])


def lifecycle_consequence(operation: LedgerLifecycleOperationId, label: str, reason: str | None) -> str:
    """Describe the exact action and the supplied reason."""
    return joined(
        (
            tr(_LIFECYCLE_CONSEQUENCE_LOCALE_KEYS[operation], entry=label),
            tr("tui.ledger.entry_tools.browse.reason_line", reason=reason) if bool(reason) else "",
        )
    )


def lifecycle_done(operation: LedgerLifecycleOperationId, label: str) -> str:
    """Describe the settled lifecycle action."""
    return tr(_LIFECYCLE_DONE_LOCALE_KEYS[operation], entry=label)


def removal_preview_text(preview: LedgerRemoveOperationResult, label: str) -> str:
    """Say what removing one entry would do, as its dry run reported it."""
    report = preview.report
    return joined(
        (
            tr("tui.ledger.entry_tools.browse.remove_consequence", entry=label),
            tr(
                "tui.ledger.entry_tools.browse.remove_cascade",
                evidence=len(report.cascaded_purchase_invoice_evidence_ids),
                attachments=len(report.cascaded_attachment_ids),
            ),
            tr("tui.ledger.entry_tools.stale_drafts", count=len(report.stale_draft_revision_references))
            if report.stale_draft_revision_references
            else "",
        )
    )
