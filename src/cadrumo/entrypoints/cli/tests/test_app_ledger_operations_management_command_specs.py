"""Literal and resolution contracts for ledger operations and management specs."""

from __future__ import annotations

from typing import Final

import pytest

from .._app_ledger_command_spec_support import (
    _EVIDENCE_ACTOR_OPTION,
    _EVIDENCE_TRANSACTION_ID_ARGUMENT,
    _GROUP_INVOCATION,
    _LEAF_INVOCATION,
    _LEDGER_ACTOR_OPTION,
    _MERGE_REASON_OPTION,
    _NO_RESULT_SCHEMA,
    _OPTIONAL_PERIOD_OPTION,
    _OPTIONAL_YEAR_OPTION,
)
from .._app_ledger_lifecycle_command_specs import LEDGER_LIFECYCLE_COMMAND_SPECS
from .._app_ledger_management_command_specs import LEDGER_MANAGEMENT_COMMAND_SPECS
from .._app_ledger_operations_command_specs import LEDGER_OPERATIONS_COMMAND_SPECS
from .._command_target import resolve_deferred_target
from ..command_spec import ArgumentSpec, CommandSpec, ParameterSpec
from ..command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_NO_VALUE_HOOKS: Final[tuple[object, ...]] = (None, None, None, None)
_DEFAULT_CONSTRAINT: Final[tuple[object, ...]] = (
    None,
    None,
    False,
    True,
    False,
    True,
    True,
    False,
    True,
    False,
    False,
)
_MINIMUM_ONE_CONSTRAINT: Final[tuple[object, ...]] = (1, *_DEFAULT_CONSTRAINT[1:])
_MINIMUM_ZERO_CONSTRAINT: Final[tuple[object, ...]] = (0, *_DEFAULT_CONSTRAINT[1:])
_NO_TRANSPORT: Final[tuple[str, ...]] = ("none", "not_applicable", "not_applicable")
_REMOTE_HANDLE_TRANSPORT: Final[tuple[str, ...]] = ("remote_handle", "not_applicable", "not_applicable")
_LOCAL_IN_FILE_PRIMARY_TRANSPORT: Final[tuple[str, ...]] = ("local_in", "file", "primary")
_LOCAL_IN_FILE_AUXILIARY_TRANSPORT: Final[tuple[str, ...]] = ("local_in", "file", "auxiliary")
_LOCAL_OUT_FILE_PRIMARY_TRANSPORT: Final[tuple[str, ...]] = ("local_out", "file", "primary")

_REQUIRED_DEFAULT: Final[tuple[object, ...]] = ("REQUIRED", None, None)
_NONE_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", None, None)
_EMPTY_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", "", None)
_FALSE_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", False, None)
_EMPTY_TUPLE_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", (), None)
_CSV_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", "csv", None)
_ASC_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", "asc", None)
_HALF_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", 0.5, None)

_GROUP_INVOCATION_CONTRACT: Final[tuple[object, ...]] = (False, True, False, True, False, False, None, None)
_LEAF_INVOCATION_CONTRACT: Final[tuple[object, ...]] = (False, False, False, True, False, False, "ctx", None)
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
_NO_RESULT_SCHEMA_CONTRACT: Final[tuple[object, ...]] = ("not-supported", None, None, None)


def _expected_argument(
    name: str,
    help_key: str,
    *,
    annotation: str = "builtins:str",
    default: tuple[object, ...] = _REQUIRED_DEFAULT,
    value_hooks: tuple[object, ...] = _NO_VALUE_HOOKS,
    choices: tuple[str, ...] = (),
    metavar: str | None = None,
    show_default: bool = True,
    hidden: bool = False,
    constraint: tuple[object, ...] = _DEFAULT_CONSTRAINT,
    transport: tuple[str, ...] = _NO_TRANSPORT,
) -> tuple[object, ...]:
    """Build a complete expected ArgumentSpec projection from literal facts."""
    return (
        "argument",
        name,
        (annotation, *value_hooks, choices),
        default,
        help_key,
        metavar,
        show_default,
        hidden,
        constraint,
        transport,
    )


