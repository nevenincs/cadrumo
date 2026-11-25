"""Ledger classification-rule removal through the real supervisor matrix."""

from __future__ import annotations

from ...adapters.persistence.profile.ledger_classification_rules import LedgerClassificationRuleRepository
from ...application.ledger.actions_classification import add_classification_rule
from ...application.ledger.rule_contracts import LedgerRuleRowProjection
from ...application.ledger.rule_remove_operation import (
    LEDGER_RULE_REMOVE_OPERATION_DEFINITION_ID,
    LedgerRuleRemoveProjection,
    LedgerRuleRemoveRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.transactions.enums import BusinessClassification
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)

_ACTOR = "registered-rule-remove-conformance"


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    if context.definition.definition_id != LEDGER_RULE_REMOVE_OPERATION_DEFINITION_ID:
        raise AssertionError(f"unsupported ledger rule removal definition: {context.definition.definition_id}")
    bucket_id = str(context.profile_id)
    repository = LedgerClassificationRuleRepository(bucket_id=bucket_id)
    # The neighbour proves the removal deletes the named rule and nothing else.
    kept = add_classification_rule(
        bucket_id=bucket_id,
        description_pattern=f"^Registered Rule Remove Kept {context.profile_id.hex}$",
        classification=BusinessClassification.PERSONAL,
        category_id=None,
        priority=21,
        actor=_ACTOR,
        rule_repository=repository,
    )
    removed = add_classification_rule(
        bucket_id=bucket_id,
        description_pattern=f"^Registered Rule Remove Target {context.profile_id.hex}$",
        classification=BusinessClassification.BUSINESS,
        category_id="material_oficina",
        priority=3,
        actor=_ACTOR,
        rule_repository=repository,
    )
    assert {rule.rule_id for rule in repository.list_rules()} == {kept.rule_id, removed.rule_id}

    def verify(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(LedgerRuleRemoveProjection)
        assert result.profile_id == context.profile_id
        assert result.outcome == "removed"
        assert result.rule == LedgerRuleRowProjection.from_rule(removed)
        assert repository.list_rules() == (kept,)

    return ConformancePreparation(
        profile_operation_subject(str(context.profile_id)),
        LedgerRuleRemoveRequest(
            profile_id=context.profile_id,
            rule_id=removed.rule_id,
            expected_created_at=removed.created_at,
        ),
        verify=verify,
    )


LEDGER_RULE_REMOVE_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            LEDGER_RULE_REMOVE_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (LEDGER_RULE_REMOVE_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)
