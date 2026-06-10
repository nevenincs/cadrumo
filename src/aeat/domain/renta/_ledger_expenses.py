"""Renta deductible-expense observations derived from ledger facts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from ...core import Modelo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..categories import (
    CategoryCitation,
    CategoryProfile,
    ProportionalityKind,
    ProportionalityRule,
    SpendingCategory,
    SpendingCategoryFamily,
    StatutoryCapPeriod,
    family_for,
)
from ._errors import RentaValidationError
from ._first_slice_routing import FIRST_SLICE_EXPENSE_CASILLAS

LEDGER_RENTA_EXPENSE_SOURCE = "ledger_renta_expense_aggregation"
EUR_CURRENCY: Literal["EUR"] = "EUR"

# Re-export the canonical first-slice routing table. The single source
# of truth lives in ``_first_slice_routing.py`` so the validator path
# (this module) and any future snapshot-time integrity gate consult
# the same Mapping without risk of divergence.
RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS: Mapping[SpendingCategory, str] = FIRST_SLICE_EXPENSE_CASILLAS


class RentaExpenseDirection(StrEnum):
    """Closed direction values for first-slice Renta expense facts."""

    OUTGOING_EXPENSE = "outgoing_expense"
    REFUND = "refund"
    REVERSAL = "reversal"


class RentaDeductibilityStatus(StrEnum):
    """Whether a ledger fact can produce a Renta calculation observation."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"


class RentaInvoiceEvidenceStatus(StrEnum):
    """Invoice-evidence state carried by the Renta observation."""

    NONE = "none"
    LINKED = "linked"


class RentaReconciliationStatus(StrEnum):
    """Transaction/invoice reconciliation state for duplicate prevention."""

    TRANSACTION_ONLY = "transaction_only"
    LINKED_INVOICE = "linked_invoice"


