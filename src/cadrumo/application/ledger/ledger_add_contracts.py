"""Canonical typed request and result contracts for manual ledger addition."""

from __future__ import annotations

from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.country_code import CountryCodeAlpha2
from ...core.decimal.grammar import CENT_FRACTION_DIGITS, DECIMAL_TEXT_MAX_LENGTH, try_parse_canonical_decimal
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.parsing.dates import require_iso8601_date
from ...domain.iva.prorrata import ProrrataReferenceText
from ...domain.transactions.enums import (
    BusinessClassification,
    ManualEntryClassificationToken,
    TransactionDirectionToken,
)
from ...domain.transactions.own_accounts import OwnAccountId
from ..operations.form_field_annotation import form_field_schema
from ..review.filter import LedgerReviewStatus
from .transaction_projection import LedgerTransactionProjection

LEDGER_ADD_VALIDATION_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"
LEDGER_ADD_OPERATION_DEFINITION_ID = "ledger.add"
MAX_LEDGER_ADD_EVENT_IDS = 1
MAX_LEDGER_ADD_ATTACHMENTS = 4096
MAX_LEDGER_ADD_VALIDATION_MESSAGES = 32
_AddText = Annotated[str, Field(max_length=4096)]
_AddOptionalText = Annotated[str, Field(max_length=4096)] | None
_AddDecimalText = Annotated[str, Field(min_length=1, max_length=DECIMAL_TEXT_MAX_LENGTH)]
_AddOptionalDecimalText = _AddDecimalText | None
_AddDateText = Annotated[str, Field(min_length=1, max_length=16)]
_AddOptionalDateText = _AddDateText | None
_AddId = Annotated[str, Field(min_length=1, max_length=256)]
_AddOptionalId = _AddId | None
_AddDirection = TransactionDirectionToken
_AddClassification = ManualEntryClassificationToken
_AddIvaCategory = Annotated[str, Field(min_length=1, max_length=128)] | None
_AddEUMemberState = CountryCodeAlpha2 | None
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


_DIRECTION_CHOICE_LOCALE_KEYS: Final[dict[str, str]] = {
    "INCOMING": "application.ledger.add.choice.direction.incoming",
    "OUTGOING": "application.ledger.add.choice.direction.outgoing",
    "INTERNAL_TRANSFER": "application.ledger.add.choice.direction.internal_transfer",
}
"""The words of each direction token the request takes, by token."""
_CLASSIFICATION_CHOICE_LOCALE_KEYS: Final[dict[str, str]] = {
    "BUSINESS": "application.ledger.add.choice.business_classification.business",
    "PERSONAL": "application.ledger.add.choice.business_classification.personal",
    "MIXED": "application.ledger.add.choice.business_classification.mixed",
    "NOT_YET_PROCESSED": "application.ledger.add.choice.business_classification.not_yet_processed",
}
"""The words of each classification token a person may assign, by token."""


