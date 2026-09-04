"""Frontend-neutral read projection for the local Ledger workspace.

The provider in this module is deliberately pure.  Its callers load the
bucket-scoped catalogues and canonical Ledger query results, then hand those
facts in as one snapshot.  No repository, adapter, entrypoint, filesystem, or
network dependency is resolved here.

Only safe coordinates and aggregate state cross the frontend boundary.  The
source catalogues can contain descriptions, counterparties, monetary values,
invoice contents, and filing evidence; none is retained by, serialised from,
or exposed in the representation of :class:`LedgerWorkspaceProjectionV1`.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Final, Protocol

from pydantic import BaseModel, NonNegativeInt, model_validator

from ...core.filing_year import FilingYear
from ...core.identifier_grammar import NamespacedId
from ...core.identity import CalculationRevisionId, InvoiceId, TransactionId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.invoices.models import InvoiceCatalogue
from ...domain.invoices.service import (
    LinkInconsistency,
    ReconciliationSuggestion,
    suggest_reconciliations,
    verify_link_consistency,
)
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.ledger_filing_snapshot import LedgerFilingStalenessVerdict
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ...domain.transactions.enums import TransactionLifecycleState
from ...domain.transactions.models import TransactionCatalogue
from ..review.filter import LedgerReviewStatus
from .actions_manual import ledger_transaction_review_payload
from .models import LedgerReviewQueryResult, LedgerStatusReport, LedgerTransactionReviewPayload
from .preflight import LedgerPreflightReport

LEDGER_WORKSPACE_CONTRACT_VERSION: Final[int] = 1


class LedgerWorkspaceProjectionError(ValueError):
    """Canonical input facts cannot form one truthful workspace snapshot."""


class LedgerWorkspaceArea(StrEnum):
    """Closed set of operator-facing areas in the Ledger workspace."""

    OVERVIEW = "overview"
    ENTRIES = "entries"
    REVIEW = "review"
    IMPORT = "import"
    CLASSIFICATION = "classification"
    EVIDENCE = "evidence"
    RECONCILIATION = "reconciliation"


class LedgerWorkspaceSource(StrEnum):
    """Closed local authority that supplied an area projection.

    There is intentionally no AEAT member.  Remote evidence comparison and
    reconciliation belong to the AEAT Sync workspace, not Ledger.
    """

    LOCAL_LEDGER = "local.ledger"
    LOCAL_INVOICES = "local.invoices"
    LOCAL_DECLARATIONS = "local.declarations"


class LedgerWorkspaceAvailability(StrEnum):
    """Whether the already-admitted local area can currently be opened."""

    AVAILABLE = "available"
    LOCKED = "locked"
    STALE = "stale"
    NEVER_CAPTURED = "never_captured"
    UNAVAILABLE = "unavailable"


class LedgerWorkspaceStatus(StrEnum):
    """Source-native state, kept distinct from route availability."""

    READY = "ready"
    EMPTY = "empty"
    NEEDS_ATTENTION = "needs_attention"
    UNMEASURED = "unmeasured"


class LedgerWorkspaceAreaStateV1(BaseModel):
    """Safe availability and status for one workspace area."""

    model_config = STRICT_FROZEN_CONFIG

    area: LedgerWorkspaceArea
    sources: tuple[LedgerWorkspaceSource, ...]
    availability: LedgerWorkspaceAvailability = LedgerWorkspaceAvailability.AVAILABLE
    reason_code: NamespacedId | None = None
    status: LedgerWorkspaceStatus
    item_count: NonNegativeInt

    @model_validator(mode="after")
    def _sources_are_present_and_unique(self) -> LedgerWorkspaceAreaStateV1:
        if not self.sources:
            raise ValueError("a Ledger workspace area requires at least one local source")
        if len(set(self.sources)) != len(self.sources):
            raise ValueError("a Ledger workspace area cannot repeat a source")
        if self.availability is LedgerWorkspaceAvailability.AVAILABLE and self.reason_code is not None:
            raise ValueError("an available Ledger workspace area cannot carry an availability reason")
        if self.availability is not LedgerWorkspaceAvailability.AVAILABLE and self.reason_code is None:
            raise ValueError("a non-available Ledger workspace area requires an availability reason")
        if self.status is LedgerWorkspaceStatus.EMPTY and self.item_count != 0:
            raise ValueError("an empty Ledger workspace area cannot report items")
        return self


class LedgerWorkspaceEntryRefV1(BaseModel):
    """One local Ledger entry, as the operator's own record.

    This carries the entry's substance, not a coordinate pointing at it. The
    surface that reads this projection is reached only through an
    authenticated session over the operator's own ledger, so withholding the
    date, amount, counterparty or classification withholds nothing from an
    adversary and everything from the person doing the work: an opaque
    identifier and a status word cannot be reviewed, and review is what the
    surface is for.

    Storage and transport rules are untouched by this. Nothing here weakens
    encryption at rest, and a diagnostic or log record -- which can travel
    somewhere an authenticated session does not -- keeps its own redaction.
    """

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    review_status: str
    date: str
    amount: str
    currency: str
    direction: str
    counterparty: str
    description: str
    business_classification: str


class LedgerInvoiceReconciliationRefV1(BaseModel):
    """One suggested invoice/entry link, with the values it was suggested on.

    The booleans alone are unreviewable. `amount_match=True` asks the operator
    to confirm a link while withholding the two amounts that supposedly match,
    and `amount_match=False` is worse: it reports a disagreement without
    saying between what and what. A suggestion is a claim the operator is meant
    to ADJUDICATE, and adjudicating it means seeing both sides.

    Both values are local records the session is already authenticated for, and
    both are in scope where the suggestion is built -- they were being
    discarded, not protected.
    """

    model_config = STRICT_FROZEN_CONFIG

    invoice_id: InvoiceId
    transaction_id: TransactionId
    amount_match: bool
    counterparty_match: bool
    score: str
    invoice_total: str
    transaction_amount: str
    invoice_counterparty: str
    transaction_counterparty: str


class LedgerLinkInconsistencyRefV1(BaseModel):
    """Safe coordinate for one inconsistent local invoice/entry link."""

    model_config = STRICT_FROZEN_CONFIG

    invoice_id: str
    transaction_id: TransactionId
    direction: str


class LedgerAffectedDeclarationRefV1(BaseModel):
    """Natural declaration address whose sealed revision has Ledger drift."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    calculation_revision_id: CalculationRevisionId
    changed_count: NonNegativeInt
    removed_count: NonNegativeInt

    @model_validator(mode="after")
    def _period_matches_year(self) -> LedgerAffectedDeclarationRefV1:
        if self.period.filing_year != self.filing_year:
            raise ValueError("affected declaration period must match its filing year")
        if self.changed_count + self.removed_count == 0:
            raise ValueError("an affected declaration must carry Ledger drift")
        return self