class _RentaStrictFrozenModel(BaseModel):
    """Shared strict immutable boundary model."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")


class RentaDeductibilityContext(_RentaStrictFrozenModel):
    """Inputs that affect proportionality but are not ledger facts."""

    profile_year: int = Field(ge=2000, le=2099)
    usage_ratios: dict[SpendingCategory, Decimal] = Field(default_factory=dict)
    statutory_cap_days: Decimal | None = Field(default=None, gt=Decimal("0"))
    statutory_cap_variant_id: str | None = Field(default=None, min_length=1, max_length=64)
    statutory_cap_person_count: int = Field(default=1, ge=1)
    exclusive_use_confirmed: bool = False

    @field_validator("usage_ratios", mode="after")
    @classmethod
    def _usage_ratios_in_bounds(cls, value: dict[SpendingCategory, Decimal]) -> dict[SpendingCategory, Decimal]:
        for category, ratio in value.items():
            _require_decimal(ratio, f"usage ratio for {category.value!r}")
            if not (Decimal("0") <= ratio <= Decimal("1")):
                raise RentaValidationError(f"usage ratio for {category.value!r} must be in [0, 1]")
        return {category: value[category] for category in sorted(value, key=lambda item: item.value)}

    @field_validator("statutory_cap_days")
    @classmethod
    def _cap_days_decimal(cls, value: Decimal | None) -> Decimal | None:
        if value is not None:
            _require_decimal(value, "statutory_cap_days")
        return value


class RentaDeductibleExpenseFact(_RentaStrictFrozenModel):
    """Canonical ledger fact eligible for Renta deductibility evaluation."""

    transaction_id: str = Field(min_length=1, max_length=128)
    invoice_id: str | None = Field(default=None, min_length=1, max_length=128)
    catalogue_id: str = Field(min_length=1, max_length=128)
    operation_date: date
    invoice_issue_date: date | None = None
    posting_date: date | None = None
    payment_date: date | None = None
    gross_amount: Decimal = Field(gt=Decimal("0"))
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    currency: Literal["EUR"] = EUR_CURRENCY
    direction: RentaExpenseDirection = RentaExpenseDirection.OUTGOING_EXPENSE
    category: SpendingCategory
    activity_key: str = Field(default="default", min_length=1, max_length=128)

    @field_validator("gross_amount", "taxable_base", "iva_amount")
    @classmethod
    def _amounts_are_finite_decimals(cls, value: Decimal | None) -> Decimal | None:
        if value is not None:
            _require_decimal(value, "monetary amount")
        return value

    @model_validator(mode="after")
    def _validate_invoice_and_direction(self) -> RentaDeductibleExpenseFact:
        if self.invoice_id is None and self.invoice_issue_date is not None:
            raise RentaValidationError("invoice_issue_date requires invoice_id")
        if self.invoice_id is not None and self.invoice_issue_date is None:
            raise RentaValidationError("linked invoice facts require invoice_issue_date")
        if self.direction in {RentaExpenseDirection.REFUND, RentaExpenseDirection.REVERSAL} and self.invoice_id is None:
            raise RentaValidationError("refund and reversal facts must be linked to an invoice")
        return self

    @property
    def filing_date(self) -> date:
        """Return the filing date used for first-slice selection.

        Prefers ``invoice_issue_date`` when present, falling back to
        ``operation_date`` so observations without invoices still get a
        deterministic anchor.
        """
        return self.invoice_issue_date if self.invoice_issue_date is not None else self.operation_date

    @property
    def sign(self) -> Literal[-1, 1]:
        """Return +1 for expenses and -1 for linked corrections."""
        if self.direction is RentaExpenseDirection.OUTGOING_EXPENSE:
            return 1
        return -1


class RentaDeductibilityResult(_RentaStrictFrozenModel):
    """Deductibility evaluation result before registry binding resolution."""

    transaction_id: str = Field(min_length=1, max_length=128)
    invoice_id: str | None = Field(default=None, min_length=1, max_length=128)
    category: SpendingCategory
    category_family: SpendingCategoryFamily
    profile_year: int = Field(ge=2000, le=2099)
    proportionality_kind: ProportionalityKind
    status: RentaDeductibilityStatus
    reason: str = Field(min_length=1, max_length=256)
    gross_amount: Decimal
    deductible_amount: Decimal
    non_deductible_amount: Decimal
    applied_ratio: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    statutory_cap_applied: Decimal | None = Field(default=None, ge=Decimal("0"))
    legal_references: tuple[CategoryCitation, ...] = Field(min_length=1)

    @field_validator("gross_amount", "deductible_amount", "non_deductible_amount", "statutory_cap_applied")
    @classmethod
    def _result_amounts_are_decimals(cls, value: Decimal | None) -> Decimal | None:
        if value is not None:
            _require_decimal(value, "deductibility result amount")
        return value

    @model_validator(mode="after")
    def _validate_category_family(self) -> RentaDeductibilityResult:
        if self.category_family is not family_for(self.category):
            raise RentaValidationError("category_family must match category")
        return self


class RentaDeductibleExpenseObservation(_RentaStrictFrozenModel):
    """Binding-ready Renta expense observation for the first Modelo 100 slice."""

    observation_id: str = Field(min_length=1, max_length=160)
    source_kind: Literal["ledger_renta_expense_aggregation"] = LEDGER_RENTA_EXPENSE_SOURCE
    modelo: Literal[Modelo.M100] = Modelo.M100
    period: Literal["0A"] = "0A"
    tax_year: int = Field(ge=2000, le=2099)
    activity_key: str = Field(min_length=1, max_length=128)
    target_casilla: str = Field(min_length=4, max_length=4)
    transaction_id: str = Field(min_length=1, max_length=128)
    invoice_id: str | None = Field(default=None, min_length=1, max_length=128)
    catalogue_id: str = Field(min_length=1, max_length=128)
    operation_date: date
    invoice_issue_date: date | None = None
    posting_date: date | None = None
    payment_date: date | None = None
    filing_date: date
    gross_amount: Decimal
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None
    deductible_amount: Decimal
    non_deductible_amount: Decimal
    currency: Literal["EUR"] = EUR_CURRENCY
    direction: RentaExpenseDirection
    sign: Literal[-1, 1]
    category: SpendingCategory
    category_family: SpendingCategoryFamily
    profile_year: int = Field(ge=2000, le=2099)
    proportionality_kind: ProportionalityKind
    applied_ratio: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    invoice_evidence_status: RentaInvoiceEvidenceStatus
    reconciliation_status: RentaReconciliationStatus
    legal_references: tuple[CategoryCitation, ...] = Field(min_length=1)

    @field_validator("gross_amount", "taxable_base", "iva_amount", "deductible_amount", "non_deductible_amount")
    @classmethod
    def _observation_amounts_are_decimals(cls, value: Decimal | None) -> Decimal | None:
        if value is not None:
            _require_decimal(value, "observation amount")
        return value

    @model_validator(mode="after")
    def _validate_period_and_invoice_state(self) -> RentaDeductibleExpenseObservation:
        if self.category_family is not family_for(self.category):
            raise RentaValidationError("category_family must match category")
        if self.target_casilla != RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS.get(self.category):
            raise RentaValidationError("target_casilla must match the first-slice category mapping")
        if not (date(self.tax_year, 1, 1) <= self.filing_date < date(self.tax_year + 1, 1, 1)):
            raise RentaValidationError("filing_date must fall inside the observation tax year")
        if self.invoice_id is None and self.invoice_issue_date is not None:
            raise RentaValidationError("invoice_issue_date requires invoice_id")
        if self.invoice_id is None and self.invoice_evidence_status is not RentaInvoiceEvidenceStatus.NONE:
            raise RentaValidationError("transaction-only observations must not declare linked invoice evidence")
        if self.invoice_id is not None and self.invoice_evidence_status is not RentaInvoiceEvidenceStatus.LINKED:
            raise RentaValidationError("linked invoice observations must declare linked invoice evidence")
        return self


def normalize_spending_category(value: SpendingCategory | str) -> SpendingCategory:
    """Normalize persisted category identifiers to closed enum members.

    Returns:
        The :class:`SpendingCategory` member for the given value.
    """
    if isinstance(value, SpendingCategory):
        return value
    return SpendingCategory(value)


def evaluate_renta_deductibility(
    fact: RentaDeductibleExpenseFact,
    profile: CategoryProfile,
    context: RentaDeductibilityContext,
) -> RentaDeductibilityResult:
    """Evaluate one classified ledger fact and return a :class:`RentaDeductibilityResult`."""
    if profile.category is not fact.category:
        raise RentaValidationError(
            f"profile category {profile.category.value!r} does not match fact category {fact.category.value!r}"
        )
    rule = profile.proportionality
    deductible_abs: Decimal
    applied_ratio: Decimal | None
    cap_applied: Decimal | None = None
    status = RentaDeductibilityStatus.ELIGIBLE
    reason = "deductible"

    if rule.kind is ProportionalityKind.FULL_DEDUCTIBLE:
        deductible_abs = fact.gross_amount
        applied_ratio = Decimal("1")
    elif rule.kind is ProportionalityKind.FIXED_PERCENTAGE:
        assert rule.fixed_pct is not None
        applied_ratio = rule.fixed_pct
        deductible_abs = fact.gross_amount * applied_ratio
    elif rule.kind in {ProportionalityKind.USAGE_RATIO_HOME_AREA, ProportionalityKind.USAGE_RATIO_PERSONAL}:
        ratio = context.usage_ratios.get(fact.category, rule.default_ratio)
        if ratio is None:
            status = RentaDeductibilityStatus.INELIGIBLE
            reason = "missing usage ratio"
            applied_ratio = None
            deductible_abs = Decimal("0")
        else:
            applied_ratio = ratio
            deductible_abs = fact.gross_amount * ratio
    elif rule.kind is ProportionalityKind.STATUTORY_CAP:
        cap_applied = _resolve_statutory_cap(rule=rule, context=context)
        if cap_applied is None:
            status = RentaDeductibilityStatus.INELIGIBLE
            reason = "missing statutory cap context"
            applied_ratio = None
            deductible_abs = Decimal("0")
        else:
            deductible_abs = min(fact.gross_amount, cap_applied)
            applied_ratio = deductible_abs / fact.gross_amount
    elif rule.kind is ProportionalityKind.NON_DEDUCTIBLE:
        status = RentaDeductibilityStatus.INELIGIBLE
        reason = "non deductible category"
        applied_ratio = Decimal("0")
        deductible_abs = Decimal("0")
    elif rule.kind is ProportionalityKind.REQUIRES_EXCLUSIVE_USE:
        if context.exclusive_use_confirmed:
            applied_ratio = Decimal("1")
            deductible_abs = fact.gross_amount
        else:
            status = RentaDeductibilityStatus.INELIGIBLE
            reason = "exclusive use not confirmed"
            applied_ratio = None
            deductible_abs = Decimal("0")
    else:  # pragma: no cover - closed enum exhaustiveness guard
        raise RentaValidationError(f"unsupported proportionality kind: {rule.kind.value}")

    signed_deductible = deductible_abs * fact.sign
    signed_non_deductible = (fact.gross_amount - deductible_abs) * fact.sign
    return RentaDeductibilityResult(
        transaction_id=fact.transaction_id,
        invoice_id=fact.invoice_id,
        category=fact.category,
        category_family=family_for(fact.category),
        profile_year=context.profile_year,
        proportionality_kind=rule.kind,
        status=status,
        reason=reason,
        gross_amount=fact.gross_amount * fact.sign,
        deductible_amount=signed_deductible,
        non_deductible_amount=signed_non_deductible,
        applied_ratio=applied_ratio,
        statutory_cap_applied=cap_applied,
        legal_references=rule.citations,
    )


def build_renta_deductible_expense_observation(
    fact: RentaDeductibleExpenseFact,
    result: RentaDeductibilityResult,
    *,
    tax_year: int,
) -> RentaDeductibleExpenseObservation:
    """Build a first-slice Modelo 100 observation from an eligible result.

    Returns:
        A :class:`RentaDeductibleExpenseObservation` ready for filing assembly.
    """
    if result.status is not RentaDeductibilityStatus.ELIGIBLE:
        raise RentaValidationError(f"ineligible deductibility result cannot become an observation: {result.reason}")
    if fact.category is not result.category:
        raise RentaValidationError("fact and result categories must match")
    target_casilla = RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS.get(fact.category)
    if target_casilla is None:
        raise RentaValidationError(f"category {fact.category.value!r} is outside the first Renta expense slice")
    if not (date(tax_year, 1, 1) <= fact.filing_date < date(tax_year + 1, 1, 1)):
        raise RentaValidationError("fact filing date falls outside the requested tax year")
    invoice_status = (
        RentaInvoiceEvidenceStatus.LINKED if fact.invoice_id is not None else RentaInvoiceEvidenceStatus.NONE
    )
    reconciliation_status = (
        RentaReconciliationStatus.LINKED_INVOICE
        if fact.invoice_id is not None
        else RentaReconciliationStatus.TRANSACTION_ONLY
    )
    return RentaDeductibleExpenseObservation(
        observation_id=_observation_id(fact),
        tax_year=tax_year,
        activity_key=fact.activity_key,
        target_casilla=target_casilla,
        transaction_id=fact.transaction_id,
        invoice_id=fact.invoice_id,
        catalogue_id=fact.catalogue_id,
        operation_date=fact.operation_date,
        invoice_issue_date=fact.invoice_issue_date,
        posting_date=fact.posting_date,
        payment_date=fact.payment_date,
        filing_date=fact.filing_date,
        gross_amount=result.gross_amount,
        taxable_base=fact.taxable_base * fact.sign if fact.taxable_base is not None else None,
        iva_amount=fact.iva_amount * fact.sign if fact.iva_amount is not None else None,
        deductible_amount=result.deductible_amount,
        non_deductible_amount=result.non_deductible_amount,
        direction=fact.direction,
        sign=fact.sign,
        category=fact.category,
        category_family=result.category_family,
        profile_year=result.profile_year,
        proportionality_kind=result.proportionality_kind,
        applied_ratio=result.applied_ratio,
        invoice_evidence_status=invoice_status,
        reconciliation_status=reconciliation_status,
        legal_references=result.legal_references,
    )


def _resolve_statutory_cap(
    *,
    rule: ProportionalityRule,
    context: RentaDeductibilityContext,
) -> Decimal | None:
    if rule.statutory_cap_eur is not None:
        if rule.statutory_cap_period is StatutoryCapPeriod.YEAR_PER_PERSON:
            return rule.statutory_cap_eur * Decimal(context.statutory_cap_person_count)
        return rule.statutory_cap_eur
    if rule.statutory_cap_eur_per_day is not None:
        if context.statutory_cap_days is None:
            return None
        return rule.statutory_cap_eur_per_day * context.statutory_cap_days
    if rule.statutory_cap_variants:
        if context.statutory_cap_variant_id is None or context.statutory_cap_days is None:
            return None
        for variant in rule.statutory_cap_variants:
            if variant.id == context.statutory_cap_variant_id:
                return variant.statutory_cap_eur_per_day * context.statutory_cap_days
        return None
    return None


def _observation_id(fact: RentaDeductibleExpenseFact) -> str:
    if fact.invoice_id is None:
        return f"renta-expense:{fact.catalogue_id}:{fact.transaction_id}"
    return f"renta-expense:{fact.catalogue_id}:{fact.transaction_id}:{fact.invoice_id}"


def _require_decimal(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Decimal) or not value.is_finite():
        raise RentaValidationError(f"{field_name} must be a finite Decimal")


__all__ = [
    "LEDGER_RENTA_EXPENSE_SOURCE",
    "RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS",
    "RentaDeductibilityContext",
    "RentaDeductibilityResult",
    "RentaDeductibilityStatus",
    "RentaDeductibleExpenseFact",
    "RentaDeductibleExpenseObservation",
    "RentaExpenseDirection",
    "RentaInvoiceEvidenceStatus",
    "RentaReconciliationStatus",
    "build_renta_deductible_expense_observation",
    "evaluate_renta_deductibility",
    "normalize_spending_category",
]
