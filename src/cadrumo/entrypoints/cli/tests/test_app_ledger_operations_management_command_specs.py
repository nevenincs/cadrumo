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
from ..command_spec import CommandSpec, OptionSpec, ParameterSpec
from ..command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

# (key, parent, token, kind, help, policy route, handler, schema identity, parameter names)
_EXPECTED_COMMANDS: Final[tuple[tuple[object, ...], ...]] = (
    (
        "app_ledger_counterparty",
        "app_ledger",
        "counterparty",
        "group",
        "cli.app.ledger.counterparty.group_help",
        "none",
        None,
        None,
        (),
    ),
    (
        "app_ledger_detach",
        "app_ledger",
        "detach",
        "leaf",
        "cli.ledger.detach.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_detach",
        "ledger.detach",
        ("transaction_id", "attachment_ids", "actor"),
    ),
    (
        "app_ledger_evidence_pull",
        "app_ledger_evidence",
        "pull",
        "leaf",
        "cli.app.ledger.evidence.pull_help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_evidence_pull",
        "ledger.evidence.pull",
        ("transaction_id", "source", "reference", "note", "actor"),
    ),
    (
        "app_ledger_evidence",
        "app_ledger",
        "evidence",
        "group",
        "cli.app.ledger.evidence.group_help",
        "none",
        None,
        None,
        (),
    ),
    (
        "app_ledger_exclude",
        "app_ledger",
        "exclude",
        "leaf",
        "cli.ledger.exclude.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_exclude",
        "ledger.exclude",
        ("transaction_id", "reason", "yes", "actor"),
    ),
    (
        "app_ledger_export",
        "app_ledger",
        "export",
        "leaf",
        "cli.ledger.export.help",
        "profile-bound",
        "cadrumo.entrypoints.cli._ledger_read_cli:ledger_export",
        "ledger.export",
        ("output", "export_kind", "include_inactive", "period", "year", "actor"),
    ),
    (
        "app_ledger_history",
        "app_ledger",
        "history",
        "leaf",
        "cli.ledger.history.help",
        "none",
        "cadrumo.entrypoints.cli._ledger_read_cli:ledger_history",
        "ledger.history",
        ("transaction_id", "include_split_siblings"),
    ),
    (
        "app_ledger_import",
        "app_ledger",
        "import",
        "leaf",
        "cli.ledger.import.help",
        "profile-bound",
        "cadrumo.entrypoints.cli._ledger_import_cli:ledger_import",
        "ledger.import",
        ("file", "provider", "dry_run", "verify", "verify_source", "verbose", "period", "year"),
    ),
    (
        "app_ledger_inventory",
        "app_ledger",
        "inventory",
        "group",
        "cli.app.ledger.inventory.group_help",
        "none",
        None,
        None,
        (),
    ),
    (
        "app_ledger_invoice",
        "app_ledger",
        "invoice",
        "group",
        "cli.app.ledger.invoice.group_help",
        "none",
        None,
        None,
        (),
    ),
    (
        "app_ledger_link",
        "app_ledger",
        "link",
        "leaf",
        "cli.ledger.link.help",
        "profile-bound",
        "cadrumo.entrypoints.cli._ledger:ledger_link",
        "ledger.link",
        ("transaction_id", "invoice_id", "actor"),
    ),
    (
        "app_ledger_list",
        "app_ledger",
        "list",
        "leaf",
        "cli.ledger.list.help",
        "none",
        "cadrumo.entrypoints.cli._ledger_read_cli:ledger_list",
        "ledger.list",
        (
            "filters",
            "period",
            "year",
            "limit",
            "offset",
            "group",
            "by_group",
            "sort_by",
            "sort_order",
            "hide_llm_rejected",
        ),
    ),
    (
        "app_ledger_llm_diagnostics",
        "app_ledger",
        "llm-diagnostics",
        "leaf",
        "cli.ledger.llm_diagnostics.help",
        "none",
        "cadrumo.entrypoints.cli._ledger_read_cli:ledger_llm_diagnostics",
        "ledger.llm_diagnostics",
        ("since", "until", "low_confidence_below"),
    ),
    (
        "app_ledger_merge",
        "app_ledger",
        "merge",
        "leaf",
        "cli.ledger.merge.help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_merge",
        "ledger.merge",
        ("child_id", "reason", "yes", "actor"),
    ),
    (
        "app_ledger_participation",
        "app_ledger",
        "participation",
        "group",
        "cli.ledger.participation.help",
        "none",
        "cadrumo.entrypoints.cli._participation_cli:participation_lookup",
        "ledger.participation",
        ("transaction_id",),
    ),
    (
        "app_ledger_preflight",
        "app_ledger",
        "preflight",
        "leaf",
        "cli.ledger.preflight.help",
        "none",
        "cadrumo.entrypoints.cli._ledger_read_cli:ledger_preflight",
        "ledger.preflight",
        ("period", "year"),
    ),
    (
        "app_ledger_prorrata",
        "app_ledger",
        "prorrata",
        "group",
        "cli.app.ledger.prorrata.group_help",
        "none",
        None,
        None,
        (),
    ),
    (
        "app_ledger_evidence_pull_all",
        "app_ledger_evidence",
        "pull-all",
        "leaf",
        "cli.app.ledger.evidence.pull_all_help",
        "profile-bound",
        "cadrumo.entrypoints.cli.ledger_lifecycle_cli:ledger_evidence_pull_all",
        "ledger.evidence.pull_all",
        ("folder", "note"),
    ),
    (
        "app_ledger_ratios",
        "app_ledger",
        "ratios",
        "group",
        "cli.app.ledger.ratios.group_help",
        "none",
        None,
        None,
        (),
    ),
)

