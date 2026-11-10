"""Repository-backed Renta deductible-expense (gasto) aggregation.

Loads ledger rows through the application-facing
:class:`~domain.transactions.protocols.TransactionCatalogueRepositoryProtocol`.

Used by the source mesh for the selected deductible-expense target.

This is the OUTGOING sibling of :mod:`~.renta_income_ledger`. Where the income
pipeline accumulates professional-activity revenue into its selected target,
this pipeline accumulates deductible business expenses into its selected target over the same
cumulative year-to-date quarterly window (RD 439/2007 art. 110.2). The two
pipelines share the lightweight ledger-projection mechanism and the cumulative
window; they differ only in flow direction and the casilla they feed.

Cumulative window rule (RD 439/2007 art. 110.2):
  For period Qn in year Y the window is [Jan 1, Y] through [last day of Qn, Y].

Only ACTIVE, EUR-denominated, OUTGOING transactions whose explicit
``irpf_category`` marks ``actividad_economica`` or whose
``business_classification`` is BUSINESS or MIXED are eligible. The deductible
amount is the IVA-exclusive base imponible (``taxable_base``), plus the
non-recoverable share of ``iva_amount`` when the activity's IVA-deduction ratio
(:func:`~.renta_ledger.resolve_iva_deduction_ratio`, the provisional percentage
a quarter runs on; the annual return closes on the definitive one) is less than
full: IVA soportado a taxpayer cannot recover through
The indirect-tax input is PGC NRV 12.ª acquisition cost, same as the annual side (LIRPF arts.
28-30 base-imponible deductibility governs the pago fraccionado's gasto
determination identically to the annual declaration). A declarable expense
without ``taxable_base`` is surfaced as ``missing_taxable_base`` instead of being
gross-folded into the selected target.

A row that declares a spending category is run through that category's
proportionality rule by the SAME evaluator the annual first-slice pipeline uses
(:func:`~cadrumo.domain.renta.ledger_expenses.evaluate_renta_deductibility`),
against rules built by :func:`~.renta_ledger.resolve_category_deduction_rules`.
A usage-ratio category (home-office suministros) is therefore
apportioned once, by the operator's ratio and the rule's statutory multiplier,
whatever the row's classification; a MIXED row's stored ``business_pct`` scales
every other category. A row declaring no category is refused, as the annual
pipeline refuses it: the payment is computed on the same rendimiento neto
(RIRPF art. 110.1.a), and no deduction rule can run without knowing the expense.

This module does NOT reuse the annual pipeline's invoice-evidence
reconciliation or its annual window, which are constraint-shape-divergent from
the quarterly cumulative gasto sum. It shares that module's category-rule
construction, its provisional IVA-deduction-ratio resolver
(:func:`~.renta_ledger.resolve_iva_deduction_ratio`) and its residence lookup;
:class:`InvoiceCatalogue`, the profile's invoice catalogue.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, NamedTuple

from pydantic import BaseModel, Field

from ...core.casilla_id import CasillaId
from ...core.i18n.translatable import Translatable as tr
from ...core.identity.transaction_ids import TransactionId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.money.rounding import round_to_cents
from ...core.period import Period
from ...core.prose_elision import IssueDetail
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.categories.profile import CategoryProfile
from ...domain.categories.spending_category import SpendingCategory
from ...domain.contribuyente.ccaa import CCAA
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.iva.schema import InvoiceKind
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.renta.ledger_expenses import (
    RentaDeductibilityStatus,
    RentaDeductibleExpenseFact,
    RentaExpenseDirection,
    StatutoryCapClaim,
    evaluate_renta_deductibility,
    normalize_spending_category,
    statutory_cap_trims,
)
from ...domain.transactions.date_partition import OutOfWindowTransactionSummary
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...domain.transactions.tipo_actividad_partitions import agrarian_instalment_activity_codes
from ...domain.user_profile.values import UserProfileRecord
from . import shared_issue_reasons
from .currency_predicates import (
    effective_eur_amount,
    effective_eur_iva_amount,
    effective_eur_recargo_amount,
    effective_eur_taxable_base,
    is_non_eur_without_conversion,
)
from .errors import AggregationValidationError
from .grouping import CumulativeWindow, cumulative_year_to_date_window, fold_casilla_observations
from .models import CasillaAggregation, LedgerAggregationResultBase
from .renta_business_eligibility import (
    RentaExpenseAdvisory,
    exclusive_business_use,
    is_supplier_refund,
    renta_expense_business_proportion,
    row_scaling_proportion,
)

# Intra-package reuse of the sibling ledger's category-rule construction and
# resolvers, permitted by the architecture rule; the cross-package boundary is
# enforced elsewhere.
from .renta_imputation import (
    ImputationCriteria,
    ImputationUnresolved,
    expense_incurred_date,
    impute_ledger_row,
    received_invoice_reference,
    rows_left_out_summary,
    rows_touching_window,
)
from .renta_income_diagnostics import received_rectificativa_reading
from .renta_ledger import (
    RentaCategoryDeductionRules,
    accepted_row_advisory,
    resolve_category_deduction_rules,
    resolve_iva_deduction_ratio,
    resolve_residence_ccaa,
)
from .renta_ledger_classification import CategoryRuleRefusal, refusal_issue_reason, resolve_category_rule
from .renta_ledger_evidence import (
    LinkedInvoiceCuotas,
    linked_invoice_cuotas,
    purchase_invoice_evidence_payload,
    refund_left_to_correction_netting,
)
from .renta_ledger_models import RentaLedgerAggregationIssue

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext

# Registry authority: selected Renta expense model, target, category policy, and
# binding declarations are consumed through RegistryQueryService


class RentaGastoLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce a gasto observation.

    Only reasons that represent a *dropped declarable gasto* — a BUSINESS / MIXED
    expense excluded by a downstream gate — are modelled, so every emitted issue
    is a genuine no-silent-under-declaration signal. Receipts and PERSONAL /
    unclassified OUTGOING rows are skipped silently (they are not deductible
    gastos) and never produce an issue.
    """

    UNSUPPORTED_CURRENCY = shared_issue_reasons.UNSUPPORTED_CURRENCY
    OUTSIDE_PERIOD = shared_issue_reasons.OUTSIDE_PERIOD
    # RIRPF art. 7 cannot place the row in an ejercicio; it enters no box.
    IMPUTATION_UNRESOLVED = "imputation_unresolved"
    # A BUSINESS / MIXED expense with no declared IVA-exclusive base imponible:
    # the gross transfer includes indirect tax recovered elsewhere,
    # which is NOT a Renta gasto, so it cannot be aggregated IVA-exclusively. The
    # row is surfaced (no silent over-declaration of gastos) rather than
    # gross-folded; the operator tags it with a taxable_base via classify.
    MISSING_TAXABLE_BASE = "missing_taxable_base"
    # An expense with no spending category: no deduction rule can run on it, and
    # the gasto is not zero either, so the row is held back.
    MISSING_CATEGORY = shared_issue_reasons.MISSING_CATEGORY
    # The row's category rule could not be evaluated or refused the row. Each
    # is a declarable gasto the rule dropped, so it is surfaced, never summed
    # at full value in place of the rule.
    UNKNOWN_CATEGORY = shared_issue_reasons.UNKNOWN_CATEGORY
    MISSING_CATEGORY_PROFILE = shared_issue_reasons.MISSING_CATEGORY_PROFILE
    REGION_UNDECLARED_FOR_OVERRIDE = shared_issue_reasons.REGION_UNDECLARED_FOR_OVERRIDE
    INVALID_LEDGER_FACT = shared_issue_reasons.INVALID_LEDGER_FACT
    INELIGIBLE_DEDUCTIBILITY = shared_issue_reasons.INELIGIBLE_DEDUCTIBILITY
    EXCLUSIVE_USE_REQUIRED = shared_issue_reasons.EXCLUSIVE_USE_REQUIRED
    MISSING_OWNERSHIP_SHARE = shared_issue_reasons.MISSING_OWNERSHIP_SHARE
    # A supplier's refund whose invoice cannot state what it takes back.
    REFUND_EVIDENCE_REFUSED = "refund_evidence_refused"