class LedgerAddRequest(BaseModel):
    """Bounded private CLI input; taxpayer-derived values are resolved in the worker."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: Annotated[UUID, Field(json_schema_extra=form_field_schema(bound="profile"))]
    booked_date: Annotated[
        _AddDateText, Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.booked_date"))
    ]
    amount: Annotated[
        _AddDecimalText, Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.amount"))
    ]
    direction: Annotated[
        _AddDirection,
        Field(
            json_schema_extra=form_field_schema(
                label_key="application.ledger.add.field.direction", choice_label_keys=_DIRECTION_CHOICE_LOCALE_KEYS
            )
        ),
    ]
    description: Annotated[
        Annotated[str, Field(min_length=1, max_length=4096)],
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.description")),
    ]
    value_date: Annotated[
        _AddOptionalDateText,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.value_date")),
    ] = None
    operation_date: Annotated[
        _AddOptionalDateText,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.operation_date")),
    ] = None
    accrual_date: Annotated[
        _AddOptionalDateText,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.accrual_date")),
    ] = None
    currency: Annotated[
        Annotated[str, Field(min_length=1, max_length=16)],
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.currency")),
    ] = "EUR"
    counterparty: Annotated[
        _AddOptionalText,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.counterparty")),
    ] = None
    business_classification: Annotated[
        _AddClassification,
        Field(
            json_schema_extra=form_field_schema(
                label_key="application.ledger.add.field.business_classification",
                choice_label_keys=_CLASSIFICATION_CHOICE_LOCALE_KEYS,
            )
        ),
    ] = BusinessClassification.NOT_YET_PROCESSED.value
    business_pct: Annotated[
        _AddOptionalDecimalText,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.business_pct")),
    ] = None
    category_id: Annotated[
        _AddOptionalId, Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.category_id"))
    ] = None
    taxable_base: Annotated[
        _AddOptionalDecimalText,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.taxable_base")),
    ] = None
    iva_rate: Annotated[
        _AddOptionalDecimalText,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.iva_rate")),
    ] = None
    iva_amount: Annotated[
        _AddOptionalDecimalText,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.iva_amount")),
    ] = None
    iva_category: Annotated[
        _AddIvaCategory,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.iva_category")),
    ] = None
    deduction_fact_kind: Annotated[
        Annotated[str, Field(max_length=128)] | None,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.deduction_fact_kind")),
    ] = None
    investment_asset_id: Annotated[
        _AddOptionalId,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.investment_asset_id")),
    ] = None
    iva_vehicle_use: Annotated[str, Field(max_length=128)] | None = None
    counterparty_country: Annotated[
        CountryCodeAlpha2 | None,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.counterparty_country")),
    ] = None
    counterparty_identification_state: Annotated[
        _AddEUMemberState,
        Field(
            json_schema_extra=form_field_schema(
                label_key="application.ledger.add.field.counterparty_identification_state"
            )
        ),
    ] = None
    arrendamiento_ref: Annotated[
        Annotated[str, Field(max_length=64)] | None,
        Field(
            json_schema_extra=form_field_schema(
                label_key="application.ledger.add.field.arrendamiento_ref", entry_option_family="rental_lease"
            )
        ),
    ] = None
    inmueble_ref: Annotated[
        Annotated[str, Field(max_length=64)] | None,
        Field(
            json_schema_extra=form_field_schema(
                label_key="application.ledger.add.field.inmueble_ref", entry_option_family="rental_property"
            )
        ),
    ] = None
    gasto_capital_inmobiliario: Annotated[
        Annotated[str, Field(max_length=128)] | None,
        Field(
            json_schema_extra=form_field_schema(
                label_key="application.ledger.add.field.gasto_capital_inmobiliario",
                entry_option_family="gasto_capital_inmobiliario",
            )
        ),
    ] = None
    posicion_ref: Annotated[str, Field(max_length=64)] | None = None
    concepto_capital_mobiliario: Annotated[str, Field(max_length=128)] | None = None
    recargo_amount: Annotated[
        _AddOptionalDecimalText,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.recargo_amount")),
    ] = None
    irpf_category: Annotated[
        _AddOptionalText,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.irpf_category")),
    ] = None
    usage_ratio_id: Annotated[
        _AddOptionalId,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.usage_ratio_id")),
    ] = None
    prorrata_reference: Annotated[
        ProrrataReferenceText | None,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.prorrata_reference")),
    ] = None
    art_104_tres_exclusion: Annotated[
        Annotated[str, Field(max_length=128)] | None,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.art_104_tres_exclusion")),
    ] = None
    input_classification: Annotated[
        Annotated[str, Field(max_length=128)] | None,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.input_classification")),
    ] = None
    prorrata_sector: Annotated[
        Annotated[str, Field(max_length=64)] | None,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.prorrata_sector")),
    ] = None
    purchase_invoice_evidence_id: Annotated[
        _AddOptionalId,
        Field(
            json_schema_extra=form_field_schema(label_key="application.ledger.add.field.purchase_invoice_evidence_id")
        ),
    ] = None
    attachment_ids: _AddAttachmentIds = ()
    notes: Annotated[
        _AddText, Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.notes"))
    ] = ""
    actor: Annotated[str, Field(max_length=64)] | None = None
    idempotency_key: Annotated[str, Field(max_length=256)] | None = None
    source_jurisdiction: Annotated[
        Annotated[str, Field(max_length=16)] | None,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.source_jurisdiction")),
    ] = None
    own_account_id: Annotated[
        OwnAccountId | None,
        Field(json_schema_extra=form_field_schema(label_key="application.ledger.add.field.own_account_id")),
    ] = None

    @field_validator("booked_date", "value_date", "operation_date", "accrual_date")
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
        field_name = getattr(info, "field_name", None)
        is_amount = field_name == "amount"
        # Only euro amounts are held to cents; a share or a rate keeps the fraction digits it has (0.052).
        cents = None if field_name in {"business_pct", "iva_rate"} else CENT_FRACTION_DIGITS
        if try_parse_canonical_decimal(value, signed=not is_amount, max_fraction_digits=cents) is None:
            if is_amount and try_parse_canonical_decimal(value, max_fraction_digits=CENT_FRACTION_DIGITS) is not None:
                raise ValueError(
                    "ledger add amount must be a non-negative magnitude; "
                    "set the flow with direction (OUTGOING / INCOMING / INTERNAL_TRANSFER), not a negative amount"
                )
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
