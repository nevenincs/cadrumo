"""Repository-backed Modelo 100 Renta expense aggregation.

This is the annual first-slice expense projection behind the
``ledger_renta_gastos_estimacion_directa_aggregation`` source. It loads both a
:class:`~domain.transactions.TransactionCatalogue` and a
:class:`~domain.invoices.InvoiceCatalogue` from the active bucket through
:class:`~adapters.persistence.profile.transactions.TransactionCatalogueRepository` and
:class:`~adapters.persistence.profile.invoices.InvoiceCatalogueRepository`, uses
purchase-invoice evidence to validate deductible-expense facts, and returns
binding-ready :class:`~domain.renta.RentaDeductibleExpenseObservation`
records.

The source-mesh resolver in :mod:`~._modelo_bindings` applies the target
:class:`~domain.calculations.registry.ModeloRevision`, resolves registry
bindings, and reports source issues or unrouted expenses on its
:class:`~._source_mesh.CalculationSourceResolution`. The M130 quarterly gasto
projection is intentionally separate in :mod:`~._renta_gasto_ledger`.

Related: :mod:`~.iva_ledger` and :mod:`~._renta_income_ledger` for sibling
ledger projections.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Final, overload

from pydantic import BaseModel, Field

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...core.casilla_id import CasillaId
from ...core.filing_year import FilingYear
from ...core.identity import TransactionId
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period, PeriodKind
from ...core.prorrata_register import regime_apportions_deduction
from ...core.prose_elision import IssueDetail
from ...core.resources.registry import resources
from ...domain.categories.profile import CategoryProfile
from ...domain.categories.spending_category import SpendingCategory
from ...domain.contribuyente.ccaa import CCAA
from ...domain.contribuyente.errors import ForalRegimeError, TaxResidenceProfileError
from ...domain.contribuyente.seguro_enfermedad_insured import (
    seguro_enfermedad_insured_counts_from_facts,
)
from ...domain.contribuyente.tax_residence import parse_tax_region
from ...domain.deadlines.models import IVARegime
from ...domain.invoices.models import InvoiceCatalogue
from ...domain.invoices.protocols import InvoiceCatalogueRepositoryProtocol
from ...domain.iva.classification import InvoiceKind
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.renta.ledger_expenses import (
    RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS,
    RentaDeductibilityContext,
    RentaDeductibilityStatus,
    RentaDeductibleExpenseFact,
    RentaDeductibleExpenseObservation,
    RentaExpenseDirection,
    build_renta_deductible_expense_observation,
    evaluate_renta_deductibility,
    normalize_spending_category,
    resolve_region_category_profiles,
    select_deductibility_profile,
)
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ...domain.user_profile.errors import ProfileNotFoundError
from ...domain.user_profile.loader import load_user_profile_schema
from ...domain.user_profile.values import UserProfileRecord
from ..user_profile.profile_record_repository import ProfileRecordRepository
from ..user_profile.projections import fact_value, profile_fact_index
from . import _shared_issue_reasons
from ._currency_predicates import (
    effective_eur_amount,
    effective_eur_iva_amount,
    effective_eur_taxable_base,
    is_non_eur_without_conversion,
)
from ._models import CasillaAggregation, CasillaProvenance, LedgerAggregationResultBase
from ._renta_business_eligibility import (
    relies_on_activity_marker,
    renta_expense_business_proportion,
)
from .errors import AggregationPeriodError, AggregationValidationError, t

_LEDGER_CATALOGUE_ID = "ledger"


def _first_slice_supported_mappings() -> str:
    grouped: dict[CasillaId, list[str]] = {}
    for category, casilla_id in sorted(
        RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS.items(),
        key=lambda item: (str(item[1]), item[0].value),
    ):
        grouped.setdefault(casilla_id, []).append(category.value)
    return "; ".join(f"{casilla_id}={', '.join(categories)}" for casilla_id, categories in grouped.items())


class RentaLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce an observation.

    The five upstream filter rejections (``UNSUPPORTED_DIRECTION``,
    ``UNSUPPORTED_CURRENCY``, ``UNCLASSIFIED_BUSINESS_STATE``,
    ``PERSONAL_TRANSACTION``, ``OUTSIDE_PERIOD``) are shared with
    :class:`~application.aggregation.iva_ledger.IvaLedgerAggregationIssueReason`
    through :mod:`._shared_issue_reasons`. ``UNSUPPORTED_PERIOD`` is a
    Renta-only refusal raised against quarter-level requests; the
    remaining values describe Renta-specific deductibility checks.
    """

    UNSUPPORTED_PERIOD = "unsupported_period"
    UNSUPPORTED_DIRECTION = _shared_issue_reasons.UNSUPPORTED_DIRECTION
    UNSUPPORTED_CURRENCY = _shared_issue_reasons.UNSUPPORTED_CURRENCY
    UNCLASSIFIED_BUSINESS_STATE = _shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE
    ACTIVITY_MARKED_PENDING_ANNUAL_REVIEW = "activity_marked_pending_annual_review"
    """An actividad-marked expense the quarterly M130 accepts but the annual declaration holds for review.

    Narrower than ``UNCLASSIFIED_BUSINESS_STATE``: the row carries an explicit
    ``actividad_economica`` IRPF category, so it is not unclassified -- it is
    awaiting the business-classification review the filing-grade annual
    projection requires. Naming it separately tells the operator that the same
    row already fed a pago fraccionado and what action clears it.
    """
    PERSONAL_TRANSACTION = _shared_issue_reasons.PERSONAL_TRANSACTION
    MISSING_CATEGORY = "missing_category"
    UNKNOWN_CATEGORY = "unknown_category"
    CATEGORY_OUTSIDE_FIRST_SLICE = "category_outside_first_slice"
    MISSING_CATEGORY_PROFILE = "missing_category_profile"
    OUTSIDE_PERIOD = _shared_issue_reasons.OUTSIDE_PERIOD
    MISSING_PURCHASE_INVOICE_EVIDENCE = "missing_purchase_invoice_evidence"
    UNSUPPORTED_PURCHASE_INVOICE_EVIDENCE_KIND = "unsupported_purchase_invoice_evidence_kind"
    PURCHASE_INVOICE_EVIDENCE_BUCKET_MISMATCH = "purchase_invoice_evidence_bucket_mismatch"
    PURCHASE_INVOICE_EVIDENCE_LINK_MISMATCH = "purchase_invoice_evidence_link_mismatch"
    PARTIAL_OR_MULTI_TRANSACTION_PURCHASE_INVOICE_EVIDENCE = "partial_or_multi_transaction_purchase_invoice_evidence"
    AMOUNT_MISMATCH = "amount_mismatch"
    INVALID_LEDGER_FACT = "invalid_ledger_fact"
    INELIGIBLE_DEDUCTIBILITY = "ineligible_deductibility"
    REGION_UNDECLARED_FOR_OVERRIDE = "region_undeclared_for_override"


