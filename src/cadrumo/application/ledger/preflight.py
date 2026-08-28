"""Backend readiness preflight for bucket-scoped ledger transactions.

:func:`preflight_ledger_tax_readiness` loads a
:class:`~cadrumo.domain.transactions.TransactionCatalogue` via
:class:`~cadrumo.domain.transactions.TransactionCatalogueRepositoryProtocol` from the
active bucket and delegates to :func:`preflight_transaction_catalogue` for pure
in-memory analysis. The report is consumed by modelo readiness projection and
ledger read surfaces; it is not a calculation engine and never mutates the
catalogue it inspects.

See Also:
    :func:`~cadrumo.application.state_projection.build_operator_state_projection`
        Modelo readiness consumer that embeds blocking ledger issues in the
        operator state projection.
    :mod:`cadrumo.entrypoints.cli._ledger_read_cli`
        CLI read surface that reports these preflight issues without mutating
        ledger state.
    :mod:`cadrumo.application.aggregation`
        Calculation source mesh that consumes ledger facts only after this
        readiness layer has reported operator-facing gaps.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final, Literal

from pydantic import BaseModel, Field, computed_field, field_serializer, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import ElidedProse, OperatorActionAxis, Period
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.identity import BucketId, TransactionId
from ...domain.categories import (
    HOME_OFFICE_FAMILIES,
    SpendingCategory,
    family_for,
    home_office_categories,
)
from ...domain.iva import IvaCategory
from ...domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepositoryProtocol,
    TransactionDirection,
    TransactionLifecycleState,
    TransactionValidationError,
    has_employment_irpf_category,
)
from ...domain.usage_ratios import CensoRatioMismatchError
from ..aggregation import (
    IVA_LEDGER_COUNTERPARTY_GATE_REASONS,
    IVA_LEDGER_MISSING_FACT_REASONS,
    IvaLedgerAggregationIssueReason,
    iva_ledger_missing_fact_reasons,
    validate_iva_ledger_counterparty_category,
)
from ..user_profile.censo_sync import bound_raw_afectacion_ratio_for_bucket
from .transaction_repository import transaction_catalogue_repository
from .usage_ratio_repository import usage_ratio_profile_with_censo_guard

_CLASSIFIED_TAX_STATES = frozenset(
    {
        BusinessClassification.BUSINESS,
        BusinessClassification.MIXED,
        BusinessClassification.PERSONAL,
    },
)


class LedgerPreflightIssueReason(StrEnum):
    """Machine-readable ledger facts missing before modelo calculation."""

    MISSING_BUSINESS_CLASSIFICATION = "missing_business_classification"
    MISSING_CATEGORY = "missing_category"
    MISSING_TAXABLE_BASE = "missing_taxable_base"
    MISSING_IVA_AMOUNT = "missing_iva_amount"
    MISSING_IVA_RATE = "missing_iva_rate"
    MISSING_EUR_TAX_SUBSTRATE = "missing_eur_tax_substrate"
    # Ley 37/1992 art. 25 exempts an intra-community supply on the acquirer's IVA
    # IDENTIFICATION in another Member State, not on where it is established, so
    # these two name identification. An operator-facing reason has to name what
    # actually determines the outcome: keyed on establishment it sent the
    # operator to check the wrong field, and it moved money in BOTH directions --
    # a Spanish-established acquirer holding a German IVA number, and a
    # German-established acquirer purchasing under a Spanish NIF-IVA.
    MISSING_COUNTERPARTY_IDENTIFICATION_STATE = "missing_counterparty_identification_state"
    DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION = "domestic_identification_on_intra_community_transaction"
    # Establishment, deliberately, and NOT identification: an export leaves the
    # Union, so the question is where the counterparty IS, not who IVA-identifies
    # it. The narrowing above is one concept, not a global substitution.
    EU_MEMBER_STATE_ON_EXPORT_TRANSACTION = "eu_member_state_on_export_transaction"
    # The other half of the same establishment question, and the direction that
    # cost money: an EU member state on an export is a wrong place, while NO
    # place at all was silently accepted as a third country. The operator is
    # sent to the same field either way, which is why both name establishment.
    MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT = "missing_counterparty_establishment_on_export"
    MISSING_PROPORTIONALITY_REFERENCE = "missing_proportionality_reference"
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    UNSUPPORTED_PERIOD = "unsupported_period"
    CENSO_RATIO_MISMATCH = "censo_ratio_mismatch"
    # The absence that used to pass silently. A home-office row deducts a
    # PROPORTION, and art. 30.2.5.b takes that proportion from the taxpayer's own
    # declared m2. With neither a stored ratio nor censo m2 the row is ineligible
    # and contributes nothing, which looks identical to having no such expense.
    # Unlike the mismatch above, nothing here disagrees -- the datum is simply
    # absent, and the operator is the only one who can supply it.
    MISSING_HOME_OFFICE_AFECTACION = "missing_home_office_afectacion"
    # Anomaly channel: present-but-suspicious rows (distinct from missing-fact),
    # so an asesor sees real anomalies without first classifying every row.
    ANOMALY_NON_DECLARABLE_IVA_CATEGORY = "anomaly_non_declarable_iva_category"
    ANOMALY_NON_DECLARABLE_RECARGO_EQUIVALENCIA = "anomaly_non_declarable_recargo_equivalencia"


#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.
_IssueDetail = Annotated[str, ElidedProse(512)]


class LedgerPreflightIssue(BaseModel):
    """One model-readiness issue attached to a bucket-local transaction."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId | Literal["__period__"]
    reason: LedgerPreflightIssueReason
    detail: _IssueDetail


