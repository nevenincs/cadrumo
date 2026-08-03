"""Typed ``--json`` payload schemas for the ledger invoice/inventory/evidence sub-apps.

Extracted from :mod:`~entrypoints.cli._ledger_payloads` to keep that
module under its size budget (`aeat-architecture-boundaries`,
`registry-resolver-family-extraction`); follows the same split pattern the
module's own docstring documents for
:mod:`~entrypoints.cli._ledger_rule_payloads`,
:mod:`~entrypoints.cli._ledger_llm_payloads`, and
:mod:`~entrypoints.cli._ledger_catalogue_invoice_payloads`.
Covers three CLI sub-app payload families:

* P06 -- the unified business-operation ``invoice`` noun-group (gated by
  ``--kind issued|received``; the persisted ``source_kind`` discriminator
  carries payable / collectible).
* P07 -- the ``inventory`` sub-app.
* P08 -- the purchase-invoice ``evidence`` sub-app.

Each class is a strict :class:`~entrypoints.cli._schemas.OutputSchema`
subclass, decorated with :func:`~entrypoints.cli._schemas.register_schema`
so the JSON-contract test suite can enumerate the surface. Re-imported into
:mod:`~entrypoints.cli._ledger_payloads` so existing ``from ._ledger_payloads import
BusinessInvoiceRecordPayload`` (etc.) call sites keep resolving unchanged.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from pydantic import AfterValidator, Field

from ...domain.contribuyente.inventory import INVENTORY_SCHEMA_VERSION, MovementKind, ValuationMethod
from ._decimal_wire import bounded_decimal_wire_text
from ._schemas import OutputSchema, register_schema
from ._wire_scalars import IsoDateText, enum_value_text

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")
_ONE = Decimal("1")

# The inventory transport is built by dumping the canonical InventoryLedger to
# JSON and re-validating the mapping, so every field below stays a string on
# the wire while carrying the canonical model's own bound.
_PositiveQuantity = bounded_decimal_wire_text(minimum=_ZERO, exclusive_minimum=True)
_NonNegativeAmount = bounded_decimal_wire_text(minimum=_ZERO)
_IvaRatePct = bounded_decimal_wire_text(minimum=_ZERO, maximum=_HUNDRED)
_DeductibleRatio = bounded_decimal_wire_text(minimum=_ZERO, maximum=_ONE)
_MovementKindText = enum_value_text(MovementKind)
_ValuationMethodText = enum_value_text(ValuationMethod)


def _validate_inventory_schema_version(value: str) -> str:
    """Refuse a schema version the canonical InventoryLedger would reject."""
    if value != INVENTORY_SCHEMA_VERSION:
        raise ValueError(f"unsupported inventory schema_version {value!r}; expected {INVENTORY_SCHEMA_VERSION!r}")
    return value


_InventorySchemaVersion = Annotated[str, AfterValidator(_validate_inventory_schema_version)]

if TYPE_CHECKING:
    from ...application.inventory import InventoryValuationPreviewResult as _AppInventoryValuationPreviewResult

# ---------------------------------------------------------------------------
# P06 — Unified business operation invoice sub-app
# (one ``invoice`` noun-group gated by ``--kind issued|received``; the
# persisted ``source_kind`` discriminator carries payable / collectible)
# ---------------------------------------------------------------------------


class BusinessInvoiceRecordPayload(OutputSchema):
    """One business-operation invoice record.

    Mirrors ``BusinessOperationInvoice.model_dump(mode='json')``
    plus the ``bucket_event_ids`` field the CLI appends at the emit
    site for mutation verbs (defaults to empty for read verbs). The
    ``source_kind`` field carries the persisted ``payable_invoice`` /
    ``collectible_invoice`` taxonomy value selected by ``--kind``.

    ``fx_rate`` / ``fx_rate_date`` mirror the euro-conversion stamp the
    record carries for a foreign-currency invoice; both are ``None`` for a
    EUR invoice and for a foreign invoice whose ECB rate could not be
    resolved (which is withheld from modelo projection rather than declared
    at face value). Surfacing them keeps the conversion provenance visible
    on the operator payload instead of dropping it at the CLI boundary.
    """

    invoice_id: str
    bucket_id: str
    source_kind: str
    counterparty_nif: str
    counterparty_name: str = ""
    invoice_number: str
    invoice_date: str
    currency: str
    taxable_base: str
    iva_rate: str | None = None
    iva_amount: str
    total_amount: str
    fx_rate: str | None = None
    fx_rate_date: str | None = None
    notes: str = ""
    country_code: str | None = None
    eu_iva_id: str | None = None
    operation_type: str | None = None
    created_at: str
    updated_at: str
    bucket_event_ids: list[str] = []


class BusinessInvoiceListResult(OutputSchema):
    """Shared list result for the unified invoice ``list`` verb.

    ``rows`` carries both ``payable_invoice`` and ``collectible_invoice``
    records when ``--kind`` is omitted (each row's own ``source_kind``
    discriminates the kind), or a single kind when ``--kind`` filters.
    """

    bucket_id: str
    rows: list[BusinessInvoiceRecordPayload]
    count: int


@register_schema("ledger.invoice.add")
class InvoiceAddResult(BusinessInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger invoice add``."""


