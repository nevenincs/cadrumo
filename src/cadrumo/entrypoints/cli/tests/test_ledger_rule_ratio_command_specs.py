"""Independent literal contracts for ledger rule and ratios CommandSpecs."""

from __future__ import annotations

import pytest

from .._app_ledger_command_specs import LEDGER_COMMAND_SPECS
from .._app_ledger_ratios_command_specs import LEDGER_RATIOS_COMMAND_SPECS
from .._app_ledger_rule_command_specs import LEDGER_RULE_COMMAND_SPECS
from .._app_ledger_rule_ratio_command_spec_support import (
    _LEDGER_RULE_RATIO_LEAF_INVOCATION,
    _RATIOS_OUTPUT_LANGUAGE_OPTION,
    _RATIOS_YEAR_OPTION,
    _RULE_ACTOR_OPTION,
)
from .._root_command_specs import ROOT_COMMAND_SPECS
from ..command_spec import ArgumentSpec, CommandSpec, CommandSpecGraph, InvocationSpec, OptionSpec

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DEFAULT_CONSTRAINT = (None, None, False, True, False, True, True, False, True, False, False)
_NO_TRANSPORT = ("none", "not_applicable", "not_applicable")
_NO_VALUE_HOOKS = (None, None, None, None, ())


def _value_contract(parameter: ArgumentSpec | OptionSpec) -> tuple[object, ...]:
    value = parameter.value
    return (
        value.annotation.identity,
        *(
            target.identity if target is not None else None
            for target in (value.click_type, value.parser, value.completion, value.callback)
        ),
        value.choices,
    )


def _constraint_contract(parameter: ArgumentSpec | OptionSpec) -> tuple[object, ...]:
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


def _parameter_contract(parameter: ArgumentSpec | OptionSpec) -> tuple[object, ...]:
    common = (
        parameter.kind.value,
        parameter.name,
        _value_contract(parameter),
        parameter.default.kind.value,
        parameter.default.literal,
        parameter.help_key.value if parameter.help_key is not None else None,
        parameter.metavar,
        parameter.show_default,
        parameter.hidden,
        _constraint_contract(parameter),
        (
            parameter.transport_locus.value,
            parameter.transport_shape.value,
            parameter.transport_role.value,
        ),
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
        parameter.prompt_key.value if parameter.prompt_key is not None else None,
        parameter.confirmation_prompt_key.value if parameter.confirmation_prompt_key is not None else None,
        parameter.envvar,
        parameter.eager,
        parameter.machine_secret_channel.value if parameter.machine_secret_channel is not None else None,
        parameter.profile_secret_channel.value if parameter.profile_secret_channel is not None else None,
    )


def _policy_contract(spec: CommandSpec) -> tuple[object, ...]:
    policy = spec.policy
    return (
        policy.capabilities,
        policy.side_effects,
        policy.performance,
        policy.write_route.value,
        policy.destructive,
        policy.handoff,
        policy.live_write,
    )


def _invocation_contract(invocation: InvocationSpec) -> tuple[object, ...]:
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


def _leaf_contract(spec: CommandSpec) -> tuple[object, ...]:
    assert spec.handler is not None and spec.handler.target is not None
    assert spec.result_schema.target is not None
    return (
        spec.parent_key,
        spec.token,
        spec.kind.value,
        _invocation_contract(spec.invocation),
        spec.help_key.value,
        spec.short_help_key,
        tuple(_parameter_contract(parameter) for parameter in spec.parameters),
        _policy_contract(spec),
        spec.handler.target.identity,
        spec.result_schema.state.value,
        spec.result_schema.target.identity,
        spec.result_schema.identity,
    )