#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.


class RentaGastoLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while aggregating gasto ledger rows."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    reason: RentaGastoLedgerAggregationIssueReason
    detail: IssueDetail
    category_id: str | None = Field(default=None, min_length=1, max_length=128)
    """The row's ledger category, so a refused row can still be recognised by what it declares."""


class RentaGastoObservation(BaseModel):
    """One eligible OUTGOING deductible-expense ledger row.

    Carries the typed deductible amount and the target casilla id it feeds. The
    domain registry resolver matches ``target_casilla_id`` against the binding
    selector and sums ``deductible_amount`` across all observations for that
    casilla, mirroring the income resolver's casilla-keyed fold.

    ``deductible_amount`` is the IVA-exclusive base imponible
    (``transaction.taxable_base``), plus any non-recoverable input IVA, after the
    row's category rule: a usage-ratio category applies the operator's ratio, any
    other category the MIXED business fraction. A supplier's refund states it below
    zero, so the fold takes it off the expense.
    """

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    target_casilla_id: CasillaId
    deductible_amount: Decimal
    filing_date: date
    category_id: str | None = Field(default=None, min_length=1, max_length=128)
    """The row's ledger spending category, or ``None`` when it declares none.

    Every quarterly gasto lands on one target casilla, so the category cannot be
    read back from :attr:`target_casilla_id` the way the annual first-slice
    observation allows. It is carried here because a consumer still has to tell
    an amortization-labelled row from an ordinary one -- the activity-asset
    register's collision test is exactly that question -- and a row marked
    business by classification alone legitimately carries no category.
    """