#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.


class RentaLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while aggregating ledger rows."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    purchase_invoice_evidence_id: str | None = Field(default=None, min_length=1, max_length=128)
    category_id: str | None = Field(default=None, min_length=1, max_length=128)
    reason: RentaLedgerAggregationIssueReason
    detail: IssueDetail


class _PurchaseInvoiceEvidencePayload(BaseModel):
    """Typed enrichment fields copied from a reconciled linked invoice."""

    model_config = _STRICT_FROZEN

    invoice_issue_date: date | None = None
    taxable_base: Decimal | None = None
    iva_amount: Decimal | None = None


class RentaLedgerExpenseAggregation(
    LedgerAggregationResultBase[RentaDeductibleExpenseObservation, RentaLedgerAggregationIssue],
):
    """First-slice Renta observations plus binding-ready casilla totals.

    Carries no ``out_of_window_summary``: this annual first-slice aggregation
    has no repository-backed date partition, unlike the base's four other
    known subclasses -- deliberately not declared here (see
    :class:`~._models.LedgerAggregationResultBase`).
    """

    profile_year: FilingYear

    @property
    def casilla_values(self) -> Mapping[CasillaId, Decimal]:
        """Return the frozen mapping of binding-ready casilla totals."""
        return self.casilla_aggregation.casilla_values


#: The Art. 30.2.5.a cap variant ids the spending-category corpus declares. The
#: resolver keys its per-population counts by variant id, and a parity test asserts
#: the shipped rule still declares exactly these two, so a rename in the corpus reds
#: rather than silently zeroing a population.
_SEGURO_GENERAL_VARIANT: Final[str] = "general"
_SEGURO_DISCAPACIDAD_VARIANT: Final[str] = "discapacidad"


def _seguro_enfermedad_person_counts(
    *,
    bucket_id: str,
    profile_record: UserProfileRecord | None,
    filing_year: int,
) -> dict[str, int]:
    """Count the Art. 30.2.5.a insured persons for the statutory-cap resolver.

    Returns an EMPTY mapping when no profile is reachable, which the resolver reads
    as "nothing counted" and answers with the ordinary limb over the persons it does
    know about. A bucket without a profile therefore stays exactly where it was
    before the higher limb existed rather than losing its cap altogether.

    The counting itself is domain work and lives there: both this package and
    application.modelo need it, and neither may import the other.
    """
    record = profile_record
    if record is None:
        try:
            record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
        except ProfileNotFoundError:
            return {}
    counts = seguro_enfermedad_insured_counts_from_facts(
        profile_fact_index(record, load_user_profile_schema()),
        filing_year=filing_year,
    )
    return {
        _SEGURO_GENERAL_VARIANT: counts.general,
        _SEGURO_DISCAPACIDAD_VARIANT: counts.discapacidad,
    }


