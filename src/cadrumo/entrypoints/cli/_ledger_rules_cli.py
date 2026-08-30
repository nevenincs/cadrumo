"""Ledger classification rule CLI command surface.

Rule commands apply, list, and mutate classification rules through
:class:`TransactionCatalogueRepository` for the active bucket.
"""

from __future__ import annotations

import typer

from ...application.ledger.models import ApplyRulesResult
from ...core.external_constants import CLASSIFIED_BY_MANUAL
from ...core.i18n import tr
from ...domain.transactions.classification_rule import LedgerClassificationRule
from ...domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ...domain.transactions.models import Transaction
from ._common import _bad, emit_envelope
from ._common import active_bucket_id_or_refuse as _rule_bucket_id


def _short_display_id(value: str) -> str:
    """Return the 16-char prefix of an id with an ellipsis, for table display."""
    return f"{value[:16]}..."


def _validate_category_id(category_id: str | None) -> str | None:
    if category_id is None:
        return None
    from ...domain.categories.spending_category import SpendingCategory

    value = category_id.strip()
    if not value:
        return None
    if value not in {category.value for category in SpendingCategory}:
        known = ", ".join(category.value for category in SpendingCategory)
        raise _bad(
            tr("cli.ledger.errors.invalid_category", category=value, known=known),
        )
    return value


def rule_add(
    ctx: typer.Context,
    description_pattern: str,
    classification: BusinessClassification,
    category_id: str | None = None,
    priority: int = 100,
    actor: str | None = None,
) -> None:
    """Add or idempotently update a ledger classification rule."""
    from ...application.ledger.actions_classification import add_classification_rule
    from ...core.bucket_pointer import resolve_active_bucket_id

    bucket_id = _rule_bucket_id()
    if not description_pattern.strip():
        # An empty pattern trips the model's ``min_length=1`` as a raw pydantic
        # ValidationError (not a ValueError, so the except below misses it) and a
        # whitespace-only pattern matches nothing useful. Refuse both at the
        # boundary with an instructive message instead of leaking the pydantic repr.
        raise _bad(
            tr("cli.app.ledger.rule.empty_pattern"),
        )
    validated_category_id = _validate_category_id(category_id)
    rule = add_classification_rule(
        bucket_id=bucket_id,
        description_pattern=description_pattern,
        classification=classification,
        category_id=validated_category_id,
        priority=priority,
        actor=actor or resolve_active_bucket_id() or "operator",
    )
    payload = {
        "rule_id": rule.rule_id,
        "description_pattern": rule.description_pattern,
        "classification": rule.classification,
        "category_id": rule.category_id,
        "priority": rule.priority,
        "actor": rule.actor,
        "created_at": rule.created_at,
    }
    lines = [
        f"rule_id\t{_short_display_id(rule.rule_id)}",
        f"pattern\t{rule.description_pattern}",
        f"classification\t{rule.classification.value}",
        f"priority\t{rule.priority}",
    ]
    from ._ledger_payloads import RuleAddResult

    emit_envelope(
        ctx,
        command="ledger.rule.add",
        result=RuleAddResult.model_validate(payload),
        lines=lines,
    )


def _rule_apply_transaction_is_candidate(transaction: Transaction, *, reaffirm: bool) -> bool:
    if transaction.lifecycle_state is not TransactionLifecycleState.ACTIVE:
        return False
    if transaction.business_classification is BusinessClassification.NOT_YET_PROCESSED:
        return True
    return reaffirm and transaction.classified_by == CLASSIFIED_BY_MANUAL


def _first_matching_rule(
    transaction: Transaction,
    rules: tuple[LedgerClassificationRule, ...],
) -> LedgerClassificationRule | None:
    for rule in rules:
        if rule.matches(transaction.raw.description):
            return rule
    return None


def _rule_apply_dry_run_matches(
    *,
    bucket_id: str,
    reaffirm: bool,
) -> list[dict[str, object]]:
    from ...application.ledger.rule_repository import ledger_classification_rule_repository
    from ...application.ledger.transaction_repository import transaction_catalogue_repository

    rule_repo = ledger_classification_rule_repository(bucket_id=bucket_id)
    rules = rule_repo.list_rules()
    tx_repo = transaction_catalogue_repository(bucket_id=bucket_id)
    catalogue = tx_repo.load()
    would_match: list[dict[str, object]] = []
    for transaction in catalogue.transactions.values():
        if not _rule_apply_transaction_is_candidate(transaction, reaffirm=reaffirm):
            continue
        rule = _first_matching_rule(transaction, rules)
        if rule is None:
            continue
        would_match.append(
            {
                "transaction_id": transaction.transaction_id,
                "description": transaction.raw.description,
                "matched_rule_id": rule.rule_id,
                "classification": rule.classification,
            },
        )
    return would_match


