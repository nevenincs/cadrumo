"""Immutable presentation records for the host-neutral Ledger workspace."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, Protocol, get_args

from pydantic import BaseModel, Field, model_validator

from ....application.invoices.catalogue_lifecycle import CatalogueInvoicePatch
from ....application.ledger.actions_import import LedgerProviderID
from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.ledger.models import (
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)
from ....application.ledger.workspace import (
    LedgerAffectedDeclarationRefV1,
    LedgerInvoiceReconciliationRefV1,
    LedgerLinkInconsistencyRefV1,
    LedgerWorkspaceArea,
    LedgerWorkspaceAvailability,
    LedgerWorkspaceEntryRefV1,
)
from ....application.operator_actions.models import ActionReference
from ....core.aggregation import IntracomOperationType
from ....core.country_code import CountryCodeAlpha2
from ....core.identity.hex_ids import InvoiceId
from ....core.identity.transaction_ids import TransactionId
from ....core.models import STRICT_FROZEN_CONFIG
from ....domain.invoices.models import Invoice
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.models import Transaction

type LedgerDestinationIdV1 = Literal[
    "ledger.overview",
    "ledger.entries",
    "ledger.review",
    "ledger.import",
    "ledger.classification",
    "ledger.evidence",
    "ledger.reconciliation",
]


def declared_ledger_destination_ids() -> frozenset[str]:
    """Read the internal closed destination set from its defining type alias.

    Defined beside the alias it reads rather than beside a consumer, so the
    set and its declaration cannot drift apart.
    """
    return frozenset(item for item in get_args(LedgerDestinationIdV1.__value__) if isinstance(item, str))


#: The one pairing of workspace area to internal destination.
#:
#: Declared here rather than beside either consumer because both need it and
#: the route catalogue imports the controller, so neither module can own it.
#:
#: It used to be written twice: once in the route catalogue, whose totality
#: gate checked it, and once in the controller behind a ``cast`` to this
#: alias. A ``cast`` asserts rather than validates, so the controller copy was
#: checked by nothing at all -- not by the type checker, which believed the
#: assertion, and not by the route gate, which never read it. A destination
#: misspelled there stayed invisible until an operator selected that area and
#: the route lookup raised ``KeyError``; a destination swapped between two
#: areas surfaced as a disagreement refusal at the same moment. Both are
#: import-time facts about a closed set, so they are settled at import now.
LEDGER_DESTINATION_BY_AREA: Final[dict[LedgerWorkspaceArea, LedgerDestinationIdV1]] = {
    LedgerWorkspaceArea.OVERVIEW: "ledger.overview",
    LedgerWorkspaceArea.ENTRIES: "ledger.entries",
    LedgerWorkspaceArea.REVIEW: "ledger.review",
    LedgerWorkspaceArea.IMPORT: "ledger.import",
    LedgerWorkspaceArea.CLASSIFICATION: "ledger.classification",
    LedgerWorkspaceArea.EVIDENCE: "ledger.evidence",
    LedgerWorkspaceArea.RECONCILIATION: "ledger.reconciliation",
}


def _require_total_destination_pairing() -> None:
    """Refuse at import unless the pairing is a bijection in canonical order.

    Totality over the enum is what keeps navigation from raising on an area
    nobody remembered to map; uniqueness of the destinations is what keeps two
    areas from resolving to one screen. Order is checked because the route
    catalogue presents areas in enum order and reads its destinations from
    here.
    """
    if tuple(LEDGER_DESTINATION_BY_AREA) != tuple(LedgerWorkspaceArea):
        raise ValueError("Ledger destinations must cover every workspace area in canonical order")
    destinations = tuple(LEDGER_DESTINATION_BY_AREA.values())
    if frozenset(destinations) != declared_ledger_destination_ids() or len(frozenset(destinations)) != len(
        destinations
    ):
        raise ValueError("Ledger destinations must cover the internal catalogue exactly once")


_require_total_destination_pairing()


class LedgerRouteTargetV1(BaseModel):
    """One internal destination selected by its stable area identity."""

    model_config = STRICT_FROZEN_CONFIG

    destination: LedgerDestinationIdV1
    area: LedgerWorkspaceArea


class LedgerRouteRefusalV1(BaseModel):
    """A route that cannot be opened, preserving the authority that refused it."""

    model_config = STRICT_FROZEN_CONFIG

    target: LedgerRouteTargetV1
    availability: LedgerWorkspaceAvailability
    reason_key: str


class LedgerEntryRowV1(BaseModel):
    """Safe entry row containing no description, amount, counterparty, or evidence."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    review_status: str
    source: LedgerWorkspaceEntryRefV1

    @model_validator(mode="after")
    def _mirror_source(self) -> LedgerEntryRowV1:
        if self.transaction_id != self.source.transaction_id or self.review_status != self.source.review_status:
            raise ValueError("Ledger entry row must mirror its application projection source")
        return self


