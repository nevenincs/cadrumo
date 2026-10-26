"""Synthetic invoice and transaction projections, and in-memory doors, for the invoice screens.

Every value is the registered operation's own public model, built from
synthetic data. The doors hold their records in memory and answer with those
models; nothing is read from or written to storage.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from textual.screen import Screen

from .....application.invoices.catalogue_intake_contracts import (
    InvoiceImportProjection,
    InvoiceImportRequest,
    InvoiceImportRowFailure,
    InvoiceWizardOutcome,
    InvoiceWizardProjection,
    InvoiceWizardRequest,
)
from .....application.invoices.catalogue_intake_refusal import (
    InvoiceWizardFieldFailure,
    InvoiceWizardValidationRefusalProjection,
)
from .....application.invoices.catalogue_lifecycle import CatalogueInvoicePatch
from .....application.invoices.catalogue_read_projection import CatalogueInvoiceSnapshot, InvoiceLineSnapshot
from .....application.invoices.catalogue_selection import InvoiceLookupRefusalReason, InvoiceLookupRefusedError
from .....application.ledger.transaction_projection import LedgerTransactionProjection
from .....application.ledger.update_contracts import LedgerUpdatePatch, LedgerUpdatePatchField
from .....application.operations.public_scalar import PublicDecimal
from .....core.errors.hierarchy import CadrumoError
from .....domain.invoices.enums import PaymentStatus
from .....domain.invoices.errors import InvoiceValidationError
from .....domain.iva.schema import InvoiceKind
from .....domain.transactions.errors import TransactionValidationError
from ...components.host import ScreenHostApp
from ..invoices_import import LedgerInvoiceImportSourceV1

INVOICES_PROFILE_ID = UUID("4dd00000-0000-4000-8000-0000000000dd")
"""The synthetic profile every fixture record belongs to."""
STALE_KEY = "tui.ledger.records.stale"
"""The refusal an in-memory door raises when a write names a record that changed."""
SYNTHETIC_SOURCE_PATH = str(Path(Path.cwd().anchor, "synthetic", "facturas-recibidas.xlsx"))
"""An absolute reference on this platform; no such file is read."""
SYNTHETIC_SOURCE_SHA256 = "5" * 64


def _decimal(value: str) -> PublicDecimal:
    return PublicDecimal(decimal=value)


def invoice_id_for(index: int) -> str:
    """A distinct synthetic hex-64 invoice identity."""
    return f"{index + 1:064x}"


def invoice_snapshot(
    index: int = 0,
    *,
    kind: InvoiceKind = InvoiceKind.RECEIVED,
    notes: str = "",
    linked: tuple[str, ...] = (),
    source_filename: str | None = None,
) -> CatalogueInvoiceSnapshot:
    """One synthetic catalogue snapshot: a base of 100.00 at 21 % with one printed line."""
    return CatalogueInvoiceSnapshot(
        invoice_id=invoice_id_for(index),
        bucket_id=str(INVOICES_PROFILE_ID),
        kind=kind,
        invoice_number=f"F-{index + 1:05d}",
        issued_at=date(2026, 3, 1 + index % 28),
        counterparty_name=f"Synthetic supplier {index + 1}",
        counterparty_tax_id=None,
        counterparty_country="ES",
        base_total=_decimal("100.00"),
        iva_total=_decimal("21.00"),
        grand_total=_decimal("121.00"),
        currency="EUR",
        payment_status=PaymentStatus.PENDING,
        linked_transaction_ids=linked,
        source_filename=source_filename,
        source_sha256=None if source_filename is None else SYNTHETIC_SOURCE_SHA256,
        source_row_index=None if source_filename is None else 7,
        notes=notes,
        retention_rate=None,
        retention_amount=None,
        recargo_amount=None,
        operation_type=None,
        lines=(
            InvoiceLineSnapshot(
                description="Synthetic service",
                quantity=_decimal("1"),
                unit_price=_decimal("100.00"),
                subtotal=_decimal("100.00"),
                iva_rate="RATE_21",
                iva_amount=_decimal("21.00"),
            ),
        ),
        invoice_class="ordinaria",
        series=None,
        operation_date=None,
        operation_date_role=None,
        iva_category=None,
        rectifies_invoice_number=None,
        fx_rate=None,
        fx_rate_date=None,
        fx_rate_source=None,
        base_total_eur=None,
        iva_total_eur=None,
        grand_total_eur=None,
    )


def transaction_projection(
    transaction_id: str = "a" * 64,
    *,
    description: str = "Synthetic bank movement",
    invoice_id: str | None = None,
) -> LedgerTransactionProjection:
    """One synthetic outgoing transaction projection of 121 EUR, in the canonical decimal text the worker emits."""
    return LedgerTransactionProjection(
        transaction_id=transaction_id,
        date="2026-03-18",
        booked_date="2026-03-18",
        value_date=None,
        amount="121",
        currency="EUR",
        direction="OUTGOING",
        counterparty="Synthetic supplier 1",
        description=description,
        business_classification="BUSINESS",
        business_pct=None,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        iva_category=None,
        counterparty_country=None,
        counterparty_identification_state=None,
        irpf_category=None,
        m210_income_classification=None,
        usage_ratio_id=None,
        prorrata_reference=None,
        purchase_invoice_evidence_id=None,
        invoice_id=invoice_id,
        attachment_ids=(),
        notes="synthetic note",
        lifecycle_state="ACTIVE",
        classified_by="operator",
        classified_at=None,
        classification_reason="",
        classification_confidence=None,
        source_jurisdiction=None,
        value_in_eur=None,
        fx_rate=None,
        created_at="2026-03-18T10:00:00+00:00",
        modified_at="2026-03-18T10:00:00+00:00",
    )


class ReplacingHostApp(ScreenHostApp[None]):
    """A host that swaps the workspace body the way the root shell does, removing the old body first.

    The root waits for each popped body to be removed before pushing the next,
    so a fresh body carrying the same id as the one it replaces can mount.
    """

    def replace_workspace_body(self, screen: Screen[None], /) -> None:
        """Defer the swap onto this host's pump, as the root shell does."""
        self.call_next(self._swap, screen)

    async def _swap(self, screen: Screen[None]) -> None:
        while len(self.screen_stack) > 1:
            await self.pop_screen()
        await self.push_screen(screen, self.exit)