class LedgerPreflightReport(BaseModel):
    """Readiness report for ledger facts consumed by modelo calculation."""

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    period: Period
    checked_transaction_count: int = Field(ge=0)
    issues: Sequence[LedgerPreflightIssue] = Field(default_factory=tuple)

    @field_validator("issues")
    @classmethod
    def _freeze_issues(cls, value: Sequence[LedgerPreflightIssue]) -> tuple[LedgerPreflightIssue, ...]:
        return tuple(value)

    @field_serializer("issues")
    def _serialize_issues(self, value: Sequence[LedgerPreflightIssue]) -> tuple[LedgerPreflightIssue, ...]:
        return tuple(value)

    @computed_field
    @property
    def ready(self) -> bool:
        """Whether the report contains no modelo-readiness issues."""
        return not self.issues


def preflight_ledger_tax_readiness(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
    raw_afectacion_ratio: Decimal | None = None,
) -> LedgerPreflightReport:
    """Load a bucket-local catalogue and report modelo-readiness gaps.

    Args:
        bucket_id: Bucket whose ledger catalogue is being checked.
        period: Filing period used to decide whether each transaction belongs in
            the readiness window.
        transaction_repository: Optional transaction-catalogue port used to
            load the bucket-local catalogue; the outward-composed repository
            is resolved when ``None``.
        raw_afectacion_ratio: Optional home-office usage ratio from censo data,
            used only to surface proportionality mismatches.

    Returns:
        A :class:`LedgerPreflightReport` describing blocking or advisory ledger
        facts for modelo-readiness projection.
    """
    repository = (
        transaction_repository
        if transaction_repository is not None
        else transaction_catalogue_repository(bucket_id=bucket_id)
    )
    if repository.bucket_id != bucket_id:
        raise TransactionValidationError(
            "transaction repository bucket_id does not match the ledger preflight bucket",
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    transactions = repository.load()
    censo_ratio_mismatch_detail = None
    missing_home_office_afectacion_detail = None
    if _catalogue_uses_home_office_usage_ratio(period=period, transactions=transactions):
        censo_ratio_mismatch_detail = _censo_ratio_mismatch_detail(
            bucket_id=bucket_id,
            raw_afectacion_ratio=raw_afectacion_ratio,
            year=period.filing_year,
        )
        missing_home_office_afectacion_detail = _missing_home_office_afectacion_detail(
            bucket_id=bucket_id,
            year=period.filing_year,
        )
    return preflight_transaction_catalogue(
        bucket_id=bucket_id,
        period=period,
        transactions=transactions,
        censo_ratio_mismatch_detail=censo_ratio_mismatch_detail,
        missing_home_office_afectacion_detail=missing_home_office_afectacion_detail,
    )


def preflight_transaction_catalogue(
    *,
    bucket_id: str,
    period: Period,
    transactions: TransactionCatalogue,
    censo_ratio_mismatch_detail: str | None = None,
    missing_home_office_afectacion_detail: str | None = None,
) -> LedgerPreflightReport:
    """Report missing ledger facts without mutating the transaction catalogue.

    Args:
        bucket_id: Stable bucket identifier for the ledger being checked.
        period: Filing period as a typed :class:`Period` instance.
        transactions: The :class:`TransactionCatalogue` to inspect for missing facts.
        censo_ratio_mismatch_detail: Optional censo mismatch detail previously
            resolved from the secure ratio profile. When supplied, active
            HOME_OFFICE ratio rows surface it as a preflight issue.
        missing_home_office_afectacion_detail: Optional detail reporting that no
            afectación proportion resolves at all. When supplied, active
            HOME_OFFICE ratio rows surface it, so a row that will deduct nothing
            says so instead of passing as though the expense were absent.

    Returns a :class:`LedgerPreflightReport`.
    """
    resolved_period = period
    if not resolved_period.has_date_span():
        return LedgerPreflightReport(
            bucket_id=bucket_id,
            period=resolved_period,
            checked_transaction_count=0,
            issues=(_unsupported_period_issue(resolved_period),),
        )
    issues: list[LedgerPreflightIssue] = []
    checked = 0
    for transaction in _sorted_transactions(transactions):
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        operation_date = transaction.raw.value_date or transaction.raw.booked_date
        if not resolved_period.contains(operation_date):
            continue
        checked += 1
        issues.extend(
            _issues_for_transaction(
                transaction,
                censo_ratio_mismatch_detail=censo_ratio_mismatch_detail,
                missing_home_office_afectacion_detail=missing_home_office_afectacion_detail,
            ),
        )
    return LedgerPreflightReport(
        bucket_id=bucket_id,
        period=resolved_period,
        checked_transaction_count=checked,
        issues=tuple(issues),
    )


def _unsupported_period_issue(period: Period) -> LedgerPreflightIssue:
    return LedgerPreflightIssue(
        transaction_id="__period__",
        reason=LedgerPreflightIssueReason.UNSUPPORTED_PERIOD,
        detail=(
            f"ledger preflight requires a calendar date-span period; {period.registry_token!r} has no date span "
            "and cannot be checked through ledger aggregation"
        ),
    )


def _sorted_transactions(transactions: TransactionCatalogue) -> tuple[Transaction, ...]:
    return tuple(
        sorted(
            transactions.values(),
            key=lambda transaction: (
                transaction.raw.value_date or transaction.raw.booked_date,
                transaction.transaction_id,
            ),
        ),
    )


def _period_transactions(*, period: Period, transactions: TransactionCatalogue) -> tuple[Transaction, ...]:
    if not period.has_date_span():
        return ()
    return tuple(
        transaction
        for transaction in _sorted_transactions(transactions)
        if transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
        and period.contains(transaction.raw.value_date or transaction.raw.booked_date)
    )


def _missing_home_office_afectacion_detail(*, bucket_id: str, year: int) -> str | None:
    """Report the absence of any proportion a home-office row could deduct on.

    Asked through the same resolver the calculation uses, so the question is
    exactly "will this row deduct anything" rather than a second opinion about
    the profile. Returns ``None`` when a ratio resolves from either source --
    a stored override, or the censo m2 the resolver derives from.

    The absence used to be silent. A home-office row with no proportion is
    ineligible and contributes nothing, which on a return looks identical to
    having had no such expense at all, so the filer under-deducts with no signal.
    """
    from ..user_profile.usage_ratio_resolution import resolve_effective_usage_ratios

    ratios = resolve_effective_usage_ratios(bucket_id=bucket_id, year=year)
    if any(category in ratios for category in home_office_categories()):
        return None
    return (
        "this period has home-office rows but no afectacion proportion to deduct them on: "
        "declare the dwelling m2 with 'aeat config profile edit' (vivienda_office.office_m2 "
        "and vivienda_office.total_m2), or set a ratio with 'aeat app ledger ratios set "
        "<category-id> <ratio>'. Until then these rows deduct nothing, which LIRPF "
        "art. 30.2.5.b does not require: the deductible share is 30 per cent of your "
        "declared proportion"
    )


def _censo_ratio_mismatch_detail(*, bucket_id: str, raw_afectacion_ratio: Decimal | None, year: int) -> str | None:
    resolved_raw = raw_afectacion_ratio
    if resolved_raw is None:
        resolved_raw = bound_raw_afectacion_ratio_for_bucket(bucket_id)
    try:
        usage_ratio_profile_with_censo_guard(
            bucket_id=bucket_id,
            raw_afectacion_ratio=resolved_raw,
            year=year,
        )
    except CensoRatioMismatchError as exc:
        return str(exc)
    return None


def _is_home_office_usage_ratio_id(value: str | None) -> bool:
    if value is None:
        return False
    try:
        category = SpendingCategory(value.strip())
    except ValueError:
        return False
    return family_for(category) in HOME_OFFICE_FAMILIES


def _transaction_takes_home_office_ratio(transaction: Transaction) -> bool:
    """Return whether a home-office usage ratio would actually apply to this row.

    Screens the row's CATEGORY, because that is the field the expense
    aggregation keys the override on -- ``usage_ratios.get(fact.category, ...)``
    in the Renta first-slice resolver. ``usage_ratio_id`` does not select the
    ratio at all.

    Screening the id alone let a real over-claim through. The operator may
    persist a censo-divergent ratio deliberately (the write is advisory by
    design, to model a planned change of afectación), and the refusal that is
    meant to catch it at filing time sat on the wrong field: classify utility
    bills into a home-office category, leave ``--usage-ratio-id`` unset -- the
    CLI default -- and the aggregation still applies the override while this
    screen sees nothing. LIRPF art. 30.2.5.b caps the suministros deduction at
    30% of the afectación proportion; the divergent override deducted the full
    amount, unrefused at every step.

    The id remains part of the test rather than being replaced by it. A row
    naming a home-office ratio is an operator declaration of intent, and the
    screen gates only a non-blocking advisory, so a superset that occasionally
    speaks up where nothing applies is the safe direction to be wrong in.
    """
    if _is_home_office_usage_ratio_id(transaction.usage_ratio_id):
        return True
    return _is_home_office_usage_ratio_id(transaction.category_id)


def _catalogue_uses_home_office_usage_ratio(*, period: Period, transactions: TransactionCatalogue) -> bool:
    return any(
        _transaction_takes_home_office_ratio(transaction)
        for transaction in _period_transactions(period=period, transactions=transactions)
    )


def _transaction_needs_expense_category(transaction: Transaction) -> bool:
    """Return whether the transaction feeds the deductible-expense pipeline.

    ``category_id`` is a :class:`SpendingCategory` foreign key — a
    deductible-expense taxonomy. The only modelo binding that consumes
    it is the Renta first-slice expense aggregation, which only admits
    OUTGOING transactions (expenses) and INCOMING transactions that
    carry a purchase-invoice evidence id (expense refunds). Pure income
    (INCOMING with no purchase-invoice evidence) is classified solely
    by direction and never reads a spending category, so it must not
    be flagged as ``missing_category``.
    """
    if transaction.direction is TransactionDirection.OUTGOING:
        return True
    return (
        transaction.direction is TransactionDirection.INCOMING and transaction.purchase_invoice_evidence_id is not None
    )


_ANOMALY_IVA_REASONS: dict[IvaCategory, tuple[LedgerPreflightIssueReason, str]] = {
    IvaCategory.UNKNOWN: (
        LedgerPreflightIssueReason.ANOMALY_NON_DECLARABLE_IVA_CATEGORY,
        "iva_category 'unknown' is not declarable; classify the row or query the source",
    ),
    IvaCategory.ERRONEOUS_INVOICE: (
        LedgerPreflightIssueReason.ANOMALY_NON_DECLARABLE_IVA_CATEGORY,
        "iva_category 'erroneous_invoice' marks a rectified/void row; not declarable",
    ),
}


def _issues_for_transaction(
    transaction: Transaction,
    *,
    censo_ratio_mismatch_detail: str | None = None,
    missing_home_office_afectacion_detail: str | None = None,
) -> tuple[LedgerPreflightIssue, ...]:
    issues: list[LedgerPreflightIssue] = []
    common = {"transaction_id": transaction.transaction_id}
    if transaction.direction not in {
        TransactionDirection.INCOMING,
        TransactionDirection.OUTGOING,
    }:
        return ()
    if transaction.business_classification not in _CLASSIFIED_TAX_STATES:
        return (
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.MISSING_BUSINESS_CLASSIFICATION,
                detail=(
                    f"business classification {transaction.business_classification.value!r} "
                    "is not ready for modelo calculation"
                ),
            ),
        )
    if transaction.business_classification is BusinessClassification.PERSONAL:
        return ()
    iva_cat = transaction.iva_category
    anomaly = _ANOMALY_IVA_REASONS.get(iva_cat) if iva_cat is not None else None
    if anomaly is not None:
        reason, detail = anomaly
        return (LedgerPreflightIssue(**common, reason=reason, detail=detail),)
    if iva_cat is IvaCategory.RECARGO_EQUIVALENCIA:
        return (
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.ANOMALY_NON_DECLARABLE_RECARGO_EQUIVALENCIA,
                detail=_recargo_equivalencia_preflight_detail(transaction),
            ),
        )
    # A foreign row is only unsupported when no EUR conversion was applied at
    # import; converted rows still need explicit EUR-denominated tax substrate.
    if transaction.raw.currency != DEFAULT_CURRENCY and transaction.value_in_eur is None:
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.UNSUPPORTED_CURRENCY,
                detail=f"transaction currency {transaction.raw.currency!r} is not supported for modelo aggregation",
            ),
        )
        return tuple(issues)
    if transaction.raw.currency != DEFAULT_CURRENCY and transaction.value_in_eur is not None:
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.MISSING_EUR_TAX_SUBSTRATE,
                detail=(
                    f"transaction currency {transaction.raw.currency!r} has value_in_eur but taxable_base and "
                    "iva_amount remain native-currency facts; supply explicit EUR tax substrate or exclude the "
                    "row before modelo calculation"
                ),
            ),
        )
        return tuple(issues)
    if _transaction_needs_expense_category(transaction) and transaction.category_id is None:
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.MISSING_CATEGORY,
                detail="deductible-expense ledger transaction has no category_id",
            ),
        )
    if transaction.business_classification is BusinessClassification.MIXED and transaction.usage_ratio_id is None:
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.MISSING_PROPORTIONALITY_REFERENCE,
                detail=(
                    "mixed ledger transaction has no usage_ratio_id; use an existing configured "
                    "eligible category id from 'aeat app ledger ratios list' or 'aeat app ledger "
                    "ratios eligible', create one with 'aeat app ledger ratios set <category-id> "
                    "<ratio>', then allocate with --usage-ratio-id <category-id>"
                ),
            ),
        )
    # Same screen as the catalogue-level gate above: the detail is computed
    # from the category the aggregation keys on, so it must attach on the same
    # test or it would be raised for the period and land on no row.
    if censo_ratio_mismatch_detail is not None and _transaction_takes_home_office_ratio(transaction):
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.CENSO_RATIO_MISMATCH,
                detail=(
                    f"{censo_ratio_mismatch_detail}; update your censo vivienda_office data with "
                    "'aeat config profile edit', or unset the HOME_OFFICE ratio before using it in modelo "
                    "calculations"
                ),
            ),
        )
    if missing_home_office_afectacion_detail is not None and _transaction_takes_home_office_ratio(transaction):
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=LedgerPreflightIssueReason.MISSING_HOME_OFFICE_AFECTACION,
                detail=missing_home_office_afectacion_detail,
            ),
        )
    # Trabajo (nómina) incoming rows are IVA-exempt by definition: an
    # employer-paid wage/salary carries no taxable_base / iva_rate /
    # iva_amount because the IRPF retenciones flow consumes the row,
    # not the IVA aggregation. Skip the IVA-fact preflight on these
    # rows so a payroll-receipt entry does not surface as three false-
    # positive missing_iva_* findings every period.
    if _transaction_is_trabajo_income(transaction):
        return tuple(issues)
    for reason in iva_ledger_missing_fact_reasons(transaction):
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=_preflight_reason_for_iva_issue(reason),
                detail=_preflight_detail_for_iva_issue(reason),
            ),
        )
    d5_issue = validate_iva_ledger_counterparty_category(transaction)
    if d5_issue is not None:
        issues.append(
            LedgerPreflightIssue(
                **common,
                reason=_preflight_reason_for_iva_issue(d5_issue.reason),
                detail=d5_issue.detail,
            ),
        )
    return tuple(issues)