def _resolve_residence_ccaa(
    *,
    bucket_id: str,
    profile_record: UserProfileRecord | None = None,
) -> CCAA | None:
    """Derive the ordinary-residence comunidad autonoma from the bucket's profile.

    Reads the ``tax_residence.ccaa`` fact from the bucket's user profile and
    parses it to the closed :class:`CCAA` enum. Returns ``None`` -- the D4
    fail-closed outcome that falls the aggregation through to the state year
    profile -- when no profile is selected, the fact is absent, or the recorded
    region is a foral regime or otherwise unparseable. The value is inert while
    :func:`resolve_region_category_profiles` returns an empty mapping (general
    expense deductibility is state base-imponible law, invariant across
    comunidades); it is derived here so a future territorial-regime override
    selects by residence with no further caller wiring.

    Args:
        bucket_id: Stable bucket identifier used to load the user profile.
        profile_record: Optional :class:`UserProfileRecord` override for testing;
            when ``None`` the record is loaded from the bucket.
    """
    record = profile_record
    if record is None:
        try:
            record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
        except ProfileNotFoundError:
            return None

    raw = fact_value(record, "tax_residence.ccaa")
    if raw is None:
        return None
    try:
        return parse_tax_region(raw)
    except (ForalRegimeError, TaxResidenceProfileError):
        return None


def resolve_iva_deduction_ratio(
    *,
    bucket_id: str,
    ejercicio: int,
    profile_record: UserProfileRecord | None = None,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
) -> Decimal | None:
    """Resolve the activity's IVA-deduction fraction for :attr:`RentaDeductibilityContext.iva_deduction_ratio`.

    Two independent taxpayer facts feed this axis, checked in order:

    1. A wholly ``EXENTO`` :attr:`~domain.deadlines.TaxpayerProfile.iva_regime`
       (LIVA art. 20, no right to deduct under art. 94.Uno a contrario) resolves
       to ``0`` outright. This is deliberately NOT a prorrata-register state: a
       taxpayer performing ONLY sin-derecho operations never triggers LIVA
       art. 102.Uno prorrata (which requires con-derecho and sin-derecho
       operations "conjuntamente"), so the register legitimately carries no
       entry for them.
    2. Otherwise, the bucket's :class:`~domain.prorrata_register.ProrrataRegister`
       whole-entity (``sector_id=None``) entry for ``ejercicio``: a ``GENERAL``
       or ``ESPECIAL`` regime entry contributes its in-force provisional
       percentage (LIVA art. 104.Uno + 105.Uno) as a ``0``-``1`` ratio, mirroring
       the resolution :func:`~application.aggregation.iva_ledger._active_prorrata_apportionment`
       already applies on the M303 side -- the SAME percentage that governed
       what this ejercicio's ledger rows actually recovered through IVA, so the
       two filings stay consistent for the same ejercicio. A ``NINGUNA`` regime,
       an interrupted or absent entry, or an unresolved provisional percentage
       all fall through to ``None``.

    Returns ``None`` -- the historic base-only fallback -- when neither fact
    resolves a ratio (no profile, an unparseable regime, no register entry, or
    an unresolved percentage). Never fabricates a percentage.

    Args:
        bucket_id: Stable bucket identifier used to load the profile and register.
        ejercicio: Filing year to resolve the register entry for.
        profile_record: Optional :class:`UserProfileRecord` override for testing;
            when ``None`` the record is loaded from the bucket.
        prorrata_register_repository: Canonical repository for the bucket's
            prorrata register. The caller owns its store selection so a
            non-active bucket cannot be shadowed by a process-global default.
    """
    record = profile_record
    if record is None:
        try:
            record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
        except ProfileNotFoundError:
            record = None
    if record is not None:
        raw_regime = fact_value(record, "iva.regime")
        if raw_regime is not None:
            try:
                regime = IVARegime(str(raw_regime).strip().upper())
            except ValueError:
                regime = None
            if regime is IVARegime.EXENTO:
                return Decimal("0")

    register = prorrata_register_repository.load()
    entry = register.entry_for(ejercicio, sector_id=None)
    if entry is None or not regime_apportions_deduction(entry.regime):
        return None
    resolution = register.resolve_provisional(ejercicio, sector_id=None)
    if resolution.percentage is None:
        return None
    return resolution.percentage / Decimal("100")


