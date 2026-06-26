"""Repository-backed IVA observation projection from ledger catalogues.

Consumes a :class:`~aeat.domain.calculations.registry.ModeloRevision` to resolve the IVA aggregation binding
values declared for the target modelo period. The primary entry point
:func:`aggregate_iva_ledger_observations` accepts a
:class:`~aeat.domain.transactions.TransactionCatalogue` and returns an :class:`IvaLedgerAggregation`.
The repository-backed entry point constructs a
:class:`~aeat.domain.transactions.TransactionCatalogueRepository` for the active bucket when none
is supplied.

Related: :mod:`_renta_ledger`, :mod:`_renta_income_ledger` for similar pipelines.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_serializer, field_validator

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...domain.calculations.registry import (
    BindingId,
    IvaLedgerObservation,
    ModeloRevision,
    resolve_ledger_iva_aggregation_binding_values,
    unsupported_ledger_iva_observations,
)
from ...domain.iva import (
    EUMemberState,
    InvoiceKind,
    IvaCategory,
    IvaFlowDirection,
    IvaRateKind,
    IvaRateNotFoundError,
    ProrrataInputError,
    ProrrataReference,
    derive_flow_for_classification,
    lookup_rate,
    validate_prorrata_reference,
)
from ...domain.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionCatalogueRepositoryProtocol,
    TransactionDirection,
    TransactionLifecycleState,
)
from . import _shared_issue_reasons
from ._business_proportion import business_proportion
from ._currency_predicates import is_non_eur_without_conversion
from ._errors import AggregationValidationError, t

_LedgerId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]

_RATE_KIND_TO_DOMESTIC_CATEGORY: dict[IvaRateKind, IvaCategory] = {
    IvaRateKind.ZERO: IvaCategory.DOMESTIC_ZERO,
    IvaRateKind.SUPER_REDUCED: IvaCategory.DOMESTIC_SUPER_REDUCED_4,
    IvaRateKind.REDUCED: IvaCategory.DOMESTIC_REDUCED_10,
    IvaRateKind.GENERAL: IvaCategory.DOMESTIC_GENERAL_21,
}


class IvaLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a ledger row did not produce IVA observations.

    The first five values are shared with
    :class:`aeat.application.aggregation._renta_ledger.RentaLedgerAggregationIssueReason`
    through :mod:`._shared_issue_reasons` so cross-ledger telemetry can
    group upstream filter rejections under one key. The remaining values
    are IVA-specific.
    """

    UNSUPPORTED_DIRECTION = _shared_issue_reasons.UNSUPPORTED_DIRECTION
    UNSUPPORTED_CURRENCY = _shared_issue_reasons.UNSUPPORTED_CURRENCY
    UNCLASSIFIED_BUSINESS_STATE = _shared_issue_reasons.UNCLASSIFIED_BUSINESS_STATE
    PERSONAL_TRANSACTION = _shared_issue_reasons.PERSONAL_TRANSACTION
    OUTSIDE_PERIOD = _shared_issue_reasons.OUTSIDE_PERIOD
    MISSING_TAXABLE_BASE = "missing_taxable_base"
    MISSING_IVA_AMOUNT = "missing_iva_amount"
    MISSING_IVA_RATE = "missing_iva_rate"
    UNSUPPORTED_IVA_RATE = "unsupported_iva_rate"
    INVALID_PRORRATA_REFERENCE = "invalid_prorrata_reference"
    UNSUPPORTED_IVA_CATEGORY = "unsupported_iva_category"
    MISSING_COUNTERPARTY_EU_MEMBER_STATE = "missing_counterparty_eu_member_state"
    DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION = "domestic_counterparty_on_intra_community_transaction"
    EU_MEMBER_STATE_ON_EXPORT_TRANSACTION = "eu_member_state_on_export_transaction"


class IvaLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while projecting IVA ledger observations."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    reason: IvaLedgerAggregationIssueReason
    detail: str = Field(min_length=1, max_length=512)


