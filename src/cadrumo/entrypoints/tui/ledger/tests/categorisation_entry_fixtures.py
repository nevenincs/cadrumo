"""An in-memory ledger behind the entry-scoped categorisation doors.

The ledger holds synthetic entries and answers the list, bulk classification,
IVA derivation, allocation, split and participation requests with each
operation's own public result model, so the screens meet the same request
validation and result invariants the registered operations publish.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal
from typing import cast

from .....application.ledger.allocate_operation import LedgerAllocateOperationResult, LedgerAllocateRequest
from .....application.ledger.bulk_classify_operation import LedgerBulkClassifyProjection, LedgerBulkClassifyRequest
from .....application.ledger.classify_result_contracts import LedgerClassifyOperationResult
from .....application.ledger.list_operation import LedgerListProjection, LedgerListRequest
from .....application.ledger.models import BulkClassifyFailure, BulkClassifyResult
from .....application.ledger.operator_iva_contracts import LedgerOperatorIvaRequest, LedgerOperatorIvaResult
from .....application.ledger.participation_operation import LedgerParticipationProjection, LedgerParticipationRequest
from .....application.ledger.participation_rebuild_operation import (
    LedgerParticipationRebuildProjection,
    LedgerParticipationRebuildRequest,
)
from .....application.ledger.split_operation import LedgerSplitOperationResult, LedgerSplitRequest
from .....application.ledger.tracking_projection import (
    LedgerParticipationProjection as LedgerParticipationEntryProjection,
)
from .....application.ledger.transaction_projection import (
    LedgerTransactionProjection,
    LedgerTransactionReviewProjection,
)
from .....application.operations.public_period import PublicPeriod
from .....application.review.filter import LedgerReviewStatus
from .....core.identity.transaction_ids import TransactionId
from .....domain.transactions.enums import BusinessClassification
from .categorisation_fixtures import CATEGORISATION_PROFILE_ID, synthetic_id

_STAMP = "2026-03-01T09:00:00+00:00"


def synthetic_transaction(
    transaction_id: TransactionId,
    *,
    description: str,
    amount: str = "100.00",
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
    business_pct: str | None = None,
    category_id: str | None = None,
    iva_category: str | None = None,
) -> LedgerTransactionProjection:
    """One synthetic ledger entry as the list operation projects it."""
    return LedgerTransactionProjection(
        transaction_id=transaction_id,
        date="2026-03-14",
        booked_date="2026-03-14",
        value_date=None,
        amount=amount,
        currency="EUR",
        direction="outgoing",
        counterparty="Suministros Delta SL",
        description=description,
        business_classification=classification.value,
        business_pct=business_pct,
        category_id=category_id,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        iva_category=iva_category,
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
        lifecycle_state="ACTIVE",
        classified_by="operator",
        classified_at=None,
        classification_reason="",
        classification_confidence=None,
        source_jurisdiction=None,
        value_in_eur=None,
        fx_rate=None,
        created_at=_STAMP,
        modified_at=_STAMP,
    )


def _event_id(index: int) -> str:
    return f"{index:064x}"


@dataclass
class MemoryLedger:
    """Synthetic entries every entry-scoped door reads and changes."""

    entries: dict[TransactionId, LedgerTransactionProjection] = field(default_factory=dict)
    participations: tuple[LedgerParticipationEntryProjection, ...] = ()
    events: int = 0

    @classmethod
    def with_entries(cls, count: int, *, classification: BusinessClassification | None = None) -> MemoryLedger:
        """A ledger of ``count`` synthetic entries, alternating unclassified and business."""
        entries = {}
        for index in range(1, count + 1):
            transaction_id = synthetic_id(index)
            chosen = classification or (
                BusinessClassification.BUSINESS if index % 2 == 0 else BusinessClassification.NOT_YET_PROCESSED
            )
            entries[transaction_id] = synthetic_transaction(
                transaction_id, description=f"Compra sintética {index:05d}", classification=chosen
            )
        return cls(entries=entries)

    def _event(self) -> str:
        self.events += 1
        return _event_id(self.events)

    def _resolve(self, prefix: str) -> TransactionId:
        matches = [key for key in self.entries if key.startswith(prefix)]
        if len(matches) != 1:
            raise AssertionError("the synthetic ledger resolves each request to exactly one entry")
        return matches[0]

    def _status(self, transaction: LedgerTransactionProjection) -> LedgerReviewStatus:
        if transaction.business_classification == BusinessClassification.REVIEWED_EXCLUDED.value:
            return LedgerReviewStatus.EXCLUDED
        if transaction.business_classification == BusinessClassification.NOT_YET_PROCESSED.value:
            return LedgerReviewStatus.PENDING
        return LedgerReviewStatus.REVIEWED

    def list_page(self, request: LedgerListRequest) -> LedgerListProjection:
        spec = request.filter_spec()
        rows = [
            transaction
            for transaction in sorted(self.entries.values(), key=lambda item: item.transaction_id)
            if (spec.status is None or self._status(transaction) is spec.status)
            and (spec.text is None or spec.text.lower() in transaction.description.lower())
        ]
        window = (
            rows[request.offset :] if request.limit is None else rows[request.offset : request.offset + request.limit]
        )
        return LedgerListProjection(
            profile_id=request.profile_id,
            rows=tuple(
                LedgerTransactionReviewProjection(transaction=row, review_status=self._status(row), group_label=None)
                for row in window
            ),
            total=len(rows),
            truncated=request.offset > 0 or (request.limit is not None and request.offset + request.limit < len(rows)),
            offset=request.offset,
            limit=request.limit,
            by_group=request.by_group,
        )

    def bulk_classify(self, request: LedgerBulkClassifyRequest) -> LedgerBulkClassifyProjection:
        reader = csv.DictReader(io.StringIO(request.csv_text))
        applied = 0
        events: list[str] = []
        failures: list[BulkClassifyFailure] = []
        total = 0
        for index, row in enumerate(reader):
            total += 1
            transaction_id = cast("TransactionId", row["transaction_id"])
            current = self.entries.get(transaction_id)
            if current is None:
                failures.append(
                    BulkClassifyFailure(row_index=index, transaction_id=transaction_id, reason="unknown entry")
                )
                continue
            update: dict[str, object] = {"business_classification": row["classification"]}
            if "business_pct" in row:
                update["business_pct"] = row["business_pct"]
            if "category_id" in row:
                update["category_id"] = row["category_id"]
            self.entries[transaction_id] = current.model_copy(update=update)
            applied += 1
            events.append(self._event())
        return LedgerBulkClassifyProjection(
            profile_id=request.profile_id,
            outcome="classified",
            result=BulkClassifyResult(
                total=total, applied=applied, skipped=0, failures=tuple(failures), bucket_event_ids=tuple(events)
            ),
        )

    def _classified(self, transaction: LedgerTransactionProjection) -> LedgerClassifyOperationResult:
        return LedgerClassifyOperationResult(
            outcome="classified",
            profile_id=CATEGORISATION_PROFILE_ID,
            transaction=transaction,
            review_status=self._status(transaction),
            bucket_event_ids=(self._event(),),
        )

    def derive_iva(self, request: LedgerOperatorIvaRequest) -> LedgerOperatorIvaResult:
        transaction_id = self._resolve(request.transaction_id)
        if request.iva_category == "UNKNOWN":
            return LedgerOperatorIvaResult(
                profile_id=request.profile_id,
                outcome="validation_error",
                transaction_id=request.transaction_id,
                iva_category=request.iva_category,
                derivable=False,
                validation_messages=("IVA category is not declared by the pinned authority",),
            )
        current = self.entries[transaction_id]
        updated = current.model_copy(update={"iva_category": request.iva_category, "iva_rate": "0.21"})
        self.entries[transaction_id] = updated
        return LedgerOperatorIvaResult(
            profile_id=request.profile_id,
            transaction_id=transaction_id,
            iva_category=request.iva_category,
            derivable=True,
            iva_rate="0.21",
            taxable_base="82.64",
            iva_amount="17.36",
            note="derived from the gross amount",
            classification=self._classified(updated),
        )

    def allocate(self, request: LedgerAllocateRequest) -> LedgerAllocateOperationResult:
        transaction_id = self._resolve(request.transaction_id)
        share = Decimal(request.business_pct)
        classification = (
            BusinessClassification.BUSINESS
            if share == 1
            else BusinessClassification.PERSONAL
            if share == 0
            else BusinessClassification.MIXED
        )
        updated = self.entries[transaction_id].model_copy(
            update={
                "business_classification": classification.value,
                "business_pct": request.business_pct if classification is BusinessClassification.MIXED else None,
                "category_id": request.category_id,
            }
        )
        self.entries[transaction_id] = updated
        return LedgerAllocateOperationResult(
            profile_id=request.profile_id,
            transaction=updated,
            review_status=self._status(updated),
            bucket_event_ids=(self._event(),),
        )

    def split(self, request: LedgerSplitRequest) -> LedgerSplitOperationResult:
        transaction_id = self._resolve(request.transaction_id)
        parent = self.entries[transaction_id]
        if sum(Decimal(child.amount) for child in request.children) != Decimal(parent.amount):
            raise AssertionError("the screen sent a split whose children do not add up to the entry")
        children: list[TransactionId] = []
        for offset, child in enumerate(request.children, start=1):
            child_id = synthetic_id(10_000 + len(self.entries) + offset)
            self.entries[child_id] = synthetic_transaction(child_id, description=child.description, amount=child.amount)
            children.append(child_id)
        self.entries[transaction_id] = parent.model_copy(update={"lifecycle_state": "SPLIT"})
        return LedgerSplitOperationResult(
            profile_id=request.profile_id,
            parent_transaction_id=transaction_id,
            split_group_id=self._event(),
            child_transaction_ids=tuple(children),
            bucket_event_id=self._event(),
            parent_business_classification=BusinessClassification(parent.business_classification),
            child_business_classification=BusinessClassification.NOT_YET_PROCESSED,
            remerged_by=("ledger.merge",),
        )

    def participation(self, request: LedgerParticipationRequest) -> LedgerParticipationProjection:
        return LedgerParticipationProjection(
            profile_id=request.profile_id,
            transaction_prefix=request.transaction_prefix,
            transaction_id=self._resolve(request.transaction_prefix),
            participations=self.participations,
        )

    def rebuild(self, request: LedgerParticipationRebuildRequest) -> LedgerParticipationRebuildProjection:
        return LedgerParticipationRebuildProjection(
            profile_id=request.profile_id,
            transaction_count=len(self.entries),
            participation_count=len(self.participations),
            revision_count=len(self.participations),
            stale_removed_count=0,
        )


def synthetic_participation(index: int, *, modelo: str = "303") -> LedgerParticipationEntryProjection:
    """One finalised declaration revision an entry took part in."""
    return LedgerParticipationEntryProjection(
        calculation_revision_id=f"{index:064x}",
        work_unit_id=f"{index + 100:064x}",
        modelo=modelo,
        filing_year=2026,
        period=PublicPeriod(filing_year=2026, code="1T"),
        revision_state="PRESENTADO",
        filing_record_id=None,
        justificante_reference=None,
    )


__all__ = ["MemoryLedger", "synthetic_participation", "synthetic_transaction"]
