"""Private request and public answer of the invoice figures preview.

Every draft field is optional, because a draft is incomplete while it is typed.
A figure nobody can determine yet is ``null``, which is never the same as zero.
"""

from __future__ import annotations

from datetime import date
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import IntracomOperationType
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.invoices.figures import FigureFindingCode, FigureFindingSeverity, StatedFigureVerdict
from ...domain.iva.schema import InvoiceKind
from ..operations.public_scalar import PublicDecimal, PublicNamedScalar
from .catalogue_add_contracts import InvoiceAddBusinessPremisesLease

INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID: Final = "ledger.invoice.preview"

INVOICE_FIGURES_PREVIEW_LABEL_PREFIX: Final = "application.invoices.figures_preview."
"""Where the words of the served codes live: ``finding.<code>`` and ``rate_slot.<slot>``."""

INVALID_INVOICE_REFUSAL: Final[Literal["invalid_invoice"]] = "invalid_invoice"
"""A refusal by a rule outside the figures owner, the same code the add operation reports."""

type InvoiceFiguresPreviewVerdict = Literal["incomplete", "would_accept", "would_refuse"]
type InvoiceFiguresPreviewOnDateSource = Literal["operation_date", "issued_at", "today"]


class InvoiceFiguresPreviewLine(BaseModel):
    """One draft line. Stated figures are what the document prints; the rest is typed."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4096)
    quantity: PublicDecimal | None = None
    unit_price: PublicDecimal | None = None
    iva_rate: str | None = Field(default=None, max_length=128)
    subtotal: PublicDecimal | None = None
    iva_amount: PublicDecimal | None = None
    spending_category_id: str | None = Field(default=None, max_length=128)
    oss_rate_kind: str | None = Field(default=None, max_length=128)


class InvoiceFiguresPreviewRequest(BaseModel):
    """One draft invoice, with lines or with a bare base for a correction editor."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    operation_date: date | None = None
    issued_at: date | None = None
    lines: tuple[InvoiceFiguresPreviewLine, ...] = ()
    base_total: PublicDecimal | None = None
    recargo_amount: PublicDecimal | None = None
    retention_rate: PublicDecimal | None = None
    retention_amount: PublicDecimal | None = None
    printed_total: PublicDecimal | None = None
    kind: InvoiceKind | None = None
    invoice_number: str | None = None
    counterparty_name: str | None = None
    counterparty_tax_id: str | None = None
    counterparty_country: str | None = Field(default=None, max_length=16)
    currency: str | None = Field(default=None, max_length=16)
    invoice_class: str | None = Field(default=None, max_length=64)
    iva_category: str | None = Field(default=None, max_length=128)
    operation_type: IntracomOperationType | None = None
    series: str | None = None
    rectifies_invoice_number: str | None = None
    notes: str = ""
    business_premises_lease: InvoiceAddBusinessPremisesLease | None = None

    @model_validator(mode="after")
    def _line_input_shape(self) -> InvoiceFiguresPreviewRequest:
        if self.lines and self.base_total is not None:
            raise ValueError("a draft states lines or a base_total, never both")
        if len({line.key for line in self.lines}) != len(self.lines):
            raise ValueError("draft line keys must be unique")
        return self


class InvoiceFiguresPreviewRateSlot(BaseModel):
    """One slot's standing on the draft's date; ``fraction`` is ``null`` when no rate applies."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    slot: str
    fraction: PublicDecimal | None
    in_force: bool
    coverage_gap: bool
    label_key: str


class InvoiceFiguresPreviewFigure(BaseModel):
    """The backend's figure, the stated figure with its verdict, and what add would store."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    computed: PublicDecimal | None = None
    stated: PublicDecimal | None = None
    verdict: StatedFigureVerdict | None = None
    submitted: PublicDecimal | None = None


class InvoiceFiguresPreviewLineResult(BaseModel):
    """One line's figures, correlated to the request by its key."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: str
    subtotal: InvoiceFiguresPreviewFigure
    iva_amount: InvoiceFiguresPreviewFigure


class InvoiceFiguresPreviewTotals(BaseModel):
    """Totals known so far. ``recargo`` is ``null`` when the draft states nothing about it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    base: PublicDecimal | None
    iva: PublicDecimal | None
    recargo: PublicDecimal | None
    total: PublicDecimal | None
    net_of_retention: PublicDecimal | None


class InvoiceFiguresPreviewRetention(BaseModel):
    """The stated retención and the amount its rate implies on the known base."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    rate: PublicDecimal | None
    amount: PublicDecimal | None
    implied: PublicDecimal | None


class InvoiceFiguresPreviewFinding(BaseModel):
    """One closed finding, located by field and, on a line, by the line's key."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: FigureFindingCode
    severity: FigureFindingSeverity
    fields: tuple[str, ...]
    line_key: str | None = None
    values: tuple[PublicNamedScalar, ...] = ()
    label_key: str


class InvoiceFiguresPreviewResult(BaseModel):
    """The backend's whole answer for one draft, bound to it by ``input_digest``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    input_digest: str
    on_date: date
    on_date_source: InvoiceFiguresPreviewOnDateSource
    rate_slots: tuple[InvoiceFiguresPreviewRateSlot, ...]
    lines: tuple[InvoiceFiguresPreviewLineResult, ...]
    totals: InvoiceFiguresPreviewTotals
    retention: InvoiceFiguresPreviewRetention
    findings: tuple[InvoiceFiguresPreviewFinding, ...]
    missing_fields: tuple[str, ...]
    verdict: InvoiceFiguresPreviewVerdict
    refusal_code: FigureFindingCode | Literal["invalid_invoice"] | None = None
    invoice_id: str | None = None

    @model_validator(mode="after")
    def _coherent_verdict(self) -> InvoiceFiguresPreviewResult:
        if (self.verdict == "would_refuse") != (self.refusal_code is not None):
            raise ValueError("a refusal code belongs to exactly a refused draft")
        if (self.verdict == "would_accept") != (self.invoice_id is not None):
            raise ValueError("an invoice id belongs to exactly an accepted draft")
        if (self.verdict == "incomplete") != bool(self.missing_fields):
            raise ValueError("missing fields belong to exactly an incomplete draft")
        return self


class InvoiceFiguresPreviewExecutionResult(BaseModel):
    """Private result kept in the worker's encrypted operation record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: InvoiceFiguresPreviewResult


__all__ = [
    "INVALID_INVOICE_REFUSAL",
    "INVOICE_FIGURES_PREVIEW_LABEL_PREFIX",
    "INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID",
    "InvoiceFiguresPreviewExecutionResult",
    "InvoiceFiguresPreviewFigure",
    "InvoiceFiguresPreviewFinding",
    "InvoiceFiguresPreviewLine",
    "InvoiceFiguresPreviewLineResult",
    "InvoiceFiguresPreviewOnDateSource",
    "InvoiceFiguresPreviewRateSlot",
    "InvoiceFiguresPreviewRequest",
    "InvoiceFiguresPreviewResult",
    "InvoiceFiguresPreviewRetention",
    "InvoiceFiguresPreviewTotals",
    "InvoiceFiguresPreviewVerdict",
]
