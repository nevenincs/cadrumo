from __future__ import annotations

from dataclasses import replace

import pytest
from click import IntRange
from typer.testing import CliRunner

from .._command_runtime import (
    _parameter,
    build_command_app,
    build_command_subtree,
    command_schema_targets,
    resolve_deferred_target,
)
from ..command_spec import (
    ArgumentSpec,
    CommandNodeKind,
    CommandSpec,
    CommandSpecGraph,
    CommandWriteRoute,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_SEEN: list[tuple[object, str]] = []
_SEEN_MULTIPLE: list[list[str]] = []
_POLICY = ExecutionPolicySpec(
    capabilities=frozenset({"state-free"}),
    side_effects=frozenset({"none"}),
    performance="metadata",
    write_route=CommandWriteRoute.NONE,
)
_NO_SCHEMA = ResultSchemaSpec(SchemaState.NOT_SUPPORTED)


def public_behavior(ctx: object, *, name: str) -> None:
    _SEEN.append((ctx, name))


def public_multiple_behavior(ctx: object, *, name: list[str]) -> None:
    del ctx
    _SEEN_MULTIPLE.append(name)


def public_parser(value: str) -> str:
    return value


def _graph() -> CommandSpecGraph:
    root = CommandSpec(
        key="root",
        parent_key=None,
        token="aeat",  # noqa: S106 - CLI operator token, not a credential
        kind=CommandNodeKind.ROOT,
        help_key=TranslationKey("cli.root.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=_POLICY,
        handler=None,
        result_schema=_NO_SCHEMA,
    )
    leaf = CommandSpec(
        key="greet",
        parent_key="root",
        token="greet",  # noqa: S106 - CLI operator token, not a credential
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.root.version_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="name",
                declarations=("--name",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.root.language_help"),
            ),
        ),
        policy=_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli.tests.test_command_runtime", "public_behavior")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("builtins", "dict"),
            identity="root.greet",
        ),
    )
    return CommandSpecGraph((root, leaf))


def test_runtime_preflights_and_invokes_a_synthetic_graph_behavior() -> None:
    _SEEN.clear()
    result = CliRunner().invoke(build_command_app(_graph()), ["greet", "--name", "Ada"])

    assert result.exit_code == 0, result.output
    assert len(_SEEN) == 1
    assert _SEEN[0][1] == "Ada"


def test_runtime_schema_projection_and_public_target_boundary() -> None:
    assert command_schema_targets(_graph()) == (("root.greet", DeferredTarget("builtins", "dict")),)
    assert resolve_deferred_target(DeferredTarget("builtins", "str")) is str
    assert build_command_subtree(_graph(), "greet").registered_commands[0].name == "greet"


def test_runtime_preserves_an_option_with_no_help_text() -> None:
    graph = _graph()
    leaf = graph.by_key()["greet"]
    option = leaf.parameters[0]
    assert isinstance(option, OptionSpec)
    exact_graph = CommandSpecGraph(
        tuple(
            replace(spec, parameters=(replace(option, help_key=None),)) if spec.key == "greet" else spec
            for spec in graph.specs
        )
    )

    result = CliRunner().invoke(build_command_app(exact_graph), ["greet", "--help"])

    assert result.exit_code == 0, result.output
    assert "--name" in result.output


def test_runtime_compiles_spec_owned_choices_without_a_handler_enum() -> None:
    graph = _graph()
    leaf = graph.by_key()["greet"]
    option = leaf.parameters[0]
    assert isinstance(option, OptionSpec)
    exact_graph = CommandSpecGraph(
        tuple(
            replace(spec, parameters=(replace(option, value=replace(option.value, choices=("Ada", "Grace"))),))
            if spec.key == "greet"
            else spec
            for spec in graph.specs
        )
    )

    accepted = CliRunner().invoke(build_command_app(exact_graph), ["greet", "--name", "Ada"])
    refused = CliRunner().invoke(build_command_app(exact_graph), ["greet", "--name", "Linus"])
    help_result = CliRunner().invoke(build_command_app(exact_graph), ["greet", "--help"])

    assert accepted.exit_code == 0, accepted.output
    assert refused.exit_code == 2
    assert "Ada" in refused.output
    assert "Grace" in refused.output
    assert "<Ada|Grace>" in help_result.output


def test_runtime_preserves_repeated_options_as_a_list_of_items() -> None:
    graph = _graph()
    leaf = graph.by_key()["greet"]
    option = leaf.parameters[0]
    assert isinstance(option, OptionSpec)
    exact_graph = CommandSpecGraph(
        tuple(
            replace(
                spec,
                parameters=(replace(option, multiple=True),),
                handler=LazyBinding.available(
                    DeferredTarget(
                        "cadrumo.entrypoints.cli.tests.test_command_runtime",
                        "public_multiple_behavior",
                    )
                ),
            )
            if spec.key == "greet"
            else spec
            for spec in graph.specs
        )
    )
    _SEEN_MULTIPLE.clear()

    result = CliRunner().invoke(
        build_command_app(exact_graph),
        ["greet", "--name", "Ada", "--name", "Grace"],
    )

    assert result.exit_code == 0, result.output
    assert _SEEN_MULTIPLE == [["Ada", "Grace"]]


@pytest.mark.parametrize(
    ("value", "expected_parser", "expected_click_type"),
    (
        (
            ValueContract(
                DeferredTarget("builtins", "str"),
                parser=DeferredTarget(
                    "cadrumo.entrypoints.cli.tests.test_command_runtime",
                    "public_parser",
                ),
            ),
            public_parser,
            None,
        ),
        (
            ValueContract(
                DeferredTarget("builtins", "int"),
                click_type=DeferredTarget("click", "IntRange"),
            ),
            None,
            IntRange,
        ),
    ),
)
def test_runtime_materializes_shared_value_and_constraint_kwargs_for_arguments_and_options(
    value: ValueContract,
    expected_parser: object | None,
    expected_click_type: type[IntRange] | None,
) -> None:
    constraint = ParameterConstraint(
        minimum=1,
        maximum=3,
        clamp=True,
        case_sensitive=False,
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=False,
        resolve_path=True,
        allow_dash=True,
    )
    argument = _parameter(
        ArgumentSpec(
            name="item",
            value=value,
            default=ParameterDefault.required(),
            help_key=None,
            constraint=constraint,
        )
    ).default
    option = _parameter(
        OptionSpec(
            name="item",
            declarations=("--item",),
            value=value,
            default=ParameterDefault.required(),
            help_key=None,
            constraint=constraint,
        )
    ).default

    shared_values = (
        "default_factory",
        "help",
        "show_default",
        "hidden",
        "min",
        "max",
        "clamp",
        "case_sensitive",
        "exists",
        "file_okay",
        "dir_okay",
        "writable",
        "readable",
        "resolve_path",
        "allow_dash",
        "parser",
    )
    assert tuple(getattr(argument, name) for name in shared_values) == tuple(
        getattr(option, name) for name in shared_values
    )
    assert argument.parser is expected_parser
    assert option.parser is expected_parser
    if expected_click_type is None:
        assert argument.click_type is None
        assert option.click_type is None
    else:
        assert isinstance(argument.click_type, expected_click_type)
        assert isinstance(option.click_type, expected_click_type)
