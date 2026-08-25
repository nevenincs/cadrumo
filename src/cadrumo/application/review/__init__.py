"""Application facade for the read-only operator review queue.

Callers import review enums, models, adapters, and projections exclusively from
:mod:`application.review`; private underscore modules remain implementation
details. The canonical CLI surface is ``aeat app review queue`` and ``show``.
Those commands are read-only: queue adapters load bucket-scoped source records,
derive severity, and emit typed rows without mutating ledger, invoice, filing, or
modelo state.

Internally, :class:`ReviewQueue` aggregates the three concrete
:class:`ReviewItem` variants:
:class:`TransactionReviewItem`, :class:`InvoiceReviewItem`, and
:class:`FindingReviewItem`. The operator-facing projection layer maps those
internal kinds into :class:`ReviewQueueRow` values using the accepted
``--kind`` / ``--source-kind`` vocabulary exposed by :data:`ACCEPTED_KINDS`:
``ledger_transaction``, ``purchase_invoice_evidence``, ``payable_invoice``,
``collectible_invoice``, and ``modelo_finding``. ``live_notification`` and
``sync_divergence`` remain reserved vocabulary until concrete review sources are
wired.

The exported :func:`update_ledger_review` and :func:`update_invoice_review`
helpers append workflow-attention history only. Durable ledger facts, invoice
facts, filing findings, and bucket events stay owned by their source
application surfaces.

See Also:
    :class:`ReviewQueue`
        Cross-source aggregator over read-only adapters.
    :class:`ReviewQueueReport`
        Application report consumed by the CLI review renderer.
    :class:`ReviewQueueRow`
        Operator-facing queue row with owner surface and next command metadata.
    :class:`ReviewItem`
        Internal discriminated union emitted by source adapters.
    :class:`ReviewItemKind`
        Internal adapter-kind enum, distinct from accepted operator kind strings.
    :data:`ACCEPTED_KINDS`
        Accepted operator ``--kind`` values after source-kind projection.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._actions import update_invoice_review, update_ledger_review
    from ._adapters import (
        drafts_pending,
        invoices_pending,
        transactions_pending,
    )
    from ._aggregator import ReviewQueue
    from ._edit import (
        EditClause,
        EditParseError,
        InvoiceEditKey,
        InvoiceEditSpec,
        LedgerEditKey,
        LedgerEditSpec,
        parse_edit_clause,
        parse_edit_clauses,
    )
    from ._enums import (
        ReviewFormat,
        ReviewItemKind,
        ReviewSeverity,
        ReviewState,
        reserved_kind_reason,
        severity_rank,
    )
    from ._errors import ReviewError, ReviewKindReservedError, ReviewSourceLoadError
    from ._filter import (
        DeclaracionReviewFilterKey,
        DeclaracionReviewFilterSpec,
        DeclaracionReviewStatus,
        FilterClause,
        FilterParseError,
        InvoiceReviewFilterKey,
        InvoiceReviewFilterSpec,
        InvoiceReviewStatus,
        LedgerReviewFilterKey,
        LedgerReviewFilterSpec,
        LedgerReviewStatus,
        parse_filter_clause,
        parse_filter_clauses,
    )
    from ._models import (
        FindingReviewItem,
        InvoiceReviewItem,
        InvoiceReviewRecord,
        LedgerReviewRecord,
        ReviewItem,
        TransactionReviewItem,
    )
    from ._operator import (
        ACCEPTED_KINDS,
        ReviewQueueReport,
        ReviewQueueRow,
        project_review_item,
        project_review_queue,
    )


#: Public name -> owning submodule, resolved on first attribute access.
#:
#: This facade's ``_models`` submodule pulls in ``application.filing`` and its
#: PDF-extraction chain (``pdfplumber``/``pdfminer``) -- measured at ~160,000 us
#: cumulative import cost -- for consumers that only ever wanted a single enum
#: (e.g. ``application.ledger.models`` importing ``LedgerReviewStatus`` for two
#: pydantic field annotations). A CLI process runs one command, so most of that
#: cost was paid for symbols the invocation never touched.
_LAZY_EXPORTS: dict[str, str] = {
    "ACCEPTED_KINDS": "._operator",
    "DeclaracionReviewFilterKey": "._filter",
    "DeclaracionReviewFilterSpec": "._filter",
    "DeclaracionReviewStatus": "._filter",
    "EditClause": "._edit",
    "EditParseError": "._edit",
    "FilterClause": "._filter",
    "FilterParseError": "._filter",
    "FindingReviewItem": "._models",
    "InvoiceEditKey": "._edit",
    "InvoiceEditSpec": "._edit",
    "InvoiceReviewFilterKey": "._filter",
    "InvoiceReviewFilterSpec": "._filter",
    "InvoiceReviewItem": "._models",
    "InvoiceReviewRecord": "._models",
    "InvoiceReviewStatus": "._filter",
    "LedgerEditKey": "._edit",
    "LedgerEditSpec": "._edit",
    "LedgerReviewFilterKey": "._filter",
    "LedgerReviewFilterSpec": "._filter",
    "LedgerReviewRecord": "._models",
    "LedgerReviewStatus": "._filter",
    "ReviewError": "._errors",
    "ReviewFormat": "._enums",
    "ReviewItem": "._models",
    "ReviewItemKind": "._enums",
    "ReviewKindReservedError": "._errors",
    "ReviewQueue": "._aggregator",
    "ReviewQueueReport": "._operator",
    "ReviewQueueRow": "._operator",
    "ReviewSeverity": "._enums",
    "ReviewSourceLoadError": "._errors",
    "ReviewState": "._enums",
    "TransactionReviewItem": "._models",
    "drafts_pending": "._adapters",
    "invoices_pending": "._adapters",
    "parse_edit_clause": "._edit",
    "parse_edit_clauses": "._edit",
    "parse_filter_clause": "._filter",
    "parse_filter_clauses": "._filter",
    "project_review_item": "._operator",
    "project_review_queue": "._operator",
    "reserved_kind_reason": "._enums",
    "severity_rank": "._enums",
    "transactions_pending": "._adapters",
    "update_invoice_review": "._actions",
    "update_ledger_review": "._actions",
}


# Every loader target is a closed literal from the map above.  The attribute
# name selects one of these pre-bound loaders; it never becomes an import path.
_LAZY_MODULE_LOADERS: dict[str, Callable[[], ModuleType]] = {
    module_path: partial(import_module, module_path, __name__) for module_path in frozenset(_LAZY_EXPORTS.values())
}


def __getattr__(name: str) -> object:
    """Resolve one public name by importing only the submodule that owns it.

    The resolved value is written into module globals, so only the first
    access to a name goes through this hook; every later one is an ordinary
    global lookup with no import machinery in the path.

    Ownership is unchanged: every name still has exactly one canonical home in
    this package's ``__all__``, and consumers still import it from here. Only
    WHEN the owning submodule executes has moved.
    """
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    loader = _LAZY_MODULE_LOADERS.get(module_name)
    if loader is None:
        raise RuntimeError(f"missing lazy loader for {module_name!r}")
    value = getattr(loader(), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Report the full public surface, including names not yet resolved."""
    return sorted(set(__all__) | set(globals()))