class LedgerWorkspaceProjectionV1(BaseModel):
    """Serializable safe index over one preloaded local Ledger snapshot."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: int = LEDGER_WORKSPACE_CONTRACT_VERSION
    bucket_id: str
    areas: tuple[LedgerWorkspaceAreaStateV1, ...]
    entries: tuple[LedgerWorkspaceEntryRefV1, ...]
    review_transaction_ids: tuple[TransactionId, ...]
    invoice_reconciliations: tuple[LedgerInvoiceReconciliationRefV1, ...]
    link_inconsistencies: tuple[LedgerLinkInconsistencyRefV1, ...]
    affected_declarations: tuple[LedgerAffectedDeclarationRefV1, ...]

    @model_validator(mode="after")
    def _area_catalogue_is_total_and_ordered(self) -> LedgerWorkspaceProjectionV1:
        expected = tuple(LedgerWorkspaceArea)
        actual = tuple(item.area for item in self.areas)
        if actual != expected:
            raise ValueError("Ledger workspace areas must cover the closed catalogue in canonical order")
        return self


class LedgerFilingStalenessReaderProtocol(Protocol):
    """Pure injected reader for sealed-revision Ledger staleness."""

    def __call__(
        self,
        *,
        revisions: Mapping[str, CalculationRevision],
        catalogue: TransactionCatalogue,
    ) -> tuple[tuple[CalculationRevision, LedgerFilingStalenessVerdict], ...]:
        """Return only sealed revisions whose captured Ledger has drifted."""
        ...


class LedgerInvoiceReconciliationReaderProtocol(Protocol):
    """Pure injected reader for local invoice/entry match suggestions."""

    def __call__(
        self,
        invoices: InvoiceCatalogue,
        transactions: TransactionCatalogue,
        /,
    ) -> tuple[ReconciliationSuggestion, ...]:
        """Return deterministic local match suggestions."""
        ...


class LedgerLinkConsistencyReaderProtocol(Protocol):
    """Pure injected reader for local bidirectional-link consistency."""

    def __call__(
        self,
        invoices: InvoiceCatalogue,
        transactions: TransactionCatalogue,
        /,
    ) -> tuple[LinkInconsistency, ...]:
        """Return deterministic one-sided-link findings."""
        ...


def _canonical_filing_staleness_reader(
    *,
    revisions: Mapping[str, CalculationRevision],
    catalogue: TransactionCatalogue,
) -> tuple[tuple[CalculationRevision, LedgerFilingStalenessVerdict], ...]:
    """Reach the existing pure implementation behind this public door."""
    from ..aggregation.ledger_filing_snapshot import stale_filed_revisions

    return stale_filed_revisions(revisions=revisions, catalogue=catalogue)


def project_affected_declaration_reconciliations(
    *,
    bucket_id: str,
    revisions: Mapping[str, CalculationRevision],
    transactions: TransactionCatalogue,
    work_units: WorkUnitCatalogue,
    staleness_reader: LedgerFilingStalenessReaderProtocol = _canonical_filing_staleness_reader,
) -> tuple[LedgerAffectedDeclarationRefV1, ...]:
    """Project local Ledger drift onto natural declaration addresses.

    Every input is preloaded.  Missing or cross-bucket declaration identity is
    refused instead of silently dropping an affected revision.
    """
    rows: list[LedgerAffectedDeclarationRefV1] = []
    for revision, verdict in staleness_reader(revisions=revisions, catalogue=transactions):
        work_unit = work_units.get(revision.work_unit_id)
        if work_unit is None:
            raise LedgerWorkspaceProjectionError("affected revision has no declaration identity")
        if work_unit.bucket_id != bucket_id:
            raise LedgerWorkspaceProjectionError("affected revision belongs to a different Ledger bucket")
        rows.append(
            LedgerAffectedDeclarationRefV1(
                modelo=work_unit.modelo,
                filing_year=work_unit.filing_year,
                period=work_unit.period,
                calculation_revision_id=revision.calculation_revision_id,
                changed_count=len(verdict.changed),
                removed_count=len(verdict.removed),
            )
        )
    return tuple(
        sorted(
            rows,
            key=lambda item: (
                str(item.modelo),
                item.filing_year,
                item.period.registry_token,
                item.calculation_revision_id,
            ),
        )
    )


def project_ledger_workspace(
    *,
    summary: LedgerStatusReport,
    preflight: LedgerPreflightReport | None,
    review: LedgerReviewQueryResult,
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    revisions: Mapping[str, CalculationRevision],
    work_units: WorkUnitCatalogue,
    invoice_reconciliation_reader: LedgerInvoiceReconciliationReaderProtocol = suggest_reconciliations,
    link_consistency_reader: LedgerLinkConsistencyReaderProtocol = verify_link_consistency,
    filing_staleness_reader: LedgerFilingStalenessReaderProtocol = _canonical_filing_staleness_reader,
) -> LedgerWorkspaceProjectionV1:
    """Build one deterministic, frontend-neutral snapshot from canonical facts."""
    bucket_id = summary.bucket_id
    if review.bucket_id != bucket_id:
        raise LedgerWorkspaceProjectionError("Ledger summary and review facts name different buckets")
    if preflight is not None and preflight.bucket_id != bucket_id:
        raise LedgerWorkspaceProjectionError("Ledger summary and preflight facts name different buckets")

    _validate_workspace_facts(
        bucket_id=bucket_id,
        summary=summary,
        preflight=preflight,
        review=review,
        transactions=transactions,
        invoices=invoices,
    )

    entries = tuple(
        _entry_ref(ledger_transaction_review_payload(transaction))
        for transaction in sorted(transactions.values(), key=lambda item: item.transaction_id)
    )
    review_ids = tuple(row.id for row in review.rows)
    suggestions = tuple(
        LedgerInvoiceReconciliationRefV1(
            invoice_id=row.invoice_id,
            transaction_id=row.transaction_id,
            amount_match=row.amount_match,
            counterparty_match=row.counterparty_match,
            score=str(row.score),
            invoice_total=str(invoices.invoices[row.invoice_id].grand_total),
            transaction_amount=str(transactions.transactions[row.transaction_id].raw.amount),
            invoice_counterparty=invoices.invoices[row.invoice_id].counterparty_name or "",
            transaction_counterparty=transactions.transactions[row.transaction_id].raw.counterparty or "",
        )
        for row in invoice_reconciliation_reader(invoices, transactions)
    )
    inconsistencies = tuple(
        LedgerLinkInconsistencyRefV1(
            invoice_id=row.invoice_id,
            transaction_id=row.transaction_id,
            direction=row.direction.value,
        )
        for row in link_consistency_reader(invoices, transactions)
    )
    affected = project_affected_declaration_reconciliations(
        bucket_id=bucket_id,
        revisions=revisions,
        transactions=transactions,
        work_units=work_units,
        staleness_reader=filing_staleness_reader,
    )
    reconciliation_count = len(suggestions) + len(inconsistencies) + len(affected)
    pending = summary.pending_review_count
    readiness_issues = 0 if preflight is None else len(preflight.issues)

    areas = (
        LedgerWorkspaceAreaStateV1(
            area=LedgerWorkspaceArea.OVERVIEW,
            sources=(LedgerWorkspaceSource.LOCAL_LEDGER, LedgerWorkspaceSource.LOCAL_DECLARATIONS),
            status=(
                LedgerWorkspaceStatus.NEEDS_ATTENTION
                if pending or readiness_issues or affected
                else LedgerWorkspaceStatus.READY
            ),
            item_count=pending + readiness_issues + len(affected),
        ),
        LedgerWorkspaceAreaStateV1(
            area=LedgerWorkspaceArea.ENTRIES,
            sources=(LedgerWorkspaceSource.LOCAL_LEDGER,),
            status=LedgerWorkspaceStatus.EMPTY if not entries else LedgerWorkspaceStatus.READY,
            item_count=len(entries),
        ),
        LedgerWorkspaceAreaStateV1(
            area=LedgerWorkspaceArea.REVIEW,
            sources=(LedgerWorkspaceSource.LOCAL_LEDGER,),
            status=LedgerWorkspaceStatus.EMPTY if not review_ids else LedgerWorkspaceStatus.NEEDS_ATTENTION,
            item_count=len(review_ids),
        ),
        LedgerWorkspaceAreaStateV1(
            area=LedgerWorkspaceArea.IMPORT,
            sources=(LedgerWorkspaceSource.LOCAL_LEDGER,),
            status=LedgerWorkspaceStatus.UNMEASURED,
            item_count=0,
        ),
        LedgerWorkspaceAreaStateV1(
            area=LedgerWorkspaceArea.CLASSIFICATION,
            sources=(LedgerWorkspaceSource.LOCAL_LEDGER,),
            status=LedgerWorkspaceStatus.NEEDS_ATTENTION if pending else LedgerWorkspaceStatus.READY,
            item_count=pending,
        ),
        LedgerWorkspaceAreaStateV1(
            area=LedgerWorkspaceArea.EVIDENCE,
            sources=(LedgerWorkspaceSource.LOCAL_LEDGER, LedgerWorkspaceSource.LOCAL_INVOICES),
            status=LedgerWorkspaceStatus.UNMEASURED,
            item_count=0,
        ),
        LedgerWorkspaceAreaStateV1(
            area=LedgerWorkspaceArea.RECONCILIATION,
            sources=(
                LedgerWorkspaceSource.LOCAL_LEDGER,
                LedgerWorkspaceSource.LOCAL_INVOICES,
                LedgerWorkspaceSource.LOCAL_DECLARATIONS,
            ),
            status=(
                LedgerWorkspaceStatus.EMPTY if reconciliation_count == 0 else LedgerWorkspaceStatus.NEEDS_ATTENTION
            ),
            item_count=reconciliation_count,
        ),
    )
    return LedgerWorkspaceProjectionV1(
        bucket_id=bucket_id,
        areas=areas,
        entries=entries,
        review_transaction_ids=review_ids,
        invoice_reconciliations=suggestions,
        link_inconsistencies=inconsistencies,
        affected_declarations=affected,
    )


def _entry_ref(payload: LedgerTransactionReviewPayload) -> LedgerWorkspaceEntryRefV1:
    """Carry the entry's own facts into the projection, not a pointer to them."""
    return LedgerWorkspaceEntryRefV1(
        transaction_id=payload.transaction_id,
        review_status=payload.review_status,
        date=payload.date,
        amount=payload.amount,
        currency=payload.currency,
        direction=payload.direction,
        counterparty=payload.counterparty,
        description=payload.description,
        business_classification=payload.business_classification,
    )


