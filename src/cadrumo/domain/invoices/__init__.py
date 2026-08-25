"""Public facade for immutable invoice catalogue records.

The package root is the import boundary for :class:`InvoiceLine`,
:class:`Invoice`, :class:`InvoiceCatalogue`, invoice errors, repository
ports, and reconciliation helpers. :class:`Invoice` is a strict frozen
commercial-document record; :func:`derive_invoice_id` derives its stable id
from kind, number, issue date, counterparty, currency, and grand total, while
line and invoice validators preserve totals, tax-rate slots, payment state,
bucket ownership, and ``linked_transaction_ids`` provenance.

The IVA bridge re-exports :class:`IvaRate`, :class:`PaymentStatus`,
:class:`IvaInvoiceClassification`, :func:`classify_invoice_line_for_iva`,
:func:`invoice_line_to_iva_observation`, and rate helpers. The standard helper
covers domestic IVA rate slots; reverse-charge, intra-community, OSS/IOSS, and
other non-domestic cases use explicit substrate fields such as
:class:`domain.iva.IvaCategory` already carried on :class:`Invoice`.

Service helpers such as :func:`link_transaction`,
:func:`suggest_reconciliations`, and :func:`verify_link_consistency` are pure
operations over :class:`InvoiceCatalogue` and
:class:`domain.transactions.TransactionCatalogue`; persisted cross-catalogue
workflows belong in :mod:`application.invoices`.
Ledger ``purchase_invoice_evidence_id`` references must resolve to
bucket-owned :class:`Invoice` records with matching ``linked_transaction_ids``
before aggregation treats them as purchase evidence.

Persistence is exposed through the narrow
:class:`InvoiceCatalogueRepositoryProtocol` port; the concrete
:class:`~cadrumo.adapters.persistence.profile.invoices.InvoiceCatalogueRepository`
lives in the persistence adapter and stores the active-bucket catalogue
singleton through
:class:`adapters.persistence.storage.SecureObjectRepository` as
``FINANCIAL`` :class:`adapters.persistence.storage.SensitivityClass`
payloads wrapped in :class:`adapters.persistence.storage.Envelope`; no
plaintext invoice row, JSON catalogue, or envelope file is the durable store.
Callers must import public objects from ``cadrumo.domain.invoices`` and must not
reach into the private underscore modules inside this package.

Records are classified for calculation use by :func:`decompose_invoice` and
:func:`partition_invoices`, which yield either the euro components of the
canonical identity (``total = taxable_base + cuota + recargo + suplido``;
``cash = total - retención``) or the typed :class:`InvoiceDecompositionDefect`
reasons that exclude the record. An excluded record stays in the catalogue and
must be surfaced to the operator rather than dropped.

See Also:
    :class:`Invoice`
        Strict frozen invoice record that carries identity, totals, payment,
        bucket, tax-substrate, and linked-transaction facts.
    :func:`decompose_invoice`
        The decomposition contract separating usable records from
        excluded-but-visible ones.
    :class:`InvoiceCatalogue`
        Frozen aggregate persisted as the encrypted invoice catalogue.
    :class:`InvoiceCatalogueRepositoryProtocol`
        Narrow port used by application services that only need load/save
        semantics.
    :mod:`application.invoices`
        Persisted invoice import, reconciliation, repository linking, and
        :class:`application.invoices.InvoiceCatalogueSourceResolver`.
    :mod:`application.ledger`
        Ledger lifecycle that attaches ``purchase_invoice_evidence_id`` to
        bucket-scoped transactions after evidence ownership checks.
    :mod:`application.aggregation`
        Calculation-source resolvers that consume invoice and purchase-evidence
        records for modelo bindings.
"""

from __future__ import annotations

# isort: off
from ._enums import (
    InvoiceClass,
    InvoiceLegalMention,
    InvoiceOperationDateRole,
    IvaRate,
    PaymentStatus,
    invoice_legal_mention_text,
    iva_rate_kind,
    iva_rate_percentage,
    iva_rate_slot_percentage,
    numeric_iva_rate_percentages,
    numeric_iva_rate_slots,
)
from .errors import (
    InvoiceCatalogueError,
    InvoiceError,
    InvoiceLinkError,
    InvoiceLinkInconsistencyError,
    InvoiceNotFoundError,
    InvoicePersistenceError,
    InvoiceValidationError,
)

# Sibling-package import deferred below `._enums` and `.errors`: the
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
from ._decomposition import (
    INVOICE_DECOMPOSITION_DEFECT_GUIDANCE,
    InvoiceComponents,
    InvoiceDecomposition,
    InvoiceDecompositionDefect,
    InvoiceDecompositionPartition,
    decompose_invoice,
    partition_invoices,
)
from ._protocols import InvoiceCatalogueRepositoryProtocol
from ._service import (
    LinkInconsistency,
    ReconciliationSuggestion,
    find_invoice,
    find_unmatched,
    link_transaction,
    suggest_reconciliations,
    verify_link_consistency,
)
from ._validators import validate_country_code, validate_iva_number
# isort: on

__all__ = [
    "INVOICE_DECOMPOSITION_DEFECT_GUIDANCE",
    "Invoice",
    "InvoiceCatalogue",
    "InvoiceCatalogueError",
    "InvoiceCatalogueRepositoryProtocol",
    "InvoiceClass",
    "InvoiceComponents",
    "InvoiceDecomposition",
    "InvoiceDecompositionDefect",
    "InvoiceDecompositionPartition",
    "InvoiceError",
    "InvoiceLegalMention",
    "InvoiceLine",
    "InvoiceLinkError",
    "InvoiceLinkInconsistencyError",
    "InvoiceNotFoundError",
    "InvoiceOperationDateRole",
    "InvoicePersistenceError",
    "InvoiceValidationError",
    "IvaInvoiceClassification",
    "IvaRate",
    "LinkInconsistency",
    "PaymentStatus",
    "ReconciliationSuggestion",
    "classify_invoice_line_for_iva",
    "decompose_invoice",
    "derive_invoice_id",
    "find_invoice",
    "find_unmatched",
    "invoice_legal_mention_text",
    "invoice_line_to_iva_observation",
    "iva_rate_kind",
    "iva_rate_percentage",
    "iva_rate_slot_percentage",
    "link_transaction",
    "numeric_iva_rate_percentages",
    "numeric_iva_rate_slots",
    "partition_invoices",
    "suggest_reconciliations",
    "validate_country_code",
    "validate_iva_number",
    "verify_link_consistency",
]
