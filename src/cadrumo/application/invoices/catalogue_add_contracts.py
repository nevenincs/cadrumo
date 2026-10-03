"""Canonical private requests and public receipts for registered invoice addition."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import IntracomOperationType
from ...core.country_code import CountryCodeAlpha2
from ...core.errors.hierarchy import CadrumoError
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.iva_rate_kind_catalogue import IvaRateKindCatalogue
from ...domain.invoices.enums import IvaRate
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.invoices.models import InvoiceLine, SituacionInmueble
from ...domain.iva.classification import InvoiceKind
from ...domain.iva.schema import IvaRateKind
from ..operations.models import OperationTerminalReceipt, require_succeeded_receipt_references
from ..operations.public_scalar import PublicDecimal
from .catalogue_read_projection import CatalogueInvoiceSnapshot

INVOICE_ADD_OPERATION_DEFINITION_ID = "ledger.invoice.add"
INVOICE_ADD_VALIDATION_REFUSAL_CODE = "REFUSED_INVOICE_ADD_VALIDATION"


class InvoiceAddValidationRefusedError(CadrumoError):
    """An invoice the add operation refused as invalid or duplicate.

    The executor records this refusal as operation evidence under
    :data:`INVOICE_ADD_VALIDATION_REFUSAL_CODE`; this class is that code's
    registered failure, so the code resolves to its category and message.
    """


class InvoiceAddLine(BaseModel):
    """Closed JSON-safe line input resolved into a dated canonical line by the worker."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    description: str = Field(min_length=1, max_length=4096)
    quantity: PublicDecimal
    unit_price: PublicDecimal
    subtotal: PublicDecimal
    iva_rate: str = Field(min_length=1, max_length=128)
    iva_amount: PublicDecimal
    spending_category_id: str | None = Field(default=None, max_length=128)
    oss_rate_kind: str | None = Field(default=None, max_length=128)

    @classmethod
    def from_invoice_line(cls, line: InvoiceLine) -> InvoiceAddLine:
        """Copy one parsed CLI line into its closed secure-reference wire form."""
        return cls(
            description=line.description,
            quantity=PublicDecimal(decimal=str(line.quantity)),
            unit_price=PublicDecimal(decimal=str(line.unit_price)),
            subtotal=PublicDecimal(decimal=str(line.subtotal)),
            iva_rate=str(line.iva_rate),
            iva_amount=PublicDecimal(decimal=str(line.iva_amount)),
            spending_category_id=line.spending_category_id,
            oss_rate_kind=None if line.oss_rate_kind is None else str(line.oss_rate_kind),
        )

    def to_invoice_line(
        self,
        *,
        rate_slots: tuple[IvaRate, ...],
        rate_kind_catalogue: IvaRateKindCatalogue | None,
    ) -> InvoiceLine:
        """Project tokens from already-resolved catalogues and refuse unknown input."""
        iva_rate = next((slot for slot in rate_slots if str(slot) == self.iva_rate), None)
        if iva_rate is None:
            raise InvoiceValidationError("invoice line IVA rate is not declared by the active registry")
        oss_rate_kind: IvaRateKind | None = None
        if self.oss_rate_kind is not None:
            normalized_kind = self.oss_rate_kind.strip()
            oss_rate_kind = (
                None
                if rate_kind_catalogue is None
                else next(
                    (
                        definition.token
                        for definition in rate_kind_catalogue.definitions
                        if str(definition.token) == normalized_kind
                    ),
                    None,
                )
            )
            if oss_rate_kind is None:
                raise InvoiceValidationError("invoice line OSS rate kind is not declared by the active registry")
        return InvoiceLine(
            description=self.description,
            quantity=Decimal(self.quantity.decimal),
            unit_price=Decimal(self.unit_price.decimal),
            subtotal=Decimal(self.subtotal.decimal),
            iva_rate=iva_rate,
            iva_amount=Decimal(self.iva_amount.decimal),
            spending_category_id=self.spending_category_id,
            oss_rate_kind=oss_rate_kind,
        )


