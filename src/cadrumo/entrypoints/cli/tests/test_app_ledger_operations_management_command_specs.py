"""Literal and resolution contracts for ledger operations and management specs."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

import pytest

from cadrumo_client.commands.shared_contracts import TranslationKey
from cadrumo_client.commands.spec import CommandSpec

from ..app_ledger_command_spec_support import (
    EVIDENCE_ACTOR_OPTION,
    EVIDENCE_TRANSACTION_ID_ARGUMENT,
    GROUP_INVOCATION,
    LEAF_INVOCATION,
    LEDGER_ACTOR_OPTION,
    MERGE_REASON_OPTION,
    NO_RESULT_SCHEMA,
    OPTIONAL_PERIOD_OPTION,
    OPTIONAL_YEAR_OPTION,
)
from ..app_ledger_lifecycle_command_specs import LEDGER_LIFECYCLE_COMMAND_SPECS
from ..app_ledger_management_command_specs import LEDGER_MANAGEMENT_COMMAND_SPECS
from ..app_ledger_operations_command_specs import LEDGER_OPERATIONS_COMMAND_SPECS
from ..command_specs import COMMAND_GRAPH
from .ledger_command_spec_matrix import (
    DEFAULT_CONSTRAINT,
    EMPTY_DEFAULT,
    EMPTY_TUPLE_DEFAULT,
    FALSE_DEFAULT,
    GROUP_INVOCATION_CONTRACT,
    NO_RESULT_SCHEMA_CONTRACT,
    NON_BLANK_CONSTRAINT_CONTRACT,
    NONE_DEFAULT,
    REQUIRED_DEFAULT,
    TARGET,
    ExpectedCommand,
    assert_live_targets_match_expected,
    expected_argument,
    expected_command,
    expected_option,
    expected_result_schema,
    literal_contract,
    parameter_contract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


_STDIN_CHANNEL: Final = "stdin"
_FD_CHANNEL: Final = "file-descriptor"

_MINIMUM_ONE_CONSTRAINT: Final[tuple[object, ...]] = (1, *DEFAULT_CONSTRAINT[1:])
_MINIMUM_ZERO_CONSTRAINT: Final[tuple[object, ...]] = (0, *DEFAULT_CONSTRAINT[1:])
_EXISTING_PATH_CONSTRAINT: Final[tuple[object, ...]] = (*DEFAULT_CONSTRAINT[:4], True, *DEFAULT_CONSTRAINT[5:])
_EXISTING_FILE_CONSTRAINT: Final[tuple[object, ...]] = (
    *DEFAULT_CONSTRAINT[:4],
    True,
    True,
    False,
    *DEFAULT_CONSTRAINT[7:],
)

_LOCAL_IN_FILE_PRIMARY_TRANSPORT: Final[tuple[str, ...]] = ("local_in", "file", "primary")
_LOCAL_IN_FILE_AUXILIARY_TRANSPORT: Final[tuple[str, ...]] = ("local_in", "file", "auxiliary")
_LOCAL_OUT_FILE_PRIMARY_TRANSPORT: Final[tuple[str, ...]] = ("local_out", "file", "primary")

_CSV_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", "csv", None)
_ASC_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", "asc", None)
_HALF_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", 0.5, None)

_PARTICIPATION_INVOCATION_CONTRACT: Final[tuple[object, ...]] = (
    True,
    False,
    False,
    True,
    False,
    False,
    "ctx",
    "executable",
)


def _graph_path(spec: CommandSpec) -> tuple[str, ...]:
    if spec.parent_key == "app_ledger_evidence":
        return ("aeat", "app", "ledger", "evidence", spec.token)
    return ("aeat", "app", "ledger", spec.token)


_EXPECTED_COMMANDS: Final[tuple[ExpectedCommand, ...]] = (
    expected_command(
        "app_ledger_counterparty",
        "app_ledger",
        "counterparty",
        "group",
        "cli.app.ledger.counterparty.group_help",
        "none",
        None,
        NO_RESULT_SCHEMA_CONTRACT,
        invocation=GROUP_INVOCATION_CONTRACT,
    ),
    expected_command(
        "app_ledger_detach",
        "app_ledger",
        "detach",
        "leaf",
        "cli.ledger.detach.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_detach",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerDetachResult", "ledger.detach"),
        (
            expected_argument("transaction_id", "cli.ledger.detach.id_help", constraint=NON_BLANK_CONSTRAINT_CONTRACT),
            expected_option(
                "attachment_ids",
                "--attachment-id",
                "cli.ledger.detach.attachment_help",
                default=EMPTY_TUPLE_DEFAULT,
                multiple=True,
                constraint=NON_BLANK_CONSTRAINT_CONTRACT,
            ),
            expected_option("actor", "--actor", "cli.ledger.detach.actor_help"),
        ),
    ),
    expected_command(
        "app_ledger_evidence",
        "app_ledger",
        "evidence",
        "group",
        "cli.app.ledger.evidence.group_help",
        "none",
        None,
        NO_RESULT_SCHEMA_CONTRACT,
        invocation=GROUP_INVOCATION_CONTRACT,
    ),
    expected_command(
        "app_ledger_exclude",
        "app_ledger",
        "exclude",
        "leaf",
        "cli.ledger.exclude.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_exclude",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerExcludeResult", "ledger.exclude"),
        (
            expected_argument(
                "transaction_id", "cli.app.ledger.evidence.pull_id_help", constraint=NON_BLANK_CONSTRAINT_CONTRACT
            ),
            expected_option("reason", "--reason", "cli.ledger.exclude.reason_help", default=EMPTY_DEFAULT),
            expected_option(
                "yes",
                "--yes",
                "cli.ledger.exclude.yes_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option("actor", "--actor", "cli.app.ledger.evidence.pull_actor_help"),
        ),
    ),
    expected_command(
        "app_ledger_export",
        "app_ledger",
        "export",
        "leaf",
        "cli.ledger.export.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_export_commands:ledger_export",
        expected_result_schema(
            TARGET, "cadrumo.entrypoints.cli.ledger_interchange_results:LedgerExportPayload", "ledger.export"
        ),
        (
            expected_option(
                "output",
                "--output",
                "cli.ledger.export.output_help",
                annotation="pathlib:Path",
                default=REQUIRED_DEFAULT,
                transport=_LOCAL_OUT_FILE_PRIMARY_TRANSPORT,
            ),
            expected_option(
                "export_kind",
                "--export-format",
                "cli.ledger.export.format_help",
                annotation="cadrumo.application.export.tabular:ExportSerializationFormat",
                default=_CSV_DEFAULT,
            ),
            expected_option(
                "include_inactive",
                "--include-inactive",
                "cli.ledger.export.include_inactive_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option("period", "--period", "cli.ledger.export.period_help"),
            expected_option("year", "--year", "cli.ledger.check.year_help", annotation="builtins:int"),
            expected_option("actor", "--actor", "cli.ledger.add.actor_help"),
        ),
    ),
    expected_command(
        "app_ledger_history",
        "app_ledger",
        "history",
        "leaf",
        "cli.ledger.history.help",
        "none",
        "cadrumo.entrypoints.cli.ledger_read_commands:ledger_history",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerHistoryResult", "ledger.history"),
        (
            expected_argument("transaction_id", "cli.ledger.history.id_help", constraint=NON_BLANK_CONSTRAINT_CONTRACT),
            expected_option(
                "include_split_siblings",
                "--include-split-siblings",
                "cli.ledger.history.include_split_siblings_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
        ),
    ),
    expected_command(
        "app_ledger_import",
        "app_ledger",
        "import",
        "leaf",
        "cli.ledger.import.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_import_commands:ledger_import",
        expected_result_schema(
            TARGET, "cadrumo.entrypoints.cli.ledger_interchange_results:LedgerImportPayload", "ledger.import"
        ),
        (
            expected_option(
                "file",
                "--file",
                "cli.ledger.import.file_help",
                annotation="pathlib:Path",
                default=REQUIRED_DEFAULT,
                constraint=_EXISTING_PATH_CONSTRAINT,
                transport=_LOCAL_IN_FILE_PRIMARY_TRANSPORT,
            ),
            expected_option(
                "provider",
                "--provider",
                "cli.ledger.import.provider_help",
                annotation="cadrumo.application.ledger.actions_import:LedgerProviderID",
                default=REQUIRED_DEFAULT,
            ),
            expected_option(
                "dry_run",
                "--dry-run",
                "cli.ledger.import.dry_run_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option(
                "verify",
                "--verify",
                "cli.ledger.import.verify_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option(
                "verify_source",
                "--verify-source",
                "cli.ledger.import.verify_source_help",
                annotation="pathlib:Path",
                constraint=_EXISTING_FILE_CONSTRAINT,
                transport=_LOCAL_IN_FILE_AUXILIARY_TRANSPORT,
            ),
            expected_option(
                "verbose",
                "--verbose",
                "cli.ledger.import.verbose_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option("period", "--period", "cli.ledger.import.period_help"),
            expected_option("year", "--year", "cli.ledger.import.year_help", annotation="builtins:int"),
            expected_option("account", "--account", "cli.ledger.import.account_help"),
        ),
    ),
    expected_command(
        "app_ledger_inventory",
        "app_ledger",
        "inventory",
        "group",
        "cli.app.ledger.inventory.group_help",
        "none",
        None,
        NO_RESULT_SCHEMA_CONTRACT,
        invocation=GROUP_INVOCATION_CONTRACT,
    ),
    expected_command(
        "app_ledger_invoice",
        "app_ledger",
        "invoice",
        "group",
        "cli.app.ledger.invoice.group_help",
        "none",
        None,
        NO_RESULT_SCHEMA_CONTRACT,
        invocation=GROUP_INVOCATION_CONTRACT,
    ),
    expected_command(
        "app_ledger_link",
        "app_ledger",
        "link",
        "leaf",
        "cli.ledger.link.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_commands:ledger_link",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerLinkResult", "ledger.link"),
        (
            expected_argument("transaction_id", "cli.ledger.link.id_help", constraint=NON_BLANK_CONSTRAINT_CONTRACT),
            expected_option(
                "invoice_id",
                "--invoice-id",
                "cli.ledger.link.invoice_id_help",
                default=REQUIRED_DEFAULT,
                constraint=NON_BLANK_CONSTRAINT_CONTRACT,
            ),
            expected_option("actor", "--by", "cli.ledger.link.actor_help"),
        ),
    ),
    expected_command(
        "app_ledger_list",
        "app_ledger",
        "list",
        "leaf",
        "cli.ledger.list.help",
        "none",
        "cadrumo.entrypoints.cli.ledger_read_commands:ledger_list",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerListResult", "ledger.list"),
        (
            expected_option(
                "filters", "--filter", "cli.ledger.list.filter_help", default=EMPTY_TUPLE_DEFAULT, multiple=True
            ),
            expected_option("period", "--period", "cli.ledger.export.period_help"),
            expected_option("year", "--year", "cli.ledger.check.year_help", annotation="builtins:int"),
            expected_option(
                "limit",
                "--limit",
                "cli.ledger.list.limit_help",
                annotation="builtins:int",
                constraint=_MINIMUM_ONE_CONSTRAINT,
            ),
            expected_option(
                "offset",
                "--offset",
                "cli.ledger.list.offset_help",
                annotation="builtins:int",
                default=("LITERAL", 0, None),
                constraint=_MINIMUM_ZERO_CONSTRAINT,
            ),
            expected_option("group", "--group", "cli.ledger.list.group_filter_help"),
            expected_option(
                "by_group",
                "--by-group",
                "cli.ledger.list.by_group_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option(
                "sort_by",
                "--sort-by",
                "cli.ledger.list.sort_by_help",
                annotation="cadrumo.core.ledger_sort:LedgerSortField",
            ),
            expected_option(
                "sort_order",
                "--sort-order",
                "cli.ledger.list.sort_order_help",
                annotation="cadrumo.core.ledger_sort:LedgerSortOrder",
                default=_ASC_DEFAULT,
            ),
            expected_option(
                "hide_llm_rejected",
                "--hide-llm-rejected",
                "cli.ledger.list.hide_llm_rejected_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option("account", "--account", "cli.ledger.list.account_help"),
        ),
    ),
    expected_command(
        "app_ledger_llm_diagnostics",
        "app_ledger",
        "llm-diagnostics",
        "leaf",
        "cli.ledger.llm_diagnostics.help",
        "none",
        "cadrumo.entrypoints.cli.ledger_read_commands:ledger_llm_diagnostics",
        expected_result_schema(
            TARGET,
            "cadrumo.entrypoints.cli.ledger_rule_results:LedgerLlmDiagnosticsResult",
            "ledger.llm_diagnostics",
        ),
        (
            expected_option("since", "--since", "cli.ledger.llm_diagnostics.since_help"),
            expected_option("until", "--until", "cli.ledger.llm_diagnostics.until_help"),
            expected_option(
                "low_confidence_below",
                "--low-confidence-below",
                "cli.ledger.llm_diagnostics.threshold_help",
                annotation="builtins:float",
                default=_HALF_DEFAULT,
            ),
        ),
    ),
    expected_command(
        "app_ledger_merge",
        "app_ledger",
        "merge",
        "leaf",
        "cli.ledger.merge.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_merge",
        expected_result_schema(TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerMergeResult", "ledger.merge"),
        (
            expected_option(
                "child_id", "--child-id", "cli.ledger.merge.child_id_help", default=EMPTY_TUPLE_DEFAULT, multiple=True
            ),
            expected_option("reason", "--reason", "cli.ledger.merge.reason_help", default=EMPTY_DEFAULT),
            expected_option(
                "yes",
                "--yes",
                "cli.ledger.merge.yes_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            expected_option("actor", "--actor", "cli.ledger.merge.actor_help"),
        ),
    ),
    expected_command(
        "app_ledger_entry_options",
        "app_ledger",
        "entry-options",
        "leaf",
        "cli.ledger.entry_options_help",
        "none",
        "cadrumo.entrypoints.cli.entry_options_commands:entry_options",
        expected_result_schema(
            TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerEntryOptionsResult", "ledger.entry-options"
        ),
    ),
    expected_command(
        "app_ledger_split_check",
        "app_ledger",
        "split-check",
        "leaf",
        "cli.ledger.split_check_help",
        "none",
        "cadrumo.entrypoints.cli.split_check_commands:split_check",
        expected_result_schema(
            TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerSplitCheckEnvelope", "ledger.split-check"
        ),
        parameters=(
            expected_argument(
                "transaction_id", "cli.ledger.split_check_id_help", constraint=NON_BLANK_CONSTRAINT_CONTRACT
            ),
            expected_option(
                "secrets_stdin",
                "--secrets-stdin",
                "cli.config.custody.secrets_stdin_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
                machine_secret_channel=_STDIN_CHANNEL,
            ),
            expected_option(
                "secrets_fd",
                "--secrets-fd",
                "cli.config.custody.secrets_fd_help",
                annotation="builtins:int",
                default=NONE_DEFAULT,
                machine_secret_channel=_FD_CHANNEL,
            ),
        ),
    ),
    expected_command(
        "app_ledger_staged_check",
        "app_ledger",
        "staged-check",
        "leaf",
        "cli.ledger.staged_check_help",
        "none",
        "cadrumo.entrypoints.cli.staged_check_commands:staged_check",
        expected_result_schema(
            TARGET, "cadrumo.entrypoints.cli.ledger_results:LedgerStagedCheckEnvelope", "ledger.staged-check"
        ),
        parameters=(
            expected_option(
                "category",
                "--category",
                "cli.ledger.staged_check_category_help",
                default=EMPTY_TUPLE_DEFAULT,
                multiple=True,
            ),
            expected_option(
                "secrets_stdin",
                "--secrets-stdin",
                "cli.config.custody.secrets_stdin_help",
                annotation="builtins:bool",
                default=FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
                machine_secret_channel=_STDIN_CHANNEL,
            ),
            expected_option(
                "secrets_fd",
                "--secrets-fd",
                "cli.config.custody.secrets_fd_help",
                annotation="builtins:int",
                default=NONE_DEFAULT,
                machine_secret_channel=_FD_CHANNEL,
            ),
        ),
    ),
    expected_command(
        "app_ledger_participation",
        "app_ledger",
        "participation",
        "group",
        "cli.ledger.participation.help",
        "none",
        "cadrumo.entrypoints.cli.participation_commands:participation_lookup",
        expected_result_schema(
            TARGET,
            "cadrumo.entrypoints.cli.ledger_participation_results:LedgerTransactionParticipationPayload",
            "ledger.participation",
        ),
        (
            expected_argument(
                "transaction_id",
                "cli.ledger.participation.transaction_id_help",
                default=NONE_DEFAULT,
                constraint=NON_BLANK_CONSTRAINT_CONTRACT,
            ),
        ),
        invocation=_PARTICIPATION_INVOCATION_CONTRACT,
    ),
    expected_command(
        "app_ledger_preflight",
        "app_ledger",
        "preflight",
        "leaf",
        "cli.ledger.preflight.help",
        "none",
        "cadrumo.entrypoints.cli.ledger_read_commands:ledger_preflight",
        expected_result_schema(
            TARGET, "cadrumo.entrypoints.cli.ledger_diagnostic_results:LedgerPreflightResult", "ledger.preflight"
        ),
        (
            expected_option("period", "--period", "cli.ledger.export.period_help", default=REQUIRED_DEFAULT),
            expected_option(
                "year", "--year", "cli.ledger.preflight.year_help", annotation="builtins:int", default=REQUIRED_DEFAULT
            ),
        ),
    ),
    expected_command(
        "app_ledger_prorrata",
        "app_ledger",
        "prorrata",
        "group",
        "cli.app.ledger.prorrata.group_help",
        "none",
        None,
        NO_RESULT_SCHEMA_CONTRACT,
        invocation=GROUP_INVOCATION_CONTRACT,
    ),
    expected_command(
        "app_ledger_ratios",
        "app_ledger",
        "ratios",
        "group",
        "cli.app.ledger.ratios.group_help",
        "none",
        None,
        NO_RESULT_SCHEMA_CONTRACT,
        invocation=GROUP_INVOCATION_CONTRACT,
    ),
)


_EXPECTED_SHARED_PARAMETERS: Final[tuple[tuple[str, tuple[object, ...]], ...]] = (
    (
        "evidence_transaction_id",
        expected_argument(
            "transaction_id", "cli.app.ledger.evidence.pull_id_help", constraint=NON_BLANK_CONSTRAINT_CONTRACT
        ),
    ),
    ("evidence_actor", expected_option("actor", "--actor", "cli.app.ledger.evidence.pull_actor_help")),
    ("ledger_actor", expected_option("actor", "--actor", "cli.ledger.add.actor_help")),
    ("merge_reason", expected_option("reason", "--reason", "cli.ledger.merge.reason_help", default=EMPTY_DEFAULT)),
    ("optional_period", expected_option("period", "--period", "cli.ledger.export.period_help")),
    ("optional_year", expected_option("year", "--year", "cli.ledger.check.year_help", annotation="builtins:int")),
)


def test_ledger_operations_and_management_keep_their_literal_contract_matrix() -> None:
    """All command-specific public facts remain distinct after construction reuse."""
    specs = (*LEDGER_OPERATIONS_COMMAND_SPECS, *LEDGER_MANAGEMENT_COMMAND_SPECS)
    assert tuple(literal_contract(spec) for spec in specs) == _EXPECTED_COMMANDS


def test_shared_ledger_construction_contracts_are_exact_and_reused() -> None:
    """Only complete immutable contracts are shared between authored fragments."""
    operations = {spec.key: spec for spec in LEDGER_OPERATIONS_COMMAND_SPECS}
    management = {spec.key: spec for spec in LEDGER_MANAGEMENT_COMMAND_SPECS}

    for spec in (
        operations["app_ledger_counterparty"],
        operations["app_ledger_evidence"],
        management["app_ledger_inventory"],
        management["app_ledger_invoice"],
        management["app_ledger_prorrata"],
        management["app_ledger_ratios"],
    ):
        assert spec.invocation is GROUP_INVOCATION
        assert spec.result_schema is NO_RESULT_SCHEMA

    for spec in (
        *(spec for spec in LEDGER_OPERATIONS_COMMAND_SPECS if spec.kind.value == "leaf"),
        management["app_ledger_link"],
        management["app_ledger_list"],
        management["app_ledger_llm_diagnostics"],
        management["app_ledger_merge"],
        management["app_ledger_preflight"],
    ):
        assert spec.invocation is LEAF_INVOCATION

    assert operations["app_ledger_exclude"].parameters[0] is EVIDENCE_TRANSACTION_ID_ARGUMENT
    assert operations["app_ledger_exclude"].parameters[-1] is EVIDENCE_ACTOR_OPTION
    assert operations["app_ledger_export"].parameters[-1] is LEDGER_ACTOR_OPTION
    for key in ("app_ledger_remove", "app_ledger_reset", "app_ledger_restore", "app_ledger_stash", "app_ledger_update"):
        assert {spec.key: spec for spec in LEDGER_LIFECYCLE_COMMAND_SPECS}[key].parameters[-1] is LEDGER_ACTOR_OPTION
    assert management["app_ledger_merge"].parameters[1] is MERGE_REASON_OPTION
    assert {spec.key: spec for spec in LEDGER_LIFECYCLE_COMMAND_SPECS}["app_ledger_split"].parameters[
        6
    ] is MERGE_REASON_OPTION
    for spec, positions in (
        (operations["app_ledger_export"], (3, 4)),
        (management["app_ledger_list"], (1, 2)),
    ):
        assert spec.parameters[positions[0]] is OPTIONAL_PERIOD_OPTION
        assert spec.parameters[positions[1]] is OPTIONAL_YEAR_OPTION
    # Import filters rows by the period, so it reuses the shared contracts and
    # replaces only the help text that describes what the scope does.
    import_period, import_year = operations["app_ledger_import"].parameters[6:8]
    assert import_period == replace(OPTIONAL_PERIOD_OPTION, help_key=TranslationKey("cli.ledger.import.period_help"))
    assert import_year == replace(OPTIONAL_YEAR_OPTION, help_key=TranslationKey("cli.ledger.import.year_help"))

    assert (
        tuple(
            (name, parameter_contract(parameter))
            for name, parameter in (
                ("evidence_transaction_id", EVIDENCE_TRANSACTION_ID_ARGUMENT),
                ("evidence_actor", EVIDENCE_ACTOR_OPTION),
                ("ledger_actor", LEDGER_ACTOR_OPTION),
                ("merge_reason", MERGE_REASON_OPTION),
                ("optional_period", OPTIONAL_PERIOD_OPTION),
                ("optional_year", OPTIONAL_YEAR_OPTION),
            )
        )
        == _EXPECTED_SHARED_PARAMETERS
    )


def test_ledger_dispatch_flags_and_remove_handler_are_mutation_sensitive() -> None:
    """The matrix pins group help behavior, parameter display, and destructive dispatch."""
    operations = {spec.key: spec for spec in LEDGER_OPERATIONS_COMMAND_SPECS}
    lifecycle = {spec.key: spec for spec in LEDGER_LIFECYCLE_COMMAND_SPECS}

    assert operations["app_ledger_counterparty"].invocation.no_args_is_help is True
    assert operations["app_ledger_detach"].invocation.no_args_is_help is False
    assert operations["app_ledger_detach"].parameters[0].show_default is True
    assert operations["app_ledger_export"].parameters[0].show_default is True

    remove = lifecycle["app_ledger_remove"]
    assert remove.handler is not None and remove.handler.target is not None
    assert remove.handler.target.identity == "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_remove"


def test_ledger_operations_and_management_resolve_through_the_live_graph() -> None:
    """Graph paths and deferred targets resolve to the identities in the literal matrix."""
    specs = (*LEDGER_OPERATIONS_COMMAND_SPECS, *LEDGER_MANAGEMENT_COMMAND_SPECS)
    for spec, expected in zip(specs, _EXPECTED_COMMANDS, strict=True):
        assert COMMAND_GRAPH.resolve_path(_graph_path(spec)) is spec
        assert_live_targets_match_expected(spec, expected)