_EXPECTED_SHARED_PARAMETERS: Final[tuple[tuple[str, tuple[object, ...]], ...]] = (
    (
        "evidence_transaction_id",
        ("argument", "transaction_id", (), "builtins:str", "REQUIRED", None, "cli.app.ledger.evidence.pull_id_help"),
    ),
    (
        "evidence_actor",
        ("option", "actor", ("--actor",), "builtins:str", "LITERAL", None, "cli.app.ledger.evidence.pull_actor_help"),
    ),
    (
        "ledger_actor",
        ("option", "actor", ("--actor",), "builtins:str", "LITERAL", None, "cli.ledger.add.actor_help"),
    ),
    (
        "merge_reason",
        ("option", "reason", ("--reason",), "builtins:str", "LITERAL", "", "cli.ledger.merge.reason_help"),
    ),
    (
        "optional_period",
        ("option", "period", ("--period",), "builtins:str", "LITERAL", None, "cli.ledger.export.period_help"),
    ),
    (
        "optional_year",
        ("option", "year", ("--year",), "builtins:int", "LITERAL", None, "cli.ledger.check.year_help"),
    ),
)

_EXPECTED_LIFECYCLE_COMMANDS: Final[tuple[tuple[object, ...], ...]] = (
    (
        "app_ledger_remove",
        "remove",
        "cli.ledger.remove.help",
        "profile-bound",
        "ledger.remove",
        ("transaction_id", "reason", "dry_run", "yes", "actor"),
    ),
    (
        "app_ledger_reset",
        "reset",
        "cli.ledger.reset.help",
        "profile-bound",
        "ledger.reset",
        ("reason", "dry_run", "yes", "actor"),
    ),
    (
        "app_ledger_restore",
        "restore",
        "cli.ledger.restore.help",
        "profile-bound",
        "ledger.restore",
        ("transaction_id", "reason", "yes", "actor"),
    ),
    ("app_ledger_review", "review", "cli.ledger.review.help", "none", "ledger.review", ("filters", "verbose")),
    ("app_ledger_rule", "rule", "cli.app.ledger.rule.group_help", "none", None, ()),
    (
        "app_ledger_split",
        "split",
        "cli.ledger.split.help",
        "profile-bound",
        "ledger.split",
        (
            "transaction_id",
            "child_amount",
            "child_description",
            "llm",
            "apply",
            "read_evidence",
            "vision_model",
            "reason",
            "yes",
            "actor",
        ),
    ),
    (
        "app_ledger_stash",
        "stash",
        "cli.ledger.stash.help",
        "profile-bound",
        "ledger.stash",
        ("transaction_id", "reason", "yes", "actor"),
    ),
    ("app_ledger_status", "status", "cli.ledger.status.help", "none", "ledger.status", ("period", "year")),
    ("app_ledger_track", "track", "cli.ledger.track.help", "none", "ledger.track", ("transaction_id",)),
    (
        "app_ledger_update",
        "update",
        "cli.ledger.update.help",
        "profile-bound",
        "ledger.update",
        (
            "transaction_id",
            "booked_date",
            "value_date",
            "amount",
            "direction",
            "currency",
            "counterparty",
            "description",
            "taxable_base",
            "iva_rate",
            "iva_amount",
            "irpf_category",
            "notes",
            "group",
            "actor",
        ),
    ),
    ("app_ledger_view", "view", "cli.ledger.view.help", "none", "ledger.view", ("transaction_id",)),
)


