"""Request and result contracts for one reviewed batch edit of ledger movements.

A batch edit writes a typed property set onto many movements at once. Each row
names the movement, the ``modified_at`` the person saw, and the properties to
write; the preview answers what would happen to each row and a digest of that
answer, and the apply writes only when the plan it finds is the reviewed one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .classify_requests import (
    LedgerClassifyDecimalText,
    LedgerClassifyLongText,
    LedgerClassifyPatch,
    LedgerClassifyShortText,
)

LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID = "ledger.update.batch"
LEDGER_BATCH_UPDATE_PREVIEW_OPERATION_DEFINITION_ID = "ledger.update.batch.preview"
LEDGER_BATCH_UPDATE_PLAN_CHANGED_REFUSAL_CODE = "REFUSED_LEDGER_BATCH_PLAN_CHANGED"
LEDGER_BATCH_UPDATE_MAX_ROWS = 2048
"""The most movements one batch edit request carries: a capacity of the request, not of any form."""
LEDGER_BATCH_UPDATE_MAX_ROW_MESSAGES = 4
LEDGER_BATCH_GROUP_LABEL_MAX = 64

LedgerPropertySetField = Literal[
    "business_classification",
    "business_pct",
    "category_id",
    "usage_ratio_id",
    "iva_category",
    "iva_rate",
    "irpf_category",
    "deduction_fact_kind",
    "exemption_article",
    "counterparty",
    "notes",
    "group_label",
]
LEDGER_PROPERTY_SET_FIELD_NAMES: tuple[LedgerPropertySetField, ...] = (
    "business_classification",
    "business_pct",
    "category_id",
    "usage_ratio_id",
    "iva_category",
    "iva_rate",
    "irpf_category",
    "deduction_fact_kind",
    "exemption_article",
    "counterparty",
    "notes",
    "group_label",
)
"""Every property a batch edit writes, in the order the person reads them."""

LEDGER_PROPERTY_SET_CLASSIFY_FIELD_NAMES = frozenset(
    {
        "business_classification",
        "business_pct",
        "category_id",
        "iva_category",
        "iva_rate",
        "irpf_category",
        "deduction_fact_kind",
        "exemption_article",
        "notes",
    }
)
"""The properties resolved against the pinned catalogues as a classification resolves them."""

LEDGER_PROPERTY_SET_UNCLEARABLE_FIELD_NAMES = frozenset({"business_classification", "notes"})
"""Properties a batch edit may replace but never blank."""

LedgerBatchRowOutcome = Literal["applied", "unchanged", "refused", "conflict"]
LedgerBatchRowCause = Literal["changed_since_seen", "not_found", "not_active", "sealed", "invalid"]
"""Why a row was not written: ``conflict`` carries the first two, ``refused`` the others."""

_PropertyFields = Annotated[
    tuple[LedgerPropertySetField, ...], Field(min_length=1, max_length=len(LEDGER_PROPERTY_SET_FIELD_NAMES))
]
_TransactionId = Annotated[str, Field(min_length=1, max_length=128)]
_Timestamp = Annotated[str, Field(min_length=1, max_length=64)]
_Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
_Message = Annotated[str, Field(min_length=1, max_length=2048)]


class LedgerPropertySet(BaseModel):
    """The typed property values one movement takes, or one movement held, as text.

    ``fields`` names the properties the set carries; a selected property whose
    value is null clears it, and every unselected value must be null. This is
    also what the window copies from one movement and pastes onto others.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    fields: _PropertyFields
    business_classification: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    business_pct: LedgerClassifyDecimalText | None = None
    category_id: LedgerClassifyShortText | None = None
    usage_ratio_id: LedgerClassifyShortText | None = None
    iva_category: LedgerClassifyShortText | None = None
    iva_rate: LedgerClassifyDecimalText | None = None
    irpf_category: LedgerClassifyLongText | None = None
    deduction_fact_kind: LedgerClassifyShortText | None = None
    exemption_article: LedgerClassifyShortText | None = None
    counterparty: LedgerClassifyLongText | None = None
    notes: LedgerClassifyLongText | None = None
    group_label: Annotated[str, Field(max_length=LEDGER_BATCH_GROUP_LABEL_MAX)] | None = None

    @field_validator("fields")
    @classmethod
    def _unique_fields(cls, value: tuple[LedgerPropertySetField, ...]) -> tuple[LedgerPropertySetField, ...]:
        if len(set(value)) != len(value):
            raise ValueError("a property set names each property once")
        return tuple(name for name in LEDGER_PROPERTY_SET_FIELD_NAMES if name in value)

    @model_validator(mode="after")
    def _selected_values_only(self) -> LedgerPropertySet:
        selected = set(self.fields)
        for name in LEDGER_PROPERTY_SET_FIELD_NAMES:
            if name not in selected and getattr(self, name) is not None:
                raise ValueError(f"property set carries an unselected value for {name}")
        return self

    def classify_patch(self) -> LedgerClassifyPatch:
        """Return the selected classification values as the patch a classification validates."""
        return LedgerClassifyPatch.model_validate(
            {
                name: getattr(self, name)
                for name in self.fields
                if name in LEDGER_PROPERTY_SET_CLASSIFY_FIELD_NAMES and getattr(self, name) is not None
            }
        )