class RentaGastoLedgerAggregation(
    LedgerAggregationResultBase[RentaGastoObservation, RentaGastoLedgerAggregationIssue],
):
    """Cumulative deductible-expense observations for one quarter window.

    ``out_of_window_summary`` is populated by repository-backed date partitions.
    Full-catalogue aggregation keeps row-level issues because every transaction
    is already loaded for classification.
    """

    out_of_window_summary: OutOfWindowTransactionSummary | None = None
    advisories: tuple[RentaExpenseAdvisory, ...] = ()
    """Rows that keep their figure under a reading of the law the operator should review."""


def aggregate_renta_gasto_ledger_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    modelo: str,
    target_casilla_id: CasillaId,
    accept_activity_marker: bool,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
    usage_ratios: Mapping[SpendingCategory, Decimal] | None = None,
    profile_record: UserProfileRecord | None = None,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    operation: PinnedAuthorityOperation | None = None,
    ownership_share: Decimal | None = None,
    register_owned_transaction_ids: frozenset[str] = frozenset(),
    criteria: ImputationCriteria | None = None,
    invoices: InvoiceCatalogue | None = None,
) -> RentaGastoLedgerAggregation:
    """Load the transaction catalogue and aggregate a cumulative expense window.

    Derives the activity's IVA-deduction ratio through
    :func:`~.renta_ledger.resolve_iva_deduction_ratio`, for the ejercicio
    (``period.filing_year``). ``profile_record`` (a
    :class:`UserProfileRecord`) and ``prorrata_register_repository`` supply the
    profile and canonical register directly. ``usage_ratios`` carries the
    effective per-category ratios (the same mapping the annual pipeline is
    given), which the category rule of a usage-ratio row multiplies by.
    ``operation`` retains the caller's generation for every registry lookup;
    a lease is admitted here only for standalone callers.

    Returns a :class:`RentaGastoLedgerAggregation`.

    ``invoices`` is the :class:`InvoiceCatalogue`, the profile's invoice catalogue.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return aggregate_renta_gasto_ledger_from_repositories(
                bucket_id=bucket_id,
                period=period,
                modelo=modelo,
                target_casilla_id=target_casilla_id,
                accept_activity_marker=accept_activity_marker,
                transaction_repository=transaction_repository,
                usage_ratios=usage_ratios,
                profile_record=profile_record,
                prorrata_register_repository=prorrata_register_repository,
                operation=indexed_operation,
                ownership_share=ownership_share,
                register_owned_transaction_ids=register_owned_transaction_ids,
                criteria=criteria,
                invoices=invoices,
            )
    repository = transaction_repository
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            tr("aggregation.renta_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    # Only the cumulative in-window subset is decrypted and classified. The
    # out-of-window remainder comes from the plaintext date index and is
    # reported uniformly as ``OUTSIDE_PERIOD``.
    window = cumulative_year_to_date_window(period)
    left_out: OutOfWindowTransactionSummary | None = None
    if criteria is None or invoices is None:
        partition = repository.partition_by_date_range(window.start, window.end)
        catalogue = partition.in_window
    else:
        # A row's date may be its invoice's, so a row banked outside the window can belong in it.
        partition = None
        whole_catalogue = repository.load()
        catalogue = rows_touching_window(
            whole_catalogue,
            invoices,
            kind=InvoiceKind.RECEIVED,
            invoice_id_of=received_invoice_reference,
            start=window.start,
            end=window.end,
            criteria=criteria,
        )
        left_out = rows_left_out_summary(whole_catalogue, catalogue)
    iva_deduction_ratio = resolve_iva_deduction_ratio(
        bucket_id=bucket_id,
        ejercicio=period.filing_year,
        profile_record=profile_record,
        prorrata_register_repository=prorrata_register_repository,
        operation=operation,
    )
    result = aggregate_renta_gasto_ledger(
        catalogue,
        bucket_id=bucket_id,
        period=period,
        iva_deduction_ratio=iva_deduction_ratio,
        modelo=modelo,
        target_casilla_id=target_casilla_id,
        accept_activity_marker=accept_activity_marker,
        usage_ratios=usage_ratios,
        residence_ccaa=resolve_residence_ccaa(
            bucket_id=bucket_id,
            profile_record=profile_record,
            operation=operation,
        ),
        profile_record=profile_record,
        operation=operation,
        ownership_share=ownership_share,
        register_owned_transaction_ids=register_owned_transaction_ids,
        criteria=criteria,
        invoices=invoices,
    )
    out_of_window_summary = (
        left_out
        if partition is None
        else partition.out_of_window_summary
        or OutOfWindowTransactionSummary.from_index_entries(partition.out_of_window)
    )
    return result.model_copy(
        update={"out_of_window_summary": out_of_window_summary},
    )


def aggregate_renta_gasto_ledger(
    transactions: TransactionCatalogue,
    *,
    bucket_id: str,
    period: Period,
    modelo: str,
    target_casilla_id: CasillaId,
    accept_activity_marker: bool,
    iva_deduction_ratio: Decimal | None = None,
    usage_ratios: Mapping[SpendingCategory, Decimal] | None = None,
    residence_ccaa: CCAA | None = None,
    region_category_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]] | None = None,
    profile_record: UserProfileRecord | None = None,
    profile_decode_context: ProfileDecodeContext | None = None,
    operation: PinnedAuthorityOperation | None = None,
    ownership_share: Decimal | None = None,
    register_owned_transaction_ids: frozenset[str] = frozenset(),
    criteria: ImputationCriteria | None = None,
    invoices: InvoiceCatalogue | None = None,
) -> RentaGastoLedgerAggregation:
    """Aggregate OUTGOING deductible-expense transactions into a selected target.

    Args:
        transactions: The :class:`TransactionCatalogue` of ledger transactions to aggregate.
        bucket_id: Bucket identifier carried through to provenance and audit
            records so the resulting aggregation cannot be silently misattributed.
        period: The quarterly :class:`Period` whose year anchors the cumulative
            window.
        modelo: Selected model identifier receiving the aggregation.
        target_casilla_id: Registry-selected output casilla for deductible expenses.
        accept_activity_marker: Whether activity-marked transactions are eligible.
        iva_deduction_ratio: Optional activity-wide IVA-deduction fraction (LIVA
            arts. 94/104), joining the non-recoverable share of a row's
            ``iva_amount`` to its deductible base (PGC NRV 12.ª). ``None`` (the
            default) preserves the historic base-only behaviour.
        usage_ratios: Optional per-:class:`SpendingCategory` effective usage
            ratios (statutory multiplier included), applied once by the
            category rule of a usage-ratio row.
        residence_ccaa: Optional ordinary-residence comunidad, selecting a
            territorial-regime category override.
        region_category_overrides: Optional per-comunidad category-profile
            override layer; defaults to the registry-provisioned (empty) layer.
        profile_record: Optional :class:`UserProfileRecord` supplying the
            insured-person counts of the statutory cap; loaded from the bucket
            when ``None``.
        profile_decode_context: Optional decode context from the caller-held
            authority operation.
        operation: Existing generation-pinned authority operation. When omitted,
            one indexed operation is opened at this composition boundary.
        ownership_share: The taxpayer's ownership share of the partly affected
            dwelling, applied by the categories whose rule requires it.
        register_owned_transaction_ids: The ledger rows the activity-asset
            register declares as an asset's acquisition; the register deducts
            them through its amortization schedule.
        criteria: The dated imputation election that places each row; ``None``
            keeps the bank date, for a caller not consulting the profile.
        invoices: The catalogue whose received invoices date a row under accrual.

    Returns a :class:`RentaGastoLedgerAggregation` covering the cumulative
    fiscal window. ``period`` must be quarterly; the cumulative window extends
    from Jan 1 of the period's year through the last day of the declared quarter
    (RD 439/2007 art. 110.2).

    ``invoices`` is the :class:`InvoiceCatalogue`, the profile's invoice catalogue.
    """
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return aggregate_renta_gasto_ledger(
                transactions,
                bucket_id=bucket_id,
                period=period,
                modelo=modelo,
                target_casilla_id=target_casilla_id,
                accept_activity_marker=accept_activity_marker,
                iva_deduction_ratio=iva_deduction_ratio,
                usage_ratios=usage_ratios,
                residence_ccaa=residence_ccaa,
                region_category_overrides=region_category_overrides,
                profile_record=profile_record,
                profile_decode_context=profile_decode_context,
                operation=indexed_operation,
                ownership_share=ownership_share,
                register_owned_transaction_ids=register_owned_transaction_ids,
                criteria=criteria,
                invoices=invoices,
            )
    window = cumulative_year_to_date_window(period)
    rules = resolve_category_deduction_rules(
        bucket_id=bucket_id,
        profile_year=period.filing_year,
        modelo=modelo,
        usage_ratios=usage_ratios,
        residence_ccaa=residence_ccaa,
        region_category_overrides=region_category_overrides,
        iva_deduction_ratio=iva_deduction_ratio,
        profile_record=profile_record,
        profile_decode_context=profile_decode_context,
        operation=operation,
        ownership_share=ownership_share,
        register_owned_transaction_ids=register_owned_transaction_ids,
    )

    observations, issues, advisories = _classified_gasto_rows(
        transactions,
        bucket_id=bucket_id,
        window=window,
        target_casilla_id=target_casilla_id,
        accept_activity_marker=accept_activity_marker,
        rules=rules,
        criteria=criteria,
        invoices=invoices,
        operation=operation,
    )

    if criteria is not None and invoices is not None:
        observations = _net_received_corrections(
            observations,
            transactions,
            received_rectificativa_reading(
                invoices,
                transactions,
                bucket_id=bucket_id,
                window_start=window.start,
                window_end=window.end,
                criteria=criteria,
            ).fractions,
        )
    observations = _apply_statutory_cap_trims(observations, rules=rules, transactions=transactions, invoices=invoices)
    casilla_aggregation = _gasto_casilla_aggregation(
        window.period,
        observations,
        modelo=modelo,
    )
    return RentaGastoLedgerAggregation(
        modelo=modelo,
        period=window.period,
        observations=tuple(observations),
        issues=tuple(issues),
        casilla_aggregation=casilla_aggregation,
        advisories=tuple(advisories),
    )


def _classified_gasto_rows(
    transactions: TransactionCatalogue,
    *,
    bucket_id: str,
    window: CumulativeWindow,
    target_casilla_id: CasillaId,
    accept_activity_marker: bool,
    rules: RentaCategoryDeductionRules,
    criteria: ImputationCriteria | None,
    invoices: InvoiceCatalogue | None,
    operation: PinnedAuthorityOperation,
) -> tuple[list[RentaGastoObservation], list[RentaGastoLedgerAggregationIssue], list[RentaExpenseAdvisory]]:
    """Place every active, non-agrarian ledger row into the target casilla, an issue or an advisory."""
    observations: list[RentaGastoObservation] = []
    issues: list[RentaGastoLedgerAggregationIssue] = []
    advisories: list[RentaExpenseAdvisory] = []

    # Apartado I of the form takes no agrarian figure; apartado II is a share of income alone.
    agrarian = agrarian_instalment_activity_codes(effective_date=window.period.end_date, authority=operation)
    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        if transaction.tipo_actividad in agrarian:
            continue
        outcome = classify_gasto_transaction(
            transaction,
            bucket_id=bucket_id,
            cumulative_start=window.start,
            cumulative_end=window.end,
            target_casilla_id=target_casilla_id,
            accept_activity_marker=accept_activity_marker,
            rules=rules,
            criteria=criteria,
            invoices=invoices,
        )
        if outcome is None:
            continue
        if isinstance(outcome, RentaGastoLedgerAggregationIssue):
            issues.append(outcome.model_copy(update={"category_id": transaction.category_id}))
        else:
            observations.append(outcome)
            advisory = accepted_row_advisory(transaction, rules=rules)
            if advisory is not None:
                advisories.append(advisory)
    return observations, issues, advisories


def classify_gasto_transaction(
    transaction: Transaction,
    *,
    bucket_id: str,
    cumulative_start: date,
    cumulative_end: date,
    target_casilla_id: CasillaId,
    accept_activity_marker: bool,
    rules: RentaCategoryDeductionRules,
    criteria: ImputationCriteria | None = None,
    invoices: InvoiceCatalogue | None = None,
) -> RentaGastoObservation | RentaGastoLedgerAggregationIssue | None:
    """Filter one ledger transaction against the selected expense pipeline.

    Returns a :class:`RentaGastoObservation` for an eligible deductible expense,
    a :class:`RentaGastoLedgerAggregationIssue` for an OUTGOING row that fails a
    gate or that its category rule refuses (so the operator sees the dropped
    expense rather than a silent zero), or ``None`` for a receipt that this
    expense pipeline simply does not own (it is the income pipeline's concern,
    never a gasto issue). A supplier's refund is an expense row with its sign
    reversed, read as the annual pipeline reads it.

    ``invoices`` is a :class:`InvoiceCatalogue`.
    """
    transaction_id = transaction.transaction_id
    refunded = is_supplier_refund(transaction)
    proportion = _owned_gasto_proportion(transaction, refunded=refunded, accept_activity_marker=accept_activity_marker)
    if proportion is None:
        return None

    filing_date = _imputed_gasto_date(transaction, criteria=criteria, invoices=invoices)
    if isinstance(filing_date, ImputationUnresolved):
        return _unplaced_gasto_issue(
            transaction,
            filing_date,
            cumulative_start=cumulative_start,
            cumulative_end=cumulative_end,
            rules=rules,
        )
    if criteria is not None and not cumulative_start <= filing_date <= cumulative_end:
        return None
    refund = None
    if refunded:
        refund = _refund_figures(transaction, invoices=invoices, bucket_id=bucket_id, netting=criteria is not None)
        if refund is None or isinstance(refund, RentaGastoLedgerAggregationIssue):
            return refund
    gate_issue = _gasto_gate_issue(
        transaction,
        transaction_id=transaction_id,
        cumulative_start=cumulative_start,
        cumulative_end=cumulative_end,
        filing_date=filing_date,
        base_known=refund is not None,
    )
    if gate_issue is not None:
        return gate_issue

    evaluated = _evaluated_gasto_deduction(
        transaction, refund=refund, proportion=proportion, rules=rules, invoices=invoices
    )
    if isinstance(evaluated, RentaGastoLedgerAggregationIssue):
        return evaluated
    return RentaGastoObservation(
        transaction_id=transaction_id,
        target_casilla_id=target_casilla_id,
        deductible_amount=evaluated,
        filing_date=filing_date,
        category_id=transaction.category_id,
    )


def _owned_gasto_proportion(
    transaction: Transaction, *, refunded: bool, accept_activity_marker: bool
) -> Decimal | None:
    """Return the business proportion of a row this expense pass owns, or ``None`` when it skips the row.

    Other INCOMING rows belong to the income pipeline; this pass skips them without
    recording an issue so the operator is not shown a spurious gasto advisory for every
    receipt. A row the operator reviewed and deliberately excluded stays excluded, a
    stronger disposition than the actividad category tag. PERSONAL and unclassified
    OUTGOING rows are not deductible gastos unless an explicit activity category marks
    them as part of the selected activity set, so the operator sees a genuinely lost
    gasto from a downstream gate rather than advisory noise on every personal line.
    """
    if transaction.direction is not TransactionDirection.OUTGOING and not refunded:
        return None
    if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
        return None
    return _gasto_business_proportion(transaction, accept_activity_marker=accept_activity_marker)


def _evaluated_gasto_deduction(
    transaction: Transaction,
    *,
    refund: _RefundFigures | None,
    proportion: Decimal,
    rules: RentaCategoryDeductionRules,
    invoices: InvoiceCatalogue | None,
) -> Decimal | RentaGastoLedgerAggregationIssue:
    """Run the row through its category rule on the figures its invoice refund, or the row itself, states."""
    return _category_rule_deductible_amount(
        transaction,
        eur_base=_eur_taxable_base_after_gate(transaction) if refund is None else refund.taxable_base,
        eur_iva_amount=effective_eur_iva_amount(transaction) if refund is None else refund.iva_amount,
        proportion=proportion,
        rules=rules,
        refund=refund,
        linked_cuotas=None if refund is not None else linked_invoice_cuotas(transaction, invoices),
    )


class _RefundFigures(NamedTuple):
    """What the received invoice a supplier's refund is linked to says it takes back, in EUR."""

    invoice_id: str
    invoice_issue_date: date
    taxable_base: Decimal
    iva_amount: Decimal