class LedgerReviewRowV1(BaseModel):
    """A reviewable transaction plus the canonical read action naming its door."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    review_status: str
    action: ActionReference
    source: LedgerWorkspaceEntryRefV1

    @model_validator(mode="after")
    def _mirror_source(self) -> LedgerReviewRowV1:
        if self.transaction_id != self.source.transaction_id or self.review_status != self.source.review_status:
            raise ValueError("Ledger review row must mirror its application projection source")
        return self


class LedgerFlowState(StrEnum):
    """Explicit state of a command-backed Ledger interaction."""

    EDITING = "editing"
    CONFIRMING = "confirming"
    SUBMITTING = "submitting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LedgerClassificationSubmissionV1(BaseModel):
    """Catalogue-authorized canonical classification patch submission."""

    model_config = STRICT_FROZEN_CONFIG

    action: ActionReference
    transaction_id: TransactionId
    patch: ManualLedgerTransactionPatch


class LedgerClassificationSubmitterV1(Protocol):
    """Injected application door for a classification mutation."""

    async def __call__(self, submission: LedgerClassificationSubmissionV1) -> ManualLedgerTransactionResult:
        """Submit one authorized canonical classification patch."""
        ...


class LedgerExclusionSubmissionV1(BaseModel):
    """Catalogue-authorized request to exclude one reviewed entry from filing."""

    model_config = STRICT_FROZEN_CONFIG

    action: ActionReference
    transaction_id: TransactionId


class LedgerExclusionSubmitterV1(Protocol):
    """Injected application door that marks one entry reviewed and excluded."""

    async def __call__(self, submission: LedgerExclusionSubmissionV1) -> ManualLedgerTransactionResult:
        """Exclude one active entry through the canonical lifecycle writer."""
        ...


class LedgerImportSourceKind(StrEnum):
    """What an operator-chosen file holds, which decides the door that reads it."""

    BANK_STATEMENT = "bank_statement"
    INVOICES_RECEIVED = "invoices_received"
    INVOICES_ISSUED = "invoices_issued"


class LedgerImportRequestV1(BaseModel):
    """One operator-chosen file or folder and how to read it.

    ``provider`` applies to a bank statement and ``country`` to an invoice
    book; each is ignored by the other kind rather than guessed for it.
    """

    model_config = STRICT_FROZEN_CONFIG

    path: Path
    source_kind: LedgerImportSourceKind
    provider: LedgerProviderID = LedgerProviderID.AUTO
    country: str | None = Field(default=None, min_length=2, max_length=2)


class LedgerImportFileRefusalV1(BaseModel):
    """One file of a folder that could not be read, with the reason it gave."""

    model_config = STRICT_FROZEN_CONFIG

    file_name: str
    reason: str


class LedgerImportRowRefusalV1(BaseModel):
    """One invoice-book row the importer refused, by its spreadsheet row number."""

    model_config = STRICT_FROZEN_CONFIG

    row_number: int
    field: str
    reason: str


class LedgerImportOutcomeV1(BaseModel):
    """What a preview or an applied import reports, in the operator's terms.

    ``imported`` and ``skipped`` are ``None`` when the preview cannot measure
    them: an invoice book is only resolved against the catalogue as it is
    written, so its preview counts rows and columns and says nothing more.
    """

    model_config = STRICT_FROZEN_CONFIG

    source_kind: LedgerImportSourceKind
    dry_run: bool
    files: int
    rows: int
    imported: int | None
    skipped: int | None
    likely_duplicates: int = 0
    diagnostics: tuple[str, ...] = ()
    refused_files: tuple[LedgerImportFileRefusalV1, ...] = ()
    refused_rows: tuple[LedgerImportRowRefusalV1, ...] = ()
    unmapped_columns: tuple[str, ...] = ()


class LedgerImportDoorV1(Protocol):
    """Injected application door that previews and then applies one import."""

    async def preview(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        """Read the source and report what applying it would do, writing nothing."""
        ...

    async def apply(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        """Write the source into the operator's ledger or invoice catalogue."""
        ...


class LedgerInvoiceClassChoice(StrEnum):
    """The invoice classes an operator may state; the registry resolves each token."""

    ORDINARIA = "ordinaria"
    SIMPLIFICADA = "simplificada"
    RECTIFICATIVA = "rectificativa"


