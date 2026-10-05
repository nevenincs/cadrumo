"""CLI presentation for registered ledger classification-rule operations."""

from __future__ import annotations

from typing import Never
from uuid import UUID

import typer
from pydantic import BaseModel

from ...application.ledger.rule_contracts import (
    LedgerRuleAddProjection,
    LedgerRuleAddRequest,
    LedgerRuleApplyProjection,
    LedgerRuleApplyRequest,
    LedgerRuleListRequest,
)
from ...core.i18n.render import tr
from ...domain.transactions.enums import BusinessClassification
from .common import active_bucket_id_or_refuse, emit_envelope
from .errors import CliRefusedBoundaryError
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_ledger_rules import submit_ledger_rule_add, submit_ledger_rule_apply, submit_ledger_rule_list


def _short_display_id(value: str) -> str:
    """Return the 16-char prefix of an id, as the existing text table does."""
    return f"{value[:16]}..."


def _refusal_context[ProjectionT: BaseModel](
    completed: RegisteredOperationCompletion[ProjectionT],
) -> dict[str, str]:
    """Retain the operation identity and the observed terminal receipt on CLI refusal."""
    return {
        "operation_id": str(completed.operation_id),
        "terminal_condition": completed.terminal_condition.value,
        "effect": completed.effect.value,
        "refusal_code": completed.refusal_code or "",
    }


def _raise_add_refusal(
    completed: RegisteredOperationCompletion[LedgerRuleAddProjection],
    *,
    category_id: str | None,
) -> Never:
    projection = completed.projection
    context = _refusal_context(completed)
    if projection.validation_code == "empty_pattern":
        raise CliRefusedBoundaryError(
            translated_message="cli.app.ledger.rule.empty_pattern",
            context=context,
        )
    if projection.validation_code == "category":
        context.update(
            {
                "category": category_id or "",
                "example": projection.category_example or "",
            }
        )
        raise CliRefusedBoundaryError(
            translated_message="cli.ledger.errors.unknown_category",
            context=context,
        )
    context["details"] = "; ".join(projection.validation_messages) or tr(
        "cli.ledger.errors.command_input_invalid_fallback"
    )
    raise CliRefusedBoundaryError(
        translated_message="cli.ledger.errors.command_input_invalid",
        context=context,
    )


def _raise_apply_refusal(
    completed: RegisteredOperationCompletion[LedgerRuleApplyProjection],
) -> Never:
    context = _refusal_context(completed)
    context["details"] = "; ".join(completed.projection.validation_messages) or tr(
        "cli.ledger.errors.command_input_invalid_fallback"
    )
    raise CliRefusedBoundaryError(
        translated_message="cli.ledger.errors.command_input_invalid",
        context=context,
    )


def rule_add(
    ctx: typer.Context,
    description_pattern: str,
    classification: BusinessClassification,
    category_id: str | None = None,
    priority: int = 100,
    actor: str | None = None,
) -> None:
    """Add or idempotently update a ledger classification rule."""
    profile_id = UUID(active_bucket_id_or_refuse())
    request = LedgerRuleAddRequest(
        profile_id=profile_id,
        description_pattern=description_pattern,
        classification=classification,
        category_id=category_id,
        priority=priority,
        actor=actor,
    )
    completed = submit_ledger_rule_add(ctx, request)
    projection = completed.projection
    if projection.outcome == "validation_error":
        _raise_add_refusal(completed, category_id=category_id)
    rule = projection.rule
    if rule is None:
        raise invalid_completion_error(completed)
    from ._ledger_rule_payloads import RuleAddResult

    result = RuleAddResult.model_validate(rule.model_dump(mode="python"))
    lines = [
        f"rule_id\t{_short_display_id(rule.rule_id)}",
        f"pattern\t{rule.description_pattern}",
        f"classification\t{rule.classification.value}",
        f"priority\t{rule.priority}",
    ]
    emit_envelope(ctx, command="ledger.rule.add", result=result, lines=lines)


def _rule_apply_dry_run_lines(projection: LedgerRuleApplyProjection) -> list[str]:
    """Render the same ordered description-free preview table as the old CLI."""
    matches = projection.would_match or ()
    lines = [tr("cli.app.ledger.rule.apply_dry_run_summary", count=len(matches))]
    lines.extend(f"  match\t{_short_display_id(row.transaction_id)}\t{row.classification.value}" for row in matches)
    return lines


def _rule_apply_result_data(projection: LedgerRuleApplyProjection) -> dict[str, object]:
    """Map the complete worker projection onto the established CLI result shape."""
    if projection.outcome == "dry_run":
        return {
            "dry_run": projection.dry_run,
            "would_match": [row.model_dump(mode="python") for row in projection.would_match or ()],
            "count": projection.count,
        }
    return {
        "rules_evaluated": projection.rules_evaluated,
        "transactions_scanned": projection.transactions_scanned,
        "matched": projection.matched,
        "skipped_already_classified": projection.skipped_already_classified,
        "no_match": projection.no_match,
        "applied": [row.model_dump(mode="python") for row in projection.applied or ()],
    }


def _rule_apply_lines(projection: LedgerRuleApplyProjection) -> list[str]:
    if projection.outcome == "dry_run":
        return _rule_apply_dry_run_lines(projection)
    lines = [
        tr(
            "cli.app.ledger.rule.apply_summary",
            rules=projection.rules_evaluated,
            scanned=projection.transactions_scanned,
            matched=projection.matched,
            skipped=projection.skipped_already_classified,
            no_match=projection.no_match,
        ),
    ]
    lines.extend(
        f"  applied\t{_short_display_id(row.transaction_id)}\t{row.classification.value}"
        for row in projection.applied or ()
    )
    return lines


def rule_apply(
    ctx: typer.Context,
    reaffirm: bool = False,
    dry_run: bool = False,
    actor: str | None = None,
) -> None:
    """Apply stored rules to ACTIVE NOT_YET_PROCESSED transactions."""
    profile_id = UUID(active_bucket_id_or_refuse())
    completed = submit_ledger_rule_apply(
        ctx,
        LedgerRuleApplyRequest(
            profile_id=profile_id,
            reaffirm=reaffirm,
            dry_run=dry_run,
            actor=actor,
        ),
    )
    projection = completed.projection
    if projection.outcome == "validation_error":
        _raise_apply_refusal(completed)

    from ._ledger_rule_payloads import RuleApplyResult

    emit_envelope(
        ctx,
        command="ledger.rule.apply",
        result=RuleApplyResult.model_validate(_rule_apply_result_data(projection)),
        lines=_rule_apply_lines(projection),
    )


def rule_list(ctx: typer.Context) -> None:
    """List all stored ledger classification rules (priority ascending)."""
    from ._ledger_rule_payloads import RuleListResult

    profile_id = UUID(active_bucket_id_or_refuse())
    completed = submit_ledger_rule_list(ctx, LedgerRuleListRequest(profile_id=profile_id))
    projection = completed.projection
    result = RuleListResult.model_validate({"rules": [rule.model_dump(mode="python") for rule in projection.rules]})
    lines: list[str] = [tr("cli.app.ledger.rule.list_header")]
    if not projection.rules:
        lines.append(tr("cli.app.ledger.rule.list_empty"))
    lines.extend(
        f"{rule.priority}\t{rule.classification.value}\t{rule.description_pattern}\t{_short_display_id(rule.rule_id)}"
        for rule in projection.rules
    )
    emit_envelope(ctx, command="ledger.rule.list", result=result, lines=lines)


__all__ = ["rule_add", "rule_apply", "rule_list"]
