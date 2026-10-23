"""An in-memory ledger behind every entry door, answering with the operations' own result models.

Each door records the typed request it received and answers it from a list of
synthetic entries, building the registered operation's real projection, so the
projections' own validators (page windows, lineage anchors, verdicts against
findings) check every answer. Values are synthetic.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from .....application.bucket_event_projection import BucketEventProjection
from .....application.export.tabular import ExportSerializationFormat
from .....application.ledger.check_operation import (
    LedgerCheckIssueProjection,
    LedgerCheckProjection,
    LedgerCheckRequest,
)
from .....application.ledger.export_operation import LedgerExportProjection, LedgerExportRequest
from .....application.ledger.history_operation import (
    LedgerHistoryProjection,
    LedgerHistoryRequest,
    LedgerHistoryTypedEvent,
    LedgerHistoryTypedProjection,
)
from .....application.ledger.ledger_add_contracts import LedgerAddOperationResult, LedgerAddRequest
from .....application.ledger.lifecycle_contracts import (
    LedgerLifecycleMutationProjection,
    LedgerLifecycleMutationRequest,
    LedgerLifecycleOperationId,
    LedgerLifecycleOperationResult,
    LedgerLifecycleReplacedStateProjection,
    LedgerLifecycleValidationProjection,
)
from .....application.ledger.list_operation import LedgerListProjection, LedgerListRequest
from .....application.ledger.merge_operation import LedgerMergeOperationResult, LedgerMergeRequest
from .....application.ledger.preflight import LedgerPreflightIssueReason
from .....application.ledger.preflight_operation import LedgerPreflightProjection, LedgerPreflightRequest
from .....application.ledger.remove_operation import (
    LedgerRemoveOperationResult,
    LedgerRemoveReportProjection,
    LedgerRemoveRequest,
)
from .....application.ledger.reset_operation import (
    LedgerResetOperationResult,
    LedgerResetReportProjection,
    LedgerResetRequest,
)
from .....application.ledger.status_operation import LedgerStatusProjection, LedgerStatusRequest
from .....application.ledger.track_operation import LedgerTrackProjection, LedgerTrackRequest
from .....application.ledger.tracking_projection import LedgerTrackingProjection
from .....application.ledger.transaction_projection import (
    LedgerTransactionProjection,
    LedgerTransactionReviewProjection,
)
from .....application.review.filter import LedgerReviewStatus
from .....core.errors.hierarchy import CadrumoError, RecordedRegisteredError
from .....core.operations import OperationEffect
from .....domain.buckets.event import BucketEventObjectType, BucketEventType
from .....domain.buckets.event_repository import build_bucket_event
from .....domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ...account import AccountSessionExpiredError
from ...operations.outcome import OperationOutcomeUnknownError
from ..controller import LedgerWorkspaceController
from ..entries_doors import LedgerEntriesDoorsV1
from ..workspace_injection import LedgerWorkspaceInjection
from .workspace_fixtures import ledger_context, ledger_projection, ledger_review_action

ENTRIES_PROFILE_ID = UUID("7dd00000-0000-4000-8000-0000000000dd")
#: An amount the in-memory worker refuses the way ``ledger.add`` records a validation refusal.
REFUSED_ADD_AMOUNT = "13.13"
ENTRIES_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"
ENTRIES_REFUSAL_KEY = "errors.refused.refused_cli_validation_boundary"
_NOW = datetime(2026, 4, 2, 9, 30, tzinfo=UTC)
_LIFECYCLE_STATES: dict[LedgerLifecycleOperationId, TransactionLifecycleState] = {
    "ledger.archive": TransactionLifecycleState.ARCHIVED,
    "ledger.stash": TransactionLifecycleState.STASHED,
    "ledger.restore": TransactionLifecycleState.ACTIVE,
    "ledger.exclude": TransactionLifecycleState.ACTIVE,
}


def entry_id(index: int) -> str:
    """A synthetic 64-hex transaction identity."""
    return f"{index + 1:064x}"


def synthetic_entry(
    index: int,
    *,
    booked_date: str | None = None,
    amount: str = "100.00",
    direction: str = "OUTGOING",
    description: str | None = None,
    lifecycle_state: str = "ACTIVE",
    classification: str = "BUSINESS",
) -> LedgerTransactionReviewProjection:
    """One synthetic entry in the shape ``ledger.list`` returns."""
    booked = booked_date or f"2026-{index % 12 + 1:02d}-{index % 28 + 1:02d}"
    transaction = LedgerTransactionProjection(
        transaction_id=entry_id(index),
        date=booked,
        booked_date=booked,
        value_date=None,
        amount=amount,
        currency="EUR",
        direction=direction,
        counterparty="Proveedor Sintético SL",
        description=description or f"Synthetic entry {index:04d}",
        business_classification=classification,
        business_pct=None,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        iva_category=None,
        counterparty_country=None,
        counterparty_identification_state=None,
        irpf_category=None,
        m210_income_classification=None,
        usage_ratio_id=None,
        prorrata_reference=None,
        purchase_invoice_evidence_id=None,
        invoice_id=None,
        attachment_ids=(),
        notes="",
        lifecycle_state=lifecycle_state,
        classified_by="manual",
        classified_at=None,
        classification_reason="",
        classification_confidence=None,
        source_jurisdiction=None,
        value_in_eur=None,
        fx_rate=None,
        created_at="2026-01-01T00:00:00+00:00",
        modified_at="2026-01-01T00:00:00+00:00",
    )
    status = (
        LedgerReviewStatus.EXCLUDED
        if classification == BusinessClassification.REVIEWED_EXCLUDED.value
        else LedgerReviewStatus.REVIEWED
    )
    return LedgerTransactionReviewProjection(transaction=transaction, review_status=status, group_label=None)


class _Door[RequestT, ResultT]:
    """One door over the shared memory ledger, recording each request it is given."""

    def __init__(self, ledger: MemoryEntriesLedger, name: str, answer: Callable[[RequestT], ResultT]) -> None:
        self._ledger = ledger
        self._name = name
        self._answer = answer

    @property
    def profile_id(self) -> UUID:
        return ENTRIES_PROFILE_ID

    async def __call__(self, request: RequestT) -> ResultT:
        self._ledger.requests.append((self._name, request))
        self._ledger.raise_if_configured(self._name)
        return self._answer(request)


class _LifecycleDoor(_Door[LedgerLifecycleMutationRequest, LedgerLifecycleOperationResult]):
    def __init__(self, ledger: MemoryEntriesLedger, operation_id: LedgerLifecycleOperationId) -> None:
        super().__init__(ledger, operation_id, lambda request: ledger.lifecycle(operation_id, request))
        self._operation_id: LedgerLifecycleOperationId = operation_id

    @property
    def operation_id(self) -> LedgerLifecycleOperationId:
        return self._operation_id


class MemoryEntriesLedger:
    """Synthetic entries and every entry door over them."""

    def __init__(self, entries: tuple[LedgerTransactionReviewProjection, ...] = ()) -> None:
        """Start with ``entries``; nothing has been requested."""
        self.entries: list[LedgerTransactionReviewProjection] = list(entries)
        self.requests: list[tuple[str, object]] = []
        self.refuse: dict[str, CadrumoError] = {}
        """Door name to the error that door raises, as a recorded refusal would surface."""
        self.validation_refusals: set[str] = set()
        """Lifecycle operations that answer with the operation's own validation refusal."""
        self.export_effect: OperationEffect = OperationEffect.UPDATED

    @classmethod
    def with_entries(cls, count: int) -> MemoryEntriesLedger:
        """A ledger of ``count`` synthetic entries."""
        return cls(tuple(synthetic_entry(index) for index in range(count)))

    def raise_if_configured(self, name: str) -> None:
        """Raise the error configured for one door, if any."""
        error = self.refuse.get(name)
        if error is not None:
            raise error

    def refuse_with_registered_error(self, name: str) -> None:
        """Make one door raise a recorded registered refusal."""
        self.refuse[name] = RecordedRegisteredError(ENTRIES_REFUSAL_CODE, translated_message=ENTRIES_REFUSAL_KEY)

    def expire(self, name: str) -> None:
        """Make one door report the admitted session as lost."""
        self.refuse[name] = AccountSessionExpiredError()

    def requested(self, name: str) -> list[object]:
        """Every request one door received, in order."""
        return [request for door, request in self.requests if door == name]

    def doors(self) -> LedgerEntriesDoorsV1:
        """Every entry door, bound to this ledger."""
        return LedgerEntriesDoorsV1(
            list_entries=_Door(self, "list", self.list_page),
            add=_Door(self, "add", self.add),
            remove=_Door(self, "remove", self.remove),
            archive=_LifecycleDoor(self, "ledger.archive"),
            stash=_LifecycleDoor(self, "ledger.stash"),
            restore=_LifecycleDoor(self, "ledger.restore"),
            exclude=_LifecycleDoor(self, "ledger.exclude"),
            merge=_Door(self, "merge", self.merge),
            history=_Door(self, "history", self.history),
            history_typed=_Door(self, "history_typed", self.history_typed),
            track=_Door(self, "track", self.track),
            status=_Door(self, "status", self.status),
            check=_Door(self, "check", self.check),
            preflight=_Door(self, "preflight", self.preflight),
            reset=_Door(self, "reset", self.reset),
            export=_Door(self, "export", self.export),
        )

    def _find(self, prefix: str) -> int:
        return next(
            index for index, row in enumerate(self.entries) if row.transaction.transaction_id.startswith(prefix)
        )

    def list_page(self, request: LedgerListRequest) -> LedgerListProjection:
        """Answer one page; this memory ledger applies paging, not the filter grammar."""
        end = None if request.limit is None else request.offset + request.limit
        rows = tuple(self.entries[request.offset : end])
        total = len(self.entries)
        return LedgerListProjection(
            profile_id=request.profile_id,
            rows=rows,
            total=total,
            truncated=request.offset > 0 or (request.limit is not None and request.offset + request.limit < total),
            offset=request.offset,
            limit=request.limit,
            by_group=request.by_group,
        )

    def add(self, request: LedgerAddRequest) -> LedgerAddOperationResult:
        """Record an entry, or refuse the configured amount as the worker records a refusal."""
        if request.amount == REFUSED_ADD_AMOUNT:
            return LedgerAddOperationResult.validation_refusal(
                request.profile_id, code="invalid_command", messages=("amount refused by the ledger",)
            )
        row = synthetic_entry(
            len(self.entries),
            booked_date=request.booked_date,
            amount=request.amount,
            direction=request.direction,
            description=request.description,
            classification=request.business_classification,
        )
        self.entries.append(row)
        return LedgerAddOperationResult.created(
            request.profile_id,
            transaction=row.transaction,
            review_status=row.review_status,
            bucket_event_ids=("e" * 64,),
        )

    def lifecycle(
        self, operation_id: LedgerLifecycleOperationId, request: LedgerLifecycleMutationRequest
    ) -> LedgerLifecycleOperationResult:
        """Move one entry to the operation's lifecycle state, or refuse it as configured."""
        if operation_id in self.validation_refusals:
            return LedgerLifecycleOperationResult(
                outcome="validation_error",
                profile_id=request.profile_id,
                operation_id=operation_id,
                validation=LedgerLifecycleValidationProjection(messages=("entry is cited by a filed declaration",)),
            )
        index = self._find(request.transaction_id)
        before = self.entries[index]
        classification = (
            BusinessClassification.REVIEWED_EXCLUDED.value
            if operation_id == "ledger.exclude"
            else before.transaction.business_classification
        )
        after = synthetic_entry(
            index,
            booked_date=before.transaction.booked_date,
            amount=before.transaction.amount,
            description=before.transaction.description,
            lifecycle_state=_LIFECYCLE_STATES[operation_id].value,
            classification=classification,
        )
        self.entries[index] = after
        return LedgerLifecycleOperationResult(
            outcome="updated",
            profile_id=request.profile_id,
            operation_id=operation_id,
            result=LedgerLifecycleMutationProjection(
                profile_id=request.profile_id,
                operation_id=operation_id,
                transaction=after.transaction,
                review_status=after.review_status,
                bucket_event_ids=("f" * 64,),
                replaced=LedgerLifecycleReplacedStateProjection(
                    lifecycle_state=TransactionLifecycleState(before.transaction.lifecycle_state),
                    business_classification=BusinessClassification(before.transaction.business_classification),
                    business_pct=None,
                    classified_by="manual",
                    reversed_by=("ledger.restore",),
                ),
            ),
        )

    def remove(self, request: LedgerRemoveRequest) -> LedgerRemoveOperationResult:
        """Preview or remove one entry."""
        index = self._find(request.transaction_id)
        transaction_id = self.entries[index].transaction.transaction_id
        if not request.dry_run:
            del self.entries[index]
        return LedgerRemoveOperationResult(
            profile_id=request.profile_id,
            report=LedgerRemoveReportProjection(
                bucket_id=str(request.profile_id),
                transaction_id=transaction_id,
                removed=not request.dry_run,
                dry_run=request.dry_run,
                actor="operator",
                reason=request.reason,
                bucket_event_ids=() if request.dry_run else ("d" * 64,),
            ),
        )

    def merge(self, request: LedgerMergeRequest) -> LedgerMergeOperationResult:
        """Merge the marked children into one new entry."""
        children = tuple(
            sorted(self.entries[self._find(prefix)].transaction.transaction_id for prefix in request.child_ids)
        )
        merged = synthetic_entry(len(self.entries) + 1000)
        self.entries = [row for row in self.entries if row.transaction.transaction_id not in children]
        self.entries.append(merged)
        return LedgerMergeOperationResult(
            profile_id=request.profile_id,
            split_group_id="a" * 64,
            parent_transaction_id="c" * 64,
            merged_transaction_id=merged.transaction.transaction_id,
            source_child_ids=children,
            bucket_event_id="b" * 64,
        )

    def _events(self, transaction_id: str) -> tuple[BucketEventProjection, ...]:
        created = build_bucket_event(
            bucket_id=str(ENTRIES_PROFILE_ID),
            event_type=BucketEventType.LEDGER_TRANSACTION_CREATED,
            occurred_at=_NOW,
            actor="operator",
            object_type=BucketEventObjectType.LEDGER_TRANSACTION,
            object_id=transaction_id,
            payload={"source_command": "aeat app ledger add", "amount": "100.00", "currency": "EUR"},
            payload_version=1,
        )
        archived = build_bucket_event(
            bucket_id=str(ENTRIES_PROFILE_ID),
            event_type=BucketEventType.LEDGER_TRANSACTION_ARCHIVED,
            occurred_at=_NOW.replace(hour=10),
            actor="operator",
            object_type=BucketEventObjectType.LEDGER_TRANSACTION,
            object_id=transaction_id,
            payload={"reason": "duplicate", "model_reason": "quoted from the document"},
            payload_version=1,
        )
        return (BucketEventProjection.from_event(created), BucketEventProjection.from_event(archived))

    def history(self, request: LedgerHistoryRequest) -> LedgerHistoryProjection:
        """Answer the full event record of one entry."""
        transaction_id = self.entries[self._find(request.transaction_prefix)].transaction.transaction_id
        events = self._events(transaction_id)
        return LedgerHistoryProjection(
            profile_id=request.profile_id,
            transaction_prefix=request.transaction_prefix,
            include_split_siblings=request.include_split_siblings,
            transaction_id=transaction_id,
            object_ids=(transaction_id,),
            events=events,
            event_count=len(events),
        )

    def history_typed(self, request: LedgerHistoryRequest) -> LedgerHistoryTypedProjection:
        """Answer the typed history of one entry from the same events."""
        transaction_id = self.entries[self._find(request.transaction_prefix)].transaction.transaction_id
        events = tuple(LedgerHistoryTypedEvent.from_event(event.to_event()) for event in self._events(transaction_id))
        return LedgerHistoryTypedProjection(
            profile_id=request.profile_id,
            transaction_prefix=request.transaction_prefix,
            include_split_siblings=request.include_split_siblings,
            transaction_id=transaction_id,
            object_ids=(transaction_id,),
            events=events,
            event_count=len(events),
        )

    def track(self, request: LedgerTrackRequest) -> LedgerTrackProjection:
        """Answer one manual entry's lineage, used by no finalized declaration."""
        row = self.entries[self._find(request.transaction_prefix)]
        return LedgerTrackProjection(
            profile_id=request.profile_id,
            transaction_prefix=request.transaction_prefix,
            transaction=row.transaction,
            tracking=LedgerTrackingProjection(
                transaction_id=row.transaction.transaction_id,
                created_event_id="e" * 64,
                evidence_provenance=(),
                edit_lineage=(),
                lifecycle_state=row.transaction.lifecycle_state,
                lifecycle_lineage=(),
            ),
            imported_provenance=None,
            participated_in=None,
        )

    def status(self, request: LedgerStatusRequest) -> LedgerStatusProjection:
        """Answer counts with readiness measured only for a chosen period."""
        return LedgerStatusProjection(
            profile_id=request.profile_id,
            period=request.period,
            business_income_total="1000.00",
            business_expense_total="400.00",
            business_net_total="600.00",
            total_count=len(self.entries),
            active_count=len(self.entries),
            archived_count=0,
            stashed_count=0,
            split_count=0,
            pending_review_count=0,
            reviewed_count=len(self.entries),
            skipped_count=0,
            checked_transaction_count=len(self.entries) if request.period is not None else 0,
            readiness_issue_count=0,
            unconverted_currency_count=0,
            ready=None if request.period is None else True,
            readiness_issues=(),
            stale_filings=(),
        )

    def check(self, request: LedgerCheckRequest) -> LedgerCheckProjection:
        """Answer one missing-category finding."""
        issue = LedgerCheckIssueProjection(
            transaction_id=entry_id(0),
            reason=LedgerPreflightIssueReason.MISSING_CATEGORY,
            detail="Category is missing.",
        )
        return LedgerCheckProjection(
            profile_id=request.profile_id,
            period=request.period,
            bucket_id=str(request.profile_id),
            periods=() if request.period is None else (str(request.period.to_period()),),
            checked_transaction_count=len(self.entries),
            issues=(issue,),
            link_inconsistencies=(),
            ready=False,
        )

    def preflight(self, request: LedgerPreflightRequest) -> LedgerPreflightProjection:
        """Answer a period with nothing missing."""
        return LedgerPreflightProjection(
            profile_id=request.profile_id,
            period=request.period,
            bucket_id=str(request.profile_id),
            checked_transaction_count=len(self.entries),
            issues=(),
            ready=True,
        )

    def reset(self, request: LedgerResetRequest) -> LedgerResetOperationResult:
        """Preview or reset the whole memory ledger."""
        removed = tuple(row.transaction.transaction_id for row in self.entries)
        if not request.dry_run:
            self.entries.clear()
        return LedgerResetOperationResult(
            profile_id=request.profile_id,
            report=LedgerResetReportProjection(
                bucket_id=str(request.profile_id),
                removed_transaction_ids=removed,
                reset=not request.dry_run,
                dry_run=request.dry_run,
                actor="operator",
                reason=request.reason.strip(),
                bucket_event_ids=() if request.dry_run else ("d" * 64,),
            ),
        )

    def export(self, request: LedgerExportRequest) -> LedgerExportProjection:
        """Report a complete export, or raise the configured partial or unknown effect as the door does."""
        if self.export_effect is not OperationEffect.UPDATED:
            raise OperationOutcomeUnknownError(
                operation_id="e" * 64,
                effect=self.export_effect,
                reason=RecordedRegisteredError(ENTRIES_REFUSAL_CODE, translated_message=ENTRIES_REFUSAL_KEY),
            )
        return LedgerExportProjection(
            profile_id=request.profile_id,
            bucket_id=str(request.profile_id),
            export_id="9" * 64,
            export_format=request.export_format,
            media_type="text/csv"
            if request.export_format is ExportSerializationFormat.CSV
            else "application/octet-stream",
            filename_extension=f".{request.export_format.value}",
            row_count=0,
            byte_size=128,
            sha256="8" * 64,
            fieldnames=("transaction_id",),
            rows=(),
            bucket_event_ids=("7" * 64,),
            output_path=request.output_path,
        )


def entries_controller() -> LedgerWorkspaceController:
    """A plain workspace the entry tools open over."""
    return LedgerWorkspaceController(
        ledger_context(), ledger_projection(), LedgerWorkspaceInjection(review_action=ledger_review_action())
    )


LifecycleName = Literal["ledger.archive", "ledger.stash", "ledger.restore", "ledger.exclude"]


def lifecycle_requests(ledger: MemoryEntriesLedger, name: LifecycleName) -> list[LedgerLifecycleMutationRequest]:
    """Every lifecycle request one door received."""
    return [cast(LedgerLifecycleMutationRequest, request) for request in ledger.requested(name)]


__all__ = [
    "ENTRIES_PROFILE_ID",
    "ENTRIES_REFUSAL_CODE",
    "ENTRIES_REFUSAL_KEY",
    "REFUSED_ADD_AMOUNT",
    "MemoryEntriesLedger",
    "entries_controller",
    "entry_id",
    "lifecycle_requests",
    "synthetic_entry",
]
