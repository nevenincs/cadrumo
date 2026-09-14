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

import pytest

from ....core.classification.policies import SensitivityClass
from ....core.secure_object_write import SecureObjectWrite
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.invoices.models import InvoiceCatalogue
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.work_unit import WorkUnitCatalogue
from ....domain.transactions.classification_rule import LedgerClassificationRule
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.usage_ratios.model import UsageRatioProfile
from ..action_ports import LedgerActionPorts
from ..actions_classification import (
    add_classification_rule,
    apply_classification_rules,
    plan_classification_rules,
)
from ..rule_repository import LedgerClassificationRuleRepositoryProtocol

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "22222222-2222-4222-8222-222222222222"


class _InMemoryRuleRepository(LedgerClassificationRuleRepositoryProtocol):
    """Application-owned rule capability for classification policy tests."""

    def __init__(self) -> None:
        self._rules: dict[str, LedgerClassificationRule] = {}

    def save(self, payload: LedgerClassificationRule) -> None:
        self._rules[payload.rule_id] = payload

    def list_rules(self) -> tuple[LedgerClassificationRule, ...]:
        return tuple(sorted(self._rules.values(), key=lambda rule: (rule.priority, rule.rule_id)))


class _InMemoryTransactionRepository:
    """Minimal co-commit transaction capability used by application policy tests."""

    def __init__(self, catalogue: TransactionCatalogue) -> None:
        self._catalogue = catalogue

    @property
    def bucket_id(self) -> str:
        return _BUCKET

    def load(self) -> TransactionCatalogue:
        return self._catalogue

    def save_with_secure_object_writes(
        self,
        catalogue: TransactionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        del extra_writes
        self._catalogue = catalogue


class _InMemoryEventRepository:
    """In-memory event capability; event persistence is outside this test seam."""

    def __init__(self) -> None:
        self._catalogue = BucketEventHistoryCatalogue()
        self._revision_id = "0" * 64

    def exists(self) -> bool:
        return bool(self._catalogue.events)

    def load(self) -> BucketEventHistoryCatalogue:
        return self._catalogue

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self._catalogue = catalogue

    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        return self._catalogue, self._revision_id

    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        del expected_revision_id
        self._catalogue = catalogue
        return SecureObjectWrite(
            namespace="application-test-events",
            object_key="classification",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"event-catalogue",
        )


class _EmptyInvoiceRepository:
    """Unused invoice capability required by the shared ledger action bundle."""

    bucket_id = _BUCKET

    def load(self) -> InvoiceCatalogue:
        return InvoiceCatalogue()


class _EmptyWorkUnitRepository:
    def load(self) -> WorkUnitCatalogue:
        return WorkUnitCatalogue()


class _EmptyCalculationRepository:
    def load(self) -> CalculationRevisionCatalogue:
        return CalculationRevisionCatalogue()


class _ClassificationScenario:
    """One explicit inward composition for a classification policy case."""

    def __init__(self, transactions: TransactionCatalogue) -> None:
        self.rule_repository = _InMemoryRuleRepository()
        self.ports = LedgerActionPorts(
            transaction_repository=_InMemoryTransactionRepository(transactions),
            bucket_event_repository=_InMemoryEventRepository(),
            invoice_repository=_EmptyInvoiceRepository(),
            attachment_store=object(),
            usage_ratio_profile=UsageRatioProfile(),
            usage_ratio_profile_loader=lambda *, bucket_id: UsageRatioProfile(),
            work_unit_repository=_EmptyWorkUnitRepository(),
            calculation_repository=_EmptyCalculationRepository(),
            purchase_invoice_evidence_records=(),
        )


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
def _stored(*transactions: Transaction) -> Iterator[_ClassificationScenario]:
    """Compose application ports around an in-memory transaction catalogue."""
    yield _ClassificationScenario(TransactionCatalogue.from_transactions(transactions))


def test_the_plan_matches_exactly_what_the_apply_writes() -> None:
    """The load-bearing parity claim: a preview cannot promise a different run."""
    with _stored(
        _transaction(provider_id="a", description="OFFICE SUPPLIES LTD"),
        _transaction(provider_id="b", description="PERSONAL GYM"),
    ) as scenario:
        add_classification_rule(
            bucket_id=_BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            actor="operator",
            rule_repository=scenario.rule_repository,
        )

        plan = plan_classification_rules(
            bucket_id=_BUCKET,
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )
        applied = apply_classification_rules(
            bucket_id=_BUCKET,
            actor="operator",
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
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
    ) as scenario:
        add_classification_rule(
            bucket_id=_BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            actor="operator",
            rule_repository=scenario.rule_repository,
        )

        plan = plan_classification_rules(
            bucket_id=_BUCKET,
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )
        applied = apply_classification_rules(
            bucket_id=_BUCKET,
            actor="operator",
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )

        assert plan.rules_evaluated == applied.rules_evaluated
        assert plan.transactions_scanned == applied.transactions_scanned
        assert plan.skipped_already_classified == applied.skipped_already_classified
        assert plan.no_match == applied.no_match == 1


def test_the_winning_rule_carries_its_category_through_to_the_patch() -> None:
    """A rule's category must survive the plan, or apply silently drops it."""
    with _stored(_transaction(provider_id="a", description="OFFICE SUPPLIES LTD")) as scenario:
        add_classification_rule(
            bucket_id=_BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            category_id="office-costs",
            actor="operator",
            rule_repository=scenario.rule_repository,
        )

        plan = plan_classification_rules(
            bucket_id=_BUCKET,
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )

        assert [row.category_id for row in plan.matches] == ["office-costs"]


def test_the_first_rule_in_priority_order_wins() -> None:
    """Two rules can match one row; the engine must pick deterministically."""
    with _stored(_transaction(provider_id="a", description="OFFICE SUPPLIES LTD")) as scenario:
        add_classification_rule(
            bucket_id=_BUCKET,
            description_pattern="SUPPLIES",
            classification=BusinessClassification.PERSONAL,
            priority=200,
            actor="operator",
            rule_repository=scenario.rule_repository,
        )
        winner = add_classification_rule(
            bucket_id=_BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            priority=10,
            actor="operator",
            rule_repository=scenario.rule_repository,
        )

        plan = plan_classification_rules(
            bucket_id=_BUCKET,
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )

        assert [row.matched_rule_id for row in plan.matches] == [winner.rule_id]
        assert [row.classification for row in plan.matches] == [BusinessClassification.BUSINESS]


def test_an_already_classified_row_is_out_of_scope_until_reaffirmed() -> None:
    """Scope is the other half the two engines had to agree on."""
    with _stored(_transaction(provider_id="a", description="OFFICE SUPPLIES LTD")) as scenario:
        add_classification_rule(
            bucket_id=_BUCKET,
            description_pattern="OFFICE",
            classification=BusinessClassification.BUSINESS,
            actor="operator",
            rule_repository=scenario.rule_repository,
        )
        apply_classification_rules(
            bucket_id=_BUCKET,
            actor="operator",
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )

        second = plan_classification_rules(
            bucket_id=_BUCKET,
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )

        assert second.matches == ()
        assert second.transactions_scanned == 0


def test_a_plan_over_no_rules_matches_nothing_but_still_reports_the_scan() -> None:
    """Zero matches and an unscanned ledger are different states."""
    with _stored(_transaction(provider_id="a", description="OFFICE SUPPLIES LTD")) as scenario:
        plan = plan_classification_rules(
            bucket_id=_BUCKET,
            ports=scenario.ports,
            rule_repository=scenario.rule_repository,
        )

        assert plan.matches == ()
        assert plan.rules_evaluated == 0
        assert plan.transactions_scanned == 1
        assert plan.no_match == 1