class InvoiceAddRequest(BaseModel):
    """Private exact-profile request matching the rich direct-add command."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    kind: InvoiceKind
    counterparty_name: str = Field(min_length=1)
    counterparty_tax_id: str | None = None
    counterparty_country: CountryCodeAlpha2
    invoice_number: str = Field(min_length=1)
    issued_at: date
    taxable_base: PublicDecimal | None = None
    iva_rate: PublicDecimal | None = None
    currency: str = Field(min_length=1, max_length=16)
    notes: str = ""
    iva_category: str | None = Field(default=None, min_length=1, max_length=128)
    operation_type: IntracomOperationType | None = None
    operation_date: date | None = None
    retention_rate: PublicDecimal | None = None
    retention_amount: PublicDecimal | None = None
    invoice_class: str | None = Field(default=None, min_length=1, max_length=64)
    series: str | None = None
    rectifies_invoice_number: str | None = None
    recargo_amount: PublicDecimal | None = None
    arrendamiento_local_negocio: bool = False
    situacion_inmueble: SituacionInmueble | None = None
    referencia_catastral: str | None = Field(default=None, min_length=1, max_length=25)
    lines: tuple[InvoiceAddLine, ...] = ()

    @model_validator(mode="after")
    def _line_input_shape(self) -> InvoiceAddRequest:
        if self.lines and (self.taxable_base is not None or self.iva_rate is not None):
            raise ValueError("structured invoice lines cannot be combined with taxable_base or iva_rate")
        if not self.lines and self.taxable_base is None:
            raise ValueError("taxable_base is required when structured invoice lines are not supplied")
        return self


class InvoiceAddResult(BaseModel):
    """Safe creation receipt or bounded pre-write refusal detail."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["created", "validation_error"]
    profile_id: UUID
    invoice: CatalogueInvoiceSnapshot | None = None
    invoice_id: str | None = None
    bucket_event_ids: tuple[str, ...] = Field(default=(), max_length=1)
    euro_value_pending: bool = False
    simplificada_tax_id_advisory_required: bool = False
    validation_code: Literal["invalid_invoice", "duplicate_invoice"] | None = None

    @model_validator(mode="after")
    def _complete_outcome(self) -> InvoiceAddResult:
        if self.outcome == "created":
            _require_created_invoice_result(self)
        else:
            _require_invoice_validation_refusal(self)
        return self

    @classmethod
    def validation_refusal(
        cls,
        profile_id: UUID,
        *,
        code: Literal["invalid_invoice", "duplicate_invoice"],
        invoice_id: str | None = None,
    ) -> InvoiceAddResult:
        """Build a safe detail for a deterministic refusal before invoice creation."""
        return cls(
            outcome="validation_error",
            profile_id=profile_id,
            invoice_id=invoice_id,
            validation_code=code,
        )

    @classmethod
    def created(
        cls,
        profile_id: UUID,
        *,
        invoice: CatalogueInvoiceSnapshot,
        bucket_event_ids: tuple[str, ...],
        euro_value_pending: bool,
        simplificada_tax_id_advisory_required: bool,
    ) -> InvoiceAddResult:
        """Build a successful invoice receipt with worker-resolved advisories."""
        return cls(
            outcome="created",
            profile_id=profile_id,
            invoice=invoice,
            bucket_event_ids=bucket_event_ids,
            euro_value_pending=euro_value_pending,
            simplificada_tax_id_advisory_required=simplificada_tax_id_advisory_required,
        )


class InvoiceAddExecutionResult(BaseModel):
    """Private secure operand whose public value is correlated with settlement."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: InvoiceAddResult


def project_invoice_add_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> InvoiceAddResult:
    """Release only a created invoice or a typed validation refusal with a matching receipt."""
    if type(result) is not InvoiceAddExecutionResult:
        raise ValueError("invalid invoice-add execution result")
    private = InvoiceAddExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)
    public = private.result
    _require_invoice_add_receipt_envelope(receipt, public)
    if public.outcome == "created":
        _require_invoice_add_success_receipt(receipt)
    else:
        _require_invoice_add_refusal_receipt(receipt, public)
    return public


def _require_created_invoice_result(result: InvoiceAddResult) -> None:
    if (
        result.invoice is None
        or result.invoice.bucket_id is None
        or str(result.invoice.bucket_id) != str(result.profile_id)
        or len(result.bucket_event_ids) != 1
        or result.invoice_id is not None
        or result.validation_code is not None
    ):
        raise ValueError("created invoice result is incomplete or belongs to another profile")


def _require_invoice_validation_refusal(result: InvoiceAddResult) -> None:
    if (
        result.invoice is not None
        or result.bucket_event_ids
        or result.euro_value_pending
        or result.simplificada_tax_id_advisory_required
        or result.validation_code is None
        or (result.validation_code == "duplicate_invoice") != (result.invoice_id is not None)
    ):
        raise ValueError("invoice validation refusal detail is incomplete")


def _require_invoice_add_receipt_envelope(receipt: OperationTerminalReceipt, result: InvoiceAddResult) -> None:
    if (
        receipt.identity.definition_id != INVOICE_ADD_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(result.profile_id))
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("invoice-add result differs from its terminal receipt")


def _require_invoice_add_success_receipt(receipt: OperationTerminalReceipt) -> None:
    message = "invoice-add success has an incompatible terminal receipt"
    if receipt.condition is not OperationTerminalCondition.SUCCEEDED or receipt.effect is not OperationEffect.UPDATED:
        raise ValueError(message)
    require_succeeded_receipt_references(receipt, message=message)


def _require_invoice_add_refusal_receipt(receipt: OperationTerminalReceipt, result: InvoiceAddResult) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_ref != INVOICE_ADD_VALIDATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.result_ref is not None
        or result.validation_code is None
    ):
        raise ValueError("invoice-add refusal has an incompatible terminal receipt")


__all__ = [
    "INVOICE_ADD_OPERATION_DEFINITION_ID",
    "INVOICE_ADD_VALIDATION_REFUSAL_CODE",
    "InvoiceAddExecutionResult",
    "InvoiceAddLine",
    "InvoiceAddRequest",
    "InvoiceAddResult",
    "InvoiceAddValidationRefusedError",
    "project_invoice_add_result",
]
