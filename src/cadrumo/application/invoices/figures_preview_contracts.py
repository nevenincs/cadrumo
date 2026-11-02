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
from ...domain.invoices.figures import (
    FigureFindingCode,
    FigureFindingSeverity,
    StatedFigureVerdict,
)
from ...domain.invoices.rule_findings import InvoiceRuleFindingCode
from ...domain.iva.schema import InvoiceKind
from ..operations.public_scalar import PublicDecimal, PublicNamedScalar

INVOICE_FIGURES_PREVIEW_OPERATION_DEFINITION_ID: Final = "ledger.invoice.preview"

INVOICE_FIGURES_PREVIEW_LABEL_PREFIX: Final = "application.invoices.figures_preview."
"""Where the words of the served codes live: ``finding.<code>``, ``rule_finding.<code>`` and ``rate_slot.<slot>``."""

INVALID_INVOICE_REFUSAL: Final[Literal["invalid_invoice"]] = "invalid_invoice"
"""A refusal by a rule outside the figures owner, the same code the add operation reports."""

type InvoiceFiguresPreviewVerdict = Literal["incomplete", "would_accept", "would_refuse"]
type InvoiceFiguresPreviewOnDateSource = Literal["operation_date", "issued_at", "today"]
type InvoiceFiguresPreviewVerdictScope = Literal["whole_draft", "correction_facts"]
"""What a verdict was reached over.

``whole_draft`` is acceptance itself: the add operation's own construction ran
on the draft. ``correction_facts`` judges only the facts a correction request
states, against the stored figures it restates: the retención against the stored
base, the class facts, the tax id against the country, the operation date against
its stored role. It reads no stored record, so ``would_accept`` there means no
rule it could ask refuses, and not that ``ledger.invoice.update`` will commit: the
update validates the whole stored record again, its lines included, and a moved
operation date can still take a stored line's rate out of force.
"""


class InvoiceFiguresPreviewLine(BaseModel):
    """One draft line. Stated figures are what the document prints; the rest is typed."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: str = Field(min_length=1, max_length=128)
    # Any length is asked about: too long for an add is a served finding, not a failed read.
    description: str | None = None
    quantity: PublicDecimal | None = None
    unit_price: PublicDecimal | None = None
    iva_rate: str | None = Field(default=None, max_length=128)
    subtotal: PublicDecimal | None = None
    iva_amount: PublicDecimal | None = None
    spending_category_id: str | None = Field(default=None, max_length=128)
    oss_rate_kind: str | None = Field(default=None, max_length=128)


class InvoiceFiguresPreviewLease(BaseModel):
    """A draft's premises facts as typed; any length is asked about, and a served finding answers it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    situacion_inmueble: str | None = Field(default=None, min_length=1)
    referencia_catastral: str | None = None


class InvoiceFiguresPreviewStored(BaseModel):
    """What a correction restates of the stored invoice it corrects; nothing here is read from storage."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    invoice_id: str = Field(min_length=1, max_length=64)
    grand_total: PublicDecimal
    operation_date_role: str | None = Field(default=None, max_length=128)


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
    business_premises_lease: InvoiceFiguresPreviewLease | None = None
    stored: InvoiceFiguresPreviewStored | None = None

    @model_validator(mode="after")
    def _line_input_shape(self) -> InvoiceFiguresPreviewRequest:
        if self.lines and self.base_total is not None:
            raise ValueError("a draft states lines or a base_total, never both")
        if len({line.key for line in self.lines}) != len(self.lines):
            raise ValueError("draft line keys must be unique")
        if self.stored is not None and self.base_total is None:
            raise ValueError("a stored invoice is corrected on its stored base_total")
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


class InvoiceFiguresPreviewRuleFinding(BaseModel):
    """One closed finding of a rule outside the figures, in the shape of a figure finding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: InvoiceRuleFindingCode
    severity: FigureFindingSeverity = FigureFindingSeverity.REFUSAL
    fields: tuple[str, ...]
    line_key: str | None = None
    values: tuple[PublicNamedScalar, ...] = ()
    label_key: str


class InvoiceFiguresPreviewResult(BaseModel):
    """The backend's whole answer for one draft, bound to it by ``input_digest``.

    ``refusal_code`` keeps its meaning for every draft: a figure's code, or
    ``invalid_invoice`` for a rule outside the figures. ``rule_findings`` names
    those rules and their fields, on an incomplete draft as far as they can be asked.
    """

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
    rule_findings: tuple[InvoiceFiguresPreviewRuleFinding, ...] = ()
    verdict_scope: InvoiceFiguresPreviewVerdictScope = "whole_draft"

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
    "InvoiceFiguresPreviewLease",
    "InvoiceFiguresPreviewLine",
    "InvoiceFiguresPreviewLineResult",
    "InvoiceFiguresPreviewOnDateSource",
    "InvoiceFiguresPreviewRateSlot",
    "InvoiceFiguresPreviewRequest",
    "InvoiceFiguresPreviewResult",
    "InvoiceFiguresPreviewRetention",
    "InvoiceFiguresPreviewRuleFinding",
    "InvoiceFiguresPreviewStored",
    "InvoiceFiguresPreviewTotals",
    "InvoiceFiguresPreviewVerdict",
    "InvoiceFiguresPreviewVerdictScope",
]
