"""Canonical secure request and receipt schemas for invoice intake operations."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import IntracomOperationType
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.iva.classification import InvoiceKind
from .catalogue_intake_refusal import (
    InvoiceWizardValidationRefusalProjection,
)
from .catalogue_read_projection import CatalogueInvoiceSnapshot

INVOICE_IMPORT_OPERATION_DEFINITION_ID = "ledger.invoice.import"
INVOICE_WIZARD_OPERATION_DEFINITION_ID = "ledger.invoice.wizard"
type _Text = Annotated[str, Field(max_length=16384)]

INVOICE_IMPORT_OPERATION_DEFINITION_ID = "ledger.invoice.import"


INVOICE_WIZARD_OPERATION_DEFINITION_ID = "ledger.invoice.wizard"


class InvoiceImportRequest(BaseModel):
    """Secure reference to the original file, checked before parsing or mapping."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: InvoiceKind
    source_path: Annotated[str, Field(min_length=1, max_length=4096)]
    source_sha256: Hex64Str
    country: _Text | None = None

    @model_validator(mode="after")
    def _absolute_reference(self) -> Self:
        if not Path(self.source_path).is_absolute():
            raise ValueError("invoice import source must be an absolute reference")
        return self


class InvoiceWizardRequest(BaseModel):
    """Original raw fields; the owning wizard accumulates all grammar refusals."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: InvoiceKind
    counterparty_nif: _Text
    counterparty_name: _Text
    invoice_number: _Text
    invoice_date: _Text
    taxable_base: _Text
    iva_rate: _Text | None
    currency: _Text
    country_code: _Text
    operation_date: _Text | None = None
    notes: _Text = ""
    iva_category: _Text | None = None
    operation_type: IntracomOperationType | None = None
    retention_rate: _Text | None = None
    retention_amount: _Text | None = None
    invoice_class: _Text | None = None
    series: _Text | None = None
    rectifies_invoice_number: _Text | None = None
    recargo_amount: _Text | None = None


class InvoiceImportRowFailure(BaseModel):
    """Every canonical row refusal, retaining its original attribution."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    row_number: Annotated[int, Field(ge=1)]
    field: _Text
    reason: _Text


class InvoiceImportProjection(BaseModel):
    """The whole current import outcome and human mapping disclosures."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    rows: Annotated[int, Field(ge=0)]
    created: Annotated[int, Field(ge=0)]
    skipped_duplicate: Annotated[int, Field(ge=0)]
    refused: tuple[InvoiceImportRowFailure, ...]
    created_invoice_ids: tuple[Hex64Str, ...]
    unmapped_column_headers: tuple[_Text, ...]
    mapping_reasons: tuple[_Text, ...]

    @model_validator(mode="after")
    def _complete_rows(self) -> Self:
        if (
            self.rows != self.created + self.skipped_duplicate + len(self.refused)
            or self.created != len(self.created_invoice_ids)
            or len(set(self.created_invoice_ids)) != self.created
        ):
            raise ValueError("invoice import outcome does not account for every row")
        return self


class InvoiceWizardProjection(BaseModel):
    """Complete canonical invoice readback and guarded no-op notice fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    invoice: CatalogueInvoiceSnapshot
    already_existed: bool
    euro_value_pending: bool

    @model_validator(mode="after")
    def _owning_profile(self) -> Self:
        if str(self.invoice.bucket_id) != str(self.profile_id):
            raise ValueError("wizard invoice belongs to another profile")
        return self


class InvoiceWizardOutcome(BaseModel):
    """Closed success or ordered canonical field refusal for one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    outcome: Literal["succeeded", "refused"]
    result: InvoiceWizardProjection | None = None
    refusal: InvoiceWizardValidationRefusalProjection | None = None

    @model_validator(mode="after")
    def _complete_owning_outcome(self) -> Self:
        if self.outcome == "succeeded":
            if self.result is None or self.refusal is not None or self.result.profile_id != self.profile_id:
                raise ValueError("wizard success requires its owning result")
        elif self.refusal is None or self.result is not None or self.refusal.profile_id != self.profile_id:
            raise ValueError("wizard refusal requires its owning field errors")
        return self


class InvoiceIntakeExecutionResult(BaseModel):
    """Private outcome correlated with the operation's actual mutation receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: InvoiceImportProjection | InvoiceWizardOutcome
    effect: Literal["none", "updated", "partial"]


INVOICE_INTAKE_REQUEST_TYPES = {
    INVOICE_IMPORT_OPERATION_DEFINITION_ID: InvoiceImportRequest,
    INVOICE_WIZARD_OPERATION_DEFINITION_ID: InvoiceWizardRequest,
}


INVOICE_INTAKE_PROJECTION_TYPES = {
    INVOICE_IMPORT_OPERATION_DEFINITION_ID: InvoiceImportProjection,
    INVOICE_WIZARD_OPERATION_DEFINITION_ID: InvoiceWizardOutcome,
}


__all__ = [
    "INVOICE_IMPORT_OPERATION_DEFINITION_ID",
    "INVOICE_INTAKE_PROJECTION_TYPES",
    "INVOICE_INTAKE_REQUEST_TYPES",
    "INVOICE_WIZARD_OPERATION_DEFINITION_ID",
    "InvoiceImportProjection",
    "InvoiceImportRequest",
    "InvoiceImportRowFailure",
    "InvoiceIntakeExecutionResult",
    "InvoiceWizardOutcome",
    "InvoiceWizardProjection",
    "InvoiceWizardRequest",
]