def _recargo_equivalencia_preflight_detail(transaction: Transaction) -> str:
    if transaction.direction is TransactionDirection.OUTGOING:
        return (
            "iva_category 'recargo_equivalencia' is the retailer purchase-side surcharge; "
            "IVA+RE is non-deductible acquisition cost and is not declared as M303 input IVA"
        )
    if transaction.direction is TransactionDirection.INCOMING:
        return (
            "iva_category 'recargo_equivalencia' is not the supplier-side recargo sales channel; "
            "record supplier recargo on a taxable output sale through recargo_amount"
        )
    return "iva_category 'recargo_equivalencia' is not declarable through IVA ledger aggregation"


def _transaction_is_trabajo_income(transaction: Transaction) -> bool:
    """Return whether the transaction is a nómina (trabajo) income row.

    AEAT classifies an IRPF rendimiento del trabajo (wage/salary)
    received from an employer as an income flow that never carries an
    IVA component; the row's IRPF-side retenciones binding consumes
    the gross amount and the IVA aggregation never reads it. The
    preflight must therefore skip the IVA-fact checks on these rows.

    Resolved through the closed catalogue so this reader and the gross
    invariant agree on what a token names. Comparing the stripped, lowercased
    string to a local ``"trabajo"`` literal here meant ``TRABAJO`` classified
    as employment in the preflight while naming no descriptor at all in the
    gross invariant.
    """
    return has_employment_irpf_category(transaction.irpf_category, direction=transaction.direction)


