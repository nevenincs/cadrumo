"""Repository-backed IRNR income ledger mechanics.

The module retains transaction filtering, classification folding, period
partitioning, and typed issue/provenance mechanics.  Target coordinates,
income-type namespaces, model applicability, source-scope membership, and
binding/legal declarations belong to the selected registry revision.

TODO(fact-relocation): resolve IRNR ledger target and M210 income-type parameter namespace from selected registry revision

No target, parameter prefix, applicability set, or binding identifier is
declared as a Python fallback.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from ...core.casilla_id import CasillaId
from ...core.country_code import CountryCodeAlpha2
from ...core.i18n.render import tr
from ...core.i18n.translatable import Translatable as t
from ...core.identity.transaction_ids import TransactionId
from ...core.irnr import M210PayerMode
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...core.prose_elision import IssueDetail
from ...core.unit_proportion import UnitProportion
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.m210_income_classification import M210IncomeClassification
from ...domain.transactions.models import OutOfWindowTransactionSummary, Transaction, TransactionCatalogue
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from . import _shared_issue_reasons
from ._grouping import fold_casilla_observations
from ._models import CasillaAggregation, LedgerAggregationResultBase
from .errors import AggregationPeriodError, AggregationValidationError


class IrnrIncomeLedgerAggregationIssueReason(StrEnum):
    """Machine-readable reasons why a row did not reach the M210 gross-income fact."""

    OUTSIDE_PERIOD = _shared_issue_reasons.OUTSIDE_PERIOD
    UNSUPPORTED_PERIOD = "unsupported_period"
    FOREIGN_SOURCE_OUT_OF_SCOPE = "foreign_source_out_of_scope"
    SOURCE_JURISDICTION_UNRESOLVED = "source_jurisdiction_unresolved"
    INCOMPLETE_M210_CLASSIFICATION = "incomplete_m210_classification"


#: The traceable-exclusion ``detail`` annotation: elides rather than refusing.
#:
#: These issues explain why a ledger row was excluded, so refusing one over its
#: length would drop the explanation for the exclusion AND fail the aggregation
#: that produced it -- a silent under-declaration dressed as a validation error.
#: Shortening the sentence is strictly the lesser loss.


class IrnrIncomeLedgerAggregationIssue(BaseModel):
    """Traceable exclusion emitted while resolving the M210 ledger projection."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    reason: IrnrIncomeLedgerAggregationIssueReason
    detail: IssueDetail
    rejected_source_jurisdiction: str | None = None


class IrnrIncomeObservation(BaseModel):
    """One selected, ES-source, explicitly M210-classified income observation."""

    model_config = _STRICT_FROZEN

    transaction_id: TransactionId
    target_casilla_id: CasillaId
    official_tipo_renta_code: str = Field(min_length=2, max_length=2)
    gross_income_amount: Decimal = Field(ge=Decimal("0"))
    applicable_rate: UnitProportion
    payer_mode: M210PayerMode
    payer_id: str | None = None
    asset_or_right_id: str | None = None
    filing_date: date
    source_jurisdiction: CountryCodeAlpha2


class IrnrIncomeLedgerAggregation(LedgerAggregationResultBase[IrnrIncomeObservation, IrnrIncomeLedgerAggregationIssue]):
    """Selected-code M210 observations for one filing period."""

    selected_official_tipo_renta_code: str = Field(min_length=2, max_length=2)
    out_of_window_summary: OutOfWindowTransactionSummary | None = None