def _expected_option(
    name: str,
    declaration: str,
    help_key: str,
    *,
    annotation: str = "builtins:str",
    default: tuple[object, ...] = _NONE_DEFAULT,
    value_hooks: tuple[object, ...] = _NO_VALUE_HOOKS,
    choices: tuple[str, ...] = (),
    metavar: str | None = None,
    show_default: bool = True,
    hidden: bool = False,
    constraint: tuple[object, ...] = _DEFAULT_CONSTRAINT,
    transport: tuple[str, ...] = _NO_TRANSPORT,
    is_flag: bool = False,
    flag_value: object = None,
    multiple: bool = False,
    count: bool = False,
    prompt_key: str | None = None,
    confirmation_prompt_key: str | None = None,
    envvar: tuple[str, ...] = (),
    eager: bool = False,
    machine_secret_channel: str | None = None,
    profile_secret_channel: str | None = None,
) -> tuple[object, ...]:
    """Build a complete expected OptionSpec projection from literal facts."""
    return (
        "option",
        name,
        (annotation, *value_hooks, choices),
        default,
        help_key,
        metavar,
        show_default,
        hidden,
        constraint,
        transport,
        (declaration,),
        is_flag,
        flag_value,
        multiple,
        count,
        prompt_key,
        confirmation_prompt_key,
        envvar,
        eager,
        machine_secret_channel,
        profile_secret_channel,
    )


def _expected_result_schema(
    state: str,
    target: str | None,
    identity: str | None,
    *,
    reason_key: str | None = None,
) -> tuple[object, ...]:
    """Build a complete expected ResultSchemaSpec projection from literal facts."""
    return (state, target, reason_key, identity)


def _expected_command(
    key: str,
    parent_key: str,
    token: str,
    kind: str,
    help_key: str,
    write_route: str,
    handler: str | None,
    result_schema: tuple[object, ...],
    parameters: tuple[tuple[object, ...], ...] = (),
    *,
    invocation: tuple[object, ...] = _LEAF_INVOCATION_CONTRACT,
) -> tuple[object, ...]:
    """Build a complete expected CommandSpec projection from literal facts."""
    return (
        key,
        parent_key,
        token,
        kind,
        help_key,
        None,
        invocation,
        parameters,
        write_route,
        handler,
        result_schema,
    )


_TARGET = "target"