def aggregate_renta_ledger_expenses_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    invoice_repository: InvoiceCatalogueRepositoryProtocol | None = None,
    profile_year: int | None = None,
    usage_ratios: Mapping[SpendingCategory, Decimal] | None = None,
    activity_key: str = "default",
    modelo: str = Modelo.M100.value,
    profile_record: UserProfileRecord | None = None,
    region_category_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]] | None = None,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
) -> RentaLedgerExpenseAggregation:
    """Load persisted catalogues and aggregate first-slice Renta expenses.

    Derives the ordinary-residence comunidad autonoma from the bucket's active
    profile (``tax_residence.ccaa``) and threads it into the aggregation so a
    territorial-regime deductibility override selects by residence; the axis is
    fail-closed (an undeclared or unparseable region resolves to the state year
    profile) and byte-identical while the override layer is empty. Pass
    ``profile_record`` to supply the :class:`UserProfileRecord` directly (the
    residence is otherwise loaded from the bucket), and ``region_category_overrides``
    to supply the per-:class:`CCAA` override layer forwarded to
    :func:`aggregate_renta_ledger_expenses` (defaulting to the empty
    registry-provisioned layer, :func:`resolve_region_category_profiles`).

    Also derives the activity's IVA-deduction ratio (:func:`resolve_iva_deduction_ratio`)
    from the bucket's ``iva.regime`` profile fact and its
    :class:`~domain.prorrata_register.ProrrataRegister`, so the non-recoverable
    share of input IVA joins the IRPF-deductible cost basis (PGC NRV 12.ª) for
    an exempt or prorrata-rationed activity. ``prorrata_register_repository``
    supplies the canonical register store explicitly.

    Returns a :class:`RentaLedgerExpenseAggregation`.
    """
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    # NOT pre-filtered by date range: a transaction's OWN
    # date can fall outside the requested annual window while its LINKED
    # INVOICE's issue date (the actual ``fact.filing_date`` the classifier
    # below tests) falls inside it, and the reverse — a transaction inside the
    # window whose linked invoice puts it outside. Pre-filtering by the
    # transaction's own date with ``load_for_date_range`` silently drops both
    # shapes before ``_classify_renta_transaction`` ever runs, so the
    # ``OUTSIDE_PERIOD`` diagnostic the operator needs to see never fires for a
    # multi-year catalogue. Mirrors the same revert already applied to
    # ``_iva_ledger`` / ``_renta_income_ledger`` / ``_renta_gasto_ledger`` /
    # ``_impatriado_income_ledger`` for the identical reason.
    transactions = repository.load()
    invoices_repository = invoice_repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    if invoices_repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.invoice_bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": invoices_repository.bucket_id},
        )
    invoices = invoices_repository.load()
    residence_ccaa = _resolve_residence_ccaa(bucket_id=bucket_id, profile_record=profile_record)
    resolved_ejercicio = profile_year if profile_year is not None else period.filing_year
    iva_deduction_ratio = resolve_iva_deduction_ratio(
        bucket_id=bucket_id,
        ejercicio=resolved_ejercicio,
        profile_record=profile_record,
        prorrata_register_repository=prorrata_register_repository,
    )
    return aggregate_renta_ledger_expenses(
        transactions,
        invoices,
        bucket_id=bucket_id,
        period=period,
        profile_year=profile_year,
        usage_ratios=usage_ratios,
        activity_key=activity_key,
        modelo=modelo,
        residence_ccaa=residence_ccaa,
        region_category_overrides=region_category_overrides,
        iva_deduction_ratio=iva_deduction_ratio,
        profile_record=profile_record,
    )