_OPTIONAL_ACTOR = (
    "option",
    "actor",
    ("builtins:str", *_NO_VALUE_HOOKS),
    "literal",
    None,
    "cli.app.ledger.rule.actor_help",
    None,
    True,
    False,
    _DEFAULT_CONSTRAINT,
    _NO_TRANSPORT,
    ("--actor",),
    False,
    None,
    False,
    False,
    None,
    None,
    (),
    False,
    None,
    None,
)
_OPTIONAL_YEAR = (
    "option",
    "year",
    ("builtins:int", *_NO_VALUE_HOOKS),
    "literal",
    None,
    "cli.app.ledger.ratios.year_help",
    "YEAR",
    True,
    False,
    _DEFAULT_CONSTRAINT,
    _NO_TRANSPORT,
    ("--year",),
    False,
    None,
    False,
    False,
    None,
    None,
    (),
    False,
    None,
    None,
)
_OPTIONAL_OUTPUT_LANGUAGE = (
    "option",
    "output_language",
    ("cadrumo.core.external_constants:OutputLanguage", *_NO_VALUE_HOOKS),
    "literal",
    None,
    "cli.config.auth.output_language_help",
    None,
    True,
    False,
    _DEFAULT_CONSTRAINT,
    _NO_TRANSPORT,
    ("--output-language", "--language"),
    False,
    None,
    False,
    False,
    None,
    None,
    (),
    False,
    None,
    None,
)


def _option(
    name: str,
    declaration: str,
    target: str,
    default_kind: str,
    default: object,
    help_key: str,
    *,
    is_flag: bool = False,
    flag_value: object = None,
) -> tuple[object, ...]:
    return (
        "option",
        name,
        (target, *_NO_VALUE_HOOKS),
        default_kind,
        default,
        help_key,
        None,
        True,
        False,
        _DEFAULT_CONSTRAINT,
        _NO_TRANSPORT,
        (declaration,),
        is_flag,
        flag_value,
        False,
        False,
        None,
        None,
        (),
        False,
        None,
        None,
    )


def _argument(name: str, target: str, help_key: str) -> tuple[object, ...]:
    return (
        "argument",
        name,
        (target, *_NO_VALUE_HOOKS),
        "required",
        None,
        help_key,
        None,
        True,
        False,
        _DEFAULT_CONSTRAINT,
        _NO_TRANSPORT,
    )


_POLICY_3_CONTRACT = (
    frozenset(("calculation", "encrypted-facts")),
    frozenset(("local-state",)),
    "compute",
    "profile-bound",
    False,
    False,
    False,
)
_POLICY_4_CONTRACT = (
    frozenset(("encrypted-facts",)),
    frozenset(("local-state",)),
    "local-io",
    "profile-bound",
    False,
    False,
    False,
)
_POLICY_5_CONTRACT = (
    frozenset(("encrypted-facts",)),
    frozenset(("none",)),
    "local-io",
    "none",
    False,
    False,
    False,
)
_POLICY_6_CONTRACT = (
    frozenset(("calculation", "encrypted-facts")),
    frozenset(("none",)),
    "compute",
    "none",
    False,
    False,
    False,
)

_LEAF_INVOCATION_CONTRACT = (False, False, False, True, False, False, "ctx", None)


