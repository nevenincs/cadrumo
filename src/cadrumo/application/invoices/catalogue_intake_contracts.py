"""Canonical secure request and receipt schemas for invoice intake operations."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import IntracomOperationType
from ...core.field_role import FieldRole
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...domain.iva.schema import InvoiceKind
from ..operator_actions.projection import PreconditionVerdictSnapshot
from .bulk_import_columns import BULK_IMPORT_FIELD_BY_ROLE, ColumnSource
from .catalogue_intake_refusal import (
    InvoiceWizardValidationRefusalProjection,
)
from .catalogue_read_projection import CatalogueInvoiceSnapshot

INVOICE_IMPORT_OPERATION_DEFINITION_ID = "ledger.invoice.import"
INVOICE_WIZARD_OPERATION_DEFINITION_ID = "ledger.invoice.wizard"
INVOICE_IMPORT_MAX_COLUMNS = 512
"""Most columns a request may assign and a preview reports; a wider book is reported as truncated."""
INVOICE_IMPORT_HEADER_MAX_CHARS = 128
"""Longest header a preview reports; a longer one is cut to this many characters."""

type _Text = Annotated[str, Field(max_length=16384)]
type _Header = Annotated[str, Field(max_length=INVOICE_IMPORT_HEADER_MAX_CHARS)]


class InvoiceBookColumnRole(BaseModel):
    """The role the operator assigns to one column of the book, by its zero-based position.

    ``UNMAPPED`` states that the column is not used, which also keeps exact
    matching and the mapping lane from reading it.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    column_index: Annotated[int, Field(ge=0, lt=INVOICE_IMPORT_MAX_COLUMNS)]
    role: FieldRole

    @model_validator(mode="after")
    def _role_the_importer_accepts(self) -> Self:
        if self.role is not FieldRole.UNMAPPED and self.role not in BULK_IMPORT_FIELD_BY_ROLE:
            raise ValueError("invoice import column role is not one the importer accepts")
        return self


class InvoiceImportRequest(BaseModel):
    """Secure reference to the original file, checked before parsing or mapping.

    ``source_sha256`` is the digest a caller expects the file to have. When it
    is given, a file whose bytes differ is refused. When it is absent, the
    operation computes the digest of the bytes it parses and returns it.

    ``column_roles`` is what the operator decided about the book's columns. It
    binds before exact header names and before the mapping lane, which is asked
    only when the stated roles and exact names leave a required field open.
    ``preview`` reads the book and reports how its columns resolve, writing
    nothing; the digest it returns can be sent back to apply the same bytes.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: InvoiceKind
    source_path: Annotated[str, Field(min_length=1, max_length=4096)]
    source_sha256: Hex64Str | None = None
    country: _Text | None = None
    column_roles: Annotated[tuple[InvoiceBookColumnRole, ...], Field(max_length=INVOICE_IMPORT_MAX_COLUMNS)] | None = (
        None
    )
    preview: bool = False

    @model_validator(mode="after")
    def _absolute_reference(self) -> Self:
        if not Path(self.source_path).is_absolute():
            raise ValueError("invoice import source must be an absolute reference")
        return self

    @model_validator(mode="after")
    def _distinct_column_roles(self) -> Self:
        stated = self.column_roles or ()
        indexes = [item.column_index for item in stated]
        roles = [item.role for item in stated if item.role is not FieldRole.UNMAPPED]
        if len(set(indexes)) != len(indexes) or len(set(roles)) != len(roles):
            raise ValueError("invoice import column roles must name each column and each role at most once")
        return self

    @property
    def operator_roles(self) -> dict[int, FieldRole]:
        """The stated roles keyed by column position, empty when none were stated."""
        return {item.column_index: item.role for item in self.column_roles or ()}


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
    #: The facts a factura rectificativa states, as raw text like every other
    #: field here: the wizard accumulates each grammar refusal rather than
    #: stopping at the first, so a mistyped cause and a mistyped date are both
    #: reported in one pass.
    rectification_method: _Text | None = None
    rectification_cause: _Text | None = None
    rectification_direction: _Text | None = None
    document_received_on: _Text | None = None
    recargo_amount: _Text | None = None


class InvoiceImportRowFailure(BaseModel):
    """Every canonical row refusal, retaining its original attribution."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    row_number: Annotated[int, Field(ge=1)]
    field: _Text
    reason: _Text


class InvoiceImportColumn(BaseModel):
    """One source column, the role it resolved to, and who settled that role."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    column_index: Annotated[int, Field(ge=0)]
    header: _Header
    role: FieldRole
    source: ColumnSource


class InvoiceImportAssignableRole(BaseModel):
    """One role the operator may assign, the importer field it feeds, and whether the book needs it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    role: FieldRole
    field: _Text
    required: bool


class InvoiceImportProjection(BaseModel):
    """The whole current import outcome and human mapping disclosures.

    ``source_sha256`` is the digest of the bytes the rows were parsed from,
    which is also what each created invoice records as its source.

    A preview writes nothing: ``rows``, ``created``, ``skipped_duplicate`` and
    ``refused`` stay empty, ``row_count`` counts the data rows read, and
    ``columns``, ``missing_fields`` and ``assignable_roles`` show how the book
    resolved and what the operator may assign. ``reader_unavailable_verdict``
    says why the column-naming model could not be asked when it was needed.
    A book missing a required field is a successful preview, not a refusal.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    source_sha256: Hex64Str
    rows: Annotated[int, Field(ge=0)]
    created: Annotated[int, Field(ge=0)]
    skipped_duplicate: Annotated[int, Field(ge=0)]
    refused: tuple[InvoiceImportRowFailure, ...]
    created_invoice_ids: tuple[Hex64Str, ...]
    unmapped_column_headers: tuple[_Text, ...]
    mapping_reasons: tuple[_Text, ...]
    preview: bool = False
    columns: Annotated[tuple[InvoiceImportColumn, ...], Field(max_length=INVOICE_IMPORT_MAX_COLUMNS)] = ()
    columns_truncated: bool = False
    missing_fields: tuple[_Text, ...] = ()
    assignable_roles: tuple[InvoiceImportAssignableRole, ...] = ()
    row_count: Annotated[int, Field(ge=0)] = 0
    reader_unavailable_verdict: PreconditionVerdictSnapshot | None = None

    @property
    def settled_effect(self) -> OperationEffect:
        """The mutation effect an import receipt must carry for these row facts."""
        return OperationEffect.of_confirmed_writes(wrote=self.created > 0, incomplete=bool(self.refused))

    @model_validator(mode="after")
    def _complete_rows(self) -> Self:
        if self.preview:
            if self.rows or self.created or self.skipped_duplicate or self.refused or self.created_invoice_ids:
                raise ValueError("invoice import preview must not report an import outcome")
            return self
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
    "INVOICE_IMPORT_HEADER_MAX_CHARS",
    "INVOICE_IMPORT_MAX_COLUMNS",
    "INVOICE_IMPORT_OPERATION_DEFINITION_ID",
    "INVOICE_INTAKE_PROJECTION_TYPES",
    "INVOICE_INTAKE_REQUEST_TYPES",
    "INVOICE_WIZARD_OPERATION_DEFINITION_ID",
    "InvoiceBookColumnRole",
    "InvoiceImportAssignableRole",
    "InvoiceImportColumn",
    "InvoiceImportProjection",
    "InvoiceImportRequest",
    "InvoiceImportRowFailure",
    "InvoiceIntakeExecutionResult",
    "InvoiceWizardOutcome",
    "InvoiceWizardProjection",
    "InvoiceWizardRequest",
]
