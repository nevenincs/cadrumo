"""Renta deductible-expense observations derived from ledger facts.

:class:`RentaDeductibleExpenseFact` is evaluated through
:func:`evaluate_renta_deductibility` using :class:`CategoryProfile` and
:class:`RentaDeductibilityContext`; eligible
:class:`RentaDeductibilityResult` values become
:class:`RentaDeductibleExpenseObservation` records routed through
:data:`RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS` to registry
:data:`CasillaId` bindings for :class:`~cadrumo.core.Modelo.M100`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG, BindingSourceKind, CasillaId, Modelo, Period
from ...core.identity import TransactionId
from ..categories import (
    CategoryCitation,
    CategoryProfile,
    ProportionalityKind,
    ProportionalityRule,
    SpendingCategory,
    SpendingCategoryFamily,
    StatutoryCapPeriod,
    StatutoryCapVariant,
    family_for,
)
from ..contribuyente import CCAA
from ._first_slice_routing import FIRST_SLICE_EXPENSE_CASILLAS
from .errors import RentaValidationError

EUR_CURRENCY: Literal["EUR"] = "EUR"

# Re-export the canonical first-slice routing table. The single source
# of truth lives in ``_first_slice_routing.py`` so the validator path
# (this module) and any future snapshot-time integrity gate consult
# the same Mapping without risk of divergence.
RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS: Mapping[SpendingCategory, CasillaId] = FIRST_SLICE_EXPENSE_CASILLAS


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

    model_config = STRICT_FROZEN_CONFIG


class RentaDeductibilityContext(_RentaStrictFrozenModel):
    """Inputs that affect proportionality but are not ledger facts."""

    profile_year: int = Field(ge=2000, le=2099)
    usage_ratios: dict[SpendingCategory, Decimal] = Field(default_factory=dict)
    statutory_cap_days: Decimal | None = Field(default=None, gt=Decimal("0"))
    statutory_cap_variant_id: str | None = Field(default=None, min_length=1, max_length=64)
    statutory_cap_person_count: int = Field(default=1, ge=1)
    statutory_cap_variant_person_counts: Mapping[str, int] = Field(default_factory=dict)
    """How many insured persons fall under each annual cap variant, keyed by variant id.

    LIRPF art. 30.2.5.a caps the seguro de enfermedad premium at 500 euros per person
    or 1.500 for a person with discapacidad, so the lawful cap is a SUM over two
    populations rather than one amount times one count. A single
    :attr:`statutory_cap_person_count` cannot express that, and using it alone applies
    the lower limb to everybody -- which understates the allowance for exactly the
    people the higher limb exists for.
    """
    exclusive_use_confirmed: bool = False
    iva_deduction_ratio: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    """Fraction of the fact's input IVA the activity affords a right to deduct (LIVA arts. 94/104).

    ``None`` (the default) means the axis has not been evaluated for this fact and
    preserves the historic base-only behaviour: when an invoice-evidenced
    ``taxable_base`` is known, only that net-of-IVA base becomes the IRPF-deductible
    cost. That is correct for the common case (an activity with full deduction
    rights recovers its input IVA through Modelo 303, so the IVA is not also an
    IRPF expense), but it is silently wrong whenever the activity's right to deduct
    is less than total: PGC NRV 12.ª treats non-recoverable input IVA as part of
    the acquisition cost, so the portion the taxpayer cannot deduct for IVA
    purposes must join the IRPF gasto. Populating this field with the resolved
    IVA-deduction percentage (``1`` for full deduction, ``0`` for a wholly exempt
    activity with no right to deduct, a fractional value under prorrata general or
    especial) makes ``1 - iva_deduction_ratio`` of ``iva_amount`` join the
    deductible base. See :func:`evaluate_renta_deductibility`.

    Populated by :func:`~application.aggregation._renta_ledger.aggregate_renta_ledger_expenses_from_repositories`
    for the M100 annual first slice, via
    ``application.aggregation._renta_ledger._resolve_iva_deduction_ratio``: a
    wholly ``EXENTO`` ``iva.regime`` profile fact resolves to ``0`` outright;
    otherwise the bucket's ``domain.prorrata_register.ProrrataRegister``
    whole-entity entry for the ejercicio contributes its in-force provisional
    percentage under ``GENERAL`` or ``ESPECIAL``. The M130 quarterly pagos
    fraccionados gasto path (``application.aggregation._renta_gasto_ledger``)
    does not construct a :class:`RentaDeductibilityContext` at all and is not
    wired to this axis -- a named follow-up, not silently covered here.
    """
    residence_ccaa: CCAA | None = None
    """Ordinary residence comunidad autonoma, sourced from ``TaxResidenceProfile.ccaa``.

    Optional and inert for the general expense path: LIRPF arts. 28-30 base-imponible
    deductibility is state law and does not vary by comunidad (Ley 22/2009 cesion
    framework grants no base competence to the CCAA). The axis only selects a
    territorial-regime override where one is declared for the fact's category; when
    an override exists but this field is ``None`` the evaluation fails closed rather
    than silently choosing a base (see :func:`select_deductibility_profile`).
    """

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

    transaction_id: TransactionId
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

    transaction_id: TransactionId
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
    source_kind: Literal[BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION] = (
        BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION
    )
    modelo: Literal[Modelo.M100] = Modelo.M100
    period: Literal["0A"] = "0A"
    tax_year: int = Field(ge=2000, le=2099)
    activity_key: str = Field(min_length=1, max_length=128)
    target_casilla_id: CasillaId
    transaction_id: TransactionId
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
        if self.target_casilla_id != RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS.get(self.category):
            raise RentaValidationError("target_casilla_id must match the first-slice category mapping")
        if not Period.from_year_and_code(self.tax_year, "0A").contains(self.filing_date):
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


def resolve_region_category_profiles(
    profile_year: int,
) -> Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]]:
    """Return the territorial-regime category-profile overrides for a filing year.

    The override layer is provisioned but deliberately empty: the only genuinely
    region-varying expense-side regimes reach the base through their own dedicated
    bindings (the Reserva para Inversiones en Canarias, Ley 19/1994 art. 27, is
    modelled as its own binding, not a :class:`SpendingCategory` profile), and the
    Ceuta/Melilla benefit is an art. 68.4 cuota deduction rather than a
    base-imponible expense rule. No :class:`SpendingCategory` therefore warrants a
    per-comunidad deductibility variant today, so this resolver returns an empty
    mapping and every fact falls through to the state year profile. A future
    territorial-regime enrollment populates this mapping (grounded to its regime
    law) with no further architectural change.

    Returns:
        Mapping from :class:`CCAA` to a per-:class:`SpendingCategory` override
        profile mapping; empty until a territorial regime is enrolled.
    """
    del profile_year
    empty: dict[CCAA, Mapping[SpendingCategory, CategoryProfile]] = {}
    return MappingProxyType(empty)


def select_deductibility_profile(
    *,
    state_profile: CategoryProfile,
    region_override_profiles: Mapping[CCAA, CategoryProfile],
    context: RentaDeductibilityContext,
) -> CategoryProfile | None:
    """Select the applicable category profile, honouring territorial-regime overrides.

    ``region_override_profiles`` holds the per-:class:`CCAA` overrides declared for
    the fact's category (empty for the general state-law case). Selection:

    - no override for the category: return ``state_profile`` unchanged (general
      expense deductibility is state base-imponible law, invariant across comunidades);
    - the category carries an override but ``context.residence_ccaa is None``: return
      ``None`` (D4 fail-closed) so the caller refuses rather than silently choosing a
      base for an undeclared region;
    - the residence comunidad has an override: return that override profile;
    - the residence comunidad has no override (a different comunidad owns the regime):
      return ``state_profile`` (state law applies to this taxpayer's region).

    Returns:
        The selected :class:`CategoryProfile`, or ``None`` when a region override
        exists for the category but the residence comunidad is undeclared.
    """
    if not region_override_profiles:
        return state_profile
    if context.residence_ccaa is None:
        return None
    return region_override_profiles.get(context.residence_ccaa, state_profile)


def evaluate_renta_deductibility(
    fact: RentaDeductibleExpenseFact,
    profile: CategoryProfile,
    context: RentaDeductibilityContext,
) -> RentaDeductibilityResult:
    """Evaluate one classified ledger fact and return a :class:`RentaDeductibilityResult`.

    ``deductible_basis`` (see :func:`_deductible_basis_amount`) folds in the
    non-deductible-for-IVA-purposes share of the fact's input IVA when
    ``context.iva_deduction_ratio`` states it, so an exempt or prorrata-rationed
    activity does not lose that real cost.
    """
    if profile.category is not fact.category:
        raise RentaValidationError(
            f"profile category {profile.category.value!r} does not match fact category {fact.category.value!r}",
        )
    rule = profile.proportionality
    deductible_basis = _deductible_basis_amount(fact, context)
    deductible_abs: Decimal
    applied_ratio: Decimal | None
    cap_applied: Decimal | None = None
    status = RentaDeductibilityStatus.ELIGIBLE
    reason = "deductible"

    if rule.kind is ProportionalityKind.FULL_DEDUCTIBLE:
        deductible_abs = deductible_basis
        applied_ratio = Decimal("1")
    elif rule.kind is ProportionalityKind.FIXED_PERCENTAGE:
        assert rule.fixed_pct is not None
        applied_ratio = rule.fixed_pct
        deductible_abs = deductible_basis * applied_ratio
    elif rule.kind in {ProportionalityKind.USAGE_RATIO_HOME_AREA, ProportionalityKind.USAGE_RATIO_PERSONAL}:
        ratio = context.usage_ratios.get(fact.category, rule.default_ratio)
        if ratio is None:
            status = RentaDeductibilityStatus.INELIGIBLE
            reason = "missing usage ratio"
            applied_ratio = None
            deductible_abs = Decimal("0")
        else:
            applied_ratio = ratio
            deductible_abs = deductible_basis * ratio
    elif rule.kind is ProportionalityKind.STATUTORY_CAP:
        cap_applied = _resolve_statutory_cap(rule=rule, context=context)
        if cap_applied is None:
            status = RentaDeductibilityStatus.INELIGIBLE
            reason = "missing statutory cap context"
            applied_ratio = None
            deductible_abs = Decimal("0")
        else:
            deductible_abs = min(deductible_basis, cap_applied)
            applied_ratio = Decimal("0") if deductible_basis == Decimal("0") else deductible_abs / deductible_basis
    elif rule.kind is ProportionalityKind.NON_DEDUCTIBLE:
        status = RentaDeductibilityStatus.INELIGIBLE
        reason = "non deductible category"
        applied_ratio = Decimal("0")
        deductible_abs = Decimal("0")
    elif rule.kind is ProportionalityKind.REQUIRES_EXCLUSIVE_USE:
        if context.exclusive_use_confirmed:
            applied_ratio = Decimal("1")
            # The confirmation gates WHETHER the cost is deductible, never what
            # the deductible cost is, so this reads the same basis its five
            # sibling branches do. Deducting the IVA-inclusive gross here would
            # claim the input IVA a second time: the activity already recovers
            # it as cuota soportada on Modelo 303, and only the share it has no
            # right to deduct is real acquisition cost (PGC NRV 12.ª) -- which
            # is exactly what ``_deductible_basis_amount`` folds in.
            deductible_abs = deductible_basis
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


def _deductible_basis_amount(fact: RentaDeductibleExpenseFact, context: RentaDeductibilityContext) -> Decimal:
    """Return the IRPF-deductible cost basis, joining non-deductible input IVA to it.

    Uses the net-of-IVA ``taxable_base`` when known, falling back to
    ``gross_amount`` (already IVA-inclusive) when no invoice evidence split it.
    When the fact carries both a ``taxable_base`` and an ``iva_amount``, and
    ``context.iva_deduction_ratio`` states the activity's IVA-deduction
    percentage, the portion of ``iva_amount`` the activity has no right to deduct
    (PGC NRV 12.ª) joins the base as real acquisition cost. A ``None`` ratio (not
    yet evaluated) or a missing ``iva_amount`` leaves the base untouched, matching
    the historic behaviour.
    """
    base = fact.taxable_base if fact.taxable_base is not None else fact.gross_amount
    if fact.taxable_base is None or fact.iva_amount is None or context.iva_deduction_ratio is None:
        return base
    non_deductible_iva = fact.iva_amount * (Decimal("1") - context.iva_deduction_ratio)
    return base + non_deductible_iva


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
    target_casilla_id = RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS.get(fact.category)
    if target_casilla_id is None:
        raise RentaValidationError(f"category {fact.category.value!r} is outside the first Renta expense slice")
    if not Period.from_year_and_code(tax_year, "0A").contains(fact.filing_date):
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
        target_casilla_id=target_casilla_id,
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
        annual = [variant for variant in rule.statutory_cap_variants if not variant.is_per_day]
        if annual:
            return _resolve_annual_variant_cap(annual, context=context)
        if context.statutory_cap_variant_id is None or context.statutory_cap_days is None:
            return None
        for variant in rule.statutory_cap_variants:
            if variant.id == context.statutory_cap_variant_id:
                per_day = variant.statutory_cap_eur_per_day
                if per_day is None:
                    return None
                return per_day * context.statutory_cap_days
        return None
    return None


def _resolve_annual_variant_cap(
    variants: Sequence[StatutoryCapVariant],
    *,
    context: RentaDeductibilityContext,
) -> Decimal | None:
    """Sum an annual per-person cap across the populations each variant governs.

    Unlike a daily variant set, where one condition selects one amount, an annual
    per-person set applies EVERY variant at once to its own share of the insured
    persons: LIRPF art. 30.2.5.a allows 500 for each ordinary person AND 1.500 for
    each person with discapacidad in the same return.

    Returns:
        The summed cap, or ``None`` when no population has been counted -- absence of
        counts is unknown, not zero, and returning zero would cap the deduction at
        nothing.
    """
    counts = context.statutory_cap_variant_person_counts
    if not counts:
        # Nothing is known about which persons meet the condition the higher limb
        # requires. The ordinary limit is what the article grants absent that
        # condition, so the conservative limb applies to the persons we do know
        # about. This reproduces the behaviour that shipped before the second limb
        # existed, so an uninformed caller is never worse off than it was, while a
        # caller that supplies the counts gets the lawful sum.
        lowest = min(
            (variant.statutory_cap_eur for variant in variants if variant.statutory_cap_eur is not None),
            default=None,
        )
        if lowest is None:
            return None
        return lowest * Decimal(context.statutory_cap_person_count)
    declared = {variant.id for variant in variants}
    unknown = sorted(set(counts) - declared)
    if unknown:
        raise RentaValidationError(
            f"statutory cap variant person counts name variants the rule does not declare: {unknown}",
        )
    total = Decimal("0")
    for variant in variants:
        amount = variant.statutory_cap_eur
        if amount is None:
            return None
        total += amount * Decimal(counts.get(variant.id, 0))
    return total


def _observation_id(fact: RentaDeductibleExpenseFact) -> str:
    if fact.invoice_id is None:
        return f"renta-expense:{fact.catalogue_id}:{fact.transaction_id}"
    return f"renta-expense:{fact.catalogue_id}:{fact.transaction_id}:{fact.invoice_id}"


def _require_decimal(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Decimal) or not value.is_finite():
        raise RentaValidationError(f"{field_name} must be a finite Decimal")


__all__ = [
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
    "resolve_region_category_profiles",
    "select_deductibility_profile",
]