def _refund_figures(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue | None,
    bucket_id: str,
    netting: bool,
) -> _RefundFigures | RentaGastoLedgerAggregationIssue | None:
    """Read a supplier's refund through the evidence check the annual pipeline applies.

    ``None`` leaves the row to what already owns it: a refund on a correction belongs to the
    correction netting, and with no catalogue there is no invoice to read it against.
    """
    invoice_id = transaction.purchase_invoice_evidence_id
    if invoices is None or invoice_id is None:
        return None
    if netting and refund_left_to_correction_netting(transaction, invoices):
        return None
    payload = purchase_invoice_evidence_payload(invoices=invoices, bucket_id=bucket_id, transaction=transaction)
    if isinstance(payload, RentaLedgerAggregationIssue):
        return RentaGastoLedgerAggregationIssue(
            transaction_id=transaction.transaction_id,
            reason=RentaGastoLedgerAggregationIssueReason.REFUND_EVIDENCE_REFUSED,
            detail=payload.detail,
        )
    if payload.invoice_issue_date is None or payload.taxable_base is None or payload.iva_amount is None:
        msg = f"transaction {transaction.transaction_id} cleared the refund evidence check without invoice figures"
        raise ValueError(msg)
    return _RefundFigures(invoice_id, payload.invoice_issue_date, payload.taxable_base, payload.iva_amount)


