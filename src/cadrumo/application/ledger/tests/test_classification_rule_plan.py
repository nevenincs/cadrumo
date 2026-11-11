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

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import override

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.transactions.classification_rule import LedgerClassificationRule
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.errors import ClassificationRuleError
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.usage_ratios.model import UsageRatioProfile
from ..action_ports import LedgerActionPorts
from ..actions_classification import (
    ClassificationRulePlan,
    add_classification_rule,
    apply_classification_rule_match,
    plan_classification_rules,
)
from ..rule_repository import LedgerClassificationRuleRepositoryProtocol
from .action_port_fakes import (
    EmptyCalculationRepository,
    EmptyInvoiceRepository,
    EmptyWorkUnitRepository,
    InMemoryAttachmentStore,
    InMemoryEventRepository,
    empty_usage_ratio_profile,
)
from .in_memory_transaction_repository import InMemoryTransactionRepository

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

BUCKET = "22222222-2222-4222-8222-222222222222"


class _InMemoryRuleRepository(LedgerClassificationRuleRepositoryProtocol):
    """Application-owned rule capability for classification policy tests."""

    def __init__(self) -> None:
        self._rules: dict[str, LedgerClassificationRule] = {}

    @override
    def save(self, payload: LedgerClassificationRule) -> None:
        self._rules[payload.rule_id] = payload

    @override
    def list_rules(self) -> tuple[LedgerClassificationRule, ...]:
        return tuple(sorted(self._rules.values(), key=lambda rule: (rule.priority, rule.rule_id)))

    @override
    def delete(self, identifier: str) -> bool:
        return self._rules.pop(identifier, None) is not None


class ClassificationScenario:
    """One explicit inward composition for a classification policy case."""

    def __init__(self, transactions: TransactionCatalogue, *, operation: PinnedAuthorityOperation) -> None:
        self.rule_repository = _InMemoryRuleRepository()
        self.ports = LedgerActionPorts(
            operation=operation,
            transaction_repository=InMemoryTransactionRepository(
                bucket_id=BUCKET,
                catalogue=transactions,
                permit_secure_object_writes=True,
            ),
            bucket_event_repository=InMemoryEventRepository(),
            invoice_repository=EmptyInvoiceRepository(bucket_id=BUCKET),
            attachment_store=InMemoryAttachmentStore(),
            usage_ratio_profile=UsageRatioProfile(),
            usage_ratio_profile_loader=empty_usage_ratio_profile,
            work_unit_repository=EmptyWorkUnitRepository(bucket_id=BUCKET),
            calculation_repository=EmptyCalculationRepository(bucket_id=BUCKET),
            purchase_invoice_evidence_records=(),
        )


def transaction(*, provider_id: str, description: str) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(_YEAR - 2, 4, 10),
        value_date=date(_YEAR - 2, 4, 10),
        amount=Decimal("10.00"),
        currency="EUR",
        counterparty="Supplier SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(_YEAR - 2, 4, 14, 9, 30, tzinfo=UTC),
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
            "created_at": datetime(_YEAR - 2, 4, 14, 9, 30, tzinfo=UTC),
            "modified_at": datetime(_YEAR - 2, 4, 14, 9, 30, tzinfo=UTC),
        }
    )


@contextmanager
def _stored(*transactions: Transaction) -> Generator[ClassificationScenario]:
    """Compose application ports around an in-memory transaction catalogue."""
    with bundled_indexed_authority().operation() as operation:
        yield ClassificationScenario(TransactionCatalogue.from_transactions(transactions), operation=operation)


def _apply_plan(scenario: ClassificationScenario, plan: ClassificationRulePlan) -> None:
    """Write every planned row through the same boundary the operation supervisor uses."""
    for row in plan.matches:
        apply_classification_rule_match(
            bucket_id=BUCKET,
            row=row,
            actor="operator",
            source_command="aeat app ledger rule apply",
            reaffirm=False,
            ports=scenario.ports,
        )


def test_the_plan_matches_exactly_what_the_apply_writes() -> None:
    """The load-bearing parity claim: a preview cannot promise a different run."""
    with _stored(
        transaction(provider_id="a", description="OFFICE SUPPLIES LTD"),
        transaction(provider_id="b", description="PERSONAL GYM"),
    ) as scenario:
        add_classification_rule(
            bucket_id=BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            actor="operator",
            rule_repository=scenario.rule_repository,
        )

        plan = plan_classification_rules(
            bucket_id=BUCKET,
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )
        _apply_plan(scenario, plan)

        written = {
            transaction.transaction_id: transaction
            for transaction in scenario.ports.transaction_repository.load()
            if transaction.business_classification is not BusinessClassification.NOT_YET_PROCESSED
        }
        assert set(written) == {row.transaction_id for row in plan.matches}
        for row in plan.matches:
            assert written[row.transaction_id].business_classification == row.classification
            assert written[row.transaction_id].classified_by == f"rule:{row.matched_rule_id}"