def aggregate_irnr_income_ledger_from_repositories(
    *,
    bucket_id: str,
    period: Period,
    revision: ModeloRevision,
    modelo: str,
    target_casilla_id: CasillaId,
    selected_official_tipo_renta_code: str,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
) -> IrnrIncomeLedgerAggregation:
    """Load an injected secure transaction catalogue and aggregate one selected M210 code.

    ``revision`` is the :class:`ModeloRevision` that declares the binding.
    ``transaction_repository`` is the composition-root-owned
    :class:`TransactionCatalogueRepositoryProtocol` for ``bucket_id``.

    The repository date partition limits decryption/classification to the
    filing span and returns a compact, provenance-free summary for the other
    dates.  Full-catalogue callers retain the per-row ``OUTSIDE_PERIOD`` issues
    instead.
    """
    repository = transaction_repository
    if repository.bucket_id != bucket_id:
        raise AggregationValidationError(
            t("aggregation.renta_ledger.errors.bucket_mismatch"),
            context={"bucket_id": bucket_id, "repository_bucket_id": repository.bucket_id},
        )
    if not period.has_date_span():
        return aggregate_irnr_income_ledger(
            repository.load(),
            bucket_id=bucket_id,
            period=period,
            revision=revision,
            modelo=modelo,
            target_casilla_id=target_casilla_id,
            selected_official_tipo_renta_code=selected_official_tipo_renta_code,
        )

    partition = repository.partition_by_date_range(period.start_date, period.end_date)
    result = aggregate_irnr_income_ledger(
        partition.in_window,
        bucket_id=bucket_id,
        period=period,
        revision=revision,
        modelo=modelo,
        target_casilla_id=target_casilla_id,
        selected_official_tipo_renta_code=selected_official_tipo_renta_code,
    )
    out_of_window_summary = partition.out_of_window_summary or OutOfWindowTransactionSummary.from_index_entries(
        partition.out_of_window,
    )
    return result.model_copy(update={"out_of_window_summary": out_of_window_summary})


def aggregate_irnr_income_ledger(
    transactions: TransactionCatalogue,
    *,
    bucket_id: str,
    period: Period,
    revision: ModeloRevision,
    modelo: str,
    target_casilla_id: CasillaId,
    selected_official_tipo_renta_code: str,
) -> IrnrIncomeLedgerAggregation:
    """Aggregate selected-code, incoming, registry-admitted IRNR income.

    ``transactions`` is the :class:`TransactionCatalogue` to aggregate.
    ``revision`` is the :class:`ModeloRevision` that declares the binding.
    ``modelo`` and ``target_casilla_id`` are selected-revision coordinates;
    neither has a Python fallback.

    The classification's ``gross_income_amount`` is the declared M210 fact; it
    is intentionally not derived from the signed raw ledger amount.  This
    preserves explicit operator evidence for deductions, partial rights, and
    the official code while leaving registry formula evaluation as the one
    arithmetic path after the gross-income binding has been resolved.
    """
    if not period.has_date_span():
        raise AggregationPeriodError(
            t("aggregation.renta_ledger.errors.unsupported_period"),
            context={"period": str(period)},
        )

    declared_codes = _resolve_selected_income_type_codes(revision, period)
    if selected_official_tipo_renta_code not in declared_codes:
        raise AggregationValidationError(
            t("aggregation.irnr_income_ledger.diagnostics.tipo_renta_code_not_declared"),
            context={
                "tipo_renta_code": selected_official_tipo_renta_code,
                "period": str(period),
            },
        )

    observations: list[IrnrIncomeObservation] = []
    issues: list[IrnrIncomeLedgerAggregationIssue] = []
    for transaction in transactions.values():
        if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
            continue
        outcome = _classify_irnr_income_transaction(
            transaction,
            period=period,
            selected_official_tipo_renta_code=selected_official_tipo_renta_code,
            declared_codes=declared_codes,
            target_casilla_id=target_casilla_id,
        )
        if outcome is None:
            continue
        if isinstance(outcome, IrnrIncomeLedgerAggregationIssue):
            issues.append(outcome)
        else:
            observations.append(outcome)

    return IrnrIncomeLedgerAggregation(
        modelo=modelo,
        period=period,
        selected_official_tipo_renta_code=selected_official_tipo_renta_code,
        observations=tuple(observations),
        issues=tuple(issues),
        casilla_aggregation=_irnr_gross_income_casilla_aggregation(modelo, period, observations),
    )


def _resolve_selected_income_type_codes(revision: ModeloRevision, period: Period) -> frozenset[str]:
    """Require selected-revision income-type resolution at the registry seam."""
    del revision, period
    raise AggregationValidationError(
        "resolve IRNR ledger target and income-type parameter namespace from selected registry revision",
    )


def _irnr_source_jurisdiction_issue(
    transaction_id: str,
    declared_jurisdiction: str | None,
) -> IrnrIncomeLedgerAggregationIssue | None:
    """Reject an unresolved source jurisdiction; registry scope owns membership."""
    if declared_jurisdiction is None:
        return IrnrIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IrnrIncomeLedgerAggregationIssueReason.SOURCE_JURISDICTION_UNRESOLVED,
            detail=tr(
                "aggregation.irnr_income_ledger.diagnostics.source_jurisdiction_unresolved",
                default=(
                    "source_jurisdiction is unresolved (None) on an incoming IRNR candidate; "
                    "resolve source-scope membership from the selected registry revision"
                ),
            ),
            rejected_source_jurisdiction=None,
        )
    return None


