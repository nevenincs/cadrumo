"""``aeat app ledger entry-options``: the vocabularies a ledger entry form offers."""

from __future__ import annotations

from uuid import UUID

import typer

from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.commands.registered_operation import run_registered_operation
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
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.NONE
        or completed.refusal_code is not None
        or completed.projection.profile_id != client.profile_id
    ):
        raise invalid_completion_error(completed)
    result = LedgerEntryOptionsResult.model_validate(
        completed.projection.model_dump(mode="json", exclude={"profile_id"})
    )
    options = (
        f"{family.family}\t{option.value}"
        + (f"\t{tr(option.label_key)}" if option.label_key is not None and option.label_key != "" else "")
        for family in result.families
        for option in family.options
    )
    classifications = (
        f"classification\t{row.classification}\t{row.takes_business_share}\t{row.takes_usage_ratio}"
        f"\t{row.carries_business_figures}\t{row.keeps_category}"
        f"\t{row.rule_may_name_category}\t{row.split_part_requires_category}"
        for row in result.classifications
    )
    limits = (f"limit\t{rule.rule}\t{rule.decimals}\t{rule.zero}" for rule in result.limits.decimal_rules)
    emit_envelope(
        ctx,
        command="ledger.entry-options",
        result=result,
        lines=(f"default_currency\t{result.default_currency}", *options, *classifications, *limits),
    )


__all__ = ["entry_options"]