class ProrrataLedgerReference(BaseModel):
    """Bucket-local ledger row pointer to a legal IVA prorrata reference."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1, max_length=128)
    transaction_date: date
    reference: ProrrataReference
    base_amount: Decimal = Field(..., ge=Decimal("0"))
    input_iva_amount: Decimal = Field(..., ge=Decimal("0"))


class IvaLedgerInputKind(StrEnum):
    """Business role of a pre-classified IVA ledger candidate.

    ``ADJUSTMENT`` rows may carry negative bases or cuotas because
    rectification and regularisation entries reverse or correct prior
    operations. The registry consumes the resulting signed observation;
    the model keeps the adjustment axis visible at the application
    boundary where source provenance still exists.
    """

    ORDINARY_OPERATION = "ordinary_operation"
    ADJUSTMENT = "adjustment"


class IvaLedgerCandidate(BaseModel):
    """One pre-classified ledger line for generic IVA aggregation.

    This is the application hand-off shape for IVA facts that cannot be
    inferred safely from a bank transaction direction plus a rate:
    exenciones, no-sujetas, recargo de equivalencia, intra-community
    reverse-charge operations, imports/exports, and explicit
    adjustments. Upstream classifiers must supply the authoritative IVA
    category, rate kind, and flow direction before this layer creates a
    registry-ready :class:`IvaLedgerObservation`.
    """

    model_config = _STRICT_FROZEN

    ledger_id: _LedgerId
    transaction_date: date
    category: IvaCategory
    rate_kind: IvaRateKind
    flow_direction: IvaFlowDirection
    base_amount: Decimal
    iva_amount: Decimal
    input_kind: IvaLedgerInputKind = IvaLedgerInputKind.ORDINARY_OPERATION
    prorrata_reference_id: _LedgerId | None = None


class IvaLedgerAggregation(BaseModel):
    """IVA observations produced from one bucket-local transaction catalogue."""

    model_config = _STRICT_FROZEN

    period: Period
    observations: Sequence[IvaLedgerObservation] = Field(default_factory=tuple)
    prorrata_references: Sequence[ProrrataLedgerReference] = Field(default_factory=tuple)
    issues: Sequence[IvaLedgerAggregationIssue] = Field(default_factory=tuple)

    @field_validator("observations")
    @classmethod
    def _freeze_observations(cls, value: Sequence[IvaLedgerObservation]) -> tuple[IvaLedgerObservation, ...]:
        return tuple(value)

    @field_validator("prorrata_references")
    @classmethod
    def _freeze_prorrata_references(
        cls,
        value: Sequence[ProrrataLedgerReference],
    ) -> tuple[ProrrataLedgerReference, ...]:
        return tuple(value)

    @field_validator("issues")
    @classmethod
    def _freeze_issues(cls, value: Sequence[IvaLedgerAggregationIssue]) -> tuple[IvaLedgerAggregationIssue, ...]:
        return tuple(value)

    @field_serializer("observations")
    def _serialize_observations(
        self,
        value: Sequence[IvaLedgerObservation],
    ) -> tuple[IvaLedgerObservation, ...]:
        return tuple(value)

    @field_serializer("prorrata_references")
    def _serialize_prorrata_references(
        self,
        value: Sequence[ProrrataLedgerReference],
    ) -> tuple[ProrrataLedgerReference, ...]:
        return tuple(value)

    @field_serializer("issues")
    def _serialize_issues(
        self,
        value: Sequence[IvaLedgerAggregationIssue],
    ) -> tuple[IvaLedgerAggregationIssue, ...]:
        return tuple(value)


def aggregate_iva_ledger_observations_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> IvaLedgerAggregation:
    """Load the bucket-local transaction catalogue and project IVA observations.

    Returns an :class:`IvaLedgerAggregation`.
    """
    repository = transaction_repository or TransactionCatalogueRepository(bucket_id=bucket_id)
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    return aggregate_iva_ledger_observations(repository.load(), period=period)


def validate_iva_ledger_observation(candidate: IvaLedgerCandidate) -> IvaLedgerObservation:
    """Validate a pre-classified IVA candidate and return an :class:`IvaLedgerObservation`.

    The validator does not re-classify the operation and does not derive
    IVA from the base. It only blocks sentinel categories that are not
    declarable ledger facts; the category, rate, and flow axes must have
    been resolved upstream from invoice/operation evidence.
    """
    if candidate.category in {IvaCategory.UNKNOWN, IvaCategory.ERRONEOUS_INVOICE}:
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.unsupported_iva_category"),
            context={
                "ledger_id": candidate.ledger_id,
                "category": candidate.category.value,
            },
        )
    return IvaLedgerObservation(
        ledger_id=candidate.ledger_id,
        transaction_date=candidate.transaction_date,
        category=candidate.category,
        rate_kind=candidate.rate_kind,
        flow_direction=candidate.flow_direction,
        base_amount=candidate.base_amount,
        iva_amount=candidate.iva_amount,
        prorrata_reference_id=candidate.prorrata_reference_id,
    )


def validate_iva_ledger_observations(candidates: Iterable[IvaLedgerCandidate]) -> tuple[IvaLedgerObservation, ...]:
    """Validate every pre-classified IVA candidate in input order.

    Returns a tuple of :class:`IvaLedgerObservation` instances.
    """
    return tuple(validate_iva_ledger_observation(candidate) for candidate in candidates)


def aggregate_iva_ledger_candidates(
    candidates: Iterable[IvaLedgerCandidate],
    *,
    period: Period,
) -> IvaLedgerAggregation:
    """Project pre-classified IVA candidates into period-scoped observations.

    This path complements :func:`aggregate_iva_ledger_observations`,
    which remains the legacy domestic-rate projection from bank
    transactions. Pre-classified candidates are required for non-domestic
    IVA and adjustments because those axes cannot be recovered from a
    transaction amount or direction without guessing.

    Returns an :class:`IvaLedgerAggregation` carrying the accepted
    observations and any period-exclusion issues.
    """
    resolved_period = period
    observations: list[IvaLedgerObservation] = []
    issues: list[IvaLedgerAggregationIssue] = []
    for candidate in candidates:
        if not resolved_period.contains(candidate.transaction_date):
            issues.append(
                IvaLedgerAggregationIssue(
                    transaction_id=candidate.ledger_id,
                    reason=IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
                    detail=(f"transaction date {candidate.transaction_date.isoformat()} is outside {resolved_period}"),
                ),
            )
            continue
        observations.append(validate_iva_ledger_observation(candidate))
    return IvaLedgerAggregation(
        period=resolved_period,
        observations=tuple(observations),
        issues=tuple(issues),
    )


def aggregate_iva_ledger_candidate_bindings(
    revision: ModeloRevision,
    candidates: Iterable[IvaLedgerCandidate],
    *,
    period: Period,
) -> dict[BindingId, Decimal]:
    """Validate pre-classified candidates and resolve registry bindings.

    Args:
        revision: The :class:`ModeloRevision` used to resolve binding values.
        candidates: Pre-classified :class:`IvaLedgerCandidate` rows to project
            into engine binding channels.
        period: The aggregation :class:`Period` whose date range bounds the
            candidate set.
    """
    aggregation = aggregate_iva_ledger_candidates(candidates, period=period)
    if aggregation.issues:
        first = aggregation.issues[0]
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.candidate_outside_period"),
            context={
                "ledger_id": first.transaction_id,
                "reason": first.reason.value,
                "detail": first.detail,
            },
        )
    unsupported = unsupported_ledger_iva_observations(revision, aggregation.observations)
    if unsupported:
        first = unsupported[0]
        raise AggregationValidationError(
            t("aggregation.iva_ledger.errors.unsupported_iva_category"),
            context={
                "ledger_id": first.ledger_id,
                "category": first.category.value,
                "rate_kind": first.rate_kind.value,
                "flow_direction": first.flow_direction.value,
                "revision_id": revision.id,
            },
        )
    return resolve_ledger_iva_aggregation_binding_values(revision, aggregation.observations)


def aggregate_iva_ledger_observations(
    transactions: TransactionCatalogue,
    *,
    period: Period,
) -> IvaLedgerAggregation:
    """Project classified ledger transaction tax facts into an :class:`IvaLedgerAggregation`.

    Args:
        transactions: The :class:`TransactionCatalogue` supplying active ledger entries.
        period: Filing period as a typed :class:`Period` instance.
    """
    resolved_period = period
    observations: list[IvaLedgerObservation] = []
    prorrata_references: list[ProrrataLedgerReference] = []
    issues: list[IvaLedgerAggregationIssue] = []
    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        outcome = _classify_iva_transaction(transaction, resolved_period=resolved_period)
        if outcome.gate_issue is not None:
            issues.append(outcome.gate_issue)
            continue
        if outcome.prorrata_issue is not None:
            issues.append(outcome.prorrata_issue)
        if outcome.prorrata_reference is not None:
            prorrata_references.append(outcome.prorrata_reference)
        if outcome.observation is not None:
            observations.append(outcome.observation)
    return IvaLedgerAggregation(
        period=resolved_period,
        observations=tuple(observations),
        prorrata_references=tuple(prorrata_references),
        issues=tuple(issues),
    )


@dataclass(frozen=True)
class _IvaTransactionOutcome:
    """Per-transaction outcome carrying the typed sinks the orchestrator drains.

    A transaction either fails a pre-observation gate (``gate_issue``
    populated, nothing else) or it survives all pre-gates and produces
    an ``observation``. The observation path may additionally emit a
    ``prorrata_reference`` AND/OR a ``prorrata_issue`` — they are
    independent sinks: an invalid prorrata-reference attaches to the
    issue list, a valid one attaches to the prorrata-references list,
    and either way the observation itself is recorded.
    """

    gate_issue: IvaLedgerAggregationIssue | None = None
    observation: IvaLedgerObservation | None = None
    prorrata_reference: ProrrataLedgerReference | None = None
    prorrata_issue: IvaLedgerAggregationIssue | None = None


# Categories that never produce a declarable IVA observation: recargo de
# equivalencia (the IVA + RE surcharge is non-deductible acquisition cost for the
# retailer, settled via the supplier) and the unknown/erroneous sentinels.
_NON_DECLARABLE_IVA_CATEGORIES = frozenset(
    {
        IvaCategory.RECARGO_EQUIVALENCIA,
        IvaCategory.UNKNOWN,
        IvaCategory.ERRONEOUS_INVOICE,
    },
)


def _classify_iva_transaction(
    transaction: Transaction,
    *,
    resolved_period: Period,
) -> _IvaTransactionOutcome:
    """Filter + classify one ledger transaction against the IVA aggregation pipeline.

    Returns an :class:`_IvaTransactionOutcome` carrying the typed
    sinks the orchestrator drains. Each pre-observation gate projects
    to ``gate_issue`` with a typed
    :class:`IvaLedgerAggregationIssueReason`. The observation-eligible
    path constructs the observation and (when present) the prorrata
    reference; an invalid prorrata reference is reported as a
    ``prorrata_issue`` alongside the observation.
    """
    transaction_id = transaction.transaction_id
    operation_date = transaction.raw.value_date or transaction.raw.booked_date
    if not resolved_period.contains(operation_date):
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.OUTSIDE_PERIOD,
                detail=f"transaction date {operation_date.isoformat()} is outside {resolved_period}",
            ),
        )
    if is_non_eur_without_conversion(transaction):
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY,
                detail=f"transaction currency {transaction.raw.currency!r} is not supported for IVA aggregation",
            ),
        )
    flow_direction = _flow_direction_for(transaction.direction)
    if flow_direction is None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION,
                detail=f"transaction direction {transaction.direction.value!r} is not an IVA settlement flow",
            ),
        )
    proportionality = _business_proportionality(transaction)
    if proportionality is None:
        reason = (
            IvaLedgerAggregationIssueReason.PERSONAL_TRANSACTION
            if transaction.business_classification is BusinessClassification.PERSONAL
            else IvaLedgerAggregationIssueReason.UNCLASSIFIED_BUSINESS_STATE
        )
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=reason,
                detail=(
                    f"business classification {transaction.business_classification.value!r} cannot feed IVA aggregation"
                ),
            ),
        )
    iva_category = transaction.iva_category
    if iva_category is not None and iva_category in _NON_DECLARABLE_IVA_CATEGORIES:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_CATEGORY,
                detail=(
                    f"iva_category {iva_category.value!r} does not produce a declarable IVA "
                    "observation (recargo-equivalencia is non-deductible cost; unknown/erroneous are sentinels)"
                ),
            ),
        )
    missing_reason = _missing_tax_fact_reason(transaction)
    if missing_reason is not None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=missing_reason,
                detail=_missing_tax_fact_detail(missing_reason),
            ),
        )
    assert transaction.taxable_base is not None
    assert transaction.iva_amount is not None
    assert transaction.iva_rate is not None
    rate_kind = _iva_rate_kind_for(transaction.iva_rate, on_date=operation_date)
    if rate_kind is None:
        return _IvaTransactionOutcome(
            gate_issue=IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE,
                detail=f"IVA rate {transaction.iva_rate} is not a canonical substrate IVA rate",
            ),
        )
    base_amount = transaction.taxable_base * proportionality
    iva_amount = transaction.iva_amount * proportionality
    recargo_amount = (transaction.recargo_amount or Decimal("0")) * proportionality

    # Resolve the effective IVA category: explicit override takes priority over
    # the rate-kind-derived domestic category (D5 decision from ADR).
    explicit_category = transaction.iva_category
    if explicit_category is not None:
        d5_issue = _validate_intracom_export_counterparty(
            transaction_id=transaction_id,
            category=explicit_category,
            eu_member_state=transaction.counterparty_eu_member_state,
        )
        if d5_issue is not None:
            return _IvaTransactionOutcome(gate_issue=d5_issue)
        effective_category = explicit_category
    else:
        effective_category = _RATE_KIND_TO_DOMESTIC_CATEGORY[rate_kind]

    # Recompute the IVA flow now the effective category is known. The
    # direction-only screen above only rejects non-settlement directions;
    # the canonical flow routes reverse-charge categories
    # (DOMESTIC_REVERSE_CHARGE, INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE)
    # to INVERSION_SUJETO_PASIVO and leaves every other category on its
    # repercutido/soportado direction. ``_invoice_kind_for`` cannot be
    # None here: ``flow_direction`` above already gated unknown directions.
    invoice_kind = _invoice_kind_for(transaction.direction)
    assert invoice_kind is not None
    flow_direction = derive_flow_for_classification(
        category=effective_category,
        invoice_direction=invoice_kind,
    )

    prorrata_reference, prorrata_issue, linked_prorrata_id = _resolve_iva_prorrata_attachment(
        transaction,
        flow_direction=flow_direction,
        operation_date=operation_date,
        base_amount=base_amount,
        iva_amount=iva_amount,
    )
    observation = IvaLedgerObservation(
        ledger_id=transaction.transaction_id,
        transaction_date=operation_date,
        category=effective_category,
        rate_kind=rate_kind,
        flow_direction=flow_direction,
        base_amount=base_amount,
        iva_amount=iva_amount,
        recargo_amount=recargo_amount,
        prorrata_reference_id=linked_prorrata_id,
    )
    return _IvaTransactionOutcome(
        observation=observation,
        prorrata_reference=prorrata_reference,
        prorrata_issue=prorrata_issue,
    )


def _resolve_iva_prorrata_attachment(
    transaction: Transaction,
    *,
    flow_direction: IvaFlowDirection,
    operation_date: date,
    base_amount: Decimal,
    iva_amount: Decimal,
) -> tuple[ProrrataLedgerReference | None, IvaLedgerAggregationIssue | None, str | None]:
    """Resolve the (prorrata-reference, prorrata-issue, linked-id) triple.

    Returns ``(None, None, None)`` when the transaction carries no
    prorrata_reference. Returns ``(None, issue, None)`` when the
    reference fails parsing OR the row is not a supported-input IVA
    row (prorrata only attaches to SOPORTADO flows). Returns
    ``(reference, None, transaction_id)`` for a valid attachment.
    """
    raw_reference = _prorrata_reference_for(
        transaction.prorrata_reference,
        transaction_id=transaction.transaction_id,
    )
    if isinstance(raw_reference, IvaLedgerAggregationIssue):
        return None, raw_reference, None
    if raw_reference is None:
        return None, None, None
    if flow_direction is not IvaFlowDirection.SOPORTADO:
        return (
            None,
            IvaLedgerAggregationIssue(
                transaction_id=transaction.transaction_id,
                reason=IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE,
                detail="prorrata_reference may only be attached to supported input IVA rows",
            ),
            None,
        )
    return (
        ProrrataLedgerReference(
            transaction_id=transaction.transaction_id,
            transaction_date=operation_date,
            reference=raw_reference,
            base_amount=base_amount,
            input_iva_amount=iva_amount,
        ),
        None,
        transaction.transaction_id,
    )


def _validate_intracom_export_counterparty(
    *,
    transaction_id: str,
    category: IvaCategory,
    eu_member_state: EUMemberState | None,
) -> IvaLedgerAggregationIssue | None:
    """Return a gate issue when the D5 counterparty/category coupling is violated.

    Rules (ADR D5):
    - ``INTRA_COMMUNITY_SUPPLY`` requires a non-ES ``EUMemberState``.
    - ``EXPORT_THIRD_COUNTRY_ZERO_RATED`` must carry no ``EUMemberState``.
    """
    if category is IvaCategory.INTRA_COMMUNITY_SUPPLY:
        if eu_member_state is None:
            return IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_EU_MEMBER_STATE,
                detail="intra-community supply requires a non-ES counterparty EU member state",
            )
        if eu_member_state is EUMemberState.ES:
            return IvaLedgerAggregationIssue(
                transaction_id=transaction_id,
                reason=IvaLedgerAggregationIssueReason.DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION,
                detail=(
                    f"counterparty EU member state {eu_member_state.value!r} is Spain — "
                    "not a valid intra-community counterparty"
                ),
            )
    if category is IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED and eu_member_state is not None:
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION,
            detail=f"export to third country must not carry an EU member state; got {eu_member_state.value!r}",
        )
    return None


def _invoice_kind_for(direction: TransactionDirection) -> InvoiceKind | None:
    """Map a bank :class:`TransactionDirection` onto the invoice-issuance axis.

    ``INCOMING`` money is a sale the autónomo issued (output IVA);
    ``OUTGOING`` money is a purchase the autónomo received (input IVA).
    Returns ``None`` for any direction that is not an IVA settlement
    flow, so the caller can reject it as ``UNSUPPORTED_DIRECTION``.
    """
    if direction is TransactionDirection.INCOMING:
        return InvoiceKind.ISSUED
    if direction is TransactionDirection.OUTGOING:
        return InvoiceKind.RECEIVED
    return None


def _flow_direction_for(direction: TransactionDirection) -> IvaFlowDirection | None:
    """Return the direction-only IVA flow, used as the settlement-flow gate.

    This screens the bank direction before the IVA category is known
    (an ``UNKNOWN``/``UNRESOLVED`` direction is not an IVA settlement
    flow). The final flow that lands on the observation is recomputed
    once the effective :class:`IvaCategory` is resolved via
    :func:`derive_flow_for_classification`, which routes reverse-charge
    categories to :attr:`IvaFlowDirection.INVERSION_SUJETO_PASIVO` while
    preserving ``REPERCUTIDO``/``SOPORTADO`` for every other category.
    """
    invoice_kind = _invoice_kind_for(direction)
    if invoice_kind is None:
        return None
    return IvaFlowDirection.REPERCUTIDO if invoice_kind is InvoiceKind.ISSUED else IvaFlowDirection.SOPORTADO


def _business_proportionality(transaction: Transaction) -> Decimal | None:
    return business_proportion(transaction.business_classification, transaction.business_pct)


def _missing_tax_fact_reason(transaction: Transaction) -> IvaLedgerAggregationIssueReason | None:
    reasons = iva_ledger_missing_fact_reasons(transaction)
    return reasons[0] if reasons else None


def iva_ledger_missing_fact_reasons(transaction: Transaction) -> tuple[IvaLedgerAggregationIssueReason, ...]:
    """Return missing IVA fact reasons for a transaction without projecting it.

    Each element is an :class:`IvaLedgerAggregationIssueReason` describing
    one absent required tax fact.
    """
    reasons: list[IvaLedgerAggregationIssueReason] = []
    if transaction.taxable_base is None:
        reasons.append(IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE)
    if transaction.iva_amount is None:
        reasons.append(IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT)
    if transaction.iva_rate is None:
        reasons.append(IvaLedgerAggregationIssueReason.MISSING_IVA_RATE)
    return tuple(reasons)


def _missing_tax_fact_detail(reason: IvaLedgerAggregationIssueReason) -> str:
    return {
        IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE: "transaction has no taxable_base fact",
        IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT: "transaction has no iva_amount fact",
        IvaLedgerAggregationIssueReason.MISSING_IVA_RATE: "transaction has no iva_rate fact",
    }[reason]


def _prorrata_reference_for(
    reference_id: str | None,
    *,
    transaction_id: str,
) -> ProrrataReference | IvaLedgerAggregationIssue | None:
    if reference_id is None:
        return None
    try:
        return validate_prorrata_reference(reference_id)
    except ProrrataInputError as exc:
        return IvaLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE,
            detail=str(exc),
        )


def _iva_rate_kind_for(rate: Decimal, *, on_date: date) -> IvaRateKind | None:
    for kind in _RATE_KIND_TO_DOMESTIC_CATEGORY:
        try:
            rate_record = lookup_rate(EUMemberState.ES, kind, on_date)
        except IvaRateNotFoundError:
            continue
        if rate_record.pct / Decimal("100") == rate:
            return kind
    return None


__all__ = [
    "IvaLedgerAggregation",
    "IvaLedgerAggregationIssue",
    "IvaLedgerAggregationIssueReason",
    "IvaLedgerCandidate",
    "IvaLedgerInputKind",
    "ProrrataLedgerReference",
    "aggregate_iva_ledger_candidate_bindings",
    "aggregate_iva_ledger_candidates",
    "aggregate_iva_ledger_observations",
    "aggregate_iva_ledger_observations_from_repositories",
    "iva_ledger_missing_fact_reasons",
    "validate_iva_ledger_observation",
    "validate_iva_ledger_observations",
]