class LedgerInvoiceLineEntryV1(BaseModel):
    """One printed invoice line as the operator typed it, with its numbers already parsed.

    It carries exactly the domain line's fields. The rate stays the registry
    slot token as typed: whether that slot is governed, and whether the line's
    arithmetic holds, are the writer's checks, made against the pinned
    authority when the line becomes the domain line.
    """

    model_config = STRICT_FROZEN_CONFIG

    description: str
    quantity: Decimal
    unit_price: Decimal
    subtotal: Decimal
    iva_rate: str
    iva_amount: Decimal
    spending_category_id: str | None = None
    oss_rate_kind: str | None = None


class LedgerInvoiceEntryV1(BaseModel):
    """One invoice as the operator typed it, already parsed into typed values.

    Legal checks -- the NIF format, the IVA slot for the date, the retention
    consistency, the recargo identity -- are the application writer's, so
    nothing here pre-judges them; this only carries what was entered.

    An invoice is entered either as one taxable base and rate or as its
    ordered lines, exactly as the writer accepts it, so a mixed-rate invoice
    reaches the writer with its per-rate breakdown intact.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: InvoiceKind
    counterparty_name: str
    counterparty_nif: str | None
    country_code: str
    invoice_number: str
    invoice_date: date
    taxable_base: Decimal | None
    iva_rate: Decimal | None
    lines: tuple[LedgerInvoiceLineEntryV1, ...] = ()
    operation_type: IntracomOperationType | None = None
    operation_date: date | None = None
    recargo_amount: Decimal | None = None
    rectifies_invoice_number: str | None = None
    iva_category: IvaCategory | None = None
    currency: str
    retention_rate: Decimal | None = None
    retention_amount: Decimal | None = None
    invoice_class: LedgerInvoiceClassChoice = LedgerInvoiceClassChoice.ORDINARIA
    series: str | None = None
    notes: str = ""


class LedgerInvoiceAddResultV1(BaseModel):
    """Identity and totals of the invoice the writer recorded."""

    model_config = STRICT_FROZEN_CONFIG

    invoice_id: InvoiceId
    invoice_number: str
    base_total: Decimal
    iva_total: Decimal
    grand_total: Decimal
    currency: str
    euro_value_pending: bool = False
    """The invoice is in a foreign currency and no euro rate was found for it."""


class LedgerInvoiceAddDoorV1(Protocol):
    """Injected application door that records one catalogue invoice."""

    async def __call__(self, entry: LedgerInvoiceEntryV1) -> LedgerInvoiceAddResultV1:
        """Build and persist one invoice through the sole catalogue writer."""
        ...


class LedgerRecordDoorsV1(Protocol):
    """Injected application doors that read and edit canonical invoice and transaction records.

    The bound implementation captures one profile and authority generation,
    so navigating between records can never retarget a write.
    """

    async def invoices(self) -> tuple[Invoice, ...]:
        """List the bucket's canonical invoices."""
        ...

    async def invoice(self, invoice_id: str) -> Invoice:
        """Resolve one canonical invoice by its full identity."""
        ...

    async def update_invoice(self, baseline: Invoice, patch: CatalogueInvoicePatch) -> Invoice:
        """Submit a baseline-guarded metadata patch through the shared writer."""
        ...

    async def transaction(self, transaction_id: str) -> Transaction:
        """Resolve one typed transaction."""
        ...

    async def update_transaction(self, baseline: Transaction, patch: ManualLedgerTransactionPatch) -> Transaction:
        """Apply a typed edit against the captured transaction baseline."""
        ...


class LedgerEvidenceRecordStatus(StrEnum):
    """Where one registered document stands; unmeasured is not the same as awaiting."""

    AWAITING = "awaiting"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    UNMEASURED = "unmeasured"


class LedgerEvidenceRecordRowV1(BaseModel):
    """One locally registered purchase-invoice document and where it stands."""

    model_config = STRICT_FROZEN_CONFIG

    evidence_id: str
    media_kind: str
    file_name: str
    supplier: str | None
    invoice_number: str | None
    created_at: str
    status: LedgerEvidenceRecordStatus


class LedgerReaderReadinessV1(BaseModel):
    """Whether documents can be read on this machine, as the reader reports it."""

    model_config = STRICT_FROZEN_CONFIG

    extraction_ready: bool
    failed_condition_id: str | None = None


class LedgerEvidenceDraftV1(BaseModel):
    """What the on-host reader found in one document, as display text.

    ``None`` is a field the reader could not ground in the document; it is
    shown as unread, never as zero.
    """

    model_config = STRICT_FROZEN_CONFIG

    evidence_id: str
    supplier_name: str | None
    supplier_tax_id: str | None
    invoice_number: str | None
    invoice_date: str | None
    taxable_base: str | None
    iva_rate: str | None
    iva_amount: str | None
    grand_total: str | None
    currency: str | None
    suggested_kind: InvoiceKind | None
    discrepancies: int


