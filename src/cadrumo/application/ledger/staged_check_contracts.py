"""Typed request and answer of the read that checks staged ledger work."""

from __future__ import annotations

from typing import Annotated, Final, Literal, get_args
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.transactions.classification_effects import LifecycleAction
from ..operations.error_detail import MAX_OPERATION_ERROR_WORDS_LENGTH

LEDGER_STAGED_CHECK_OPERATION_DEFINITION_ID: Final = "ledger.staged.check"

# A review can hold every movement a profile has loaded, and each row is short.
_MAX_DRAFTS: Final = 1_024
_MAX_CATEGORIES: Final = 256

StageFieldName = Literal[
    "booked_date",
    "value_date",
    "operation_date",
    "accrual_date",
    "amount",
    "direction",
    "currency",
    "counterparty",
    "description",
    "group_label",
    "own_account_id",
    "business_classification",
    "business_pct",
    "category_id",
    "usage_ratio_id",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "iva_category",
    "irpf_category",
    "notes",
    "deduction_fact_kind",
    "investment_asset_id",
    "counterparty_country",
    "counterparty_identification_state",
]

DraftFieldName = Literal[
    "booked_date",
    "value_date",
    "operation_date",
    "accrual_date",
    "amount",
    "direction",
    "currency",
    "counterparty",
    "description",
    "group_label",
    "own_account_id",
    "business_classification",
    "business_pct",
    "category_id",
    "usage_ratio_id",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "iva_category",
    "irpf_category",
    "recargo_amount",
    "notes",
    "deduction_fact_kind",
    "investment_asset_id",
    "counterparty_country",
    "counterparty_identification_state",
]

WriteRoute = Literal["bulk", "classify", "update"]
RouteRefusal = Literal["cannot_clear", "needs_classification"]
TaxSetSkip = Literal["transfer", "personal"]
StagedBlockerKind = Literal[
    "cannot_clear",
    "needs_classification",
    "mixed_needs_share",
    "share_needs_mixed",
    "transfer_with_tax",
    "draft_incomplete",
    "amount_signed",
    "needs_withholding_category",
]

_Text = Annotated[str, Field(max_length=4096)]
_Key = Annotated[str, Field(min_length=1, max_length=128)]


class LedgerStagedCell(BaseModel):
    """One staged change: a value to set, or a clear when ``value`` is null."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    field: StageFieldName
    value: _Text | None = None


class LedgerStagedRow(BaseModel):
    """One stored movement, read as it would be once its staged work is saved."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: _Key
    cells: Annotated[tuple[LedgerStagedCell, ...], Field(max_length=len(get_args(StageFieldName)))] = ()
    evidence_staged: bool = False
    m210_staged: bool = False

    @model_validator(mode="after")
    def _one_cell_per_field(self) -> LedgerStagedRow:
        if len({cell.field for cell in self.cells}) != len(self.cells):
            raise ValueError("a staged row states each field once")
        return self


class LedgerStagedDraftField(BaseModel):
    """One field typed on a new movement."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    field: DraftFieldName
    value: _Text


class LedgerStagedDraft(BaseModel):
    """One new movement not stored yet."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: _Key
    fields: Annotated[tuple[LedgerStagedDraftField, ...], Field(max_length=len(get_args(DraftFieldName)))] = ()


class LedgerStagedCheckRequest(BaseModel):
    """Staged work and the movements asked about, plus the categories to judge a classification against."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    rows: Annotated[tuple[LedgerStagedRow, ...], Field(max_length=50_000)] = ()
    drafts: Annotated[tuple[LedgerStagedDraft, ...], Field(max_length=_MAX_DRAFTS)] = ()
    categories: Annotated[tuple[_Key, ...], Field(max_length=_MAX_CATEGORIES)] = ()
    output_language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE
    """The language the answer's sentences are said in."""


class LedgerStagedRoute(BaseModel):
    """Where one staged cell goes, or why it can go nowhere."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    field: StageFieldName
    route: WriteRoute | None
    refused: RouteRefusal | None


class LedgerStagedBlocker(BaseModel):
    """Why a movement's staged work cannot be sent as it stands."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: StagedBlockerKind
    fields: tuple[str, ...] = ()
    words: Annotated[str, Field(min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)]
    """The sentence saying why the staged work cannot be sent; it names no field, value or command option."""
    fix_words: Annotated[str, Field(min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)]
    """The sentence saying what puts it right."""
    words_language: OutputLanguage


class LedgerStagedNote(BaseModel):
    """What sending the work carries along without holding it back."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["sends_current_classification", "sends_current_share", "new_identity"]
    value: str | None = None
    fields: tuple[str, ...] = ()


class LedgerStagedRowAnswer(BaseModel):
    """The backend's answer for one movement as staged."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: str
    found: bool
    classified: bool = False
    takes_expense_category: bool = False
    takes_share: bool = False
    category_askable: bool = False
    category_settable: bool = False
    category_on_income: bool = False
    takes_changes: bool = False
    takes_invoice: bool = False
    evidence_advised: bool = False
    lifecycle_actions: tuple[LifecycleAction, ...] = ()
    tax_set_skip: TaxSetSkip | None = None
    transfer_locked_fields: tuple[StageFieldName, ...] = ()
    classifying_fields: tuple[StageFieldName, ...] = ()
    identity_fields: tuple[StageFieldName, ...] = ()
    routes: tuple[LedgerStagedRoute, ...] = ()
    blockers: tuple[LedgerStagedBlocker, ...] = ()
    notes: tuple[LedgerStagedNote, ...] = ()


class LedgerStagedDraftAnswer(BaseModel):
    """The backend's answer for one new movement."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: str
    takes_expense_category: bool = False
    blockers: tuple[LedgerStagedBlocker, ...] = ()


class LedgerStagedCategoryFit(BaseModel):
    """Which classifications may name this category."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    category: str
    business: bool
    mixed: bool


class LedgerStagedCheckResult(BaseModel):
    """The answer to one request, identified by the digest of its canonical form."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    input_digest: str
    rows: tuple[LedgerStagedRowAnswer, ...]
    drafts: tuple[LedgerStagedDraftAnswer, ...]
    categories: tuple[LedgerStagedCategoryFit, ...]
    share_refusal_words: Annotated[str, Field(min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)]
    """The sentence a window shows beside a business share it could not read as a percentage."""
    share_refusal_words_language: OutputLanguage


class LedgerStagedCheckExecutionResult(BaseModel):
    """Private result kept in the worker's encrypted operation record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: LedgerStagedCheckResult


__all__ = [
    "LEDGER_STAGED_CHECK_OPERATION_DEFINITION_ID",
    "DraftFieldName",
    "LedgerStagedBlocker",
    "LedgerStagedCategoryFit",
    "LedgerStagedCell",
    "LedgerStagedCheckExecutionResult",
    "LedgerStagedCheckRequest",
    "LedgerStagedCheckResult",
    "LedgerStagedDraft",
    "LedgerStagedDraftAnswer",
    "LedgerStagedDraftField",
    "LedgerStagedNote",
    "LedgerStagedRoute",
    "LedgerStagedRow",
    "LedgerStagedRowAnswer",
    "RouteRefusal",
    "StageFieldName",
    "StagedBlockerKind",
    "TaxSetSkip",
    "WriteRoute",
]