def _irnr_classification_issue(
    transaction_id: str,
    classification: M210IncomeClassification | None,
    *,
    declared_codes: frozenset[str],
    period: Period,
) -> IrnrIncomeLedgerAggregationIssue | None:
    """Reject a missing or undeclared M210 income classification, else ``None``."""
    if classification is None:
        return IrnrIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IrnrIncomeLedgerAggregationIssueReason.INCOMPLETE_M210_CLASSIFICATION,
            detail=tr(
                "aggregation.irnr_income_ledger.diagnostics.incomplete_m210_classification",
                default=(
                    "in-scope incoming transaction has no explicit income classification; "
                    "the IRNR projection never infers an official income type from irpf_category"
                ),
            ),
        )
    if classification.official_tipo_renta_code not in declared_codes:
        return IrnrIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IrnrIncomeLedgerAggregationIssueReason.INCOMPLETE_M210_CLASSIFICATION,
            detail=tr(
                "aggregation.irnr_income_ledger.diagnostics.tipo_renta_code_not_declared",
                tipo_renta_code=classification.official_tipo_renta_code,
                period=str(period),
                default=(
                    "official income type %{tipo_renta_code} is not declared "
                    "for the selected revision and filing period %{period}"
                ),
            ),
        )
    return None


def _classify_irnr_income_transaction(
    transaction: Transaction,
    *,
    period: Period,
    selected_official_tipo_renta_code: str,
    declared_codes: frozenset[str],
    target_casilla_id: CasillaId,
) -> IrnrIncomeObservation | IrnrIncomeLedgerAggregationIssue | None:
    """Classify one incoming transaction for the selected registry projection."""
    if transaction.business_classification is BusinessClassification.REVIEWED_EXCLUDED:
        return None
    if transaction.direction is not TransactionDirection.INCOMING:
        return None

    transaction_id = transaction.transaction_id
    jurisdiction_issue = _irnr_source_jurisdiction_issue(transaction_id, transaction.source_jurisdiction)
    if jurisdiction_issue is not None:
        return jurisdiction_issue

    classification = transaction.m210_income_classification
    classification_issue = _irnr_classification_issue(
        transaction_id,
        classification,
        declared_codes=declared_codes,
        period=period,
    )
    if classification_issue is not None:
        return classification_issue
    # The classification helper returns None only for a present, declared classification.
    if classification is None:
        msg = (
            f"transaction {transaction_id} raised no classification issue while carrying no "
            "income classification; the classification screen and the row disagree"
        )
        raise ValueError(msg)
    if classification.official_tipo_renta_code != selected_official_tipo_renta_code:
        return None

    filing_date = transaction.raw.value_date or transaction.raw.booked_date
    if not period.contains(filing_date):
        return IrnrIncomeLedgerAggregationIssue(
            transaction_id=transaction_id,
            reason=IrnrIncomeLedgerAggregationIssueReason.OUTSIDE_PERIOD,
            detail=f"filing date {filing_date} is outside the selected filing window {period!s}",
        )

    return IrnrIncomeObservation(
        transaction_id=transaction_id,
        target_casilla_id=target_casilla_id,
        official_tipo_renta_code=classification.official_tipo_renta_code,
        gross_income_amount=classification.gross_income_amount,
        applicable_rate=classification.applicable_rate,
        payer_mode=classification.payer_mode,
        payer_id=classification.payer_id,
        asset_or_right_id=classification.asset_or_right_id,
        filing_date=filing_date,
        source_jurisdiction=transaction.source_jurisdiction,
    )


def _irnr_gross_income_casilla_aggregation(
    modelo: str,
    period: Period,
    observations: Sequence[IrnrIncomeObservation],
) -> CasillaAggregation:
    return fold_casilla_observations(
        observations,
        modelo=modelo,
        period=period,
        amount_fn=lambda observation: observation.gross_income_amount,
    )


__all__ = [
    "IrnrIncomeLedgerAggregation",
    "IrnrIncomeLedgerAggregationIssue",
    "IrnrIncomeLedgerAggregationIssueReason",
    "IrnrIncomeObservation",
    "aggregate_irnr_income_ledger",
    "aggregate_irnr_income_ledger_from_repositories",
]