def _unplaced_gasto_issue(
    transaction: Transaction,
    unresolved: ImputationUnresolved,
    *,
    cumulative_start: date,
    cumulative_end: date,
    rules: RentaCategoryDeductionRules,
) -> RentaGastoLedgerAggregationIssue:
    """Return the issue for a row no ejercicio can place: outside the window, category-refused, or unplaced."""
    transaction_id = transaction.transaction_id
    cash = transaction.raw.value_date or transaction.raw.booked_date
    if not cumulative_start <= cash <= cumulative_end:
        return RentaGastoLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaGastoLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            detail=f"payment of {cash} is outside the cumulative gasto window",
        )
    # RIRPF art. 110.1.a computes the payment on the annual rendimiento neto, and the annual
    # pipeline judges the category first: the row needs its category whichever year it lands in.
    refusal = _category_refusal(transaction, rules=rules)
    if refusal is not None:
        return refusal
    return RentaGastoLedgerAggregationIssue(
        transaction_id=transaction_id,
        reason=RentaGastoLedgerAggregationIssueReason.IMPUTATION_UNRESOLVED,
        detail=f"{unresolved.value}: payment of {cash} cannot be placed in an ejercicio",
    )


def _eur_taxable_base_after_gate(transaction: Transaction) -> Decimal:
    """Return the EUR-equivalent taxable base of a row that cleared the missing-taxable-base gate."""
    # Both taxable_base and iva_amount are denominated in the row's NATIVE
    # currency (see domain.transactions.tests.test_gross_invariant), so a
    # converted foreign-currency row must go through the EUR-equivalent
    # accessors -- summing them raw would fold a native-currency figure into
    # a EUR-denominated target total.
    eur_base = effective_eur_taxable_base(transaction)
    # taxable_base is non-None here (the MISSING_TAXABLE_BASE guard above
    # returned for the None case), so the EUR-equivalent accessor cannot
    # return None either -- it is None only when its input is.
    if eur_base is None:
        msg = (
            f"transaction {transaction.transaction_id} cleared the missing-taxable-base gate but resolves no "
            "EUR-equivalent base imponible for the Renta gasto casilla"
        )
        raise ValueError(msg)
    return eur_base