def aggregate_renta_ledger_expenses(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    bucket_id: str,
    period: Period,
    profile_year: int | None = None,
    usage_ratios: Mapping[SpendingCategory, Decimal] | None = None,
    activity_key: str = "default",
    modelo: str = Modelo.M100.value,
    residence_ccaa: CCAA | None = None,
    region_category_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]] | None = None,
    iva_deduction_ratio: Decimal | None = None,
    profile_record: UserProfileRecord | None = None,
) -> RentaLedgerExpenseAggregation:
    """Aggregate classified ledger transactions into Renta expense observations.

    Args:
        transactions: The :class:`TransactionCatalogue` supplying active ledger entries.
        invoices: The :class:`InvoiceCatalogue` used for invoice-linked deductibility checks.
        bucket_id: Activity bucket identifier for scoping the aggregation.
        period: Filing period as a typed :class:`Period` instance.
        profile_year: Optional category-profile year override; defaults to the
            ``period.filing_year`` when ``None``.
        usage_ratios: Optional per-:class:`SpendingCategory` business-use ratio
            overrides applied before deductibility calculation.
        activity_key: Activity identifier carried through to the produced
            observations' provenance; defaults to ``"default"``.
        modelo: Modelo identifier (``"100"`` IRPF or ``"130"`` pagos
            fraccionados) selecting the per-modelo deductibility rules.
        residence_ccaa: Optional ordinary residence comunidad autonoma, used only
            to select a territorial-regime deductibility override; inert while the
            override layer is empty and general expense deductibility is state law.
        region_category_overrides: Optional per-:class:`CCAA` category-profile
            override layer; defaults to :func:`resolve_region_category_profiles`
            (empty) so every fact falls through to the state year profile.
        iva_deduction_ratio: Optional activity-wide IVA-deduction fraction
            (LIVA arts. 94/104), threaded onto :class:`RentaDeductibilityContext`
            so the non-recoverable share of a fact's input IVA joins its
            IRPF-deductible cost basis. ``None`` (the default) preserves the
            historic base-only behaviour.
        profile_record: Optional :class:`UserProfileRecord` override; when ``None``
            the record is loaded from the bucket. Supplies the LIRPF art. 30.2.5.a
            insured-person counts that split the seguro de enfermedad cap across
            its 500 and 1.500 euro limbs.

    Returns a :class:`RentaLedgerExpenseAggregation` containing the accepted
    observations, exclusion issues, and binding-ready casilla totals.
    """
    resolved_period = _resolve_annual_period(period)
    resolved_profile_year = profile_year if profile_year is not None else resolved_period.filing_year
    profiles = resources().category_profiles.get(resolved_profile_year)
    region_overrides = (
        region_category_overrides
        if region_category_overrides is not None
        else resolve_region_category_profiles(resolved_profile_year)
    )
    context = RentaDeductibilityContext(
        profile_year=resolved_profile_year,
        usage_ratios=dict(usage_ratios or {}),
        residence_ccaa=residence_ccaa,
        iva_deduction_ratio=iva_deduction_ratio,
        statutory_cap_variant_person_counts=_seguro_enfermedad_person_counts(
            bucket_id=bucket_id,
            profile_record=profile_record,
            filing_year=resolved_profile_year,
        ),
    )
    observations: list[RentaDeductibleExpenseObservation] = []
    issues: list[RentaLedgerAggregationIssue] = []
    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
            # Operator reviewed and deliberately excluded this row from filing
            # (a final disposition): omit it silently, no observation and no
            # advisory-bearing issue.
            continue
        outcome = _classify_renta_transaction(
            transaction,
            invoices=invoices,
            bucket_id=bucket_id,
            resolved_period=resolved_period,
            resolved_profile_year=resolved_profile_year,
            profiles=profiles,
            region_overrides=region_overrides,
            context=context,
            activity_key=activity_key,
        )
        if isinstance(outcome, RentaLedgerAggregationIssue):
            issues.append(outcome)
        else:
            observations.append(outcome)

    casilla_aggregation = _casilla_aggregation(resolved_period, observations, modelo=modelo)
    return RentaLedgerExpenseAggregation(
        modelo=modelo,
        period=resolved_period,
        profile_year=resolved_profile_year,
        observations=tuple(observations),
        issues=tuple(issues),
        casilla_aggregation=casilla_aggregation,
    )


def _classify_renta_transaction(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    resolved_period: Period,
    resolved_profile_year: int,
    profiles: Mapping[SpendingCategory, CategoryProfile],
    region_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]],
    context: RentaDeductibilityContext,
    activity_key: str,
) -> RentaDeductibleExpenseObservation | RentaLedgerAggregationIssue:
    """Filter + classify one ledger transaction against the Renta-expense pipeline.

    Returns either a typed :class:`RentaDeductibleExpenseObservation`
    (the transaction survives every gate and is eligible) or a typed
    :class:`RentaLedgerAggregationIssue` (any gate rejects it). The
    twelve original early-return branches each project to a typed
    issue with their dedicated reason code; the eligible path returns
    the constructed observation.
    """
    direction = _renta_direction_for(transaction.direction, transaction.purchase_invoice_evidence_id)
    if direction is None:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION,
            f"transaction direction {transaction.direction.value!r} is not a Renta expense flow",
        )
    if is_non_eur_without_conversion(transaction):
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
            f"transaction currency {transaction.raw.currency!r} is not supported for Renta expenses",
        )
    # Use the EUR projection after rejecting unconverted non-EUR rows, so converted
    # rows contribute their EUR equivalent while EUR rows retain their raw amount.
    eur_amount = effective_eur_amount(transaction)
    proportion = _renta_business_proportion_or_issue(transaction)
    if isinstance(proportion, RentaLedgerAggregationIssue):
        return proportion
    category_profile = _renta_category_profile_or_issue(
        transaction,
        profiles=profiles,
        region_overrides=region_overrides,
        context=context,
        profile_year=resolved_profile_year,
    )
    if isinstance(category_profile, RentaLedgerAggregationIssue):
        return category_profile
    category, profile = category_profile
    fact = _renta_expense_fact_or_issue(
        transaction,
        invoices=invoices,
        bucket_id=bucket_id,
        direction=direction,
        category=category,
        activity_key=activity_key,
        eur_amount=eur_amount,
        proportion=proportion,
    )
    if isinstance(fact, RentaLedgerAggregationIssue):
        return fact
    return _renta_observation_or_issue(
        transaction,
        fact=fact,
        profile=profile,
        context=context,
        period=resolved_period,
    )