#: The preflight counterpart of every aggregation reason that reaches preflight.
#:
#: Preflight consumes exactly two aggregation screens --
#: :func:`~cadrumo.application.aggregation.iva_ledger_missing_fact_reasons` and
#: :func:`~cadrumo.application.aggregation.validate_iva_ledger_counterparty_category`
#: -- so this mapping's domain is their union, not the whole enum. The lookup is
#: a bare subscript and therefore total by construction: an arriving reason that
#: is absent here raises rather than resolving to a wrong operator message.
#: What keeps that safe is the partition below, gated so a new enum member
#: cannot ship without being classified into one side or the other.
_PREFLIGHT_REASON_BY_IVA_ISSUE: Final[Mapping[IvaLedgerAggregationIssueReason, LedgerPreflightIssueReason]] = {
    IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE: LedgerPreflightIssueReason.MISSING_TAXABLE_BASE,
    IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT: LedgerPreflightIssueReason.MISSING_IVA_AMOUNT,
    IvaLedgerAggregationIssueReason.MISSING_IVA_RATE: LedgerPreflightIssueReason.MISSING_IVA_RATE,
    IvaLedgerAggregationIssueReason.MISSING_EUR_TAX_SUBSTRATE: (LedgerPreflightIssueReason.MISSING_EUR_TAX_SUBSTRATE),
    IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE: (
        LedgerPreflightIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE
    ),
    IvaLedgerAggregationIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION: (
        LedgerPreflightIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION
    ),
    IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION: (
        LedgerPreflightIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION
    ),
    IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT: (
        LedgerPreflightIssueReason.MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT
    ),
}

