"""Closed request and result contracts for operator-selected IVA derivation."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .classify_requests import (
    LedgerClassifyDecimalText,
    LedgerClassifyLongText,
    LedgerClassifyTransactionPrefix,
)
from .classify_result_contracts import (
    LedgerClassifyOperationResult,
    LedgerClassifyValidationMessages,
)
from .id_resolution import normalise_transaction_id_prefix

LEDGER_OPERATOR_IVA_DEFINITION_ID = "ledger.classify.iva-derive"


class LedgerOperatorIvaRequest(BaseModel):
    """Exact-profile operator-selected IVA category, without frontend tax resolution."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    transaction_id: LedgerClassifyTransactionPrefix
    iva_category: Annotated[str, Field(min_length=1, max_length=128)]
    actor: Annotated[str, Field(min_length=1, max_length=64)] | None = None

    @field_validator("transaction_id")
    @classmethod
    def _canonical_transaction_prefix(cls, value: str) -> str:
        return normalise_transaction_id_prefix(value)


def _require_operator_iva_refusal(result: LedgerOperatorIvaResult) -> None:
    values = (result.iva_rate, result.taxable_base, result.iva_amount, result.classification)
    if result.derivable or any(value is not None for value in values) or not result.validation_messages or result.note:
        raise ValueError("operator IVA validation refusal requires only its bounded validation details")


def _require_operator_iva_substrate(result: LedgerOperatorIvaResult) -> None:
    values = (result.iva_rate, result.taxable_base, result.iva_amount, result.classification)
    if any(value is None for value in values):
        raise ValueError("derivable IVA result requires its complete substrate")
    if (
        result.classification is None
        or result.classification.profile_id != result.profile_id
        or result.classification.transaction is None
        or result.classification.transaction.transaction_id != result.transaction_id
    ):
        raise ValueError("derived IVA result belongs to another profile or row")


def _require_operator_iva_success(result: LedgerOperatorIvaResult) -> None:
    values = (result.iva_rate, result.taxable_base, result.iva_amount, result.classification)
    if result.validation_messages:
        raise ValueError("derived IVA result cannot carry validation refusal details")
    if result.derivable:
        _require_operator_iva_substrate(result)
    elif any(value is not None for value in values):
        raise ValueError("non-derivable IVA result cannot carry a write result")


class LedgerOperatorIvaResult(BaseModel):
    """Existing grounded IVA outcome, including a truthful non-derivable result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    outcome: Literal["derived", "validation_error"] = "derived"
    transaction_id: Annotated[str, Field(min_length=1, max_length=96)]
    iva_category: Annotated[str, Field(min_length=1, max_length=128)]
    derivable: bool
    iva_rate: LedgerClassifyDecimalText | None = None
    taxable_base: LedgerClassifyDecimalText | None = None
    iva_amount: LedgerClassifyDecimalText | None = None
    note: LedgerClassifyLongText = ""
    classification: LedgerClassifyOperationResult | None = None
    validation_messages: LedgerClassifyValidationMessages = ()

    @model_validator(mode="after")
    def _complete_derivation(self) -> LedgerOperatorIvaResult:
        if self.outcome == "validation_error":
            _require_operator_iva_refusal(self)
        else:
            _require_operator_iva_success(self)
        return self


class LedgerOperatorIvaExecutionResult(BaseModel):
    """Encrypted exact-request wrapper for the operator IVA result."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    request: LedgerOperatorIvaRequest
    result: LedgerOperatorIvaResult