class LedgerEvidenceConfirmationV1(BaseModel):
    """The operator's answers that confirm one read document as an invoice."""

    model_config = STRICT_FROZEN_CONFIG

    evidence_id: str
    kind: InvoiceKind
    country_code: CountryCodeAlpha2
    counterparty_name: str | None = None


class LedgerEvidenceConfirmedV1(BaseModel):
    """The invoice a confirmation recorded, or found already recorded."""

    model_config = STRICT_FROZEN_CONFIG

    invoice_id: InvoiceId
    invoice_number: str
    grand_total: Decimal
    currency: str
    created: bool
    printed_total_disagrees: bool


class LedgerEvidenceDoorV1(Protocol):
    """Injected application door over the operator's local invoice evidence."""

    def list_records(self) -> tuple[LedgerEvidenceRecordRowV1, ...]:
        """Read every registered document with its confirmation state."""
        ...

    async def add(self, source_path: str) -> LedgerEvidenceRecordRowV1:
        """Register one PDF or image file as evidence, storing its bytes securely.

        The path travels as typed: the service resolves it for byte access and
        records the operator's own spelling as provenance.
        """
        ...

    def reader_readiness(self) -> LedgerReaderReadinessV1:
        """Measure the local document reader without starting or loading anything."""
        ...

    async def extract(self, evidence_id: str) -> LedgerEvidenceDraftV1:
        """Read one stored document on this machine; nothing is recorded."""
        ...

    async def confirm(self, confirmation: LedgerEvidenceConfirmationV1) -> LedgerEvidenceConfirmedV1:
        """Re-read the document and record it as an invoice through the sole writer."""
        ...


class LedgerEvidenceRowV1(BaseModel):
    """Safe application evidence-review metadata with its declared read action."""

    model_config = STRICT_FROZEN_CONFIG

    attachment_id: str
    mime_type: str
    bytes_size: int
    captured_at: str
    pending_review: bool
    action: ActionReference
    source: AttachmentReviewItem

    @model_validator(mode="after")
    def _mirror_source(self) -> LedgerEvidenceRowV1:
        if (
            self.attachment_id != self.source.attachment_id
            or self.mime_type != self.source.mime_type
            or self.bytes_size != self.source.bytes_size
            or self.captured_at != self.source.captured_at
            or self.pending_review != self.source.pending_review
        ):
            raise ValueError("Ledger evidence row must mirror its canonical application source")
        return self


class LedgerLinkSubmissionV1(BaseModel):
    """Catalogue-authorized local invoice/transaction link request."""

    model_config = STRICT_FROZEN_CONFIG

    action: ActionReference
    transaction_id: TransactionId
    invoice_id: InvoiceId


class LedgerLinkResultV1(BaseModel):
    """Safe identity-only acknowledgement returned by an injected link door."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    invoice_id: InvoiceId


class LedgerLinkSubmitterV1(Protocol):
    """Injected application door for one admitted local Ledger link."""

    async def __call__(self, submission: LedgerLinkSubmissionV1) -> LedgerLinkResultV1:
        """Submit one authorized link request."""
        ...


type LedgerReconciliationSourceV1 = (
    LedgerInvoiceReconciliationRefV1 | LedgerLinkInconsistencyRefV1 | LedgerAffectedDeclarationRefV1
)


__all__ = [
    "LEDGER_DESTINATION_BY_AREA",
    "LedgerClassificationSubmissionV1",
    "LedgerClassificationSubmitterV1",
    "LedgerDestinationIdV1",
    "LedgerEntryRowV1",
    "LedgerEvidenceConfirmationV1",
    "LedgerEvidenceConfirmedV1",
    "LedgerEvidenceDoorV1",
    "LedgerEvidenceDraftV1",
    "LedgerEvidenceRecordRowV1",
    "LedgerEvidenceRecordStatus",
    "LedgerEvidenceRowV1",
    "LedgerExclusionSubmissionV1",
    "LedgerExclusionSubmitterV1",
    "LedgerFlowState",
    "LedgerImportDoorV1",
    "LedgerImportFileRefusalV1",
    "LedgerImportOutcomeV1",
    "LedgerImportRequestV1",
    "LedgerImportRowRefusalV1",
    "LedgerImportSourceKind",
    "LedgerInvoiceAddDoorV1",
    "LedgerInvoiceAddResultV1",
    "LedgerInvoiceClassChoice",
    "LedgerInvoiceEntryV1",
    "LedgerInvoiceLineEntryV1",
    "LedgerLinkResultV1",
    "LedgerLinkSubmissionV1",
    "LedgerLinkSubmitterV1",
    "LedgerReaderReadinessV1",
    "LedgerRecordDoorsV1",
    "LedgerReviewRowV1",
    "LedgerRouteRefusalV1",
    "LedgerRouteTargetV1",
    "declared_ledger_destination_ids",
]
