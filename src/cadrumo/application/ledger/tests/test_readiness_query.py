"""Readiness issues carry the facts that explain them, and never vanish.

Two things are asserted here. First, that an issue arrives with the row's
classification and tax facts attached — an issue naming a transaction and a
reason tells an operator a row is not ready without telling them what to fix.

Second, and the reason this is a query rather than a formatting helper: the
join can miss. The preflight report and the catalogue are two reads, so an
issue can name a row the catalogue no longer holds. Dropping it silently makes
the issues an operator sees fewer than the count printed beside them, which is
the failure mode the project's own no-silent-under-declaration rule names.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import override

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import (
    LedgerDatePartition,
    OutOfWindowTransactionIndexEntry,
    OutOfWindowTransactionSummary,
    Transaction,
    TransactionCatalogue,
)
from ....domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.usage_ratios.model import UsageRatioProfile
from ..readiness_query import LedgerReadinessIssueV1, read_ledger_readiness

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "77777777-7777-4777-8777-777777777777"
_PERIOD = Period.from_year_and_code(2026, "0A")


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Pin the compiled authority used by the readiness workflow."""
    with compiled_bundled_authority().operation() as operation:
        yield operation


class _InMemoryTransactionRepository(TransactionCatalogueRepositoryProtocol):
    """Deterministic inward fake for the readiness transaction read port."""

    def __init__(self, *, bucket_id: str, catalogue: TransactionCatalogue) -> None:
        self._bucket_id = bucket_id
        self._catalogue = catalogue

    @property
    @override
    def bucket_id(self) -> str:
        return self._bucket_id

    @override
    def exists(self) -> bool:
        return bool(self._catalogue.transactions)

    @override
    def load(self) -> TransactionCatalogue:
        return self._catalogue

    @override
    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        return TransactionCatalogue.from_transactions(
            transaction
            for transaction in self._catalogue
            if start <= (transaction.raw.value_date or transaction.raw.booked_date) <= end
        )

    @override
    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        requested = frozenset(transaction_ids)
        return TransactionCatalogue.from_transactions(
            transaction for transaction in self._catalogue if transaction.transaction_id in requested
        )

    @override
    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        in_window: list[Transaction] = []
        out_of_window: list[OutOfWindowTransactionIndexEntry] = []
        for transaction in self._catalogue:
            filing_date = transaction.raw.value_date or transaction.raw.booked_date
            if start <= filing_date <= end:
                in_window.append(transaction)
            else:
                out_of_window.append(
                    OutOfWindowTransactionIndexEntry(
                        transaction_id=transaction.transaction_id,
                        filing_date=filing_date,
                    ),
                )
        return LedgerDatePartition(
            in_window=TransactionCatalogue.from_transactions(in_window),
            out_of_window=tuple(out_of_window),
            out_of_window_summary=OutOfWindowTransactionSummary.from_index_entries(out_of_window),
            index_complete=True,
        )

    @override
    def save(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue


def _transaction(
    *,
    provider_id: str,
    classification: BusinessClassification = BusinessClassification.BUSINESS,
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 5, 2),
        value_date=None,
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Supplier SL",
        description="classified but tax facts missing",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 5, 2, 9, 30, tzinfo=UTC),
            provider_name="test",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": classification,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": datetime(2026, 5, 2, 9, 30, tzinfo=UTC),
            "modified_at": datetime(2026, 5, 2, 9, 30, tzinfo=UTC),
        }
    )


@contextmanager
def _stored(*transactions: Transaction) -> Iterator[TransactionCatalogueRepositoryProtocol]:
    """Build a deterministic catalogue through the application read protocol."""
    yield _InMemoryTransactionRepository(
        bucket_id=_BUCKET,
        catalogue=TransactionCatalogue.from_transactions(transactions),
    )


def _empty_usage_ratio_profile(*, bucket_id: str) -> UsageRatioProfile:
    """Bind an empty usage-ratio profile for readiness cases without censo rows."""
    del bucket_id
    return UsageRatioProfile()


def test_a_deductible_row_missing_its_tax_facts_reports_them_as_absent(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The explaining facts arrive with the issue, absent values included.

    A business expense with no category and no IVA facts is the ordinary
    readiness failure, and each missing fact must read as missing rather than
    as unread.
    """
    with _stored(_transaction(provider_id="a")) as repository:
        issues = read_ledger_readiness(
            bucket_id=_BUCKET,
            period=_PERIOD,
            transaction_repository=repository,
            usage_ratio_profile_loader=_empty_usage_ratio_profile,
            operation=authority_operation,
        )

    assert issues, "a deductible row with no tax facts must raise readiness issues"
    first = issues[0]
    assert first.transaction_present is True
    assert first.business_classification == BusinessClassification.BUSINESS.value
    assert first.category_id is None
    assert first.taxable_base is None
    assert first.iva_rate is None
    assert first.iva_amount is None
    assert first.reason
    assert first.detail


def test_every_issue_names_a_reason_and_a_detail(authority_operation: PinnedAuthorityOperation) -> None:
    """A reason without a detail cannot be acted on."""
    with _stored(_transaction(provider_id="a")) as repository:
        issues = read_ledger_readiness(
            bucket_id=_BUCKET,
            period=_PERIOD,
            transaction_repository=repository,
            usage_ratio_profile_loader=_empty_usage_ratio_profile,
            operation=authority_operation,
        )

    assert all(issue.reason and issue.detail for issue in issues)


def test_a_ready_ledger_reports_no_issues(authority_operation: PinnedAuthorityOperation) -> None:
    """A personal row is not deductible, so it raises nothing to fix."""
    with _stored(_transaction(provider_id="a", classification=BusinessClassification.PERSONAL)) as repository:
        issues = read_ledger_readiness(
            bucket_id=_BUCKET,
            period=_PERIOD,
            transaction_repository=repository,
            usage_ratio_profile_loader=_empty_usage_ratio_profile,
            operation=authority_operation,
        )

    assert issues == ()


def test_an_issue_whose_row_is_absent_survives_with_its_facts_unset() -> None:
    """The silent-drop case, asserted on the model rather than through a race.

    Reproducing a genuine mid-read deletion would need two interleaved reads;
    what matters is that the shape exists and stays distinguishable from a row
    that is present but incomplete — both have empty facts, and only
    ``transaction_present`` tells them apart.
    """
    absent = LedgerReadinessIssueV1(
        transaction_id="a" * 64,
        reason="missing_category",
        detail="row is gone",
        transaction_present=False,
    )
    incomplete = LedgerReadinessIssueV1(
        transaction_id="b" * 64,
        reason="missing_category",
        detail="row has no category",
        transaction_present=True,
        business_classification="business",
    )

    assert absent.category_id is incomplete.category_id is None
    assert absent.transaction_present != incomplete.transaction_present