def _renta_business_proportion_or_issue(
    transaction: Transaction,
) -> Decimal | RentaLedgerAggregationIssue:
    """Return the annual filing business proportion or its precise refusal."""
    # Annual filing deliberately refuses the actividad marker that quarterly M130
    # accepts, through the shared predicate rather than a second policy copy.
    proportion = renta_expense_business_proportion(transaction, accept_activity_marker=False)
    if proportion is not None:
        return proportion
    if relies_on_activity_marker(transaction):
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.ACTIVITY_MARKED_PENDING_ANNUAL_REVIEW,
            "actividad-marked expense needs business-classification review before the annual declaration",
        )
    reason = (
        RentaLedgerAggregationIssueReason.PERSONAL_TRANSACTION
        if transaction.business_classification is BusinessClassification.PERSONAL
        else RentaLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE
    )
    return _renta_transaction_issue(
        transaction,
        reason,
        f"business classification {transaction.business_classification.value!r} cannot feed Renta expenses",
    )


def _renta_category_profile_or_issue(
    transaction: Transaction,
    *,
    profiles: Mapping[SpendingCategory, CategoryProfile],
    region_overrides: Mapping[CCAA, Mapping[SpendingCategory, CategoryProfile]],
    context: RentaDeductibilityContext,
    profile_year: int,
) -> tuple[SpendingCategory, CategoryProfile] | RentaLedgerAggregationIssue:
    """Resolve the first-slice category and the profile selected for residence."""
    category_id = transaction.category_id
    if category_id is None:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.MISSING_CATEGORY,
            "classified expense transaction has no ledger category",
        )
    try:
        category = normalize_spending_category(category_id)
    except ValueError:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.UNKNOWN_CATEGORY,
            f"ledger category {category_id!r} is not in the spending taxonomy",
        )
    if category not in RENTA_100_FIRST_SLICE_EXPENSE_CASILLAS:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.CATEGORY_OUTSIDE_FIRST_SLICE,
            (
                f"category {category.value!r} has no first-slice Modelo 100 casilla mapping; "
                f"current supported mappings: {_first_slice_supported_mappings()}"
            ),
        )
    profile = profiles.get(category)
    if profile is None:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.MISSING_CATEGORY_PROFILE,
            f"category {category.value!r} has no profile for {profile_year}",
        )
    category_region_overrides = {
        ccaa: overrides[category] for ccaa, overrides in region_overrides.items() if category in overrides
    }
    selected_profile = select_deductibility_profile(
        state_profile=profile,
        region_override_profiles=category_region_overrides,
        context=context,
    )
    if selected_profile is None:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.REGION_UNDECLARED_FOR_OVERRIDE,
            (
                f"category {category.value!r} carries a territorial-regime deductibility override for "
                f"{profile_year} but the residence comunidad autonoma is undeclared"
            ),
        )
    return category, selected_profile


def _renta_expense_fact_or_issue(
    transaction: Transaction,
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    direction: RentaExpenseDirection,
    category: SpendingCategory,
    activity_key: str,
    eur_amount: Decimal,
    proportion: Decimal,
) -> RentaDeductibleExpenseFact | RentaLedgerAggregationIssue:
    """Enrich a transaction with invoice evidence and construct its expense fact."""
    evidence_payload = _purchase_invoice_evidence_payload(
        invoices=invoices,
        bucket_id=bucket_id,
        transaction_id=transaction.transaction_id,
        purchase_invoice_evidence_id=transaction.purchase_invoice_evidence_id,
        category_id=transaction.category_id,
        transaction_amount=eur_amount,
    )
    if isinstance(evidence_payload, RentaLedgerAggregationIssue):
        return evidence_payload
    try:
        return RentaDeductibleExpenseFact(
            transaction_id=transaction.transaction_id,
            invoice_id=transaction.purchase_invoice_evidence_id,
            catalogue_id=_LEDGER_CATALOGUE_ID,
            operation_date=transaction.raw.value_date or transaction.raw.booked_date,
            invoice_issue_date=evidence_payload.invoice_issue_date,
            posting_date=transaction.raw.booked_date,
            gross_amount=_business_fact_amount(eur_amount, proportion),
            taxable_base=_business_fact_amount(_taxable_base_for(transaction, evidence_payload), proportion),
            iva_amount=_business_fact_amount(_iva_amount_for(transaction, evidence_payload), proportion),
            direction=direction,
            category=category,
            activity_key=activity_key,
        )
    except ValueError as exc:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
            str(exc),
        )


