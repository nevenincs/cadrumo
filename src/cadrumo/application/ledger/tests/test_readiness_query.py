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

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..preflight import preflight_ledger_tax_readiness
from ..protocols import TransactionCatalogueCoCommitWriterProtocol
from ..readiness_query import LedgerReadinessIssueV1, ledger_readiness_issues
from .action_port_fakes import EmptyInvoiceRepository, empty_usage_ratio_profile
from .in_memory_transaction_repository import InMemoryTransactionRepository

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "77777777-7777-4777-8777-777777777777"
_PERIOD = Period.from_year_and_code(_YEAR, "0A")


def _transaction(
    *,
    provider_id: str,
    classification: BusinessClassification = BusinessClassification.BUSINESS,
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(_YEAR, 5, 2),
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
            ingested_at=datetime(_YEAR, 5, 2, 9, 30, tzinfo=UTC),
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
            "created_at": datetime(_YEAR, 5, 2, 9, 30, tzinfo=UTC),
            "modified_at": datetime(_YEAR, 5, 2, 9, 30, tzinfo=UTC),
        }
    )


@contextmanager
def _stored(*transactions: Transaction) -> Generator[TransactionCatalogueCoCommitWriterProtocol]:
    """Build a deterministic catalogue through the application read protocol."""
    yield InMemoryTransactionRepository(
        bucket_id=_BUCKET,
        catalogue=TransactionCatalogue.from_transactions(transactions),
    )


def _readiness(
    repository: TransactionCatalogueCoCommitWriterProtocol,
    operation: PinnedAuthorityOperation,
) -> tuple[LedgerReadinessIssueV1, ...]:
    """Run the preflight over the repository's rows and join its issues to those rows."""
    catalogue = repository.load()
    report = preflight_ledger_tax_readiness(
        bucket_id=_BUCKET,
        period=_PERIOD,
        transaction_repository=repository,
        usage_ratio_profile_loader=empty_usage_ratio_profile,
        invoice_reader=EmptyInvoiceRepository(bucket_id=_BUCKET),
        operation=operation,
        catalogue=catalogue,
    )
    return ledger_readiness_issues(report, catalogue)


def test_a_deductible_row_missing_its_tax_facts_reports_them_as_absent(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The explaining facts arrive with the issue, absent values included.

    A business expense with no category and no IVA facts is the ordinary
    readiness failure, and each missing fact must read as missing rather than
    as unread.
    """
    with _stored(_transaction(provider_id="a")) as repository:
        issues = _readiness(repository, authority_operation)

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
        issues = _readiness(repository, authority_operation)

    assert all(issue.reason and issue.detail for issue in issues)


def test_a_ready_ledger_reports_no_issues(authority_operation: PinnedAuthorityOperation) -> None:
    """A personal row is not deductible, so it raises nothing to fix."""
    with _stored(_transaction(provider_id="a", classification=BusinessClassification.PERSONAL)) as repository:
        issues = _readiness(repository, authority_operation)

    assert issues == ()


def test_an_issue_whose_row_left_the_catalogue_is_joined_with_its_facts_unset(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A report joined against rows that no longer hold its transaction keeps the issue."""
    with _stored(_transaction(provider_id="a")) as repository:
        catalogue = repository.load()
        report = preflight_ledger_tax_readiness(
            bucket_id=_BUCKET,
            period=_PERIOD,
            transaction_repository=repository,
            usage_ratio_profile_loader=empty_usage_ratio_profile,
            invoice_reader=EmptyInvoiceRepository(bucket_id=_BUCKET),
            operation=authority_operation,
            catalogue=catalogue,
        )

    assert report.issues
    issues = ledger_readiness_issues(report, TransactionCatalogue.from_transactions(()))

    assert [issue.transaction_id for issue in issues] == [issue.transaction_id for issue in report.issues]
    assert all(not issue.transaction_present for issue in issues)
    assert all(issue.business_classification is None and issue.category_id is None for issue in issues)


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
