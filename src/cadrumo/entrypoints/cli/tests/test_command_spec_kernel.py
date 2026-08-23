from __future__ import annotations

import dataclasses
import subprocess
import sys

import pytest

from .._command_policy import CommandExecutionPolicy
from .._command_schema import CommandCapabilityClass
from .._command_spec import (
    ArgumentSpec,
    CommandSpec,
    CommandSpecGraph,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

_STATE_FREE = CommandExecutionPolicy(
    classification=CommandCapabilityClass(
        capabilities=frozenset({"state-free"}),
        side_effects=frozenset({"none"}),
        performance="metadata",
    ),
    write_route="none",
)
_STRING = ValueContract(DeferredTarget("builtins", "str"))
_NO_SCHEMA = ResultSchemaSpec(SchemaState.NOT_SUPPORTED)


def _root() -> CommandSpec:
    return CommandSpec(
        key="root",
        parent_key=None,
        token="aeat",
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
        token="config",
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
        token="list",
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
        ),
    )


def test_kernel_is_immutable_import_light_and_derives_paths_from_edges() -> None:
    graph = CommandSpecGraph((_leaf(), _root(), _group()))

    assert tuple(node.path for node in graph.nodes()) == (
        ("aeat",),
        ("aeat", "config"),
        ("aeat", "config", "list"),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        graph.specs = ()  # type: ignore[misc]

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import cadrumo.entrypoints.cli._command_spec; "
                "print(int('typer' in sys.modules), int('click' in sys.modules), "
                "int('json' in sys.modules), int('pydantic' in sys.modules))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert probe.stdout.strip() == "0 0 0 0"


@pytest.mark.parametrize(
    ("specs", "message"),
    [
        ((_root(), dataclasses.replace(_root(), key="second_root", token="other")), "exactly one root"),
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
def test_graph_rejects_missing_duplicate_and_invalid_edges(
    specs: tuple[CommandSpec, ...], message: str
) -> None:
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
    with pytest.raises(ValueError, match="requires only a deferred target"):
        LazyBinding(state=unavailable.state, target=DeferredTarget("builtins", "str"))


def test_target_and_schema_identities_are_production_authored() -> None:
    leaf = _leaf()
    assert leaf.handler is not None
    assert leaf.handler.target is not None
    assert leaf.handler.target.identity.endswith(":profile_list")
    assert leaf.result_schema.target is not None
    assert leaf.result_schema.target.identity.endswith(":ProfileListPayload")
