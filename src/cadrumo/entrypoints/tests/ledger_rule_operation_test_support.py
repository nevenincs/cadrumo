"""Canonical encrypted fixtures for registered ledger-rule operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from ...adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
from ...application.ledger.action_ports import LedgerActionPorts
from ...application.ledger.actions_classification import (
    ClassificationRulePlan,
    add_classification_rule,
    plan_classification_rules,
)
from ...application.ledger.actions_manual import (
    command_from_patch,
    create_manual_transaction,
    prepare_manual_transaction_update,
)
from ...application.ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from ...application.ledger.rule_operation import (
    LEDGER_RULE_ADD_OPERATION_DEFINITION_ID,
    LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID,
    LEDGER_RULE_LIST_OPERATION_DEFINITION_ID,
    LedgerRuleAddProjection,
    LedgerRuleAddRequest,
    LedgerRuleApplyAppliedProjection,
    LedgerRuleApplyMatchProjection,
    LedgerRuleApplyProjection,
    LedgerRuleApplyRequest,
    LedgerRuleListProjection,
    LedgerRuleListRequest,
    LedgerRuleRowProjection,
)
from ...core.decimal.formatting import format_decimal
from ...core.operations import OperationEffect
from ...domain.buckets.event import (
    BucketEvent,
    BucketEventHistoryCatalogue,
    BucketEventObjectType,
    BucketEventType,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.classification_rule import LedgerClassificationRule
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ...domain.transactions.models import Transaction, TransactionCatalogue
from ..ledger_action_composition import compose_ledger_action_ports

LedgerRuleOperationDefinitionId = Literal["ledger.rule.add", "ledger.rule.list", "ledger.rule.apply"]

_SEED_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)
_ACTOR = "registered-rule-conformance"


@dataclass(frozen=True, slots=True)
class LedgerRuleOperationConformanceCase:
    """One request, expected result, and canonical encrypted before-state."""

    definition_id: LedgerRuleOperationDefinitionId
    request: LedgerRuleAddRequest | LedgerRuleListRequest | LedgerRuleApplyRequest
    expected_effect: OperationEffect
    profile_id: UUID
    operation: PinnedAuthorityOperation
    expected_projection: LedgerRuleListProjection | LedgerRuleApplyProjection | None
    rules_before: tuple[LedgerClassificationRule, ...]
    transactions_before: TransactionCatalogue
    history_before: BucketEventHistoryCatalogue
    expected_rule_id: str | None = None
    expected_plan: ClassificationRulePlan | None = None


def _seed_rule(
    *,
    repository: LedgerClassificationRuleRepository,
    bucket_id: str,
    pattern: str,
    classification: BusinessClassification,
    category_id: str | None,
    priority: int,
) -> LedgerClassificationRule:
    return add_classification_rule(
        bucket_id=bucket_id,
        description_pattern=pattern,
        classification=classification,
        category_id=category_id,
        priority=priority,
        actor=_ACTOR,
        rule_repository=repository,
    )


def prepare_ledger_rule_operation_conformance_case(
    definition_id: str,
    profile_id: UUID,
    *,
    operation: PinnedAuthorityOperation,
    dry_run: bool = False,
) -> LedgerRuleOperationConformanceCase:
    """Prepare a complete add, list, or apply request over encrypted profile state."""
    if definition_id not in {
        LEDGER_RULE_ADD_OPERATION_DEFINITION_ID,
        LEDGER_RULE_LIST_OPERATION_DEFINITION_ID,
        LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID,
    }:
        raise ValueError(f"unsupported ledger rule operation definition: {definition_id}")

    operation_id = definition_id
    bucket_id = str(profile_id)
    ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=operation)
    repository = LedgerClassificationRuleRepository(bucket_id=bucket_id)
    expected_projection: LedgerRuleListProjection | LedgerRuleApplyProjection | None = None
    expected_rule_id: str | None = None
    expected_plan: ClassificationRulePlan | None = None

    if operation_id == LEDGER_RULE_ADD_OPERATION_DEFINITION_ID:
        add_request = LedgerRuleAddRequest(
            profile_id=profile_id,
            description_pattern=f"^Registered Rule Add {profile_id.hex}$",
            classification=BusinessClassification.BUSINESS,
            category_id="material_oficina",
            priority=7,
            actor=_ACTOR,
        )
        candidate = LedgerClassificationRule.create(
            description_pattern=add_request.description_pattern,
            classification=add_request.classification,
            category_id=add_request.category_id,
            priority=add_request.priority,
            actor=add_request.actor or bucket_id,
            created_at=_SEED_AT,
        )
        expected_rule_id = str(candidate.rule_id)
        if any(rule.rule_id == expected_rule_id for rule in repository.list_rules()):
            raise RuntimeError("ledger rule add conformance identifier already exists in the fresh profile")
        request: LedgerRuleAddRequest | LedgerRuleListRequest | LedgerRuleApplyRequest = add_request
        expected_effect = OperationEffect.UPDATED

    elif operation_id == LEDGER_RULE_LIST_OPERATION_DEFINITION_ID:
        _seed_rule(
            repository=repository,
            bucket_id=bucket_id,
            pattern=f"^Registered Rule List Later {profile_id.hex}$",
            classification=BusinessClassification.PERSONAL,
            category_id=None,
            priority=21,
        )
        _seed_rule(
            repository=repository,
            bucket_id=bucket_id,
            pattern=f"^Registered Rule List First {profile_id.hex}$",
            classification=BusinessClassification.BUSINESS,
            category_id="material_oficina",
            priority=3,
        )
        list_request = LedgerRuleListRequest(profile_id=profile_id)
        request = list_request
        rows = tuple(LedgerRuleRowProjection.from_rule(rule) for rule in repository.list_rules())
        expected_projection = LedgerRuleListProjection(profile_id=profile_id, rules=rows)
        expected_effect = OperationEffect.NONE

    else:
        pattern = f"^Registered Rule Apply {profile_id.hex}$"
        seeded_rule = _seed_rule(
            repository=repository,
            bucket_id=bucket_id,
            pattern=pattern,
            classification=BusinessClassification.BUSINESS,
            category_id="material_oficina",
            priority=8,
        )
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=bucket_id,
                booked_date=_SEED_AT.date(),
                amount=Decimal("78.90"),
                direction=TransactionDirection.OUTGOING,
                description=f"Registered Rule Apply {profile_id.hex}",
                actor=_ACTOR,
                idempotency_key=f"registered-rule-apply-{profile_id.hex}",
                business_classification=BusinessClassification.NOT_YET_PROCESSED,
            ),
            ports=ports,
            occurred_at=_SEED_AT,
        )
        apply_request = LedgerRuleApplyRequest(profile_id=profile_id, dry_run=dry_run, actor=_ACTOR)
        request = apply_request
        expected_plan = plan_classification_rules(
            bucket_id=bucket_id,
            reaffirm=apply_request.reaffirm,
            ports=ports,
            rule_repository=repository,
        )
        if (
            expected_plan.rules_evaluated != 1
            or expected_plan.transactions_scanned != 1
            or expected_plan.skipped_already_classified != 0
            or expected_plan.no_match != 0
            or len(expected_plan.matches) != 1
            or expected_plan.matches[0].matched_rule_id != seeded_rule.rule_id
        ):
            raise RuntimeError("canonical ledger rule conformance plan did not produce its one expected match")
        if apply_request.dry_run:
            expected_projection = LedgerRuleApplyProjection(
                profile_id=profile_id,
                outcome="dry_run",
                dry_run=True,
                would_match=tuple(
                    LedgerRuleApplyMatchProjection(
                        transaction_id=row.transaction_id,
                        description=row.description,
                        matched_rule_id=row.matched_rule_id,
                        classification=row.classification,
                    )
                    for row in expected_plan.matches
                ),
                count=len(expected_plan.matches),
            )
            expected_effect = OperationEffect.NONE
        else:
            expected_projection = LedgerRuleApplyProjection(
                profile_id=profile_id,
                outcome="applied",
                rules_evaluated=expected_plan.rules_evaluated,
                transactions_scanned=expected_plan.transactions_scanned,
                matched=len(expected_plan.matches),
                skipped_already_classified=expected_plan.skipped_already_classified,
                no_match=expected_plan.no_match,
                applied=tuple(
                    LedgerRuleApplyAppliedProjection(
                        transaction_id=row.transaction_id,
                        matched_rule_id=row.matched_rule_id,
                        classification=row.classification,
                    )
                    for row in expected_plan.matches
                ),
                bucket_event_count=len(expected_plan.matches),
            )
            expected_effect = OperationEffect.UPDATED

    rules_before = repository.list_rules()
    transactions_before = ports.transaction_repository.load()
    history_before = ports.bucket_event_repository.load()
    return LedgerRuleOperationConformanceCase(
        definition_id=operation_id,
        request=request,
        expected_effect=expected_effect,
        profile_id=profile_id,
        operation=operation,
        expected_projection=expected_projection,
        rules_before=rules_before,
        transactions_before=transactions_before,
        history_before=history_before,
        expected_rule_id=expected_rule_id,
        expected_plan=expected_plan,
    )


def assert_canonical_ledger_rule_update(
    before: Transaction,
    after: Transaction,
    *,
    rule: LedgerClassificationRule,
    actor: str,
    occurred_at: datetime,
    ports: LedgerActionPorts,
) -> tuple[BucketEvent, ...]:
    """Compare every transaction field and event with canonical pure preparation."""
    command = command_from_patch(
        bucket_id=ports.transaction_repository.bucket_id,
        current=before,
        patch=ManualLedgerTransactionPatch(
            business_classification=rule.classification,
            category_id=rule.category_id,
        ),
        actor=actor,
        source_command="aeat app ledger rule apply",
        classified_by_override=f"rule:{rule.rule_id}",
    )
    prepared = prepare_manual_transaction_update(
        current=before,
        command=command,
        previous_transaction_id=before.transaction_id,
        now=occurred_at,
        ports=ports,
    )
    assert prepared is not None
    expected_transaction, expected_events = prepared
    assert after == expected_transaction
    return expected_events


def assert_ledger_rule_operation_conformance_result(
    case: LedgerRuleOperationConformanceCase,
    projection: BaseModel,
    *,
    operation_run_id: str,
) -> None:
    """Compare the public result against the exact-profile encrypted repositories."""
    assert len(operation_run_id) == 64
    assert all(character in "0123456789abcdef" for character in operation_run_id)
    bucket_id = str(case.profile_id)
    ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=case.operation)
    repository = LedgerClassificationRuleRepository(bucket_id=bucket_id)

    if case.definition_id == LEDGER_RULE_ADD_OPERATION_DEFINITION_ID:
        assert isinstance(case.request, LedgerRuleAddRequest)
        assert isinstance(projection, LedgerRuleAddProjection)
        assert case.expected_rule_id is not None
        assert projection.profile_id == case.profile_id
        assert projection.outcome == "added"
        assert projection.rule is not None
        assert projection.rule.rule_id == case.expected_rule_id
        stored_rules = repository.list_rules()
        by_id = {str(rule.rule_id): rule for rule in stored_rules}
        assert case.expected_rule_id in by_id
        stored = by_id[case.expected_rule_id]
        assert projection.rule == LedgerRuleRowProjection.from_rule(stored)
        assert stored.description_pattern == case.request.description_pattern
        assert stored.classification is case.request.classification
        assert stored.category_id == case.request.category_id
        assert stored.priority == case.request.priority
        assert stored.actor == (case.request.actor or bucket_id)
        assert len(stored_rules) == len(case.rules_before) + 1
        assert all(by_id.get(str(rule.rule_id)) == rule for rule in case.rules_before)
        assert ports.transaction_repository.load() == case.transactions_before
        assert ports.bucket_event_repository.load() == case.history_before
        return

    assert projection == case.expected_projection
    assert repository.list_rules() == case.rules_before
    if case.definition_id == LEDGER_RULE_LIST_OPERATION_DEFINITION_ID:
        assert isinstance(projection, LedgerRuleListProjection)
        assert projection.profile_id == case.profile_id
        assert projection.rules == tuple(LedgerRuleRowProjection.from_rule(rule) for rule in case.rules_before)
        assert ports.transaction_repository.load() == case.transactions_before
        assert ports.bucket_event_repository.load() == case.history_before
        return

    assert case.definition_id == LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID
    assert isinstance(case.request, LedgerRuleApplyRequest)
    assert isinstance(projection, LedgerRuleApplyProjection)
    plan = case.expected_plan
    assert plan is not None
    after_catalogue = ports.transaction_repository.load()
    after_history = ports.bucket_event_repository.load()
    assert all(after_history.events.get(event_id) == event for event_id, event in case.history_before.events.items())
    new_events = tuple(
        event for event_id, event in after_history.events.items() if event_id not in case.history_before.events
    )

    if case.request.dry_run:
        assert after_catalogue == case.transactions_before
        assert new_events == ()
        return

    assert len(new_events) == len(plan.matches)
    for row, event in zip(plan.matches, new_events, strict=True):
        before = case.transactions_before.get(row.transaction_id)
        after = after_catalogue.get(row.transaction_id)
        assert before is not None and after is not None
        assert after.transaction_id == before.transaction_id
        matched_rule = next(rule for rule in case.rules_before if rule.rule_id == row.matched_rule_id)
        assert assert_canonical_ledger_rule_update(
            before,
            after,
            rule=matched_rule,
            actor=case.request.actor or bucket_id,
            occurred_at=event.occurred_at,
            ports=ports,
        ) == (event,)
        assert after.business_classification is row.classification
        assert after.category_id == row.category_id
        assert after.classified_by == f"rule:{row.matched_rule_id}"
        assert event.bucket_id == bucket_id
        assert event.event_type is BucketEventType.LEDGER_TRANSACTION_CLASSIFIED
        assert event.object_type is BucketEventObjectType.LEDGER_TRANSACTION
        assert event.object_id == row.transaction_id
        assert event.actor == (case.request.actor or bucket_id)
        assert event.payload_version == 1
        assert dict(event.payload) == {
            "amount": format_decimal(before.raw.amount),
            "category_id": row.category_id or "",
            "classification": row.classification.value,
            "currency": before.raw.currency,
            "direction": before.direction.value,
            "mutation_kind": "classification",
            "previous_transaction_id": row.transaction_id,
            "source_command": "aeat app ledger rule apply",
        }


__all__ = [
    "LedgerRuleOperationConformanceCase",
    "assert_canonical_ledger_rule_update",
    "assert_ledger_rule_operation_conformance_result",
    "prepare_ledger_rule_operation_conformance_case",
]