class LedgerBatchUpdateRow(BaseModel):
    """One movement, the ``modified_at`` the person saw on it, and what to write."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: _TransactionId
    expected_modified_at: _Timestamp
    properties: LedgerPropertySet

    @field_validator("expected_modified_at")
    @classmethod
    def _aware_instant(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError("expected_modified_at must be the movement's ISO-8601 modified_at") from None
        if parsed.tzinfo is None:
            raise ValueError("expected_modified_at must carry its UTC offset")
        return value

    def expected_modified_instant(self) -> datetime:
        """Return the seen ``modified_at`` as an instant."""
        return datetime.fromisoformat(self.expected_modified_at)


_Rows = Annotated[tuple[LedgerBatchUpdateRow, ...], Field(min_length=1, max_length=LEDGER_BATCH_UPDATE_MAX_ROWS)]


def _require_unique_rows(rows: tuple[LedgerBatchUpdateRow, ...]) -> tuple[LedgerBatchUpdateRow, ...]:
    if len({row.transaction_id for row in rows}) != len(rows):
        raise ValueError("a batch edit names each movement once")
    return rows


class LedgerBatchUpdatePreviewRequest(BaseModel):
    """Private exact-profile request for what a batch edit would do, writing nothing.

    ``output_language`` is the language the row refusals are said in.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    rows: _Rows
    output_language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE

    @field_validator("rows")
    @classmethod
    def _unique_rows(cls, value: tuple[LedgerBatchUpdateRow, ...]) -> tuple[LedgerBatchUpdateRow, ...]:
        return _require_unique_rows(value)


class LedgerBatchUpdateRequest(BaseModel):
    """Private exact-profile request to write the reviewed batch edit.

    ``reviewed_plan_digest`` is the digest the preview of exactly these rows
    answered; the edit is refused, writing nothing, when the plan it finds
    differs. ``actor`` is recorded as sent for a person's session; an
    automation's session is recorded under its own session label.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    rows: _Rows
    reviewed_plan_digest: _Digest
    actor: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    output_language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE

    @field_validator("rows")
    @classmethod
    def _unique_rows(cls, value: tuple[LedgerBatchUpdateRow, ...]) -> tuple[LedgerBatchUpdateRow, ...]:
        return _require_unique_rows(value)


class LedgerBatchRowResult(BaseModel):
    """What the batch edit does, or did, to one named movement.

    ``previous`` holds the values the movement had for the written properties,
    so an undo writes them back as a new correction. ``modified_at`` is the
    movement's stamp after the edit (or as found, when nothing was written).
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: _TransactionId
    outcome: LedgerBatchRowOutcome
    cause: LedgerBatchRowCause | None = None
    messages: Annotated[tuple[_Message, ...], Field(max_length=LEDGER_BATCH_UPDATE_MAX_ROW_MESSAGES)] = ()
    changed_fields: Annotated[
        tuple[LedgerPropertySetField, ...], Field(max_length=len(LEDGER_PROPERTY_SET_FIELD_NAMES))
    ] = ()
    previous: LedgerPropertySet | None = None
    result_transaction_id: _TransactionId | None = None
    modified_at: _Timestamp | None = None

    @model_validator(mode="after")
    def _outcome_matches_cause(self) -> LedgerBatchRowResult:
        if self.outcome in {"applied", "unchanged"}:
            if self.cause is not None or self.messages:
                raise ValueError("a written or unchanged row carries no refusal")
            if (self.outcome == "applied") != bool(self.changed_fields):
                raise ValueError("an applied row names what it changed, an unchanged one nothing")
            if self.previous is None or self.result_transaction_id is None or self.modified_at is None:
                raise ValueError("a written or unchanged row carries its previous values and stamp")
        else:
            conflict = self.cause in {"changed_since_seen", "not_found"}
            if self.cause is None or conflict != (self.outcome == "conflict"):
                raise ValueError("a refused or conflicting row carries its own kind of cause")
            if self.changed_fields or self.previous is not None or self.result_transaction_id is not None:
                raise ValueError("a row that is not written carries no change")
        return self