def test_the_plan_counters_describe_the_scan() -> None:
    """A preview that under-reports the scan is how an operator misjudges scope."""
    with _stored(
        transaction(provider_id="a", description="OFFICE SUPPLIES LTD"),
        transaction(provider_id="b", description="UNMATCHED NARRATIVE"),
    ) as scenario:
        add_classification_rule(
            bucket_id=BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            actor="operator",
            rule_repository=scenario.rule_repository,
        )

        plan = plan_classification_rules(
            bucket_id=BUCKET,
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )

        assert plan.rules_evaluated == 1
        assert plan.transactions_scanned == 2
        assert plan.skipped_already_classified == 0
        assert plan.no_match == 1
        assert len(plan.matches) == 1


def test_the_winning_rule_carries_its_category_through_to_the_patch() -> None:
    """A rule's category must survive the plan, or apply silently drops it."""
    with _stored(transaction(provider_id="a", description="OFFICE SUPPLIES LTD")) as scenario:
        add_classification_rule(
            bucket_id=BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            category_id="office-costs",
            actor="operator",
            rule_repository=scenario.rule_repository,
        )

        plan = plan_classification_rules(
            bucket_id=BUCKET,
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )

        assert [row.category_id for row in plan.matches] == ["office-costs"]


def test_the_first_rule_in_priority_order_wins() -> None:
    """Two rules can match one row; the engine must pick deterministically."""
    with _stored(transaction(provider_id="a", description="OFFICE SUPPLIES LTD")) as scenario:
        add_classification_rule(
            bucket_id=BUCKET,
            description_pattern="SUPPLIES",
            classification=BusinessClassification.PERSONAL,
            priority=200,
            actor="operator",
            rule_repository=scenario.rule_repository,
        )
        winner = add_classification_rule(
            bucket_id=BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            priority=10,
            actor="operator",
            rule_repository=scenario.rule_repository,
        )

        plan = plan_classification_rules(
            bucket_id=BUCKET,
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )

        assert [row.matched_rule_id for row in plan.matches] == [winner.rule_id]
        assert [row.classification for row in plan.matches] == [BusinessClassification.BUSINESS]


def test_an_already_classified_row_is_out_of_scope_until_reaffirmed() -> None:
    """Scope is the other half the two engines had to agree on."""
    with _stored(transaction(provider_id="a", description="OFFICE SUPPLIES LTD")) as scenario:
        add_classification_rule(
            bucket_id=BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            actor="operator",
            rule_repository=scenario.rule_repository,
        )
        _apply_plan(
            scenario,
            plan_classification_rules(
                bucket_id=BUCKET,
                ports=scenario.ports,
                rule_repository=scenario.rule_repository,
            ),
        )

        second = plan_classification_rules(
            bucket_id=BUCKET,
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )

        assert second.matches == ()
        assert second.transactions_scanned == 0


def test_a_plan_over_no_rules_matches_nothing_but_still_reports_the_scan() -> None:
    """Zero matches and an unscanned ledger are different states."""
    with _stored(transaction(provider_id="a", description="OFFICE SUPPLIES LTD")) as scenario:
        plan = plan_classification_rules(
            bucket_id=BUCKET,
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )

        assert plan.matches == ()
        assert plan.rules_evaluated == 0
        assert plan.transactions_scanned == 1
        assert plan.no_match == 1


@pytest.mark.parametrize(
    ("classification", "category_id"),
    [
        (BusinessClassification.MIXED, None),
        (BusinessClassification.REVIEWED_EXCLUDED, None),
        (BusinessClassification.PERSONAL, "office_supplies"),
        (BusinessClassification.SKIPPED_BY_RULE, "office_supplies"),
    ],
)
def test_the_rule_writer_stores_nothing_a_classification_write_could_not_carry_out(
    classification: BusinessClassification, category_id: str | None
) -> None:
    with _stored(transaction(provider_id="a", description="OFFICE")) as scenario:
        with pytest.raises(ClassificationRuleError):
            add_classification_rule(
                bucket_id=BUCKET,
                description_pattern="OFFICE",
                classification=classification,
                category_id=category_id,
                actor="operator",
                rule_repository=scenario.rule_repository,
            )
        plan = plan_classification_rules(
            bucket_id=BUCKET,
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )
        assert plan.rules_evaluated == 0