def _category_refusal(
    transaction: Transaction,
    *,
    rules: RentaCategoryDeductionRules,
) -> RentaGastoLedgerAggregationIssue | None:
    """Return the issue for a row whose category cannot answer for its expense, or ``None`` when it can."""
    resolved = resolve_category_rule(
        transaction.category_id,
        profiles=rules.profiles,
        region_overrides=rules.region_overrides,
        context=rules.context,
        profile_year=rules.profile_year,
    )
    if not isinstance(resolved, CategoryRuleRefusal):
        return None
    return RentaGastoLedgerAggregationIssue(
        transaction_id=transaction.transaction_id,
        reason=RentaGastoLedgerAggregationIssueReason(resolved.reason),
        detail=resolved.detail,
    )


def _category_rule_deductible_amount(
    transaction: Transaction,
    *,
    eur_base: Decimal,
    eur_iva_amount: Decimal | None,
    proportion: Decimal,
    rules: RentaCategoryDeductionRules,
    refund: _RefundFigures | None = None,
    linked_cuotas: LinkedInvoiceCuotas | None = None,
) -> Decimal | RentaGastoLedgerAggregationIssue:
    """Run one categorised row through its category rule and return the deductible amount.

    The evaluator is the one the annual first-slice pipeline calls, so a
    usage-ratio category is apportioned by the operator's ratio and the rule's
    statutory multiplier exactly once, and the row's amounts are not also scaled
    by a MIXED ``business_pct`` that states the same ratio
    (:func:`~.renta_business_eligibility.row_scaling_proportion`).
    """
    transaction_id = transaction.transaction_id
    resolved = resolve_category_rule(
        transaction.category_id,
        profiles=rules.profiles,
        region_overrides=rules.region_overrides,
        context=rules.context,
        profile_year=rules.profile_year,
    )
    if isinstance(resolved, CategoryRuleRefusal):
        return RentaGastoLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaGastoLedgerAggregationIssueReason(resolved.reason),
            detail=resolved.detail,
        )
    category, profile = resolved
    scaling = row_scaling_proportion(transaction, proportion, profile.proportionality)
    eur_recargo = effective_eur_recargo_amount(transaction) if refund is None else None
    if linked_cuotas is not None:
        eur_iva_amount, eur_recargo = linked_cuotas.iva_amount, linked_cuotas.recargo_amount
    try:
        fact = _deductible_expense_fact(
            transaction,
            category=category,
            scaling=scaling,
            eur_base=eur_base,
            eur_iva_amount=eur_iva_amount,
            eur_recargo=eur_recargo,
            refund=refund,
        )
    except ValueError as exc:
        return RentaGastoLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaGastoLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
            detail=str(exc),
        )
    result = evaluate_renta_deductibility(fact, profile, rules.context)
    if result.status is not RentaDeductibilityStatus.ELIGIBLE:
        return RentaGastoLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaGastoLedgerAggregationIssueReason(refusal_issue_reason(result)),
            detail=result.reason,
        )
    return result.deductible_amount


