"""``aeat app ledger entry-options``: the vocabularies a ledger entry form offers."""

from __future__ import annotations

from uuid import UUID

import typer

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_errors import invalid_completion_error

from ...application.ledger.entry_options_operation import (
    LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
    LedgerEntryOptionsProjection,
    LedgerEntryOptionsRequest,
)
from ...core.bucket_pointer import require_active_bucket_id
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as active_output_language
from ...core.i18n.render import tr
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import emit_envelope
from .ledger_results import LedgerEntryOptionsResult


def entry_options(ctx: typer.Context) -> None:
    """Show each vocabulary an entry form offers, each value with its word where it has one."""
    client = require_profile_client(ctx, expected_profile_id=UUID(require_active_bucket_id()))
    completed = run_registered_operation(
        client,
        LedgerEntryOptionsRequest(
            profile_id=client.profile_id, output_language=OutputLanguage(active_output_language())
        ),
        definition_id=LEDGER_ENTRY_OPTIONS_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=LedgerEntryOptionsProjection,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=False,
    )
    _require_correlated_completion(completed, profile_id=client.profile_id)
    result = LedgerEntryOptionsResult.model_validate(
        completed.projection.model_dump(mode="json", exclude={"profile_id"})
    )
    emit_envelope(
        ctx,
        command="ledger.entry-options",
        result=result,
        lines=_entry_option_lines(result),
    )


def _require_correlated_completion(
    completed: RegisteredOperationCompletion[LedgerEntryOptionsProjection],
    *,
    profile_id: UUID,
) -> None:
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or completed.projection.profile_id != profile_id
    ):
        raise invalid_completion_error(completed)


def _entry_option_lines(result: LedgerEntryOptionsResult) -> tuple[str, ...]:
    options = (
        f"{family.family}	{option.value}" + _option_label_column(option.label_key)
        for family in result.families
        for option in family.options
    )
    classifications = (
        f"classification	{row.classification}	{row.takes_business_share}	{row.takes_usage_ratio}"
        f"	{row.carries_business_figures}	{row.keeps_category}"
        f"	{row.rule_may_name_category}	{row.split_part_requires_category}"
        for row in result.classifications
    )
    limits = (f"limit	{rule.rule}	{rule.decimals}	{rule.zero}" for rule in result.limits.decimal_rules)
    return (f"default_currency	{result.default_currency}", *options, *classifications, *limits)


def _option_label_column(label_key: str | None) -> str:
    return f"	{tr(label_key)}" if label_key is not None and label_key != "" else ""


__all__ = ["entry_options"]
