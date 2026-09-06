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

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core.period import Period
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from ..readiness_query import LedgerReadinessIssueV1, read_ledger_readiness

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "77777777-7777-4777-8777-777777777777"
_PERIOD = Period.from_year_and_code(2026, "0A")


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
def _stored(*transactions: Transaction) -> Iterator[TransactionCatalogueRepository]:
    """Persist rows through the real repository the preflight requires."""
    with TemporaryDirectory() as tmp, isolated_runtime_profile(tmp_path=Path(tmp), bucket_id=_BUCKET) as profile:
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(TransactionCatalogue.from_transactions(transactions))
        yield TransactionCatalogueRepository(bucket_id=profile.bucket_id)


def test_a_deductible_row_missing_its_tax_facts_reports_them_as_absent() -> None:
    """The explaining facts arrive with the issue, absent values included.

    A business expense with no category and no IVA facts is the ordinary
    readiness failure, and each missing fact must read as missing rather than
    as unread.
    """
    with _stored(_transaction(provider_id="a")) as repository:
        issues = read_ledger_readiness(bucket_id=_BUCKET, period=_PERIOD, transaction_repository=repository)

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


def test_every_issue_names_a_reason_and_a_detail() -> None:
    """A reason without a detail cannot be acted on."""
    with _stored(_transaction(provider_id="a")) as repository:
        issues = read_ledger_readiness(bucket_id=_BUCKET, period=_PERIOD, transaction_repository=repository)

    assert all(issue.reason and issue.detail for issue in issues)


def test_a_ready_ledger_reports_no_issues() -> None:
    """A personal row is not deductible, so it raises nothing to fix."""
    with _stored(_transaction(provider_id="a", classification=BusinessClassification.PERSONAL)) as repository:
        issues = read_ledger_readiness(bucket_id=_BUCKET, period=_PERIOD, transaction_repository=repository)

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