def _renta_observation_or_issue(
    transaction: Transaction,
    *,
    fact: RentaDeductibleExpenseFact,
    profile: CategoryProfile,
    context: RentaDeductibilityContext,
    period: Period,
) -> RentaDeductibleExpenseObservation | RentaLedgerAggregationIssue:
    """Apply filing-period and deductibility gates to one validated fact."""
    if not period.contains(fact.filing_date):
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            f"filing date {fact.filing_date.isoformat()} is outside {period}",
        )
    result = evaluate_renta_deductibility(fact, profile, context)
    if result.status is not RentaDeductibilityStatus.ELIGIBLE:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.INELIGIBLE_DEDUCTIBILITY,
            result.reason,
        )
    try:
        return build_renta_deductible_expense_observation(fact, result, tax_year=period.filing_year)
    except ValueError as exc:
        return _renta_transaction_issue(
            transaction,
            RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT,
            str(exc),
        )


def _renta_transaction_issue(
    transaction: Transaction,
    reason: RentaLedgerAggregationIssueReason,
    detail: str,
) -> RentaLedgerAggregationIssue:
    return RentaLedgerAggregationIssue(
        transaction_id=transaction.transaction_id,
        purchase_invoice_evidence_id=transaction.purchase_invoice_evidence_id,
        category_id=transaction.category_id,
        reason=reason,
        detail=detail,
    )


def _resolve_annual_period(period: Period) -> Period:
    resolved = period
    if resolved.kind is not PeriodKind.ANNUAL:
        raise AggregationPeriodError(
            t("aggregation.renta_ledger.errors.annual_period_required"),
            context={"period": str(resolved)},
        )
    return resolved


def _renta_direction_for(
    direction: TransactionDirection,
    purchase_invoice_evidence_id: str | None,
) -> RentaExpenseDirection | None:
    if direction is TransactionDirection.OUTGOING:
        return RentaExpenseDirection.OUTGOING_EXPENSE
    if direction is TransactionDirection.INCOMING and purchase_invoice_evidence_id is not None:
        return RentaExpenseDirection.REFUND
    return None


@overload
def _business_fact_amount(amount: None, proportion: Decimal) -> None: ...
@overload
def _business_fact_amount(amount: Decimal, proportion: Decimal) -> Decimal: ...
def _business_fact_amount(amount: Decimal | None, proportion: Decimal) -> Decimal | None:
    if amount is None:
        return None
    if amount < Decimal("0"):
        raise ValueError("ledger amount must be a non-negative magnitude")
    return amount * proportion