class MemoryRecordDoors:
    """Invoice and transaction records held in memory, refusing a write against a changed record."""

    def __init__(
        self,
        invoices: tuple[CatalogueInvoiceSnapshot, ...] = (),
        transactions: tuple[LedgerTransactionProjection, ...] = (),
    ) -> None:
        self.catalogue = {row.invoice_id: row for row in invoices}
        self.transactions = {row.transaction_id: row for row in transactions}
        self.writes: list[tuple[str, str]] = []
        self.invoice_patches: list[CatalogueInvoicePatch] = []
        self.transaction_patches: list[tuple[LedgerUpdatePatch, tuple[LedgerUpdatePatchField, ...]]] = []
        self.refusal: CadrumoError | None = None
        """Raised by the next write instead of writing, as the worker would refuse it."""
        self.read_refusal: CadrumoError | None = None

    async def invoices(self) -> tuple[CatalogueInvoiceSnapshot, ...]:
        if self.read_refusal is not None:
            raise self.read_refusal
        return tuple(self.catalogue.values())

    async def invoice(self, invoice_id: str) -> CatalogueInvoiceSnapshot:
        found = self.catalogue.get(invoice_id)
        if found is None:
            raise InvoiceLookupRefusedError(reason=InvoiceLookupRefusalReason.NOT_FOUND, invoice_id=invoice_id)
        return found

    def _require_current_invoice(self, baseline: CatalogueInvoiceSnapshot) -> None:
        if self.catalogue.get(baseline.invoice_id) != baseline:
            raise InvoiceValidationError(translated_message=STALE_KEY, context={})
        if self.refusal is not None:
            raise self.refusal

    async def update_invoice(
        self, baseline: CatalogueInvoiceSnapshot, patch: CatalogueInvoicePatch
    ) -> CatalogueInvoiceSnapshot:
        self.invoice_patches.append(patch)
        self._require_current_invoice(baseline)
        values: dict[str, object] = {}
        for name, value in patch.model_dump(exclude_unset=True).items():
            values[name] = _decimal(str(value)) if isinstance(value, Decimal) else value
        updated = CatalogueInvoiceSnapshot.model_validate({**baseline.model_dump(), **values})
        self.catalogue[baseline.invoice_id] = updated
        self.writes.append(("update", baseline.invoice_id))
        return updated

    async def remove_invoice(self, baseline: CatalogueInvoiceSnapshot) -> CatalogueInvoiceSnapshot:
        self._require_current_invoice(baseline)
        del self.catalogue[baseline.invoice_id]
        self.writes.append(("remove", baseline.invoice_id))
        return baseline

    async def transaction(self, transaction_id: str) -> LedgerTransactionProjection:
        found = self.transactions.get(transaction_id)
        if found is None:
            raise TransactionValidationError(translated_message=STALE_KEY, context={})
        return found

    async def update_transaction(
        self,
        baseline: LedgerTransactionProjection,
        patch: LedgerUpdatePatch,
        fields: tuple[LedgerUpdatePatchField, ...],
    ) -> LedgerTransactionProjection:
        self.transaction_patches.append((patch, fields))
        if self.transactions.get(baseline.transaction_id) != baseline:
            raise TransactionValidationError(translated_message=STALE_KEY, context={})
        if self.refusal is not None:
            raise self.refusal
        updated = LedgerTransactionProjection.model_validate(
            {**baseline.model_dump(), **{name: getattr(patch, name) for name in fields}}
        )
        self.transactions[baseline.transaction_id] = updated
        self.writes.append(("update_transaction", baseline.transaction_id))
        return updated