#: The detail sentence preflight writes for each missing-fact reason.
#:
#: A narrower domain than the mapping above, deliberately: the counterparty gate
#: already composes its own localised detail, which preflight carries through
#: verbatim rather than re-authoring. Only the missing-fact screen arrives here
#: with no sentence of its own.
_PREFLIGHT_DETAIL_BY_IVA_ISSUE: Final[Mapping[IvaLedgerAggregationIssueReason, str]] = {
    IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE: "transaction has no taxable_base fact",
    IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT: "transaction has no iva_amount fact",
    IvaLedgerAggregationIssueReason.MISSING_IVA_RATE: "transaction has no iva_rate fact",
    IvaLedgerAggregationIssueReason.MISSING_EUR_TAX_SUBSTRATE: (
        "converted non-EUR transaction requires explicit EUR tax substrate"
    ),
}

#: Aggregation reasons that cannot reach preflight, each with why it cannot.
#:
#: The counterpart half of the partition. Preflight runs the two screens named
#: above and nothing else; every other member of the enum is raised inside
#: ``_project_iva_transaction``, on the projection path preflight never enters.
#: Recording them by hand is the point -- a member added to the enum belongs on
#: exactly one side, and the gate refuses to let a new one ship on neither.
#:
#: Mapping one of these onto a preflight reason would be worse than leaving it
#: out: it would ship an operator-facing message for a condition the readiness
#: layer has no way to detect, and the nearest-looking counterpart is usually
#: the wrong sentence. ``UNSUPPORTED_IVA_RATE`` onto ``MISSING_IVA_RATE`` is the
#: worked example -- it would tell a filer their rate is absent when the rate is
#: present and it is the tier lookup that found no match.
_IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT: Final[Mapping[IvaLedgerAggregationIssueReason, str]] = {
    IvaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION: "upstream candidate filter, before any preflight screen",
    IvaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY: (
        "upstream candidate filter; preflight screens currency itself"
    ),
    IvaLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE: (
        "upstream candidate filter; preflight screens business classification itself"
    ),
    IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION: "upstream candidate filter, not a readiness gap",
    IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD: "upstream candidate filter; preflight is already period-scoped",
    IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE: (
        "projection-path rate-tier lookup; preflight does not classify rates against the tier table"
    ),
    IvaLedgerAggregationIssueReason.IVA_RATE_DATE_OUTSIDE_TABLE_COVERAGE: (
        "projection-path rate-tier lookup; preflight does not read the rate table's coverage window"
    ),
    IvaLedgerAggregationIssueReason.CUOTA_ON_ZERO_RATED_ROW: (
        "projection-path arithmetic contradiction screen between rate and cuota"
    ),
    IvaLedgerAggregationIssueReason.NON_ZERO_RATE_ON_ZERO_CUOTA_CATEGORY: (
        "projection-path screen reading the Axis-A component table for the declared category"
    ),
    IvaLedgerAggregationIssueReason.NON_ARISING_CATEGORY_FOR_INVOICE_SIDE: (
        "projection-path screen reading the Axis-A component table for the declared category"
    ),
    IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE: (
        "projection-path prorrata attachment; preflight screens the usage-ratio reference instead"
    ),
    IvaLedgerAggregationIssueReason.MISSING_DEDUCTION_CLASSIFICATION: (
        "projection-path deduction taxonomy gate; preflight does not resolve immutable deduction evidence"
    ),
    IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_CATEGORY: (
        "projection-path category resolution; preflight screens non-declarable categories itself"
    ),
    IvaLedgerAggregationIssueReason.CASH_ACCOUNTING_EXCLUDED_CATEGORY: (
        "projection-path regime screen requiring the bucket's cash-accounting treatment"
    ),
}


OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE: Mapping[
    IvaLedgerAggregationIssueReason,
    OperatorActionAxis,
] = MappingProxyType(
    {
        IvaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        IvaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY: OperatorActionAxis.IMPORT_LEDGER_DATA,
        IvaLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE: OperatorActionAxis.IMPORT_LEDGER_DATA,
        IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION: OperatorActionAxis.REVIEW_ADVISORY,
        IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD: OperatorActionAxis.REVIEW_ADVISORY,
        IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE: OperatorActionAxis.IMPORT_LEDGER_DATA,
        IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT: OperatorActionAxis.IMPORT_LEDGER_DATA,
        IvaLedgerAggregationIssueReason.MISSING_IVA_RATE: OperatorActionAxis.IMPORT_LEDGER_DATA,
        IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE: OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE,
        IvaLedgerAggregationIssueReason.IVA_RATE_DATE_OUTSIDE_TABLE_COVERAGE: (
            OperatorActionAxis.RESOLVE_REVISION_MISMATCH
        ),
        IvaLedgerAggregationIssueReason.CUOTA_ON_ZERO_RATED_ROW: OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE,
        IvaLedgerAggregationIssueReason.NON_ZERO_RATE_ON_ZERO_CUOTA_CATEGORY: (
            OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE
        ),
        IvaLedgerAggregationIssueReason.NON_ARISING_CATEGORY_FOR_INVOICE_SIDE: (
            OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE
        ),
        IvaLedgerAggregationIssueReason.MISSING_EUR_TAX_SUBSTRATE: OperatorActionAxis.IMPORT_LEDGER_DATA,
        IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE: OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE,
        IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_CATEGORY: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE: (
            OperatorActionAxis.RESOLVE_IDENTITY
        ),
        IvaLedgerAggregationIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION: (
            OperatorActionAxis.RESOLVE_IDENTITY
        ),
        IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION: OperatorActionAxis.RESOLVE_IDENTITY,
        IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_ESTABLISHMENT_ON_EXPORT: (
            OperatorActionAxis.RESOLVE_IDENTITY
        ),
        IvaLedgerAggregationIssueReason.CASH_ACCOUNTING_EXCLUDED_CATEGORY: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        IvaLedgerAggregationIssueReason.MISSING_DEDUCTION_CLASSIFICATION: (
            OperatorActionAxis.COMPLETE_DOCUMENT_EVIDENCE
        ),
    },
)
"""Total operator-action projection for every native IVA ledger issue."""

