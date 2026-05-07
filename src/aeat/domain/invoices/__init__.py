"""Immutable invoice catalogue surface for the financial pipeline.

Public surface — callers must import invoice models, errors, and service
functions exclusively from ``aeat.domain.invoices`` and must not
reach into the private underscore modules inside this package.
"""

from __future__ import annotations

from ._enums import InvoiceKind, IvaRate, PaymentStatus
from ._iva_classification import (
    IvaInvoiceClassification,
    classify_invoice_line_for_iva,
)
from ._errors import (
    InvoiceCatalogueError,
    InvoiceError,
    InvoiceLinkError,
    InvoiceLinkInconsistencyError,
    InvoiceNotFoundError,
    InvoicePersistenceError,
)
from ._models import Invoice, InvoiceCatalogue, InvoiceLine, derive_invoice_id
from ._repository import InvoiceCatalogueRepository
from ._service import (
    LinkInconsistency,
    ReconciliationSuggestion,
    link_transaction,
    link_transaction_bidirectional,
    suggest_reconciliations,
    verify_link_consistency,
)

__all__ = [
    "Invoice",
    "InvoiceCatalogue",
    "InvoiceCatalogueError",
    "InvoiceCatalogueRepository",
    "InvoiceError",
    "InvoiceKind",
    "InvoiceLine",
    "InvoiceLinkError",
    "InvoiceLinkInconsistencyError",
    "InvoiceNotFoundError",
    "InvoicePersistenceError",
    "IvaInvoiceClassification",
    "IvaRate",
    "LinkInconsistency",
    "PaymentStatus",
    "ReconciliationSuggestion",
    "classify_invoice_line_for_iva",
    "derive_invoice_id",
    "link_transaction",
    "link_transaction_bidirectional",
    "suggest_reconciliations",
    "verify_link_consistency",
]