@register_schema("ledger.invoice.view")
class InvoiceViewResult(BusinessInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger invoice view``."""


@register_schema("ledger.invoice.update")
class InvoiceUpdateResult(BusinessInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger invoice update``."""


@register_schema("ledger.invoice.remove")
class InvoiceRemoveResult(BusinessInvoiceRecordPayload):
    """JSON envelope for ``aeat app ledger invoice remove``."""


@register_schema("ledger.invoice.list")
class InvoiceListResult(BusinessInvoiceListResult):
    """JSON envelope for ``aeat app ledger invoice list``."""


# ---------------------------------------------------------------------------
# P07 — Inventory sub-app
# ---------------------------------------------------------------------------


class InventoryStockLayerPayload(OutputSchema):
    """One :class:`StockLayer` transport row."""

    sku: str = Field(default="default", min_length=1)
    quantity: _PositiveQuantity  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    unit_cost: _NonNegativeAmount  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    source_movement_id: str = Field(min_length=1)


class InventoryMovementPayload(OutputSchema):
    """One :class:`MovementRecord` transport row."""

    movement_id: str = Field(min_length=1)
    movement_date: IsoDateText
    kind: _MovementKindText  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    sku: str = Field(default="default", min_length=1)
    quantity: _PositiveQuantity  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    unit_cost: _NonNegativeAmount | None = None  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    taxable_base: _NonNegativeAmount | None = None  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    iva_rate: _IvaRatePct  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    iva_amount: _NonNegativeAmount | None = None  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    deductible_iva_ratio: _DeductibleRatio  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    schema_version: _InventorySchemaVersion


class InventoryLedgerPayload(OutputSchema):
    """One per-actividad inventory ledger record.

    Mirrors :class:`InventoryLedger`'s
    ``model_dump(mode='json')`` plus the ``bucket_event_ids`` field the
    CLI appends at the emit site.
    """

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: _ValuationMethodText  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    opening_stock: _NonNegativeAmount  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    opening_layers: list[InventoryStockLayerPayload] = []
    closing_stock: _NonNegativeAmount | None = None  # type: ignore[valid-type]  # TYPE-IGNORE-RATIONALE-DYNAMIC-BOUNDED-DECIMAL: dynamically constructed wire-text type mypy cannot statically validate as a field annotation
    period_movements: list[InventoryMovementPayload] = []
    schema_version: _InventorySchemaVersion
    bucket_event_ids: list[str] = []


class InventoryListRowPayload(InventoryLedgerPayload):
    """One inventory summary row returned by the list command."""

    schema_version: str = "1"
    movement_count: int = 0


@register_schema("ledger.inventory.list")
class InventoryListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger inventory list``."""

    bucket_id: str
    rows: list[InventoryListRowPayload]
    count: int


@register_schema("ledger.inventory.create")
class InventoryCreateResult(InventoryLedgerPayload):
    """JSON envelope for ``aeat app ledger inventory create``."""


@register_schema("ledger.inventory.movement.add")
class InventoryMovementAddResult(InventoryLedgerPayload):
    """JSON envelope for ``aeat app ledger inventory movement add``."""


@register_schema("ledger.inventory.valuation.preview")
class InventoryValuationPreviewPayload(OutputSchema):
    """JSON envelope for ``aeat app ledger inventory valuation preview``.

    Distinct from the application wrapper
    :class:`InventoryValuationPreviewResult` (DB-26
    S52): this envelope *flattens* that wrapper, projecting its inner
    ``preview`` (:class:`InventoryValuationPreview`)
    fields and lifting the wrapper's ``bucket_event_ids`` to the top level.
    Derive via
    :meth:`~entrypoints.cli._ledger_business_payloads.InventoryValuationPreviewPayload.from_result`.
    """

    actividad_id: str
    year: int
    valuation_method: str
    closing_stock: str
    cogs: str
    bucket_event_ids: list[str] = []

    @classmethod
    def from_result(cls, result: _AppInventoryValuationPreviewResult) -> InventoryValuationPreviewPayload:
        """Flatten the application preview wrapper into this CLI envelope.

        The wrapper carries an inner ``preview`` plus ``bucket_event_ids``;
        ``model_dump(mode="json")`` on the inner preview performs the
        enum/Decimal coercion, and the event ids are lifted onto the same level.

        Returns:
            :class:`InventoryValuationPreviewPayload`:
            Flattened CLI JSON envelope.
        """
        data = result.preview.model_dump(mode="json")
        data["bucket_event_ids"] = list(result.bucket_event_ids)
        return cls.model_validate(data)


# ---------------------------------------------------------------------------
# P08 — Purchase-invoice evidence sub-app
# ---------------------------------------------------------------------------


class EvidenceRecordPayload(OutputSchema):
    """One purchase-invoice evidence record.

    Mirrors ``PurchaseInvoiceEvidence.model_dump(mode='json')`` plus the
    ``bucket_event_ids`` field the CLI appends at the emit site (defaults
    to empty for read verbs).
    """

    evidence_id: str
    bucket_id: str
    source_path: str
    source_sha256: str
    attachment_id: str | None = None
    media_kind: str
    supplier: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None
    notes: str = ""
    created_at: str
    updated_at: str
    bucket_event_ids: list[str] = []


@register_schema("ledger.evidence.add")
class EvidenceAddResult(EvidenceRecordPayload):
    """JSON envelope for ``aeat app ledger evidence add``."""


@register_schema("ledger.evidence.view")
class EvidenceViewResult(EvidenceRecordPayload):
    """JSON envelope for ``aeat app ledger evidence view``."""


@register_schema("ledger.evidence.update")
class EvidenceUpdateResult(EvidenceRecordPayload):
    """JSON envelope for ``aeat app ledger evidence update``."""


@register_schema("ledger.evidence.remove")
class EvidenceRemoveResult(EvidenceRecordPayload):
    """JSON envelope for ``aeat app ledger evidence remove``."""


@register_schema("ledger.evidence.list")
class EvidenceListResult(OutputSchema):
    """JSON envelope for ``aeat app ledger evidence list``."""

    bucket_id: str
    count: int
    rows: list[EvidenceRecordPayload]


@register_schema("ledger.evidence.extract")
class EvidenceExtractResult(OutputSchema):
    """JSON envelope for ``aeat app ledger evidence extract``.

    Mirrors ``InvoiceDraft.model_dump(mode='json')`` (the on-host best-effort
    extraction) plus the resolved reference id the operator supplied. This is a
    reviewable draft only: extracting never mints or persists an
    ``cadrumo.domain.invoices.Invoice`` -- the operator confirms the fields (via
    ``aeat app ledger invoice add`` / ``invoice catalogue create``) before any
    invoice record is created.
    """

    bucket_id: str
    evidence_id: str | None = None
    attachment_id: str | None = None
    supplier_tax_id: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    taxable_base: str | None = None
    iva_rate: str | None = None
    iva_amount: str | None = None
    grand_total: str | None = None
    currency: str | None = None
    raw_text_length: int = 0


@register_schema("ledger.evidence.confirm")
class EvidenceConfirmResult(OutputSchema):
    """JSON envelope for ``aeat app ledger evidence extract --confirm``.

    Reports the persisted (or already-existing, on a guarded no-op) rich
    catalogue :class:`~domain.invoices.Invoice` -- mirroring
    ``CatalogueInvoiceRecordPayload`` -- plus the resolved evidence reference
    and a ``created`` flag distinguishing a fresh write
    (``single-subject-mutation-is-idempotent-guarded``) from a same-identity
    guarded retry.
    """

    bucket_id: str
    evidence_id: str | None = None
    attachment_id: str | None = None
    created: bool
    invoice_id: str
    kind: str
    invoice_number: str
    issued_at: str
    counterparty_name: str
    counterparty_tax_id: str
    counterparty_country: str
    base_total: str
    iva_total: str
    grand_total: str
    currency: str
    payment_status: str
    linked_transaction_ids: list[str] = []
    notes: str = ""