def _deductible_expense_fact(
    transaction: Transaction,
    *,
    category: SpendingCategory,
    scaling: Decimal,
    eur_base: Decimal,
    eur_iva_amount: Decimal | None,
    eur_recargo: Decimal | None,
    refund: _RefundFigures | None,
) -> RentaDeductibleExpenseFact:
    """Build the expense fact one categorised row states, scaled by its business proportion."""
    return RentaDeductibleExpenseFact(
        transaction_id=transaction.transaction_id,
        invoice_id=None if refund is None else refund.invoice_id,
        catalogue_id="ledger",
        operation_date=transaction.raw.value_date or transaction.raw.booked_date,
        invoice_issue_date=None if refund is None else refund.invoice_issue_date,
        posting_date=transaction.raw.booked_date,
        gross_amount=effective_eur_amount(transaction) * scaling,
        taxable_base=eur_base * scaling,
        iva_amount=eur_iva_amount * scaling if eur_iva_amount is not None else None,
        recargo_amount=(None if eur_recargo is None else eur_recargo * scaling),
        direction=RentaExpenseDirection.OUTGOING_EXPENSE if refund is None else RentaExpenseDirection.REFUND,
        category=category,
        exclusive_business_use=exclusive_business_use(transaction),
    )


def _apply_statutory_cap_trims(
    observations: list[RentaGastoObservation],
    *,
    rules: RentaCategoryDeductionRules,
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue | None,
) -> list[RentaGastoObservation]:
    """Hold the cumulative-window observations that share one statutory cap to that cap together."""
    trims = statutory_cap_trims(
        tuple(
            StatutoryCapClaim(
                claim_id=observation.transaction_id,
                transaction_id=observation.transaction_id,
                category=normalize_spending_category(observation.category_id),
                imputed_on=observation.filing_date,
                incurred_on=expense_incurred_date(transactions.transactions[observation.transaction_id], invoices),
                deductible_amount=observation.deductible_amount,
            )
            for observation in observations
            if observation.category_id is not None
        ),
        profiles=rules.profiles,
        context=rules.context,
    )
    return [
        observation.model_copy(update={"deductible_amount": trims[observation.transaction_id]})
        if observation.transaction_id in trims
        else observation
        for observation in observations
    ]