class MemoryInvoiceImportDoor:
    """Knows one synthetic invoice book and answers its import with a preset outcome."""

    def __init__(self, outcome: InvoiceImportProjection | None = None) -> None:
        self.profile_id = INVOICES_PROFILE_ID
        self.sources = {
            SYNTHETIC_SOURCE_PATH: LedgerInvoiceImportSourceV1(
                source_path=SYNTHETIC_SOURCE_PATH,
                file_name="facturas-recibidas.xlsx",
                size_bytes=18_432,
                sha256=SYNTHETIC_SOURCE_SHA256,
            )
        }
        self.outcome = outcome or import_outcome()
        self.apply_refusal: CadrumoError | None = None
        self.previews: list[str] = []
        self.requests: list[InvoiceImportRequest] = []

    async def preview(self, source_path: str) -> LedgerInvoiceImportSourceV1:
        self.previews.append(source_path)
        found = self.sources.get(source_path)
        if found is None:
            raise InvoiceValidationError(
                translated_message="application.invoices.bulk_import.errors.file_read_failed",
                context={"path_name": source_path, "error_type": "FileNotFoundError"},
            )
        return found

    async def apply(self, request: InvoiceImportRequest) -> InvoiceImportProjection:
        self.requests.append(request)
        if self.apply_refusal is not None:
            raise self.apply_refusal
        return self.outcome


def import_outcome(*, created: int = 2, skipped: int = 1, refused: int = 1) -> InvoiceImportProjection:
    """A synthetic import outcome; refused rows are numbered from row 5."""
    return InvoiceImportProjection(
        profile_id=INVOICES_PROFILE_ID,
        source_sha256=SYNTHETIC_SOURCE_SHA256,
        rows=created + skipped + refused,
        created=created,
        skipped_duplicate=skipped,
        refused=tuple(
            InvoiceImportRowFailure(row_number=5 + index, field="invoice_date", reason="must be a date")
            for index in range(refused)
        ),
        created_invoice_ids=tuple(invoice_id_for(index) for index in range(created)),
        unmapped_column_headers=("Observaciones",) if refused else (),
        mapping_reasons=(),
    )


class MemoryInvoiceWizardDoor:
    """Records each wizard request and answers with a preset outcome or a recorded invoice."""

    def __init__(self) -> None:
        self.profile_id = INVOICES_PROFILE_ID
        self.requests: list[InvoiceWizardRequest] = []
        self.refused_fields: tuple[tuple[str, str], ...] = ()
        self.refusal: CadrumoError | None = None

    async def __call__(self, request: InvoiceWizardRequest) -> InvoiceWizardOutcome:
        self.requests.append(request)
        if self.refusal is not None:
            raise self.refusal
        if self.refused_fields:
            return InvoiceWizardOutcome(
                profile_id=self.profile_id,
                outcome="refused",
                refusal=InvoiceWizardValidationRefusalProjection(
                    profile_id=self.profile_id,
                    field_errors=tuple(
                        InvoiceWizardFieldFailure.model_validate({"field": field, "reason": reason})
                        for field, reason in self.refused_fields
                    ),
                ),
            )
        invoice = invoice_snapshot(kind=request.kind).model_copy(update={"invoice_number": request.invoice_number})
        return InvoiceWizardOutcome(
            profile_id=self.profile_id,
            outcome="succeeded",
            result=InvoiceWizardProjection(
                profile_id=self.profile_id, invoice=invoice, already_existed=False, euro_value_pending=False
            ),
        )


__all__ = [
    "INVOICES_PROFILE_ID",
    "STALE_KEY",
    "SYNTHETIC_SOURCE_PATH",
    "SYNTHETIC_SOURCE_SHA256",
    "MemoryInvoiceImportDoor",
    "MemoryInvoiceWizardDoor",
    "MemoryRecordDoors",
    "ReplacingHostApp",
    "import_outcome",
    "invoice_id_for",
    "invoice_snapshot",
    "transaction_projection",
]