def _parameter_contract(parameter: ParameterSpec) -> tuple[object, ...]:
    """Project a parameter into all facts shared construction must preserve."""
    declarations = parameter.declarations if isinstance(parameter, OptionSpec) else ()
    return (
        parameter.kind.value,
        parameter.name,
        declarations,
        parameter.value.annotation.identity,
        parameter.default.kind.name,
        parameter.default.literal,
        parameter.help_key.value if parameter.help_key is not None else None,
    )


def _literal_contract(command: CommandSpec) -> tuple[object, ...]:
    """Project every command identity, routing, and parameter-order fact."""
    handler = None if command.handler is None or command.handler.target is None else command.handler.target.identity
    return (
        command.key,
        command.parent_key,
        command.token,
        command.kind.value,
        command.help_key.value,
        command.policy.write_route.value,
        handler,
        command.result_schema.identity,
        tuple(parameter.name for parameter in command.parameters),
    )


def test_ledger_operations_and_management_keep_their_literal_contract_matrix() -> None:
    """All command-specific public facts remain distinct after construction reuse."""
    specs = (*LEDGER_OPERATIONS_COMMAND_SPECS, *LEDGER_MANAGEMENT_COMMAND_SPECS)
    assert tuple(_literal_contract(spec) for spec in specs) == _EXPECTED_COMMANDS


def test_ledger_lifecycle_keeps_its_literal_contract_matrix() -> None:
    """Lifecycle command identities and parameter order remain independently literal."""
    assert (
        tuple(
            (
                spec.key,
                spec.token,
                spec.help_key.value,
                spec.policy.write_route.value,
                spec.result_schema.identity,
                tuple(parameter.name for parameter in spec.parameters),
            )
            for spec in LEDGER_LIFECYCLE_COMMAND_SPECS
        )
        == _EXPECTED_LIFECYCLE_COMMANDS
    )


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


def test_ledger_operations_and_management_resolve_through_the_live_graph() -> None:
    """Graph paths, deferred handlers, and result schemas resolve through production authorities."""
    for spec in (*LEDGER_OPERATIONS_COMMAND_SPECS, *LEDGER_MANAGEMENT_COMMAND_SPECS):
        path = ("aeat", "app", "ledger", spec.token)
        if spec.parent_key == "app_ledger_evidence":
            path = ("aeat", "app", "ledger", "evidence", spec.token)
        assert COMMAND_GRAPH.resolve_path(path) is spec
        if spec.handler is not None:
            assert spec.handler.target is not None
            assert callable(resolve_deferred_target(spec.handler.target))
        if spec.result_schema.target is not None:
            assert resolve_deferred_target(spec.result_schema.target) is not None


def test_ledger_lifecycle_resolves_through_the_live_graph() -> None:
    """Every lifecycle command continues to resolve its graph path and deferred targets."""
    for spec in LEDGER_LIFECYCLE_COMMAND_SPECS:
        assert COMMAND_GRAPH.resolve_path(("aeat", "app", "ledger", spec.token)) is spec
        if spec.handler is not None:
            assert spec.handler.target is not None
            assert callable(resolve_deferred_target(spec.handler.target))
        if spec.result_schema.target is not None:
            assert resolve_deferred_target(spec.result_schema.target) is not None
