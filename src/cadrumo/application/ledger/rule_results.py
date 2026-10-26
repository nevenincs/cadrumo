"""Canonical result projection and terminal receipt policy for ledger rules."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ..operations.models import OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from .actions_classification import ClassificationRulePlan
from .models import ApplyRulesAppliedRow, ApplyRulesResult
from .rule_contracts import (
    MAX_RULE_VALIDATION_MESSAGES,
    LedgerRuleAddExecutionResult,
    LedgerRuleAddProjection,
    LedgerRuleApplyAppliedProjection,
    LedgerRuleApplyExecutionResult,
    LedgerRuleApplyMatchProjection,
    LedgerRuleApplyProjection,
    RuleValidationMessages,
)
from .validation_messages import bounded_validation_messages

LEDGER_RULE_VALIDATION_REFUSAL_CODE = "REFUSED_CLI_VALIDATION_BOUNDARY"


def build_rule_validation_messages(error: Exception) -> RuleValidationMessages:
    """Keep only bounded validation locations or the canonical error sentence."""
    return bounded_validation_messages(
        error,
        limit=MAX_RULE_VALIDATION_MESSAGES,
        fallback="ledger classification rule values did not satisfy validation",
    )


def build_rule_dry_run_projection(profile_id: UUID, plan: ClassificationRulePlan) -> LedgerRuleApplyProjection:
    """Preserve every existing preview row and its exact match ordering."""
    rows = tuple(
        LedgerRuleApplyMatchProjection(
            transaction_id=row.transaction_id,
            description=row.description,
            matched_rule_id=row.matched_rule_id,
            classification=row.classification,
        )
        for row in plan.matches
    )
    return LedgerRuleApplyProjection(
        profile_id=profile_id,
        outcome="dry_run",
        dry_run=True,
        would_match=rows,
        count=len(rows),
    )


def build_rule_apply_plan_projection(
    profile_id: UUID,
    plan: ClassificationRulePlan,
    *,
    bucket_event_count: int,
) -> LedgerRuleApplyProjection:
    """Build the full live projection promised by a plan before its first write."""
    result = ApplyRulesResult(
        rules_evaluated=plan.rules_evaluated,
        transactions_scanned=plan.transactions_scanned,
        matched=len(plan.matches),
        skipped_already_classified=plan.skipped_already_classified,
        no_match=plan.no_match,
        applied=tuple(
            ApplyRulesAppliedRow(
                transaction_id=row.transaction_id,
                matched_rule_id=row.matched_rule_id,
                classification=row.classification,
            )
            for row in plan.matches
        ),
        bucket_event_ids=(),
    )
    return build_rule_apply_result_projection(profile_id, result, bucket_event_count=bucket_event_count)


def build_rule_apply_result_projection(
    profile_id: UUID,
    result: ApplyRulesResult,
    *,
    bucket_event_count: int,
) -> LedgerRuleApplyProjection:
    """Copy all current live CLI counts and applied rows into the operation DTO."""
    return LedgerRuleApplyProjection(
        profile_id=profile_id,
        outcome="applied",
        rules_evaluated=result.rules_evaluated,
        transactions_scanned=result.transactions_scanned,
        matched=result.matched,
        skipped_already_classified=result.skipped_already_classified,
        no_match=result.no_match,
        applied=tuple(
            LedgerRuleApplyAppliedProjection(
                transaction_id=row.transaction_id,
                matched_rule_id=row.matched_rule_id,
                classification=row.classification,
            )
            for row in result.applied
        ),
        bucket_event_count=bucket_event_count,
    )


def build_rule_apply_validation_projection(profile_id: UUID, error: Exception) -> LedgerRuleApplyProjection:
    """Build bounded refusal detail after a known no-write per-row validation."""
    return LedgerRuleApplyProjection(
        profile_id=profile_id,
        outcome="validation_error",
        validation_code="invalid_command",
        validation_messages=build_rule_validation_messages(error),
    )


async def publish_rule_apply_refusal(
    context: OperationExecutorContext,
    projection: LedgerRuleApplyProjection,
) -> OperationRefusalEvidence:
    """Persist a bounded rule-apply refusal as private result evidence."""
    detail_ref = await context.operands.put(LedgerRuleApplyExecutionResult(projection=projection), written_at=now())
    return OperationRefusalEvidence(
        refusal_code=LEDGER_RULE_VALIDATION_REFUSAL_CODE,
        detail_ref=detail_ref,
    )


def project_ledger_rule_add_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release the add projection only when its exact profile receipt agrees."""
    if type(result) is not LedgerRuleAddExecutionResult:
        raise ValueError("invalid ledger rule add result")
    projection = result.projection
    _require_rule_result_subject(projection.profile_id, receipt, operation="add")
    if projection.outcome == "added":
        _require_add_success_receipt(projection, receipt)
    else:
        _require_add_refusal_receipt(projection, receipt)
    return projection


def _require_rule_result_subject(profile_id: UUID, receipt: OperationTerminalReceipt, *, operation: str) -> None:
    if receipt.identity.subject_ref != profile_operation_subject(str(profile_id)):
        raise ValueError(f"ledger rule {operation} result belongs to another profile")


def _require_add_success_receipt(
    projection: LedgerRuleAddProjection,
    receipt: OperationTerminalReceipt,
) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.UPDATED
        or projection.rule is None
    ):
        raise ValueError("ledger rule add success has an incompatible terminal receipt")


def _require_add_refusal_receipt(
    projection: LedgerRuleAddProjection,
    receipt: OperationTerminalReceipt,
) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.refusal_ref != LEDGER_RULE_VALIDATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.effect is not OperationEffect.NONE
        or projection.rule is not None
    ):
        raise ValueError("ledger rule add refusal has an incompatible terminal receipt")


def project_ledger_rule_apply_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release the apply projection only when its result and effect receipt agree."""
    if type(result) is not LedgerRuleApplyExecutionResult:
        raise ValueError("invalid ledger rule apply result")
    projection = result.projection
    _require_rule_result_subject(projection.profile_id, receipt, operation="apply")
    if projection.outcome == "validation_error":
        _require_apply_refusal_receipt(receipt)
        return projection
    _require_apply_success_receipt(receipt, expected_effect=_apply_expected_effect(projection))
    return projection


def _require_apply_refusal_receipt(receipt: OperationTerminalReceipt) -> None:
    if (
        receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.refusal_ref != LEDGER_RULE_VALIDATION_REFUSAL_CODE
        or receipt.refusal_detail_ref is None
        or receipt.effect not in {OperationEffect.NONE, OperationEffect.PARTIAL}
    ):
        raise ValueError("ledger rule apply refusal has an incompatible terminal receipt")


def _apply_expected_effect(projection: LedgerRuleApplyProjection) -> OperationEffect:
    expected_effect = (
        (OperationEffect.UPDATED if projection.bucket_event_count else OperationEffect.NONE)
        if projection.outcome == "applied"
        else OperationEffect.NONE
    )
    return expected_effect


def _require_apply_success_receipt(receipt: OperationTerminalReceipt, *, expected_effect: OperationEffect) -> None:
    if receipt.condition is not OperationTerminalCondition.SUCCEEDED or receipt.effect is not expected_effect:
        raise ValueError("ledger rule apply success has an incompatible terminal receipt")