def _purchase_invoice_evidence_payload(
    *,
    invoices: InvoiceCatalogue,
    bucket_id: str,
    transaction_id: str,
    purchase_invoice_evidence_id: str | None,
    category_id: str | None,
    transaction_amount: Decimal,
) -> _PurchaseInvoiceEvidencePayload | RentaLedgerAggregationIssue:
    if purchase_invoice_evidence_id is None:
        return _PurchaseInvoiceEvidencePayload()
    invoice = invoices.get(purchase_invoice_evidence_id)
    if invoice is None:
        # The evidence reference addresses two id spaces and only the invoice
        # catalogue carries the fiscal totals this fold-in needs, so a miss here is
        # NOT proof the reference is broken: it is also what a legitimately
        # registered, not-yet-confirmed evidence record looks like from this side.
        # Naming both cases keeps the operator from hunting a phantom missing record.
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.MISSING_PURCHASE_INVOICE_EVIDENCE,
            detail=(
                "transaction references no confirmed invoice in the catalogue, so this expense carries no "
                "invoice totals to fold in; if the reference names a registered evidence record, confirming "
                "it into an invoice does NOT repoint this transaction, and no verb currently replaces an "
                "already-set purchase-invoice-evidence reference -- so record the expense against the "
                "confirmed invoice on a transaction that has no evidence reference yet"
            ),
        )
    if invoice.bucket_id != bucket_id:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.PURCHASE_INVOICE_EVIDENCE_BUCKET_MISMATCH,
            detail="transaction references purchase invoice evidence outside the active bucket",
        )
    if invoice.kind is not InvoiceKind.RECEIVED:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.UNSUPPORTED_PURCHASE_INVOICE_EVIDENCE_KIND,
            detail=f"purchase invoice evidence kind {invoice.kind.value!r} is not RECEIVED",
        )
    if transaction_id not in invoice.linked_transaction_ids:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.PURCHASE_INVOICE_EVIDENCE_LINK_MISMATCH,
            detail="transaction and purchase invoice evidence links are not reciprocal",
        )
    if len(invoice.linked_transaction_ids) != 1:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.PARTIAL_OR_MULTI_TRANSACTION_PURCHASE_INVOICE_EVIDENCE,
            detail="first-slice aggregation only accepts one transaction per purchase invoice evidence record",
        )
    # invoice.grand_total is denominated in invoice.currency (native), while
    # transaction_amount is the caller's already-EUR-converted eur_amount (see
    # effective_eur_amount). Comparing them directly mixes currencies: a
    # legitimate foreign-currency invoice would compare its native total
    # against a converted EUR figure and mismatch even when the two documents
    # agree, so this compares grand_total_eur instead. An invoice that cannot
    # itself resolve a EUR total (foreign currency, unconverted) has no EUR
    # figure to compare or fold in, so it is refused the same way rather than
    # silently treated as a domestic-currency match.
    invoice_grand_total_eur = invoice.grand_total_eur
    if invoice_grand_total_eur is None or transaction_amount != invoice_grand_total_eur:
        return RentaLedgerAggregationIssue(
            transaction_id=transaction_id,
            purchase_invoice_evidence_id=purchase_invoice_evidence_id,
            category_id=category_id,
            reason=RentaLedgerAggregationIssueReason.AMOUNT_MISMATCH,
            detail="linked transaction amount does not match invoice grand total",
        )
    # invoice.base_total / invoice.iva_total are native-currency (same
    # currency as invoice.currency); the EUR-safe *_eur properties are the
    # ones that already exist for exactly this purpose (used correctly in
    # _invoice_retencion.py). base_total_eur cannot be None here: the
    # grand_total_eur check above already proved the invoice resolves to EUR.
    base_total_eur = invoice.base_total_eur
    iva_total_eur = invoice.iva_total_eur
    if base_total_eur is None or iva_total_eur is None:
        msg = (
            f"purchase invoice {purchase_invoice_evidence_id} resolves a EUR grand total but no EUR "
            "base or cuota; its EUR-equivalent totals disagree with one another"
        )
        raise ValueError(msg)
    return _PurchaseInvoiceEvidencePayload(
        invoice_issue_date=invoice.issued_at,
        taxable_base=base_total_eur,
        iva_amount=iva_total_eur,
    )


def _taxable_base_for(transaction: Transaction, evidence_payload: _PurchaseInvoiceEvidencePayload) -> Decimal | None:
    """Return the EUR taxable_base: the linked invoice's (already EUR), else the transaction's own.

    ``transaction.taxable_base`` is native-currency (see
    ``domain.transactions.tests.test_gross_invariant``), so the fallback goes
    through the EUR-equivalent accessor rather than the raw field.
    """
    if evidence_payload.taxable_base is not None:
        return evidence_payload.taxable_base
    return effective_eur_taxable_base(transaction)


def _iva_amount_for(transaction: Transaction, evidence_payload: _PurchaseInvoiceEvidencePayload) -> Decimal | None:
    """Return the EUR iva_amount: the linked invoice's (already EUR), else the transaction's own.

    Via the EUR-equivalent accessor -- see :func:`_taxable_base_for`.
    """
    if evidence_payload.iva_amount is not None:
        return evidence_payload.iva_amount
    return effective_eur_iva_amount(transaction)


def _casilla_aggregation(
    period: Period,
    observations: Sequence[RentaDeductibleExpenseObservation],
    *,
    modelo: str,
) -> CasillaAggregation:
    totals: dict[CasillaId, Decimal] = {}
    provenance_rows: list[CasillaProvenance] = []
    grouped: dict[tuple[CasillaId, SpendingCategory], list[RentaDeductibleExpenseObservation]] = {}
    for observation in observations:
        totals[observation.target_casilla_id] = (
            totals.get(observation.target_casilla_id, Decimal("0")) + observation.deductible_amount
        )
        grouped.setdefault((observation.target_casilla_id, observation.category), []).append(observation)
    for (casilla, category), rows in sorted(grouped.items()):
        provenance_rows.append(
            CasillaProvenance(
                casilla_id=casilla,
                category_id=category,
                transaction_ids=tuple(sorted(row.transaction_id for row in rows)),
                subtotal=sum((row.deductible_amount for row in rows), start=Decimal("0")),
            ),
        )
    return CasillaAggregation(
        modelo=modelo,
        period=period,
        casilla_values=totals,
        provenance=tuple(provenance_rows),
    )


__all__ = [
    "RentaLedgerAggregationIssue",
    "RentaLedgerAggregationIssueReason",
    "RentaLedgerExpenseAggregation",
    "aggregate_renta_ledger_expenses",
    "aggregate_renta_ledger_expenses_from_repositories",
]
