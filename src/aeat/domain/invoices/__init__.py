"""Immutable invoice catalogue surface for the financial pipeline.

Public surface for :class:`InvoiceCatalogue` and :class:`InvoiceCatalogueRepository`.
Callers must import invoice models, errors, and service functions
exclusively from ``aeat.domain.invoices`` and must not reach into the
private underscore modules inside this package.
"""

from __future__ import annotations

# isort: off
from ._enums import IvaRate, PaymentStatus, iva_rate_percentage, numeric_iva_rate_percentages
from ._errors import (
    InvoiceCatalogueError,
    InvoiceError,
    InvoiceLinkError,
    InvoiceLinkInconsistencyError,
    InvoiceNotFoundError,
    InvoicePersistenceError,
    InvoiceValidationError,
)

# Sibling-package import deferred below `._enums` and `._errors`: the
# classification module imports back into this package for IvaRate. If
# this `from ..iva...` block is hoisted above local imports, the
# invoices package is only partially initialised when classification
# resolves `from ..invoices import IvaRate` and import fails.
from ..iva import (
    IvaInvoiceClassification,
    classify_invoice_line_for_iva,
    invoice_line_to_iva_observation,
)
from ._models import Invoice, InvoiceCatalogue, InvoiceLine, derive_invoice_id
from ._protocols import InvoiceCatalogueRepositoryProtocol
from ._repository import InvoiceCatalogueRepository
from ._service import (
    LinkInconsistency,
    ReconciliationSuggestion,
    link_transaction,
    suggest_reconciliations,
    verify_link_consistency,
)
# isort: on

__all__ = [
    "Invoice",
    "InvoiceCatalogue",
    "InvoiceCatalogueError",
    "InvoiceCatalogueRepository",
    "InvoiceCatalogueRepositoryProtocol",
    "InvoiceError",
    "InvoiceLine",
    "InvoiceLinkError",
    "InvoiceLinkInconsistencyError",
    "InvoiceNotFoundError",
    "InvoicePersistenceError",
    "InvoiceValidationError",
    "IvaInvoiceClassification",
    "IvaRate",
    "LinkInconsistency",
    "PaymentStatus",
    "ReconciliationSuggestion",
    "classify_invoice_line_for_iva",
    "derive_invoice_id",
    "invoice_line_to_iva_observation",
    "iva_rate_percentage",
    "link_transaction",
    "numeric_iva_rate_percentages",
    "suggest_reconciliations",
    "verify_link_consistency",
]