if set(OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE) != set(IvaLedgerAggregationIssueReason):
    missing = sorted(
        reason.value
        for reason in set(IvaLedgerAggregationIssueReason) - set(OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE)
    )
    stale = sorted(
        str(reason)
        for reason in set(OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE) - set(IvaLedgerAggregationIssueReason)
    )
    raise RuntimeError(
        f"every IvaLedgerAggregationIssueReason must declare an OperatorActionAxis; missing={missing}; stale={stale}",
    )

# Fails the import, not a test run, so an unclassified member cannot reach a
# run at all. The same placement and message shape as the discrepancy-kind
# guard in ``_confirmation_gate``, deliberately: that axis absorbed two
# independent misses in one week and both reached a test run rather than an
# import failure.
#
# What differs is the SHAPE of the classification, and only because the axes
# differ. That guard maps one enum onto one target and needs no second side,
# because every DraftDiscrepancyKind is a real defect its single consumer acts
# on. This enum has TWO consumers with different reach: the projection path
# raises all twenty members, and preflight runs two of the screens and never
# enters the rest. Thirteen members therefore have no preflight counterpart to
# map onto, and inventing one would ship an operator-facing message for a
# condition this layer cannot detect -- the failure S200 was written against.
# The partition records that reachability fact per member instead. Its sibling
# is right that an exemption ROW would be the worse shape on an axis where
# severity is a product choice; here the second side is a structural fact about
# which code path can emit what, which is not expressible by omission.
#
# The honest structural alternative is splitting the enum so preflight's
# consumer sees only its own reach. That is a cross-surface refactor of the
# aggregation package, and the shared members are deliberately shared with the
# renta ledger enum for cross-ledger telemetry, so it is not this module's to
# make.
_reaching_preflight = IVA_LEDGER_MISSING_FACT_REASONS | IVA_LEDGER_COUNTERPARTY_GATE_REASONS
_classified = set(_PREFLIGHT_REASON_BY_IVA_ISSUE) | set(_IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT)