def _rule_apply_dry_run_payload(would_match: list[dict[str, object]]) -> dict[str, object]:
    return {"dry_run": True, "would_match": would_match, "count": len(would_match)}


def _rule_apply_dry_run_lines(would_match: list[dict[str, object]]) -> list[str]:
    lines = [
        tr("cli.app.ledger.rule.apply_dry_run_summary", count=len(would_match)),
    ]
    lines.extend(
        f"  match\t{_short_display_id(str(row['transaction_id']))}\t{row['classification']}" for row in would_match
    )
    return lines


def _emit_rule_apply_dry_run(ctx: typer.Context, *, bucket_id: str, reaffirm: bool) -> None:
    from ._ledger_payloads import RuleApplyResult

    would_match = _rule_apply_dry_run_matches(bucket_id=bucket_id, reaffirm=reaffirm)
    emit_envelope(
        ctx,
        command="ledger.rule.apply",
        result=RuleApplyResult.model_validate(_rule_apply_dry_run_payload(would_match)),
        lines=_rule_apply_dry_run_lines(would_match),
    )


def _rule_apply_payload(result: ApplyRulesResult) -> dict[str, object]:
    return {
        "rules_evaluated": result.rules_evaluated,
        "transactions_scanned": result.transactions_scanned,
        "matched": result.matched,
        "skipped_already_classified": result.skipped_already_classified,
        "no_match": result.no_match,
        "applied": [row.model_dump(mode="python") for row in result.applied],
    }


def _rule_apply_lines(result: ApplyRulesResult) -> list[str]:
    lines = [
        tr(
            "cli.app.ledger.rule.apply_summary",
            rules=result.rules_evaluated,
            scanned=result.transactions_scanned,
            matched=result.matched,
            skipped=result.skipped_already_classified,
            no_match=result.no_match,
        ),
    ]
    lines.extend(
        f"  applied\t{_short_display_id(row.transaction_id)}\t{row.classification.value}" for row in result.applied
    )
    return lines


def _emit_rule_apply_result(ctx: typer.Context, result: ApplyRulesResult) -> None:
    from ._ledger_payloads import RuleApplyResult

    emit_envelope(
        ctx,
        command="ledger.rule.apply",
        result=RuleApplyResult.model_validate(_rule_apply_payload(result)),
        lines=_rule_apply_lines(result),
    )


def rule_apply(
    ctx: typer.Context,
    reaffirm: bool = False,
    dry_run: bool = False,
    actor: str | None = None,
) -> None:
    """Apply stored rules to ACTIVE NOT_YET_PROCESSED transactions."""
    from ...application.ledger.actions_classification import apply_classification_rules
    from ...core.bucket_pointer import resolve_active_bucket_id

    bucket_id = _rule_bucket_id()
    resolved_actor = actor or resolve_active_bucket_id() or "operator"

    if dry_run:
        _emit_rule_apply_dry_run(ctx, bucket_id=bucket_id, reaffirm=reaffirm)
        return

    result = apply_classification_rules(
        bucket_id=bucket_id,
        reaffirm=reaffirm,
        actor=resolved_actor,
        source_command="aeat app ledger rule apply",
    )
    _emit_rule_apply_result(ctx, result)


def rule_list(ctx: typer.Context) -> None:
    """List all stored ledger classification rules (priority ascending)."""
    from ...application.ledger.rule_repository import ledger_classification_rule_repository

    bucket_id = _rule_bucket_id()
    rules = ledger_classification_rule_repository(bucket_id=bucket_id).list_rules()
    payload = {
        "rules": [
            {
                "rule_id": r.rule_id,
                "description_pattern": r.description_pattern,
                "classification": r.classification,
                "category_id": r.category_id,
                "priority": r.priority,
                "actor": r.actor,
                "created_at": r.created_at,
            }
            for r in rules
        ],
    }
    lines: list[str] = [tr("cli.app.ledger.rule.list_header")]
    if not rules:
        lines.append(tr("cli.app.ledger.rule.list_empty"))
    for rule in rules:
        lines.append(
            f"{rule.priority}\t{rule.classification.value}\t{rule.description_pattern}\t{_short_display_id(rule.rule_id)}",
        )
    from ._ledger_payloads import RuleListResult

    emit_envelope(
        ctx,
        command="ledger.rule.list",
        result=RuleListResult.model_validate(payload),
        lines=lines,
    )
