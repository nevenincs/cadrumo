"""Canonical typed request and result contracts for manual ledger addition."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.parsing.dates import require_iso8601_date
from ...domain.transactions.enums import BusinessClassification
from ..review.filter import LedgerReviewStatus
from .transaction_projection import LedgerTransactionProjection

LEDGER_ADD_VALIDATION_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"
LEDGER_ADD_OPERATION_DEFINITION_ID = "ledger.add"
MAX_LEDGER_ADD_EVENT_IDS = 1
MAX_LEDGER_ADD_ATTACHMENTS = 4096
MAX_LEDGER_ADD_VALIDATION_MESSAGES = 32
_AddText = Annotated[str, Field(max_length=4096)]
_AddOptionalText = Annotated[str, Field(max_length=4096)] | None
_AddDecimalText = Annotated[str, Field(min_length=1, max_length=128)]
_AddOptionalDecimalText = _AddDecimalText | None
_AddDateText = Annotated[str, Field(min_length=10, max_length=10)]
_AddOptionalDateText = _AddDateText | None
_AddId = Annotated[str, Field(min_length=1, max_length=256)]
_AddOptionalId = _AddId | None
_AddDirection = Annotated[str, Field(min_length=1, max_length=32)]
_AddClassification = Annotated[str, Field(min_length=1, max_length=64)]
_AddIvaCategory = Annotated[str, Field(min_length=1, max_length=128)] | None
_AddEUMemberState = Annotated[str, Field(min_length=2, max_length=2)] | None
_AddAttachmentIds = Annotated[
    tuple[Annotated[str, Field(min_length=1, max_length=256)], ...], Field(max_length=MAX_LEDGER_ADD_ATTACHMENTS)
]
_AddEventIds = Annotated[
    tuple[Annotated[str, Field(min_length=1, max_length=128)], ...], Field(max_length=MAX_LEDGER_ADD_EVENT_IDS)
]
_ValidationMessage = Annotated[str, Field(min_length=1, max_length=2048)]
LedgerAddValidationMessages = Annotated[
    tuple[_ValidationMessage, ...], Field(max_length=MAX_LEDGER_ADD_VALIDATION_MESSAGES)
]
LedgerAddSourceJurisdictionCode = Literal["source_jurisdiction_required_irnr", "source_jurisdiction_required_beckham"]
LedgerAddValidationCode = LedgerAddSourceJurisdictionCode | Literal["invalid_command"]


class LedgerAddRequest(BaseModel):
    """Bounded private CLI input; taxpayer-derived values are resolved in the worker."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    booked_date: _AddDateText
    amount: _AddDecimalText
    direction: _AddDirection
    description: Annotated[str, Field(min_length=1, max_length=4096)]
    value_date: _AddOptionalDateText = None
    currency: Annotated[str, Field(min_length=1, max_length=16)] = "EUR"
    counterparty: _AddOptionalText = None
    business_classification: _AddClassification = BusinessClassification.NOT_YET_PROCESSED.value
    business_pct: _AddOptionalDecimalText = None
    category_id: _AddOptionalId = None
    taxable_base: _AddOptionalDecimalText = None
    iva_rate: _AddOptionalDecimalText = None
    iva_amount: _AddOptionalDecimalText = None
    iva_category: _AddIvaCategory = None
    deduction_fact_kind: Annotated[str, Field(max_length=128)] | None = None
    investment_asset_id: _AddOptionalId = None
    counterparty_country: Annotated[str, Field(max_length=16)] | None = None
    counterparty_identification_state: _AddEUMemberState = None
    recargo_amount: _AddOptionalDecimalText = None
    irpf_category: _AddOptionalText = None
    usage_ratio_id: _AddOptionalId = None
    prorrata_reference: Annotated[str, Field(max_length=256)] | None = None
    art_104_tres_exclusion: Annotated[str, Field(max_length=128)] | None = None
    input_classification: Annotated[str, Field(max_length=128)] | None = None
    prorrata_sector: Annotated[str, Field(max_length=64)] | None = None
    purchase_invoice_evidence_id: _AddOptionalId = None
    attachment_ids: _AddAttachmentIds = ()
    notes: _AddText = ""
    actor: Annotated[str, Field(max_length=64)] | None = None
    idempotency_key: Annotated[str, Field(max_length=256)] | None = None
    source_jurisdiction: Annotated[str, Field(max_length=16)] | None = None

    @field_validator("booked_date", "value_date")
    @classmethod
    def _extended_iso_dates(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = require_iso8601_date(value)
        except ValueError:
            raise ValueError("ledger add dates must use YYYY-MM-DD") from None
        if parsed.isoformat() != value.strip():
            raise ValueError("ledger add dates must use YYYY-MM-DD")
        return value

    @field_validator("amount", "business_pct", "taxable_base", "iva_rate", "iva_amount", "recargo_amount")
    @classmethod
    def _canonical_decimal_inputs(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        signed = getattr(info, "field_name", None) != "amount"
        if try_parse_canonical_decimal(value, signed=signed, max_fraction_digits=2) is None:
            raise ValueError("ledger add decimal values must use canonical decimal text")
        return value


class LedgerAddOperationResult(BaseModel):
    """Bounded successful add receipt or a refusal proven before the write call."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["created", "validation_error"]
    profile_id: UUID
    transaction: LedgerTransactionProjection | None = None
    review_status: LedgerReviewStatus | None = None
    bucket_event_ids: _AddEventIds = ()
    advisory_input_classification: _AddOptionalText = None
    advisory_input_classification_inert: bool = False
    advisory_sector_id: Annotated[str, Field(max_length=64)] | None = None
    advisory_sector_unmatched: bool = False
    validation_code: LedgerAddValidationCode | None = None
    validation_messages: LedgerAddValidationMessages = ()

    @classmethod
    def validation_refusal(
        cls,
        profile_id: UUID,
        *,
        code: LedgerAddValidationCode,
        messages: tuple[str, ...] = (),
    ) -> LedgerAddOperationResult:
        """Build a bounded refusal projection after validation and before writing."""
        return cls(
            outcome="validation_error",
            profile_id=profile_id,
            validation_code=code,
            validation_messages=messages or ("ledger add input is invalid",),
        )

    @classmethod
    def created(
        cls,
        profile_id: UUID,
        *,
        transaction: LedgerTransactionProjection,
        review_status: LedgerReviewStatus,
        bucket_event_ids: tuple[str, ...],
        advisory_input_classification: str | None = None,
        advisory_input_classification_inert: bool = False,
        advisory_sector_id: str | None = None,
        advisory_sector_unmatched: bool = False,
    ) -> LedgerAddOperationResult:
        """Build a successful transaction projection with its worker-resolved advisories."""
        return cls(
            outcome="created",
            profile_id=profile_id,
            transaction=transaction,
            review_status=review_status,
            bucket_event_ids=bucket_event_ids,
            advisory_input_classification=advisory_input_classification,
            advisory_input_classification_inert=advisory_input_classification_inert,
            advisory_sector_id=advisory_sector_id,
            advisory_sector_unmatched=advisory_sector_unmatched,
        )

    @model_validator(mode="after")
    def _complete_selected_outcome(self) -> LedgerAddOperationResult:
        if self.outcome == "created":
            _validate_ledger_add_created(self)
        else:
            _validate_ledger_add_refusal(self)
        return self


def _validate_ledger_add_created(result: LedgerAddOperationResult) -> None:
    if (
        result.transaction is None
        or result.review_status is None
        or result.validation_code is not None
        or result.validation_messages
        or (result.advisory_input_classification_inert and result.advisory_input_classification is None)
        or (result.advisory_sector_unmatched and result.advisory_sector_id is None)
    ):
        raise ValueError("created ledger add receipt is incomplete")


def _validate_ledger_add_refusal(result: LedgerAddOperationResult) -> None:
    if (
        result.transaction is not None
        or result.review_status is not None
        or result.bucket_event_ids
        or result.advisory_input_classification is not None
        or result.advisory_input_classification_inert
        or result.advisory_sector_id is not None
        or result.advisory_sector_unmatched
        or result.validation_code is None
        or not result.validation_messages
    ):
        raise ValueError("ledger add validation result must contain no transaction or effect")


class LedgerAddExecutionResult(BaseModel):
    """Secure worker operand for success or a bounded pre-write refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["created", "validation_error"]
    profile_id: UUID
    result: LedgerAddOperationResult | None = None
    validation_code: LedgerAddValidationCode | None = None
    validation_messages: LedgerAddValidationMessages = ()

    @model_validator(mode="after")
    def _complete_selected_outcome(self) -> LedgerAddExecutionResult:
        if self.outcome == "created":
            _validate_ledger_add_execution_created(self)
        else:
            _validate_ledger_add_execution_refusal(self)
        return self


def _validate_ledger_add_execution_created(result: LedgerAddExecutionResult) -> None:
    if (
        result.result is None
        or result.result.outcome != "created"
        or result.result.profile_id != result.profile_id
        or result.validation_code is not None
        or result.validation_messages
    ):
        raise ValueError("created ledger add execution requires its matching result")


def _validate_ledger_add_execution_refusal(result: LedgerAddExecutionResult) -> None:
    if result.result is not None or result.validation_code is None or not result.validation_messages:
        raise ValueError("ledger add refusal requires only bounded validation facts")
