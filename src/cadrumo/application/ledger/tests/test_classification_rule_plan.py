"""The rule engine's preview and its apply must describe the same scan.

``ledger rule apply --dry-run`` used to answer from a second implementation of
scope and first-match living in the CLI adapter. Two engines that agree today
agree only until one is edited, and the failure is silent in the worst way: a
preview promises an outcome the run does not produce, so an operator approves a
change they were shown incorrectly.

These tests hold the two together. The parity case is the load-bearing one --
it compares the planned matches against what the apply actually wrote, so the
engines cannot drift without a red test.
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
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....tests.secure_sql import isolated_runtime_profile
from ..actions_classification import (
    add_classification_rule,
    apply_classification_rules,
    plan_classification_rules,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "22222222-2222-4222-8222-222222222222"


def _transaction(*, provider_id: str, description: str) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2024, 4, 10),
        value_date=date(2024, 4, 10),
        amount=Decimal("10.00"),
        currency="EUR",
        counterparty="Supplier SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="test",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            "modified_at": datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
        }
    )


@contextmanager
def _stored(*transactions: Transaction) -> Iterator[TransactionCatalogueRepository]:
    """Persist rows through the real repository the engine requires.

    The manual-ledger resolver refuses a protocol stand-in on purpose, so a
    double here would exercise the refusal rather than the engine.
    """
    with TemporaryDirectory() as tmp, isolated_runtime_profile(tmp_path=Path(tmp), bucket_id=_BUCKET) as profile:
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        repository.save(TransactionCatalogue.from_transactions(transactions))
        yield TransactionCatalogueRepository(bucket_id=profile.bucket_id)


def test_the_plan_matches_exactly_what_the_apply_writes() -> None:
    """The load-bearing parity claim: a preview cannot promise a different run."""
    with _stored(
        _transaction(provider_id="a", description="OFFICE SUPPLIES LTD"),
        _transaction(provider_id="b", description="PERSONAL GYM"),
    ) as repository:
        add_classification_rule(
            bucket_id=_BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            actor="operator",
        )

        plan = plan_classification_rules(bucket_id=_BUCKET, transaction_repository=repository)
        applied = apply_classification_rules(
            bucket_id=_BUCKET,
            actor="operator",
            transaction_repository=repository,
        )

        assert [row.transaction_id for row in plan.matches] == [row.transaction_id for row in applied.applied]
        assert [row.matched_rule_id for row in plan.matches] == [row.matched_rule_id for row in applied.applied]
        assert [row.classification for row in plan.matches] == [row.classification for row in applied.applied]
        assert applied.matched == len(plan.matches)


def test_the_plan_counters_match_the_applied_counters() -> None:
    """A preview that under-reports the scan is how an operator misjudges scope."""
    with _stored(
        _transaction(provider_id="a", description="OFFICE SUPPLIES LTD"),
        _transaction(provider_id="b", description="UNMATCHED NARRATIVE"),
    ) as repository:
        add_classification_rule(
            bucket_id=_BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            actor="operator",
        )

        plan = plan_classification_rules(bucket_id=_BUCKET, transaction_repository=repository)
        applied = apply_classification_rules(
            bucket_id=_BUCKET,
            actor="operator",
            transaction_repository=repository,
        )

        assert plan.rules_evaluated == applied.rules_evaluated
        assert plan.transactions_scanned == applied.transactions_scanned
        assert plan.skipped_already_classified == applied.skipped_already_classified
        assert plan.no_match == applied.no_match == 1


def test_the_winning_rule_carries_its_category_through_to_the_patch() -> None:
    """A rule's category must survive the plan, or apply silently drops it."""
    with _stored(_transaction(provider_id="a", description="OFFICE SUPPLIES LTD")) as repository:
        add_classification_rule(
            bucket_id=_BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            category_id="office-costs",
            actor="operator",
        )

        plan = plan_classification_rules(bucket_id=_BUCKET, transaction_repository=repository)

        assert [row.category_id for row in plan.matches] == ["office-costs"]


def test_the_first_rule_in_priority_order_wins() -> None:
    """Two rules can match one row; the engine must pick deterministically."""
    with _stored(_transaction(provider_id="a", description="OFFICE SUPPLIES LTD")) as repository:
        add_classification_rule(
            bucket_id=_BUCKET,
            description_pattern="SUPPLIES",
            classification=BusinessClassification.PERSONAL,
            priority=200,
            actor="operator",
        )
        winner = add_classification_rule(
            bucket_id=_BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            priority=10,
            actor="operator",
        )

        plan = plan_classification_rules(bucket_id=_BUCKET, transaction_repository=repository)

        assert [row.matched_rule_id for row in plan.matches] == [winner.rule_id]
        assert [row.classification for row in plan.matches] == [BusinessClassification.BUSINESS]


def test_an_already_classified_row_is_out_of_scope_until_reaffirmed() -> None:
    """Scope is the other half the two engines had to agree on."""
    with _stored(_transaction(provider_id="a", description="OFFICE SUPPLIES LTD")) as repository:
        add_classification_rule(
            bucket_id=_BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            actor="operator",
        )
        apply_classification_rules(
            bucket_id=_BUCKET,
            actor="operator",
            transaction_repository=repository,
        )

        second = plan_classification_rules(bucket_id=_BUCKET, transaction_repository=repository)

        assert second.matches == ()
        assert second.transactions_scanned == 0


def test_a_plan_over_no_rules_matches_nothing_but_still_reports_the_scan() -> None:
    """Zero matches and an unscanned ledger are different states."""
    with _stored(_transaction(provider_id="a", description="OFFICE SUPPLIES LTD")) as repository:
        plan = plan_classification_rules(bucket_id=_BUCKET, transaction_repository=repository)

        assert plan.matches == ()
        assert plan.rules_evaluated == 0
        assert plan.transactions_scanned == 1
        assert plan.no_match == 1