class LedgerBatchCounts(BaseModel):
    """How many rows took each outcome."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    applied: Annotated[int, Field(ge=0)]
    unchanged: Annotated[int, Field(ge=0)]
    refused: Annotated[int, Field(ge=0)]
    conflict: Annotated[int, Field(ge=0)]


def batch_counts(rows: tuple[LedgerBatchRowResult, ...]) -> LedgerBatchCounts:
    """Count the rows of each outcome."""
    return LedgerBatchCounts(
        applied=sum(row.outcome == "applied" for row in rows),
        unchanged=sum(row.outcome == "unchanged" for row in rows),
        refused=sum(row.outcome == "refused" for row in rows),
        conflict=sum(row.outcome == "conflict" for row in rows),
    )


class LedgerBatchUpdateResult(BaseModel):
    """The per-row plan or outcome of a batch edit.

    ``outcome`` is ``previewed`` for a preview, ``applied`` once the plan was
    written (even where no row changed), and ``plan_changed`` when the apply
    found a plan other than the reviewed one and wrote nothing; ``rows`` then
    holds the plan it found, to review again.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    outcome: Literal["previewed", "applied", "plan_changed"]
    plan_digest: _Digest
    rows: Annotated[tuple[LedgerBatchRowResult, ...], Field(min_length=1, max_length=LEDGER_BATCH_UPDATE_MAX_ROWS)]
    counts: LedgerBatchCounts
    bucket_event_ids: Annotated[tuple[str, ...], Field(max_length=4 * LEDGER_BATCH_UPDATE_MAX_ROWS)] = ()

    @model_validator(mode="after")
    def _complete_outcome(self) -> LedgerBatchUpdateResult:
        if self.counts != batch_counts(self.rows):
            raise ValueError("a batch result counts every row it carries")
        if self.outcome != "applied" and self.bucket_event_ids:
            raise ValueError("only an applied batch records events")
        if self.outcome == "applied" and bool(self.bucket_event_ids) != bool(self.counts.applied):
            raise ValueError("an applied batch records events exactly when a row changed")
        return self


class LedgerBatchUpdateExecutionResult(BaseModel):
    """Encrypted worker operand holding the exact-profile batch result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: LedgerBatchUpdateResult


__all__ = [
    "LEDGER_BATCH_UPDATE_MAX_ROWS",
    "LEDGER_BATCH_UPDATE_MAX_ROW_MESSAGES",
    "LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID",
    "LEDGER_BATCH_UPDATE_PLAN_CHANGED_REFUSAL_CODE",
    "LEDGER_BATCH_UPDATE_PREVIEW_OPERATION_DEFINITION_ID",
    "LEDGER_PROPERTY_SET_CLASSIFY_FIELD_NAMES",
    "LEDGER_PROPERTY_SET_FIELD_NAMES",
    "LEDGER_PROPERTY_SET_UNCLEARABLE_FIELD_NAMES",
    "LedgerBatchCounts",
    "LedgerBatchRowCause",
    "LedgerBatchRowOutcome",
    "LedgerBatchRowResult",
    "LedgerBatchUpdateExecutionResult",
    "LedgerBatchUpdatePreviewRequest",
    "LedgerBatchUpdateRequest",
    "LedgerBatchUpdateResult",
    "LedgerBatchUpdateRow",
    "LedgerPropertySet",
    "LedgerPropertySetField",
    "batch_counts",
]
