"""Canonical request and bounded result contracts for ledger updates."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.parsing.codes import normalise_iso_4217_currency
from ...core.parsing.dates import parse_iso8601_date
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.own_accounts import OwnAccountId
from ..review.filter import LedgerReviewStatus
from .actions_common import display_decimal
from .transaction_projection import LedgerTransactionProjection

LEDGER_UPDATE_OPERATION_DEFINITION_ID = "ledger.update"
LEDGER_UPDATE_PHASE = "ledger.update"
LEDGER_UPDATE_VALIDATION_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"
_MAX_UPDATE_EVENT_IDS = 3
LEDGER_UPDATE_MAX_VALIDATION_MESSAGES = 32
LEDGER_UPDATE_FIELD_NAMES = frozenset(
    {
        "booked_date",
        "value_date",
        "amount",
        "direction",
        "currency",
        "counterparty",
        "description",
        "taxable_base",
        "iva_rate",
        "iva_amount",
        "irpf_category",
        "notes",
        "group_label",
        "own_account_id",
    }
)
LedgerUpdatePatchField = Literal[
    "booked_date",
    "value_date",
    "amount",
    "direction",
    "currency",
    "counterparty",
    "description",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "irpf_category",
    "notes",
    "group_label",
    "own_account_id",
]
_UpdateFields = Annotated[tuple[LedgerUpdatePatchField, ...], Field(min_length=1, max_length=14)]
_UpdateText = Annotated[str, Field(max_length=4096)]
_DecimalText = Annotated[str, Field(min_length=1, max_length=128)]
_IsoDateText = Annotated[str, Field(min_length=10, max_length=10)]
_TransactionPrefix = Annotated[str, Field(min_length=1, max_length=96)]
_ValidationMessage = Annotated[str, Field(min_length=1, max_length=2048)]
LedgerUpdateValidationMessages = Annotated[
    tuple[_ValidationMessage, ...], Field(max_length=LEDGER_UPDATE_MAX_VALIDATION_MESSAGES)
]


class LedgerUpdatePatch(BaseModel):
    """Bounded worker request values for the fields exposed by ``ledger update``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    booked_date: _IsoDateText | None = None
    value_date: _IsoDateText | None = None
    amount: _DecimalText | None = None
    direction: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    currency: Annotated[str, Field(min_length=3, max_length=3)] | None = None
    counterparty: _UpdateText | None = None
    description: _UpdateText | None = None
    taxable_base: _DecimalText | None = None
    iva_rate: _DecimalText | None = None
    iva_amount: _DecimalText | None = None
    irpf_category: _UpdateText | None = None
    notes: _UpdateText | None = None
    group_label: Annotated[str, Field(max_length=64)] | None = None
    own_account_id: OwnAccountId | None = None

    @field_validator("booked_date", "value_date")
    @classmethod
    def _iso_dates(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = parse_iso8601_date(value)
        except ValueError:
            raise ValueError("ledger update dates must use YYYY-MM-DD") from None
        if parsed is None or parsed.isoformat() != value:
            raise ValueError("ledger update dates must use YYYY-MM-DD")
        return value

    @field_validator("amount", "taxable_base", "iva_rate", "iva_amount")
    @classmethod
    def _canonical_decimal_text(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        field_name = info.field_name or ""
        parsed = try_parse_canonical_decimal(value, signed=field_name != "amount")
        if parsed is None:
            raise ValueError("ledger update decimal values must use canonical decimal text")
        if display_decimal(parsed) != value:
            raise ValueError("ledger update decimal values must use canonical decimal text")
        return value

    @field_validator("direction")
    @classmethod
    def _known_direction(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            TransactionDirection(value)
        except ValueError:
            raise ValueError("ledger update direction must be a canonical transaction direction") from None
        return value

    @field_validator("currency")
    @classmethod
    @pydantic_validation_boundary
    def _canonical_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalise_iso_4217_currency(value)
        if normalized != value:
            raise ValueError("ledger update currency must be canonical ISO 4217 text")
        return value


class LedgerUpdateRequest(BaseModel):
    """Private exact-profile request; ``transaction_id`` may be a CLI prefix.

    ``patch_fields`` preserves explicit ``None`` clears across JSON serialization.
    Nested defaults serialize as null, so every unselected value must be null;
    that rule makes the mask a safe omission equivalent after worker decode.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: _TransactionPrefix
    patch: LedgerUpdatePatch
    patch_fields: _UpdateFields
    actor: Annotated[str, Field(min_length=1, max_length=64)] | None = None

    @field_validator("patch_fields")
    @classmethod
    def _unique_supported_patch_fields(
        cls,
        value: tuple[LedgerUpdatePatchField, ...],
    ) -> tuple[LedgerUpdatePatchField, ...]:
        if len(set(value)) != len(value) or not set(value) <= LEDGER_UPDATE_FIELD_NAMES:
            raise ValueError("ledger update patch fields must be unique supported fields")
        return value

    @model_validator(mode="after")
    def _reject_unselected_patch_values(self) -> LedgerUpdateRequest:
        selected = set(self.patch_fields)
        if any(getattr(self.patch, field_name) is not None for field_name in LEDGER_UPDATE_FIELD_NAMES - selected):
            raise ValueError("ledger update request contains an unselected patch value")
        return self


class LedgerUpdateOperationResult(BaseModel):
    """Bounded success projection or field-safe update validation refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["updated", "validation_error"]
    profile_id: UUID
    transaction: LedgerTransactionProjection | None = None
    review_status: LedgerReviewStatus | None = None
    bucket_event_ids: Annotated[tuple[str, ...], Field(max_length=_MAX_UPDATE_EVENT_IDS)] = ()
    group_label: Annotated[str, Field(max_length=64)] | None = None
    own_account_id: OwnAccountId | None = None
    validation_messages: LedgerUpdateValidationMessages = ()

    @model_validator(mode="after")
    def _complete_selected_outcome(self) -> LedgerUpdateOperationResult:
        if self.outcome == "updated":
            _require_updated_result(self)
        else:
            _require_update_refusal_result(self)
        return self


class LedgerUpdateExecutionResult(BaseModel):
    """Encrypted worker operand for either update completion or input refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["updated", "validation_error"]
    profile_id: UUID
    result: LedgerUpdateOperationResult | None = None
    validation_messages: LedgerUpdateValidationMessages = ()

    @model_validator(mode="after")
    def _complete_selected_outcome(self) -> LedgerUpdateExecutionResult:
        if self.outcome == "updated":
            if self.result is None or self.result.outcome != "updated" or self.validation_messages:
                raise ValueError("updated ledger execution requires its result projection")
            if self.result.profile_id != self.profile_id:
                raise ValueError("updated ledger execution result belongs to another profile")
        elif self.result is not None or not self.validation_messages:
            raise ValueError("ledger validation refusal requires only bounded validation messages")
        return self


def _require_updated_result(result: LedgerUpdateOperationResult) -> None:
    if result.transaction is None or result.review_status is None or result.validation_messages:
        raise ValueError("updated ledger result requires its transaction and review status")


def _require_update_refusal_result(result: LedgerUpdateOperationResult) -> None:
    if (
        result.transaction is not None
        or result.review_status is not None
        or result.bucket_event_ids
        or result.group_label is not None
        or result.own_account_id is not None
        or not result.validation_messages
    ):
        raise ValueError("validation refusal cannot carry transaction output or an effect")


__all__ = [
    "LEDGER_UPDATE_FIELD_NAMES",
    "LEDGER_UPDATE_MAX_VALIDATION_MESSAGES",
    "LEDGER_UPDATE_OPERATION_DEFINITION_ID",
    "LEDGER_UPDATE_PHASE",
    "LEDGER_UPDATE_VALIDATION_REFUSAL_CODE",
    "LedgerUpdateExecutionResult",
    "LedgerUpdateOperationResult",
    "LedgerUpdatePatch",
    "LedgerUpdatePatchField",
    "LedgerUpdateRequest",
    "LedgerUpdateValidationMessages",
]
