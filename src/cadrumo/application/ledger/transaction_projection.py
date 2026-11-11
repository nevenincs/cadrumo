"""Closed registered-operation projections of canonical ledger read facts."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Final, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.form_codes import require_form_width
from ...domain.transactions.own_accounts import OwnAccountId
from ..review.filter import LedgerReviewStatus
from .models import LedgerTransactionPayload

type LedgerReasonSource = Literal["none", "stated", "command"]
"""Whose words a row's classification reason is: nobody's, the person's own, or a command's name."""

_COMMAND_REASON_PREFIX: Final = "aeat app ledger"
"""How every command that records a classification without a stated reason names itself."""

COMMAND_REASON_WORDS_LOCALE_KEY: Final = "application.ledger.reason.served.command"
"""The word served in place of a command's name."""


def classification_reason_source(reason: str) -> LedgerReasonSource:
    """Say whose words a stored classification reason is.

    A classification written without a stated reason stores the name of the
    command that wrote it, so a reason that names one of the product's own
    commands is a machine source, never something a person wrote.
    """
    text = reason.strip()
    if not text:
        return "none"
    return "command" if text.startswith(_COMMAND_REASON_PREFIX) else "stated"


def classification_reason_words(source: LedgerReasonSource, language: OutputLanguage) -> str:
    """The word that stands for a machine source in ``language``; a person's words and none are served as stored."""
    return tr(COMMAND_REASON_WORDS_LOCALE_KEY, locale=language.value) if source == "command" else ""


class LedgerM210IncomeProjection(BaseModel):
    """Already-admitted M210 facts without frontend registry revalidation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    official_tipo_renta_code: str = Field(min_length=1, max_length=16)
    gross_income_amount: str
    applicable_rate: str
    payer_mode: str
    payer_id: str | None
    asset_or_right_id: str | None

    @field_validator("gross_income_amount", "applicable_rate")
    @classmethod
    def _finite_decimal(cls, value: str) -> str:
        try:
            parsed = Decimal(value)
        except InvalidOperation:
            raise ValueError("income projection requires a finite decimal string") from None
        if not parsed.is_finite():
            raise ValueError("income projection requires a finite decimal string")
        return value

    @field_validator("official_tipo_renta_code")
    @classmethod
    @pydantic_validation_boundary
    def _has_the_declared_width(cls, value: str | None) -> str | None:
        return require_form_width(value, "m210.tipo_renta_digits")


class LedgerTransactionProjection(BaseModel):
    """The existing transaction payload with a strict JSON-stable M210 projection.

    Financial values are copied from canonical read facts, never recomputed.
    Domain reconstruction and registry validation remain inside the worker;
    frontends receive only the admitted display and audit facts.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: TransactionId
    date: str
    booked_date: str
    value_date: str | None
    operation_date: str | None = None
    accrual_date: str | None = None
    amount: str
    currency: str
    direction: str
    counterparty: str
    description: str
    statement_reference: str | None = None
    business_classification: str
    business_pct: str | None
    category_id: str | None
    taxable_base: str | None
    iva_rate: str | None
    iva_amount: str | None
    recargo_amount: str | None = None
    iva_category: str | None
    deduction_fact_kind: str | None = None
    investment_asset_id: str | None = None
    counterparty_country: str | None
    counterparty_identification_state: str | None
    irpf_category: str | None
    m210_income_classification: LedgerM210IncomeProjection | None
    usage_ratio_id: str | None
    prorrata_reference: str | None
    purchase_invoice_evidence_id: str | None
    invoice_id: str | None
    attachment_ids: tuple[str, ...]
    notes: str
    lifecycle_state: str
    classified_by: str
    classified_at: str | None
    classification_reason: str
    classification_confidence: str | None
    source_jurisdiction: str | None
    value_in_eur: str | None
    fx_rate: str | None
    created_at: str
    modified_at: str

    @classmethod
    def from_payload(cls, payload: LedgerTransactionPayload) -> LedgerTransactionProjection:
        """Copy the canonical JSON meaning, preserving absence and decimal text."""
        return cls.model_validate_json(payload.model_dump_json())


class LedgerMovementWithholdingProjection(BaseModel):
    """The retención a received invoice leaves on the movement that pays it.

    ``retencion`` is the euro amount the invoice recognises on this payment, as
    Modelo 111 and 115 count it; ``held_back`` names why it reaches no
    declaration, so a payment the declaration waits on is not read as a payment
    without retención. Exactly one of the two is set.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    invoice_id: str
    invoice_number: str
    modelo: str | None
    scheme: str | None
    retencion: str | None
    recognised_on: str | None
    held_back: str | None

    @model_validator(mode="after")
    def retencion_xor_held_back(self) -> LedgerMovementWithholdingProjection:
        """Refuse a row that is both a recognised retención and held back, or neither."""
        if (self.retencion is None) == (self.held_back is None):
            raise ValueError("a movement's withholding is either recognised or held back")
        return self


class LedgerTransactionReviewProjection(BaseModel):
    """A reviewed transaction with the group used by canonical list ordering.

    The own account is the register id the row is bound to, never its account
    number, so a listing can show and group by account without a second read.
    The reason's source says whether ``transaction.classification_reason`` is
    the person's own words; for a machine source the reason is a command's name
    and the served word, in the language named, stands for it.

    ``withholding`` is empty for a movement that pays no invoice stating a
    retención: its retención is absent, never zero.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction: LedgerTransactionProjection
    review_status: LedgerReviewStatus
    group_label: str | None
    own_account_id: OwnAccountId | None
    classification_reason_source: LedgerReasonSource
    classification_reason_words: str
    classification_reason_words_language: OutputLanguage | None
    withholding: tuple[LedgerMovementWithholdingProjection, ...] = ()