def _net_received_corrections(
    observations: list[RentaGastoObservation],
    transactions: TransactionCatalogue,
    fractions: Mapping[str, Decimal],
) -> list[RentaGastoObservation]:
    """Take off each row what the corrections remove from its invoice, before any statutory cap reads it."""

    def corrected(observation: RentaGastoObservation) -> RentaGastoObservation:
        row = transactions.get(observation.transaction_id)
        fraction = None if row is None else fractions.get(received_invoice_reference(row) or "")
        if fraction is None:
            return observation
        return observation.model_copy(
            update={"deductible_amount": round_to_cents(observation.deductible_amount * (Decimal("1") - fraction))}
        )

    return [corrected(observation) for observation in observations]


def _imputed_gasto_date(
    transaction: Transaction,
    *,
    criteria: ImputationCriteria | None,
    invoices: InvoiceCatalogue | None,
) -> date | ImputationUnresolved:
    """Place one payment by the dated election, or by its bank date when no election is consulted."""
    cash = transaction.raw.value_date or transaction.raw.booked_date
    if criteria is None:
        return cash
    invoice_id = received_invoice_reference(transaction)
    invoice = None if invoices is None or invoice_id is None else invoices.get(invoice_id)
    return impute_ledger_row(transaction, invoice, kind=InvoiceKind.RECEIVED, criteria=criteria)


def _gasto_gate_issue(
    transaction: Transaction,
    *,
    transaction_id: str,
    cumulative_start: date,
    cumulative_end: date,
    filing_date: date,
    base_known: bool = False,
) -> RentaGastoLedgerAggregationIssue | None:
    """Return the first downstream issue for an eligible gasto transaction."""
    if not (cumulative_start <= filing_date <= cumulative_end):
        return RentaGastoLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaGastoLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            detail=f"filing date {filing_date} is outside the cumulative gasto window",
        )
    if is_non_eur_without_conversion(transaction):
        return RentaGastoLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaGastoLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            detail=f"transaction currency {transaction.raw.currency!r} is not supported for Renta gastos",
        )

    # A deductible gasto must declare its IVA-exclusive base imponible: the gross
    # transfer carries indirect tax that is recovered elsewhere and is
    # not a Renta gasto. Without a taxable_base we cannot fold it IVA-exclusively,
    # so surface it (the operator tags it via classify) rather than gross-folding
    # and silently OVER-declaring gastos (which would under-state the pago
    # fraccionado). Preflight already requires taxable_base, so this is a backstop.
    if transaction.taxable_base is None and not base_known:
        return RentaGastoLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=RentaGastoLedgerAggregationIssueReason.MISSING_TAXABLE_BASE,
            detail=(
                "OUTGOING business expense carries no taxable_base (IVA-exclusive base imponible); "
                "classify it with --taxable-base so its deductible gasto is aggregated into the selected target"
            ),
        )
    return None


def _gasto_business_proportion(
    transaction: Transaction,
    *,
    accept_activity_marker: bool,
) -> Decimal | None:
    """Return the business-attributed gasto proportion, or None if not eligible.

    Thin adapter over the shared
    :func:`~.renta_business_eligibility.renta_expense_business_proportion`
    predicate, requested with the selected activity-marker policy. The caller
    supplies the policy so separate projections cannot drift by silently
    choosing a category marker. Reviewed exclusions are short-circuited by the
    caller before reaching this helper.
    """
    return renta_expense_business_proportion(transaction, accept_activity_marker=accept_activity_marker)


def _gasto_casilla_aggregation(
    period: Period,
    observations: Sequence[RentaGastoObservation],
    *,
    modelo: str,
) -> CasillaAggregation:
    return fold_casilla_observations(
        observations,
        modelo=modelo,
        period=period,
        amount_fn=lambda observation: observation.deductible_amount,
    )


__all__ = [
    "RentaGastoLedgerAggregation",
    "RentaGastoLedgerAggregationIssue",
    "RentaGastoLedgerAggregationIssueReason",
    "RentaGastoObservation",
    "aggregate_renta_gasto_ledger",
    "aggregate_renta_gasto_ledger_from_repositories",
]
