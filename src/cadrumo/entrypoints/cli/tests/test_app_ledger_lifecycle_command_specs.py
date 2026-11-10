"""Literal and resolution contracts for ledger lifecycle command specs."""

from __future__ import annotations

from typing import Final

import pytest

from ..app_ledger_lifecycle_command_specs import LEDGER_LIFECYCLE_COMMAND_SPECS
from ..command_specs import COMMAND_GRAPH
from .ledger_command_spec_matrix import (
    EMPTY_DEFAULT,
    EMPTY_TUPLE_DEFAULT,
    FALSE_DEFAULT,
    GROUP_INVOCATION_CONTRACT,
    NO_RESULT_SCHEMA_CONTRACT,
    NON_BLANK_CONSTRAINT_CONTRACT,
    NONE_DEFAULT,
    TARGET,
    ExpectedCommand,
    assert_live_targets_match_expected,
    expected_argument,
    expected_command,
    expected_option,
    expected_result_schema,
    literal_contract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


_EXPECTED_LIFECYCLE_COMMANDS: Final[tuple[ExpectedCommand, ...]] = (
    expected_command(
        "app_ledger_remove",
        "app_ledger",
        "remove",
        "leaf",
        "cli.ledger.remove.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_remove",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerRemoveResult", "ledger.remove"),
        (
            expected_argument("transaction_id", "cli.ledger.remove.id_help", constraint=NON_BLANK_CONSTRAINT_CONTRACT),
            expected_option("reason", "--reason", "cli.ledger.remove.reason_help", default=EMPTY_DEFAULT),
            expected_option(
                "dry_run",
                "--dry-run",
                "cli.ledger.remove.dry_run_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option(
                "yes",
                "--yes",
                "cli.ledger.remove.yes_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option("actor", "--actor", "cli.ledger.add.actor_help"),
        ),
    ),
    expected_command(
        "app_ledger_reset",
        "app_ledger",
        "reset",
        "leaf",
        "cli.ledger.reset.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_reset",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerResetResult", "ledger.reset"),
        (
            expected_option("reason", "--reason", "cli.ledger.reset.reason_help", default=EMPTY_DEFAULT),
            expected_option(
                "dry_run",
                "--dry-run",
                "cli.ledger.reset.dry_run_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option(
                "yes",
                "--yes",
                "cli.ledger.reset.yes_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option("actor", "--actor", "cli.ledger.add.actor_help"),
        ),
    ),
    expected_command(
        "app_ledger_restore",
        "app_ledger",
        "restore",
        "leaf",
        "cli.ledger.restore.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_restore",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerRestoreResult", "ledger.restore"),
        (
            expected_argument("transaction_id", "cli.ledger.restore.id_help", constraint=NON_BLANK_CONSTRAINT_CONTRACT),
            expected_option("reason", "--reason", "cli.ledger.archive.reason_help", default=EMPTY_DEFAULT),
            expected_option(
                "yes",
                "--yes",
                "cli.ledger.restore.yes_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option("actor", "--actor", "cli.ledger.add.actor_help"),
        ),
    ),
    expected_command(
        "app_ledger_review",
        "app_ledger",
        "review",
        "leaf",
        "cli.ledger.review.help",
        "none",
        "cadrumo.entrypoints.cli.ledger_review_commands:ledger_review",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerReviewResult", "ledger.review"),
        (
            expected_argument(
                "record_id",
                "cli.ledger.view.transaction_id_help",
                default=NONE_DEFAULT,
                constraint=NON_BLANK_CONSTRAINT_CONTRACT,
            ),
            expected_option(
                "filters", "--filter", "cli.ledger.review.filter_help", default=EMPTY_TUPLE_DEFAULT, multiple=True
            ),
            expected_option(
                "verbose",
                "--verbose",
                "cli.ledger.review.verbose_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
        ),
    ),
    expected_command(
        "app_ledger_rule",
        "app_ledger",
        "rule",
        "group",
        "cli.app.ledger.rule.group_help",
        "none",
        None,
        NO_RESULT_SCHEMA_CONTRACT,
        invocation=GROUP_INVOCATION_CONTRACT,
    ),
    expected_command(
        "app_ledger_split",
        "app_ledger",
        "split",
        "leaf",
        "cli.ledger.split.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_split",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerSplitResult", "ledger.split"),
        (
            expected_argument("transaction_id", "cli.ledger.split.id_help", constraint=NON_BLANK_CONSTRAINT_CONTRACT),
            expected_option(
                "child_amount",
                "--child-amount",
                "cli.ledger.split.child_amount_help",
                default=EMPTY_TUPLE_DEFAULT,
                multiple=True,
            ),
            expected_option(
                "child_description",
                "--child-description",
                "cli.ledger.split.child_description_help",
                default=EMPTY_TUPLE_DEFAULT,
                multiple=True,
            ),
            expected_option(
                "llm",
                "--llm",
                "cli.ledger.split.llm_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option(
                "apply",
                "--apply",
                "cli.ledger.split.apply_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option(
                "read_evidence",
                "--read-evidence",
                "cli.ledger.split.read_evidence_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option("reason", "--reason", "cli.ledger.merge.reason_help", default=EMPTY_DEFAULT),
            expected_option(
                "yes",
                "--yes",
                "cli.ledger.split.yes_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option("actor", "--actor", "cli.ledger.split.actor_help"),
        ),
    ),
    expected_command(
        "app_ledger_stash",
        "app_ledger",
        "stash",
        "leaf",
        "cli.ledger.stash.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_stash",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerStashResult", "ledger.stash"),
        (
            expected_argument("transaction_id", "cli.ledger.stash.id_help", constraint=NON_BLANK_CONSTRAINT_CONTRACT),
            expected_option("reason", "--reason", "cli.ledger.archive.reason_help", default=EMPTY_DEFAULT),
            expected_option(
                "yes",
                "--yes",
                "cli.ledger.stash.yes_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option("actor", "--actor", "cli.ledger.add.actor_help"),
        ),
    ),
    expected_command(
        "app_ledger_status",
        "app_ledger",
        "status",
        "leaf",
        "cli.ledger.status.help",
        "none",
        "cadrumo.entrypoints.cli.ledger_read_commands:ledger_status",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerStatusResult", "ledger.status"),
        (
            expected_option("period", "--period", "cli.ledger.export.period_help"),
            expected_option("year", "--year", "cli.ledger.check.year_help", annotation="builtins:int"),
        ),
    ),
    expected_command(
        "app_ledger_track",
        "app_ledger",
        "track",
        "leaf",
        "cli.ledger.track.help",
        "none",
        "cadrumo.entrypoints.cli.ledger_read_commands:ledger_track",
        expected_result_schema(
            TARGET, "cadrumo.entrypoints.cli.ledger_participation_results:LedgerTrackResult", "ledger.track"
        ),
        (
            expected_argument(
                "transaction_id", "cli.ledger.track.transaction_id_help", constraint=NON_BLANK_CONSTRAINT_CONTRACT
            ),
        ),
    ),
    expected_command(
        "app_ledger_update",
        "app_ledger",
        "update",
        "leaf",
        "cli.ledger.update.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_commands:ledger_update",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerUpdateResult", "ledger.update"),
        (
            expected_argument("transaction_id", "cli.ledger.update.id_help", constraint=NON_BLANK_CONSTRAINT_CONTRACT),
            expected_option("booked_date", "--date", "cli.ledger.update.date_help"),
            expected_option("value_date", "--value-date", "cli.ledger.update.value_date_help"),
            expected_option("operation_date", "--operation-date", "cli.ledger.update.operation_date_help"),
            expected_option("accrual_date", "--accrual-date", "cli.ledger.update.accrual_date_help"),
            expected_option("amount", "--amount", "cli.ledger.update.amount_help"),
            expected_option(
                "direction",
                "--direction",
                "cli.ledger.update.direction_help",
                annotation="cadrumo.domain.transactions.enums:TransactionDirection",
            ),
            expected_option("currency", "--currency", "cli.ledger.update.currency_help"),
            expected_option("counterparty", "--counterparty", "cli.ledger.update.counterparty_help"),
            expected_option("description", "--description", "cli.ledger.update.description_help"),
            expected_option("taxable_base", "--taxable-base", "cli.ledger.update.taxable_base_help"),
            expected_option("iva_rate", "--iva-rate", "cli.ledger.update.iva_rate_help"),
            expected_option("iva_amount", "--iva-amount", "cli.ledger.update.iva_amount_help"),
            expected_option(
                "irpf_category",
                "--irpf-category",
                "cli.ledger.update.irpf_category_help",
                value_hooks=("cadrumo.entrypoints.cli.common:IRPF_CATEGORY_CHOICE", None, None, None),
            ),
            expected_option("notes", "--notes", "cli.ledger.update.notes_help"),
            expected_option("group", "--group", "cli.ledger.update.group_help"),
            expected_option("account", "--account", "cli.ledger.update.account_help"),
            expected_option("actor", "--actor", "cli.ledger.add.actor_help"),
        ),
    ),
    expected_command(
        "app_ledger_view",
        "app_ledger",
        "view",
        "leaf",
        "cli.ledger.view.help",
        "none",
        "cadrumo.entrypoints.cli.ledger_read_commands:ledger_view",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerViewResult", "ledger.view"),
        (
            expected_argument(
                "transaction_id", "cli.ledger.view.transaction_id_help", constraint=NON_BLANK_CONSTRAINT_CONTRACT
            ),
        ),
    ),
)


def test_ledger_lifecycle_keeps_its_literal_contract_matrix() -> None:
    """Lifecycle command identity, hierarchy, dispatch, and nested fields remain literal."""
    assert tuple(literal_contract(spec) for spec in LEDGER_LIFECYCLE_COMMAND_SPECS) == _EXPECTED_LIFECYCLE_COMMANDS


def test_ledger_lifecycle_resolves_through_the_live_graph() -> None:
    """Every lifecycle command resolves its graph path and exact deferred targets."""
    for spec, expected in zip(LEDGER_LIFECYCLE_COMMAND_SPECS, _EXPECTED_LIFECYCLE_COMMANDS, strict=True):
        assert COMMAND_GRAPH.resolve_path(("aeat", "app", "ledger", spec.token)) is spec
        assert_live_targets_match_expected(spec, expected)