__all__ = [
    "ACCEPTED_KINDS",
    "DeclaracionReviewFilterKey",
    "DeclaracionReviewFilterSpec",
    "DeclaracionReviewStatus",
    "EditClause",
    "EditParseError",
    "FilterClause",
    "FilterParseError",
    "FindingReviewItem",
    "InvoiceEditKey",
    "InvoiceEditSpec",
    "InvoiceReviewFilterKey",
    "InvoiceReviewFilterSpec",
    "InvoiceReviewItem",
    "InvoiceReviewRecord",
    "InvoiceReviewStatus",
    "LedgerEditKey",
    "LedgerEditSpec",
    "LedgerReviewFilterKey",
    "LedgerReviewFilterSpec",
    "LedgerReviewRecord",
    "LedgerReviewStatus",
    "ReviewError",
    "ReviewFormat",
    "ReviewItem",
    "ReviewItemKind",
    "ReviewKindReservedError",
    "ReviewQueue",
    "ReviewQueueReport",
    "ReviewQueueRow",
    "ReviewSeverity",
    "ReviewSourceLoadError",
    "ReviewState",
    "TransactionReviewItem",
    "drafts_pending",
    "invoices_pending",
    "parse_edit_clause",
    "parse_edit_clauses",
    "parse_filter_clause",
    "parse_filter_clauses",
    "project_review_item",
    "project_review_queue",
    "reserved_kind_reason",
    "severity_rank",
    "transactions_pending",
    "update_invoice_review",
    "update_ledger_review",
]