if _classified != set(IvaLedgerAggregationIssueReason):
    _unclassified = ", ".join(sorted(r.value for r in set(IvaLedgerAggregationIssueReason) - _classified))
    _stale = ", ".join(sorted(str(r) for r in _classified - set(IvaLedgerAggregationIssueReason)))
    raise RuntimeError(
        "every IvaLedgerAggregationIssueReason must be classified for the ledger preflight: map it in "
        "_PREFLIGHT_REASON_BY_IVA_ISSUE if preflight can receive it, or record why it cannot in "
        f"_IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT; unclassified: {_unclassified or 'none'}; "
        f"stale: {_stale or 'none'}",
    )

if _both := set(_PREFLIGHT_REASON_BY_IVA_ISSUE) & set(_IVA_ISSUE_REASONS_NOT_REACHING_PREFLIGHT):
    raise RuntimeError(
        "an IvaLedgerAggregationIssueReason cannot be both mapped into preflight and declared unable to "
        f"reach it; on both sides: {', '.join(sorted(r.value for r in _both))}",
    )

if _unmapped := _reaching_preflight - set(_PREFLIGHT_REASON_BY_IVA_ISSUE):
    raise RuntimeError(
        "a preflight-facing screen emits an IvaLedgerAggregationIssueReason with no preflight counterpart; "
        f"unmapped: {', '.join(sorted(r.value for r in _unmapped))}",
    )

if _detailless := IVA_LEDGER_MISSING_FACT_REASONS - set(_PREFLIGHT_DETAIL_BY_IVA_ISSUE):
    raise RuntimeError(
        "a missing-fact reason reaches preflight with no detail sentence; "
        f"missing: {', '.join(sorted(r.value for r in _detailless))}",
    )


def _preflight_reason_for_iva_issue(reason: IvaLedgerAggregationIssueReason) -> LedgerPreflightIssueReason:
    return _PREFLIGHT_REASON_BY_IVA_ISSUE[reason]


def _preflight_detail_for_iva_issue(reason: IvaLedgerAggregationIssueReason) -> str:
    return _PREFLIGHT_DETAIL_BY_IVA_ISSUE[reason]


__all__ = [
    "OPERATOR_ACTION_BY_IVA_LEDGER_AGGREGATION_ISSUE",
    "LedgerPreflightIssue",
    "LedgerPreflightIssueReason",
    "LedgerPreflightReport",
    "preflight_ledger_tax_readiness",
    "preflight_transaction_catalogue",
]