_EXPECTED_LEAF_CONTRACTS = {
    "app_ledger_rule_add": (
        "app_ledger_rule",
        "add",
        "leaf",
        _LEAF_INVOCATION_CONTRACT,
        "cli.app.ledger.rule.add_help",
        None,
        (
            _option(
                "description_pattern",
                "--description-pattern",
                "builtins:str",
                "required",
                None,
                "cli.app.ledger.rule.description_pattern_help",
            ),
            _option(
                "classification",
                "--classification",
                "cadrumo.domain.transactions.enums:BusinessClassification",
                "required",
                None,
                "cli.app.ledger.rule.classification_help",
            ),
            _option(
                "category_id",
                "--category-id",
                "builtins:str",
                "literal",
                None,
                "cli.app.ledger.rule.category_id_help",
            ),
            _option(
                "priority",
                "--priority",
                "builtins:int",
                "literal",
                100,
                "cli.app.ledger.rule.priority_help",
            ),
            _OPTIONAL_ACTOR,
        ),
        _POLICY_4_CONTRACT,
        "cadrumo.entrypoints.cli._ledger_rules_cli:rule_add",
        "target",
        "cadrumo.entrypoints.cli._ledger_rule_payloads:RuleAddResult",
        "ledger.rule.add",
    ),
    "app_ledger_rule_apply": (
        "app_ledger_rule",
        "apply",
        "leaf",
        _LEAF_INVOCATION_CONTRACT,
        "cli.app.ledger.rule.apply_help",
        None,
        (
            _option(
                "reaffirm",
                "--reaffirm",
                "builtins:bool",
                "literal",
                False,
                "cli.app.ledger.rule.apply_reaffirm_help",
                is_flag=True,
                flag_value=True,
            ),
            _option(
                "dry_run",
                "--dry-run",
                "builtins:bool",
                "literal",
                False,
                "cli.app.ledger.rule.apply_dry_run_help",
                is_flag=True,
                flag_value=True,
            ),
            _OPTIONAL_ACTOR,
        ),
        _POLICY_3_CONTRACT,
        "cadrumo.entrypoints.cli._ledger_rules_cli:rule_apply",
        "target",
        "cadrumo.entrypoints.cli._ledger_rule_payloads:RuleApplyResult",
        "ledger.rule.apply",
    ),
    "app_ledger_rule_list": (
        "app_ledger_rule",
        "list",
        "leaf",
        _LEAF_INVOCATION_CONTRACT,
        "cli.app.ledger.rule.list_help",
        None,
        (),
        _POLICY_5_CONTRACT,
        "cadrumo.entrypoints.cli._ledger_rules_cli:rule_list",
        "target",
        "cadrumo.entrypoints.cli._ledger_rule_payloads:RuleListResult",
        "ledger.rule.list",
    ),
    "app_ledger_ratios_eligible": (
        "app_ledger_ratios",
        "eligible",
        "leaf",
        _LEAF_INVOCATION_CONTRACT,
        "cli.app.ledger.ratios.eligible_help",
        None,
        (_OPTIONAL_YEAR, _OPTIONAL_OUTPUT_LANGUAGE),
        _POLICY_6_CONTRACT,
        "cadrumo.entrypoints.cli._ledger_ratios_cli:ratios_eligible",
        "target",
        "cadrumo.entrypoints.cli._ledger_ratios_payloads:RatiosEligibleResult",
        "ledger.ratios.eligible",
    ),
    "app_ledger_ratios_list": (
        "app_ledger_ratios",
        "list",
        "leaf",
        _LEAF_INVOCATION_CONTRACT,
        "cli.app.ledger.ratios.list_help",
        None,
        (_OPTIONAL_YEAR, _OPTIONAL_OUTPUT_LANGUAGE),
        _POLICY_5_CONTRACT,
        "cadrumo.entrypoints.cli._ledger_ratios_cli:ratios_list",
        "target",
        "cadrumo.entrypoints.cli._ledger_ratios_payloads:RatiosListResult",
        "ledger.ratios.list",
    ),
    "app_ledger_ratios_set": (
        "app_ledger_ratios",
        "set",
        "leaf",
        _LEAF_INVOCATION_CONTRACT,
        "cli.app.ledger.ratios.set_help",
        None,
        (
            _OPTIONAL_YEAR,
            _argument(
                "category",
                "cadrumo.domain.categories.spending_category:SpendingCategory",
                "cli.app.ledger.ratios.category_help",
            ),
            _argument("ratio", "builtins:str", "cli.app.ledger.ratios.ratio_help"),
            _OPTIONAL_OUTPUT_LANGUAGE,
        ),
        _POLICY_4_CONTRACT,
        "cadrumo.entrypoints.cli._ledger_ratios_cli:ratios_set",
        "target",
        "cadrumo.entrypoints.cli._ledger_ratios_payloads:RatiosSetResult",
        "ledger.ratios.set",
    ),
    "app_ledger_ratios_unset": (
        "app_ledger_ratios",
        "unset",
        "leaf",
        _LEAF_INVOCATION_CONTRACT,
        "cli.app.ledger.ratios.unset_help",
        None,
        (
            _argument(
                "category",
                "cadrumo.domain.categories.spending_category:SpendingCategory",
                "cli.app.ledger.ratios.unset_category_help",
            ),
            _OPTIONAL_OUTPUT_LANGUAGE,
        ),
        _POLICY_4_CONTRACT,
        "cadrumo.entrypoints.cli._ledger_ratios_cli:ratios_unset",
        "target",
        "cadrumo.entrypoints.cli._ledger_ratios_payloads:RatiosUnsetResult",
        "ledger.ratios.unset",
    ),
    "app_ledger_ratios_validate": (
        "app_ledger_ratios",
        "validate",
        "leaf",
        _LEAF_INVOCATION_CONTRACT,
        "cli.app.ledger.ratios.validate_help",
        None,
        (_OPTIONAL_OUTPUT_LANGUAGE,),
        _POLICY_6_CONTRACT,
        "cadrumo.entrypoints.cli._ledger_ratios_cli:ratios_validate",
        "target",
        "cadrumo.entrypoints.cli._ledger_ratios_payloads:RatiosValidateResult",
        "ledger.ratios.validate",
    ),
}