def _validate_workspace_facts(
    *,
    bucket_id: str,
    summary: LedgerStatusReport,
    preflight: LedgerPreflightReport | None,
    review: LedgerReviewQueryResult,
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
) -> None:
    """Refuse cross-source contradictions before any downstream reader runs."""
    foreign_invoice_ids = tuple(
        sorted(invoice.invoice_id for invoice in invoices.values() if invoice.bucket_id != bucket_id)
    )
    if foreign_invoice_ids:
        raise LedgerWorkspaceProjectionError("invoice catalogue contains a foreign Ledger bucket")

    transaction_rows = tuple(transactions.values())
    expected_counts = {
        "total_count": len(transaction_rows),
        "active_count": sum(
            transaction.lifecycle_state is TransactionLifecycleState.ACTIVE for transaction in transaction_rows
        ),
        "archived_count": sum(
            transaction.lifecycle_state is TransactionLifecycleState.ARCHIVED for transaction in transaction_rows
        ),
        "stashed_count": sum(
            transaction.lifecycle_state is TransactionLifecycleState.STASHED for transaction in transaction_rows
        ),
        "split_count": sum(
            transaction.lifecycle_state is TransactionLifecycleState.SPLIT for transaction in transaction_rows
        ),
    }
    active_statuses = tuple(
        ledger_transaction_review_payload(transaction).review_status
        for transaction in transaction_rows
        if transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
    )
    expected_counts.update(
        {
            "pending_review_count": active_statuses.count(LedgerReviewStatus.PENDING),
            "reviewed_count": active_statuses.count(LedgerReviewStatus.REVIEWED),
            "skipped_count": active_statuses.count(LedgerReviewStatus.SKIPPED),
        }
    )
    contradictory_counts = tuple(
        field_name for field_name, expected in expected_counts.items() if getattr(summary, field_name) != expected
    )
    if contradictory_counts:
        raise LedgerWorkspaceProjectionError("Ledger summary counts contradict the supplied transaction catalogue")

    if preflight is None:
        if (
            summary.period is not None
            or summary.checked_transaction_count != 0
            or summary.readiness_issue_count != 0
            or summary.ready is not None
        ):
            raise LedgerWorkspaceProjectionError("Ledger summary claims preflight facts that were not supplied")
    elif (
        summary.period != preflight.period
        or summary.checked_transaction_count != preflight.checked_transaction_count
        or summary.readiness_issue_count != len(preflight.issues)
        or summary.ready is not preflight.ready
    ):
        raise LedgerWorkspaceProjectionError("Ledger summary and preflight counts contradict each other")

    transaction_by_id = {transaction.transaction_id: transaction for transaction in transaction_rows}
    review_ids = tuple(row.id for row in review.rows)
    if len(set(review_ids)) != len(review_ids):
        raise LedgerWorkspaceProjectionError("Ledger review facts contain duplicate transaction identities")
    if any(transaction_id not in transaction_by_id for transaction_id in review_ids):
        raise LedgerWorkspaceProjectionError("Ledger review facts name an absent transaction")
    if any(
        row.status != ledger_transaction_review_payload(transaction_by_id[row.id]).review_status for row in review.rows
    ):
        raise LedgerWorkspaceProjectionError("Ledger review status contradicts the supplied transaction catalogue")
    if preflight is not None and any(
        issue.transaction_id != "__period__" and issue.transaction_id not in transaction_by_id
        for issue in preflight.issues
    ):
        raise LedgerWorkspaceProjectionError("Ledger preflight facts name an absent transaction")


__all__ = [
    "LEDGER_WORKSPACE_CONTRACT_VERSION",
    "LedgerAffectedDeclarationRefV1",
    "LedgerFilingStalenessReaderProtocol",
    "LedgerInvoiceReconciliationReaderProtocol",
    "LedgerInvoiceReconciliationRefV1",
    "LedgerLinkConsistencyReaderProtocol",
    "LedgerLinkInconsistencyRefV1",
    "LedgerWorkspaceArea",
    "LedgerWorkspaceAreaStateV1",
    "LedgerWorkspaceAvailability",
    "LedgerWorkspaceEntryRefV1",
    "LedgerWorkspaceProjectionError",
    "LedgerWorkspaceProjectionV1",
    "LedgerWorkspaceSource",
    "LedgerWorkspaceStatus",
    "project_affected_declaration_reconciliations",
    "project_ledger_workspace",
]
