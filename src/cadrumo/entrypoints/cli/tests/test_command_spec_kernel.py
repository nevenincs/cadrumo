from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from .._command_spec import (
    ArgumentSpec,
    CommandSpec,
    CommandSpecGraph,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_STATE_FREE = ExecutionPolicySpec(
    capabilities=frozenset({"state-free"}),
    side_effects=frozenset({"none"}),
    performance="metadata",
    write_route="none",
)
_STRING = ValueContract(DeferredTarget("builtins", "str"))
_NO_SCHEMA = ResultSchemaSpec(SchemaState.NOT_SUPPORTED)


def _root() -> CommandSpec:
    return CommandSpec(
        key="root",
        parent_key=None,
        token="aeat",  # noqa: S106 - CLI token, not a credential.
        kind="root",
        help_key=TranslationKey("cli.root.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=_STATE_FREE,
        handler=None,
        result_schema=_NO_SCHEMA,
    )


def _group() -> CommandSpec:
    return CommandSpec(
        key="config",
        parent_key="root",
        token="config",  # noqa: S106 - CLI token, not a credential.
        kind="group",
        help_key=TranslationKey("cli.config.help"),
        short_help_key=TranslationKey("cli.config.short_help"),
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=_STATE_FREE,
        handler=None,
        result_schema=_NO_SCHEMA,
    )


def _leaf() -> CommandSpec:
    return CommandSpec(
        key="profile_list",
        parent_key="config",
        token="list",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.profile.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(),
        parameters=(
            ArgumentSpec(
                name="profile",
                value=_STRING,
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.profile.argument_help"),
            ),
            OptionSpec(
                name="output_language",
                declarations=("--output-language", "-l"),
                value=_STRING,
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.common.output_language_help"),
                envvar=("CADRUMO_OUTPUT_LANGUAGE",),
            ),
        ),
        policy=_STATE_FREE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._config._profile_list_cli", "profile_list")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._config_payloads", "ProfileListPayload"),
            identity="config.profile.list",
        ),
    )


def test_kernel_is_immutable_import_light_and_derives_paths_from_edges() -> None:
    graph = CommandSpecGraph((_leaf(), _root(), _group()))

    assert tuple(node.path for node in graph.nodes()) == (
        ("aeat",),
        ("aeat", "config"),
        ("aeat", "config", "list"),
    )
    assert type(graph).__dataclass_params__.frozen

    module_path = Path(__file__).parents[1] / "_command_spec.py"
    probe = subprocess.run(  # noqa: S603 - fixed interpreter and literal probe program.
        [
            sys.executable,
            "-c",
            (
                f"import runpy, sys; runpy.run_path({str(module_path)!r}); "
                "print(int('typer' in sys.modules), int('click' in sys.modules), "
                "int('json' in sys.modules), int('pydantic' in sys.modules))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert probe.stdout.strip() == "0 0 0 0"


@pytest.mark.parametrize("field", ["click_type", "parser"])
def test_value_contract_refuses_competing_choice_authority(field: str) -> None:
    target = DeferredTarget("builtins", "str")

    with pytest.raises(ValueError, match="choices cannot be combined"):
        ValueContract(target, choices=("on", "off"), **{field: target})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("specs", "message"),
    [
        (
            (_root(), dataclasses.replace(_root(), key="second_root", token="other")),  # noqa: S106
            "exactly one root",
        ),
        ((_root(), dataclasses.replace(_group(), parent_key="missing")), "unknown parent"),
        (
            (_root(), _group(), dataclasses.replace(_leaf(), key="nested", parent_key="profile_list"), _leaf()),
            "cannot own children",
        ),
        (
            (_root(), _group(), _leaf(), dataclasses.replace(_leaf(), key="duplicate")),
            "operator paths must be unique",
        ),
    ],
)
def test_graph_rejects_missing_duplicate_and_invalid_edges(specs: tuple[CommandSpec, ...], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        CommandSpecGraph(specs)


def test_spec_rejects_unexecutable_leaf_and_duplicate_option_tokens() -> None:
    with pytest.raises(ValueError, match="must declare a handler"):
        dataclasses.replace(_leaf(), handler=None)

    duplicate = OptionSpec(
        name="other",
        declarations=("--output-language",),
        value=_STRING,
        default=ParameterDefault.required(),
        help_key=TranslationKey("cli.other.help"),
    )
    with pytest.raises(ValueError, match="option tokens must be unique"):
        dataclasses.replace(_leaf(), parameters=(*_leaf().parameters, duplicate))


def test_deferred_bindings_are_fail_loud_and_never_resolve_during_declaration() -> None:
    unavailable = LazyBinding.unavailable(TranslationKey("cli.optional.unavailable"))
    assert unavailable.target is None
    with pytest.raises(ValueError, match="requires only a localized reason"):
        LazyBinding(state=unavailable.state, target=DeferredTarget("builtins", "str"))


def test_target_and_schema_identities_are_production_authored() -> None:
    leaf = _leaf()
    assert leaf.handler is not None
    assert leaf.handler.target is not None
    assert leaf.handler.target.identity.endswith(":profile_list")
    assert leaf.result_schema.target is not None
    assert leaf.result_schema.target.identity.endswith(":ProfileListPayload")
    assert leaf.result_schema.identity == "config.profile.list"


def test_graph_indexes_derived_paths_and_unique_schema_identities() -> None:
    graph = CommandSpecGraph((_leaf(), _root(), _group()))

    assert graph.resolve_path(("aeat", "config", "list")) == _leaf()
    assert graph.by_schema_identity() == {"config.profile.list": _leaf()}
    with pytest.raises(LookupError, match="unknown command spec path"):
        graph.resolve_path(("aeat", "missing"))

    duplicate_schema = dataclasses.replace(
        _leaf(),
        key="other_leaf",
        token="other",  # noqa: S106 - CLI operator token, not a credential
        result_schema=dataclasses.replace(_leaf().result_schema),
    )
    duplicate_graph = CommandSpecGraph((_root(), _group(), _leaf(), duplicate_schema))
    with pytest.raises(ValueError, match="schema identities must be unique"):
        duplicate_graph.by_schema_identity()


def test_execution_policy_is_self_contained_and_expands_implied_authority() -> None:
    policy = ExecutionPolicySpec(
        capabilities=frozenset({"google"}),
        side_effects=frozenset({"google"}),
        performance="external-io",
        write_route="none",
    )
    assert policy.expanded_capabilities == frozenset({"google", "network"})

    with pytest.raises(ValueError, match="lacks its owning capability"):
        ExecutionPolicySpec(
            capabilities=frozenset({"local-storage"}),
            side_effects=frozenset({"network"}),
            performance="external-io",
            write_route="none",
        )


def test_invocation_context_injection_is_explicit_and_validated() -> None:
    invocation = InvocationSpec(context_parameter="ctx")
    assert invocation.context_parameter == "ctx"
    with pytest.raises(ValueError, match="Python identifier"):
        InvocationSpec(context_parameter="not-valid")


def test_every_terminal_group_explicitly_classifies_its_behavior() -> None:
    from .._command_specs import COMMAND_GRAPH

    terminal_groups = tuple(
        node.spec
        for node in COMMAND_GRAPH.nodes()
        if node.spec.kind in {"root", "group"} and node.spec.invocation.invoke_without_command
    )

    assert terminal_groups
    assert all(spec.invocation.terminal_behavior is not None for spec in terminal_groups)
    assert {spec.key for spec in terminal_groups if spec.invocation.terminal_behavior == "executable"} == {
        "app_ledger_participation",
        "app_quickfile",
        "config_profile_descendiente",
        "config_repair",
    }