def test_rule_and_ratios_leaves_match_the_independent_literal_contract() -> None:
    specs = (*LEDGER_RULE_COMMAND_SPECS, *LEDGER_RATIOS_COMMAND_SPECS)

    assert {spec.key for spec in specs} == set(_EXPECTED_LEAF_CONTRACTS)
    assert {spec.key: _leaf_contract(spec) for spec in specs} == _EXPECTED_LEAF_CONTRACTS


def test_shared_facts_have_their_literal_contract_and_only_identical_placements() -> None:
    assert _parameter_contract(_RULE_ACTOR_OPTION) == _OPTIONAL_ACTOR
    assert _parameter_contract(_RATIOS_YEAR_OPTION) == _OPTIONAL_YEAR
    assert _parameter_contract(_RATIOS_OUTPUT_LANGUAGE_OPTION) == _OPTIONAL_OUTPUT_LANGUAGE

    rules = {spec.token: spec for spec in LEDGER_RULE_COMMAND_SPECS}
    ratios = {spec.token: spec for spec in LEDGER_RATIOS_COMMAND_SPECS}
    assert rules["add"].parameters[-1] is _RULE_ACTOR_OPTION
    assert rules["apply"].parameters[-1] is _RULE_ACTOR_OPTION
    assert all(spec.invocation is _LEDGER_RULE_RATIO_LEAF_INVOCATION for spec in (*rules.values(), *ratios.values()))
    assert all(ratios[token].parameters[0] is _RATIOS_YEAR_OPTION for token in ("eligible", "list", "set"))
    assert all(spec.parameters[-1] is _RATIOS_OUTPUT_LANGUAGE_OPTION for spec in ratios.values())


def test_rule_and_ratios_paths_resolve_from_the_complete_ledger_graph() -> None:
    graph = CommandSpecGraph((*ROOT_COMMAND_SPECS, *LEDGER_COMMAND_SPECS))
    expected_paths = {
        ("aeat", "app", "ledger", "rule", "add"): "app_ledger_rule_add",
        ("aeat", "app", "ledger", "rule", "apply"): "app_ledger_rule_apply",
        ("aeat", "app", "ledger", "rule", "list"): "app_ledger_rule_list",
        ("aeat", "app", "ledger", "ratios", "eligible"): "app_ledger_ratios_eligible",
        ("aeat", "app", "ledger", "ratios", "list"): "app_ledger_ratios_list",
        ("aeat", "app", "ledger", "ratios", "set"): "app_ledger_ratios_set",
        ("aeat", "app", "ledger", "ratios", "unset"): "app_ledger_ratios_unset",
        ("aeat", "app", "ledger", "ratios", "validate"): "app_ledger_ratios_validate",
    }

    assert {path: graph.resolve_path(path).key for path in expected_paths} == expected_paths