_EXPECTED_COMMANDS: Final[tuple[tuple[object, ...], ...]] = (
    _expected_command(
        "app_ledger_counterparty",
        "app_ledger",
        "counterparty",
        "group",
        "cli.app.ledger.counterparty.group_help",
        "none",
        None,
        _NO_RESULT_SCHEMA_CONTRACT,
        invocation=_GROUP_INVOCATION_CONTRACT,
    ),
    _expected_command(
        "app_ledger_detach",
        "app_ledger",
        "detach",
        "leaf",
        "cli.ledger.detach.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_detach",
        _expected_result_schema(
            _TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerDetachResult", "ledger.detach"
        ),
        (
            _expected_argument("transaction_id", "cli.ledger.detach.id_help"),
            _expected_option(
                "attachment_ids",
                "--attachment-id",
                "cli.ledger.detach.attachment_help",
                default=_EMPTY_TUPLE_DEFAULT,
                multiple=True,
            ),
            _expected_option("actor", "--actor", "cli.ledger.detach.actor_help"),
        ),
    ),
    _expected_command(
        "app_ledger_evidence_pull",
        "app_ledger_evidence",
        "pull",
        "leaf",
        "cli.app.ledger.evidence.pull_help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_evidence_pull",
        _expected_result_schema(
            _TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerAttachResult", "ledger.evidence.pull"
        ),
        (
            _expected_argument("transaction_id", "cli.app.ledger.evidence.pull_id_help"),
            _expected_option(
                "source",
                "--source",
                "cli.app.ledger.evidence.pull_source_help",
                annotation="cadrumo.domain.attachments.enums:DocumentLinkSource",
                default=_REQUIRED_DEFAULT,
            ),
            _expected_option(
                "reference",
                "--reference",
                "cli.app.ledger.evidence.pull_reference_help",
                default=_REQUIRED_DEFAULT,
                transport=_REMOTE_HANDLE_TRANSPORT,
            ),
            _expected_option("note", "--note", "cli.app.ledger.evidence.pull_note_help", default=_EMPTY_DEFAULT),
            _expected_option("actor", "--actor", "cli.app.ledger.evidence.pull_actor_help"),
        ),
    ),
    _expected_command(
        "app_ledger_evidence",
        "app_ledger",
        "evidence",
        "group",
        "cli.app.ledger.evidence.group_help",
        "none",
        None,
        _NO_RESULT_SCHEMA_CONTRACT,
        invocation=_GROUP_INVOCATION_CONTRACT,
    ),
    _expected_command(
        "app_ledger_exclude",
        "app_ledger",
        "exclude",
        "leaf",
        "cli.ledger.exclude.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_exclude",
        _expected_result_schema(
            _TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerExcludeResult", "ledger.exclude"
        ),
        (
            _expected_argument("transaction_id", "cli.app.ledger.evidence.pull_id_help"),
            _expected_option("reason", "--reason", "cli.ledger.exclude.reason_help", default=_EMPTY_DEFAULT),
            _expected_option(
                "yes",
                "--yes",
                "cli.ledger.exclude.yes_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option("actor", "--actor", "cli.app.ledger.evidence.pull_actor_help"),
        ),
    ),
    _expected_command(
        "app_ledger_export",
        "app_ledger",
        "export",
        "leaf",
        "cli.ledger.export.help",
        "profile-bound",
        "cadrumo.entrypoints.cli._ledger_read_cli:ledger_export",
        _expected_result_schema(
            _TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerExportPayload", "ledger.export"
        ),
        (
            _expected_option(
                "output",
                "--output",
                "cli.ledger.export.output_help",
                annotation="pathlib:Path",
                default=_REQUIRED_DEFAULT,
                transport=_LOCAL_OUT_FILE_PRIMARY_TRANSPORT,
            ),
            _expected_option(
                "export_kind",
                "--export-format",
                "cli.ledger.export.format_help",
                annotation="cadrumo.application.export.tabular:ExportSerializationFormat",
                default=_CSV_DEFAULT,
            ),
            _expected_option(
                "include_inactive",
                "--include-inactive",
                "cli.ledger.export.include_inactive_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option("period", "--period", "cli.ledger.export.period_help"),
            _expected_option("year", "--year", "cli.ledger.check.year_help", annotation="builtins:int"),
            _expected_option("actor", "--actor", "cli.ledger.add.actor_help"),
        ),
    ),
    _expected_command(
        "app_ledger_history",
        "app_ledger",
        "history",
        "leaf",
        "cli.ledger.history.help",
        "none",
        "cadrumo.entrypoints.cli._ledger_read_cli:ledger_history",
        _expected_result_schema(
            _TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerHistoryResult", "ledger.history"
        ),
        (
            _expected_argument("transaction_id", "cli.ledger.history.id_help"),
            _expected_option(
                "include_split_siblings",
                "--include-split-siblings",
                "cli.ledger.history.include_split_siblings_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
        ),
    ),
    _expected_command(
        "app_ledger_import",
        "app_ledger",
        "import",
        "leaf",
        "cli.ledger.import.help",
        "profile-bound",
        "cadrumo.entrypoints.cli._ledger_import_cli:ledger_import",
        _expected_result_schema(
            _TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerImportPayload", "ledger.import"
        ),
        (
            _expected_option(
                "file",
                "--file",
                "cli.ledger.import.file_help",
                annotation="pathlib:Path",
                default=_REQUIRED_DEFAULT,
                transport=_LOCAL_IN_FILE_PRIMARY_TRANSPORT,
            ),
            _expected_option(
                "provider",
                "--provider",
                "cli.ledger.import.provider_help",
                annotation="cadrumo.application.ledger.actions_import:LedgerProviderID",
                default=_REQUIRED_DEFAULT,
            ),
            _expected_option(
                "dry_run",
                "--dry-run",
                "cli.ledger.import.dry_run_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option(
                "verify",
                "--verify",
                "cli.ledger.import.verify_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option(
                "verify_source",
                "--verify-source",
                "cli.ledger.import.verify_source_help",
                annotation="pathlib:Path",
                transport=_LOCAL_IN_FILE_AUXILIARY_TRANSPORT,
            ),
            _expected_option(
                "verbose",
                "--verbose",
                "cli.ledger.import.verbose_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option("period", "--period", "cli.ledger.export.period_help"),
            _expected_option("year", "--year", "cli.ledger.check.year_help", annotation="builtins:int"),
        ),
    ),
    _expected_command(
        "app_ledger_inventory",
        "app_ledger",
        "inventory",
        "group",
        "cli.app.ledger.inventory.group_help",
        "none",
        None,
        _NO_RESULT_SCHEMA_CONTRACT,
        invocation=_GROUP_INVOCATION_CONTRACT,
    ),
    _expected_command(
        "app_ledger_invoice",
        "app_ledger",
        "invoice",
        "group",
        "cli.app.ledger.invoice.group_help",
        "none",
        None,
        _NO_RESULT_SCHEMA_CONTRACT,
        invocation=_GROUP_INVOCATION_CONTRACT,
    ),
    _expected_command(
        "app_ledger_link",
        "app_ledger",
        "link",
        "leaf",
        "cli.ledger.link.help",
        "profile-bound",
        "cadrumo.entrypoints.cli._ledger:ledger_link",
        _expected_result_schema(_TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerLinkResult", "ledger.link"),
        (
            _expected_argument("transaction_id", "cli.ledger.link.id_help"),
            _expected_option(
                "invoice_id", "--invoice-id", "cli.ledger.link.invoice_id_help", default=_REQUIRED_DEFAULT
            ),
            _expected_option("actor", "--by", "cli.ledger.link.actor_help"),
        ),
    ),
    _expected_command(
        "app_ledger_list",
        "app_ledger",
        "list",
        "leaf",
        "cli.ledger.list.help",
        "none",
        "cadrumo.entrypoints.cli._ledger_read_cli:ledger_list",
        _expected_result_schema(_TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerListResult", "ledger.list"),
        (
            _expected_option(
                "filters", "--filter", "cli.ledger.list.filter_help", default=_EMPTY_TUPLE_DEFAULT, multiple=True
            ),
            _expected_option("period", "--period", "cli.ledger.export.period_help"),
            _expected_option("year", "--year", "cli.ledger.check.year_help", annotation="builtins:int"),
            _expected_option(
                "limit",
                "--limit",
                "cli.ledger.list.limit_help",
                annotation="builtins:int",
                constraint=_MINIMUM_ONE_CONSTRAINT,
            ),
            _expected_option(
                "offset",
                "--offset",
                "cli.ledger.list.offset_help",
                annotation="builtins:int",
                default=("LITERAL", 0, None),
                constraint=_MINIMUM_ZERO_CONSTRAINT,
            ),
            _expected_option("group", "--group", "cli.ledger.list.group_filter_help"),
            _expected_option(
                "by_group",
                "--by-group",
                "cli.ledger.list.by_group_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option(
                "sort_by",
                "--sort-by",
                "cli.ledger.list.sort_by_help",
                annotation="cadrumo.core.ledger_sort:LedgerSortField",
            ),
            _expected_option(
                "sort_order",
                "--sort-order",
                "cli.ledger.list.sort_order_help",
                annotation="cadrumo.core.ledger_sort:LedgerSortOrder",
                default=_ASC_DEFAULT,
            ),
            _expected_option(
                "hide_llm_rejected",
                "--hide-llm-rejected",
                "cli.ledger.list.hide_llm_rejected_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
        ),
    ),
    _expected_command(
        "app_ledger_llm_diagnostics",
        "app_ledger",
        "llm-diagnostics",
        "leaf",
        "cli.ledger.llm_diagnostics.help",
        "none",
        "cadrumo.entrypoints.cli._ledger_read_cli:ledger_llm_diagnostics",
        _expected_result_schema(
            _TARGET,
            "cadrumo.entrypoints.cli._ledger_rule_payloads:LedgerLlmDiagnosticsResult",
            "ledger.llm_diagnostics",
        ),
        (
            _expected_option("since", "--since", "cli.ledger.llm_diagnostics.since_help"),
            _expected_option("until", "--until", "cli.ledger.llm_diagnostics.until_help"),
            _expected_option(
                "low_confidence_below",
                "--low-confidence-below",
                "cli.ledger.llm_diagnostics.threshold_help",
                annotation="builtins:float",
                default=_HALF_DEFAULT,
            ),
        ),
    ),
    _expected_command(
        "app_ledger_merge",
        "app_ledger",
        "merge",
        "leaf",
        "cli.ledger.merge.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_merge",
        _expected_result_schema(_TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerMergeResult", "ledger.merge"),
        (
            _expected_option(
                "child_id", "--child-id", "cli.ledger.merge.child_id_help", default=_EMPTY_TUPLE_DEFAULT, multiple=True
            ),
            _expected_option("reason", "--reason", "cli.ledger.merge.reason_help", default=_EMPTY_DEFAULT),
            _expected_option(
                "yes",
                "--yes",
                "cli.ledger.merge.yes_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option("actor", "--actor", "cli.ledger.merge.actor_help"),
        ),
    ),
    _expected_command(
        "app_ledger_participation",
        "app_ledger",
        "participation",
        "group",
        "cli.ledger.participation.help",
        "none",
        "cadrumo.entrypoints.cli._participation_cli:participation_lookup",
        _expected_result_schema(
            _TARGET,
            "cadrumo.entrypoints.cli._ledger_payloads:LedgerTransactionParticipationPayload",
            "ledger.participation",
        ),
        (_expected_argument("transaction_id", "cli.ledger.participation.transaction_id_help", default=_NONE_DEFAULT),),
        invocation=_PARTICIPATION_INVOCATION_CONTRACT,
    ),
    _expected_command(
        "app_ledger_preflight",
        "app_ledger",
        "preflight",
        "leaf",
        "cli.ledger.preflight.help",
        "none",
        "cadrumo.entrypoints.cli._ledger_read_cli:ledger_preflight",
        _expected_result_schema(
            _TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerPreflightResult", "ledger.preflight"
        ),
        (
            _expected_option("period", "--period", "cli.ledger.export.period_help", default=_REQUIRED_DEFAULT),
            _expected_option(
                "year", "--year", "cli.ledger.preflight.year_help", annotation="builtins:int", default=_REQUIRED_DEFAULT
            ),
        ),
    ),
    _expected_command(
        "app_ledger_prorrata",
        "app_ledger",
        "prorrata",
        "group",
        "cli.app.ledger.prorrata.group_help",
        "none",
        None,
        _NO_RESULT_SCHEMA_CONTRACT,
        invocation=_GROUP_INVOCATION_CONTRACT,
    ),
    _expected_command(
        "app_ledger_evidence_pull_all",
        "app_ledger_evidence",
        "pull-all",
        "leaf",
        "cli.app.ledger.evidence.pull_all_help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_evidence_pull_all",
        _expected_result_schema(
            _TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerEvidencePullAllResult", "ledger.evidence.pull_all"
        ),
        (
            _expected_option(
                "folder",
                "--folder",
                "cli.app.ledger.evidence.pull_all_folder_help",
                default=_REQUIRED_DEFAULT,
                transport=_REMOTE_HANDLE_TRANSPORT,
            ),
            _expected_option("note", "--note", "cli.app.ledger.evidence.pull_all_note_help", default=_EMPTY_DEFAULT),
        ),
    ),
    _expected_command(
        "app_ledger_ratios",
        "app_ledger",
        "ratios",
        "group",
        "cli.app.ledger.ratios.group_help",
        "none",
        None,
        _NO_RESULT_SCHEMA_CONTRACT,
        invocation=_GROUP_INVOCATION_CONTRACT,
    ),
)

_EXPECTED_SHARED_PARAMETERS: Final[tuple[tuple[str, tuple[object, ...]], ...]] = (
    ("evidence_transaction_id", _expected_argument("transaction_id", "cli.app.ledger.evidence.pull_id_help")),
    ("evidence_actor", _expected_option("actor", "--actor", "cli.app.ledger.evidence.pull_actor_help")),
    ("ledger_actor", _expected_option("actor", "--actor", "cli.ledger.add.actor_help")),
    ("merge_reason", _expected_option("reason", "--reason", "cli.ledger.merge.reason_help", default=_EMPTY_DEFAULT)),
    ("optional_period", _expected_option("period", "--period", "cli.ledger.export.period_help")),
    ("optional_year", _expected_option("year", "--year", "cli.ledger.check.year_help", annotation="builtins:int")),
)

_EXPECTED_LIFECYCLE_COMMANDS: Final[tuple[tuple[object, ...], ...]] = (
    _expected_command(
        "app_ledger_remove",
        "app_ledger",
        "remove",
        "leaf",
        "cli.ledger.remove.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_remove",
        _expected_result_schema(
            _TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerRemoveResult", "ledger.remove"
        ),
        (
            _expected_argument("transaction_id", "cli.ledger.remove.id_help"),
            _expected_option("reason", "--reason", "cli.ledger.remove.reason_help", default=_EMPTY_DEFAULT),
            _expected_option(
                "dry_run",
                "--dry-run",
                "cli.ledger.remove.dry_run_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option(
                "yes",
                "--yes",
                "cli.ledger.remove.yes_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option("actor", "--actor", "cli.ledger.add.actor_help"),
        ),
    ),
    _expected_command(
        "app_ledger_reset",
        "app_ledger",
        "reset",
        "leaf",
        "cli.ledger.reset.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_reset",
        _expected_result_schema(_TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerResetResult", "ledger.reset"),
        (
            _expected_option("reason", "--reason", "cli.ledger.reset.reason_help", default=_EMPTY_DEFAULT),
            _expected_option(
                "dry_run",
                "--dry-run",
                "cli.ledger.reset.dry_run_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option(
                "yes",
                "--yes",
                "cli.ledger.reset.yes_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option("actor", "--actor", "cli.ledger.add.actor_help"),
        ),
    ),
    _expected_command(
        "app_ledger_restore",
        "app_ledger",
        "restore",
        "leaf",
        "cli.ledger.restore.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_restore",
        _expected_result_schema(
            _TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerRestoreResult", "ledger.restore"
        ),
        (
            _expected_argument("transaction_id", "cli.ledger.restore.id_help"),
            _expected_option("reason", "--reason", "cli.ledger.archive.reason_help", default=_EMPTY_DEFAULT),
            _expected_option(
                "yes",
                "--yes",
                "cli.ledger.restore.yes_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option("actor", "--actor", "cli.ledger.add.actor_help"),
        ),
    ),
    _expected_command(
        "app_ledger_review",
        "app_ledger",
        "review",
        "leaf",
        "cli.ledger.review.help",
        "none",
        "cadrumo.entrypoints.cli._ledger_review_cli:ledger_review",
        _expected_result_schema(
            _TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerReviewResult", "ledger.review"
        ),
        (
            _expected_option(
                "filters", "--filter", "cli.ledger.review.filter_help", default=_EMPTY_TUPLE_DEFAULT, multiple=True
            ),
            _expected_option(
                "verbose",
                "--verbose",
                "cli.ledger.review.verbose_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
        ),
    ),
    _expected_command(
        "app_ledger_rule",
        "app_ledger",
        "rule",
        "group",
        "cli.app.ledger.rule.group_help",
        "none",
        None,
        _NO_RESULT_SCHEMA_CONTRACT,
        invocation=_GROUP_INVOCATION_CONTRACT,
    ),
    _expected_command(
        "app_ledger_split",
        "app_ledger",
        "split",
        "leaf",
        "cli.ledger.split.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_split",
        _expected_result_schema(_TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerSplitResult", "ledger.split"),
        (
            _expected_argument("transaction_id", "cli.ledger.split.id_help"),
            _expected_option(
                "child_amount",
                "--child-amount",
                "cli.ledger.split.child_amount_help",
                default=_EMPTY_TUPLE_DEFAULT,
                multiple=True,
            ),
            _expected_option(
                "child_description",
                "--child-description",
                "cli.ledger.split.child_description_help",
                default=_EMPTY_TUPLE_DEFAULT,
                multiple=True,
            ),
            _expected_option(
                "llm",
                "--llm",
                "cli.ledger.split.llm_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option(
                "apply",
                "--apply",
                "cli.ledger.split.apply_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option(
                "read_evidence",
                "--read-evidence",
                "cli.ledger.split.read_evidence_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option("vision_model", "--vision-model", "cli.ledger.classify.vision_model_help"),
            _expected_option("reason", "--reason", "cli.ledger.merge.reason_help", default=_EMPTY_DEFAULT),
            _expected_option(
                "yes",
                "--yes",
                "cli.ledger.split.yes_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option("actor", "--actor", "cli.ledger.split.actor_help"),
        ),
    ),
    _expected_command(
        "app_ledger_stash",
        "app_ledger",
        "stash",
        "leaf",
        "cli.ledger.stash.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_stash",
        _expected_result_schema(_TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerStashResult", "ledger.stash"),
        (
            _expected_argument("transaction_id", "cli.ledger.stash.id_help"),
            _expected_option("reason", "--reason", "cli.ledger.archive.reason_help", default=_EMPTY_DEFAULT),
            _expected_option(
                "yes",
                "--yes",
                "cli.ledger.stash.yes_help",
                annotation="builtins:bool",
                default=_FALSE_DEFAULT,
                is_flag=True,
                flag_value=True,
            ),
            _expected_option("actor", "--actor", "cli.ledger.add.actor_help"),
        ),
    ),
    _expected_command(
        "app_ledger_status",
        "app_ledger",
        "status",
        "leaf",
        "cli.ledger.status.help",
        "none",
        "cadrumo.entrypoints.cli._ledger_read_cli:ledger_status",
        _expected_result_schema(
            _TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerStatusResult", "ledger.status"
        ),
        (
            _expected_option("period", "--period", "cli.ledger.export.period_help"),
            _expected_option("year", "--year", "cli.ledger.check.year_help", annotation="builtins:int"),
        ),
    ),
    _expected_command(
        "app_ledger_track",
        "app_ledger",
        "track",
        "leaf",
        "cli.ledger.track.help",
        "none",
        "cadrumo.entrypoints.cli._ledger_read_cli:ledger_track",
        _expected_result_schema(_TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerTrackResult", "ledger.track"),
        (_expected_argument("transaction_id", "cli.ledger.track.transaction_id_help"),),
    ),
    _expected_command(
        "app_ledger_update",
        "app_ledger",
        "update",
        "leaf",
        "cli.ledger.update.help",
        "profile-bound",
        "cadrumo.entrypoints.cli._ledger:ledger_update",
        _expected_result_schema(
            _TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerUpdateResult", "ledger.update"
        ),
        (
            _expected_argument("transaction_id", "cli.ledger.update.id_help"),
            _expected_option("booked_date", "--date", "cli.ledger.update.date_help"),
            _expected_option("value_date", "--value-date", "cli.ledger.update.value_date_help"),
            _expected_option("amount", "--amount", "cli.ledger.update.amount_help"),
            _expected_option(
                "direction",
                "--direction",
                "cli.ledger.update.direction_help",
                annotation="cadrumo.domain.transactions.enums:TransactionDirection",
            ),
            _expected_option("currency", "--currency", "cli.ledger.update.currency_help"),
            _expected_option("counterparty", "--counterparty", "cli.ledger.update.counterparty_help"),
            _expected_option("description", "--description", "cli.ledger.update.description_help"),
            _expected_option("taxable_base", "--taxable-base", "cli.ledger.update.taxable_base_help"),
            _expected_option("iva_rate", "--iva-rate", "cli.ledger.update.iva_rate_help"),
            _expected_option("iva_amount", "--iva-amount", "cli.ledger.update.iva_amount_help"),
            _expected_option("irpf_category", "--irpf-category", "cli.ledger.update.irpf_category_help"),
            _expected_option("notes", "--notes", "cli.ledger.update.notes_help"),
            _expected_option("group", "--group", "cli.ledger.update.group_help"),
            _expected_option("actor", "--actor", "cli.ledger.add.actor_help"),
        ),
    ),
    _expected_command(
        "app_ledger_view",
        "app_ledger",
        "view",
        "leaf",
        "cli.ledger.view.help",
        "none",
        "cadrumo.entrypoints.cli._ledger_read_cli:ledger_view",
        _expected_result_schema(_TARGET, "cadrumo.entrypoints.cli._ledger_payloads:LedgerViewResult", "ledger.view"),
        (_expected_argument("transaction_id", "cli.ledger.view.transaction_id_help"),),
    ),
)


def _target_identity(target: object | None) -> str | None:
    """Project a deferred target or translation key to its stable identity."""
    if target is None:
        return None
    return getattr(target, "identity", getattr(target, "value", None))


def _value_contract(parameter: ParameterSpec) -> tuple[object, ...]:
    value = parameter.value
    return (
        _target_identity(value.annotation),
        _target_identity(value.click_type),
        _target_identity(value.parser),
        _target_identity(value.completion),
        _target_identity(value.callback),
        value.choices,
    )


def _default_contract(parameter: ParameterSpec) -> tuple[object, ...]:
    default = parameter.default
    return (default.kind.name, default.literal, _target_identity(default.factory))


def _constraint_contract(parameter: ParameterSpec) -> tuple[object, ...]:
    constraint = parameter.constraint
    return (
        constraint.minimum,
        constraint.maximum,
        constraint.clamp,
        constraint.case_sensitive,
        constraint.exists,
        constraint.file_okay,
        constraint.dir_okay,
        constraint.writable,
        constraint.readable,
        constraint.resolve_path,
        constraint.allow_dash,
    )


def _transport_contract(parameter: ParameterSpec) -> tuple[str, ...]:
    return (parameter.transport_locus.value, parameter.transport_shape.value, parameter.transport_role.value)


def _parameter_contract(parameter: ParameterSpec) -> tuple[object, ...]:
    """Project every ArgumentSpec/OptionSpec field into a stable literal tuple."""
    common = (
        parameter.kind.value,
        parameter.name,
        _value_contract(parameter),
        _default_contract(parameter),
        _target_identity(parameter.help_key),
        parameter.metavar,
        parameter.show_default,
        parameter.hidden,
        _constraint_contract(parameter),
        _transport_contract(parameter),
    )
    if isinstance(parameter, ArgumentSpec):
        return common
    return (
        *common,
        parameter.declarations,
        parameter.is_flag,
        parameter.flag_value,
        parameter.multiple,
        parameter.count,
        _target_identity(parameter.prompt_key),
        _target_identity(parameter.confirmation_prompt_key),
        parameter.envvar,
        parameter.eager,
        parameter.machine_secret_channel.value if parameter.machine_secret_channel is not None else None,
        parameter.profile_secret_channel.value if parameter.profile_secret_channel is not None else None,
    )


def _invocation_contract(command: CommandSpec) -> tuple[object, ...]:
    invocation = command.invocation
    return (
        invocation.invoke_without_command,
        invocation.no_args_is_help,
        invocation.chain,
        invocation.add_help_option,
        invocation.add_completion,
        invocation.hidden,
        invocation.context_parameter,
        invocation.terminal_behavior,
    )


def _result_schema_contract(command: CommandSpec) -> tuple[object, ...]:
    schema = command.result_schema
    return (schema.state.value, _target_identity(schema.target), _target_identity(schema.reason_key), schema.identity)


def _literal_contract(command: CommandSpec) -> tuple[object, ...]:
    """Project every command and nested declaration field into stable literals."""
    handler = None if command.handler is None else _target_identity(command.handler.target)
    return (
        command.key,
        command.parent_key,
        command.token,
        command.kind.value,
        _target_identity(command.help_key),
        _target_identity(command.short_help_key),
        _invocation_contract(command),
        tuple(_parameter_contract(parameter) for parameter in command.parameters),
        command.policy.write_route.value,
        handler,
        _result_schema_contract(command),
    )


def _graph_path(spec: CommandSpec) -> tuple[str, ...]:
    if spec.parent_key == "app_ledger_evidence":
        return ("aeat", "app", "ledger", "evidence", spec.token)
    return ("aeat", "app", "ledger", spec.token)


def _assert_live_targets_match_expected(spec: CommandSpec, expected: tuple[object, ...]) -> None:
    expected_handler = expected[9]
    if expected_handler is None:
        assert spec.handler is None
    else:
        assert spec.handler is not None and spec.handler.target is not None
        assert spec.handler.target.identity == expected_handler
        assert callable(resolve_deferred_target(spec.handler.target))

    expected_schema = expected[10]
    expected_schema_target = expected_schema[1]
    if expected_schema_target is None:
        assert spec.result_schema.target is None
    else:
        assert spec.result_schema.target is not None
        assert spec.result_schema.target.identity == expected_schema_target
        assert resolve_deferred_target(spec.result_schema.target) is not None


def test_ledger_operations_and_management_keep_their_literal_contract_matrix() -> None:
    """All command-specific public facts remain distinct after construction reuse."""
    specs = (*LEDGER_OPERATIONS_COMMAND_SPECS, *LEDGER_MANAGEMENT_COMMAND_SPECS)
    assert tuple(_literal_contract(spec) for spec in specs) == _EXPECTED_COMMANDS


def test_ledger_lifecycle_keeps_its_literal_contract_matrix() -> None:
    """Lifecycle command identity, hierarchy, dispatch, and nested fields remain literal."""
    assert tuple(_literal_contract(spec) for spec in LEDGER_LIFECYCLE_COMMAND_SPECS) == _EXPECTED_LIFECYCLE_COMMANDS


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
        assert spec.invocation is _GROUP_INVOCATION
        assert spec.result_schema is _NO_RESULT_SCHEMA

    for spec in (
        *(spec for spec in LEDGER_OPERATIONS_COMMAND_SPECS if spec.kind.value == "leaf"),
        management["app_ledger_link"],
        management["app_ledger_list"],
        management["app_ledger_llm_diagnostics"],
        management["app_ledger_merge"],
        management["app_ledger_preflight"],
        management["app_ledger_evidence_pull_all"],
    ):
        assert spec.invocation is _LEAF_INVOCATION

    assert operations["app_ledger_evidence_pull"].parameters[0] is _EVIDENCE_TRANSACTION_ID_ARGUMENT
    assert operations["app_ledger_exclude"].parameters[0] is _EVIDENCE_TRANSACTION_ID_ARGUMENT
    assert operations["app_ledger_evidence_pull"].parameters[-1] is _EVIDENCE_ACTOR_OPTION
    assert operations["app_ledger_exclude"].parameters[-1] is _EVIDENCE_ACTOR_OPTION
    assert operations["app_ledger_export"].parameters[-1] is _LEDGER_ACTOR_OPTION
    for key in ("app_ledger_remove", "app_ledger_reset", "app_ledger_restore", "app_ledger_stash", "app_ledger_update"):
        assert {spec.key: spec for spec in LEDGER_LIFECYCLE_COMMAND_SPECS}[key].parameters[-1] is _LEDGER_ACTOR_OPTION
    assert management["app_ledger_merge"].parameters[1] is _MERGE_REASON_OPTION
    assert {spec.key: spec for spec in LEDGER_LIFECYCLE_COMMAND_SPECS}["app_ledger_split"].parameters[
        7
    ] is _MERGE_REASON_OPTION
    for spec, positions in (
        (operations["app_ledger_export"], (3, 4)),
        (operations["app_ledger_import"], (6, 7)),
        (management["app_ledger_list"], (1, 2)),
    ):
        assert spec.parameters[positions[0]] is _OPTIONAL_PERIOD_OPTION
        assert spec.parameters[positions[1]] is _OPTIONAL_YEAR_OPTION

    assert (
        tuple(
            (name, _parameter_contract(parameter))
            for name, parameter in (
                ("evidence_transaction_id", _EVIDENCE_TRANSACTION_ID_ARGUMENT),
                ("evidence_actor", _EVIDENCE_ACTOR_OPTION),
                ("ledger_actor", _LEDGER_ACTOR_OPTION),
                ("merge_reason", _MERGE_REASON_OPTION),
                ("optional_period", _OPTIONAL_PERIOD_OPTION),
                ("optional_year", _OPTIONAL_YEAR_OPTION),
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
        _assert_live_targets_match_expected(spec, expected)


def test_ledger_lifecycle_resolves_through_the_live_graph() -> None:
    """Every lifecycle command resolves its graph path and exact deferred targets."""
    for spec, expected in zip(LEDGER_LIFECYCLE_COMMAND_SPECS, _EXPECTED_LIFECYCLE_COMMANDS, strict=True):
        assert COMMAND_GRAPH.resolve_path(("aeat", "app", "ledger", spec.token)) is spec
        _assert_live_targets_match_expected(spec, expected)
