from __future__ import annotations

from dataclasses import replace

import pytest
from click import IntRange
from typer.testing import CliRunner

from ....core.i18n.render import tr
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
_SEEN_OPTION_RUNTIME: list[tuple[str, bool]] = []
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


def public_default_factory() -> str:
    return "factory default"


def public_option_callback(value: str) -> str:
    return value.upper()


def public_option_completion() -> list[str]:
    return ["Ada"]


def public_option_behavior(ctx: object, *, name: str, enabled: bool) -> None:
    del ctx
    _SEEN_OPTION_RUNTIME.append((name, enabled))


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
    default = ParameterDefault.value("literal default")
    help_key = TranslationKey("cli.root.language_help")
    argument_spec = ArgumentSpec(
        name="item",
        value=value,
        default=default,
        help_key=help_key,
        metavar="ITEM",
        show_default=False,
        hidden=True,
        constraint=constraint,
    )
    option_spec = OptionSpec(
        name="item",
        declarations=("--item",),
        value=value,
        default=default,
        help_key=help_key,
        metavar="ITEM",
        show_default=False,
        hidden=True,
        constraint=constraint,
    )
    argument = _parameter(argument_spec).default
    option = _parameter(option_spec).default

    for parameter, spec in ((argument, argument_spec), (option, option_spec)):
        assert spec.help_key is not None
        assert parameter.default == spec.default.literal
        assert parameter.default_factory is None
        assert parameter.help == tr(spec.help_key.value)
        assert parameter.metavar == spec.metavar
        assert parameter.show_default is spec.show_default
        assert parameter.hidden is spec.hidden
        assert parameter.min == spec.constraint.minimum
        assert parameter.max == spec.constraint.maximum
        assert parameter.clamp is spec.constraint.clamp
        assert parameter.case_sensitive is spec.constraint.case_sensitive
        assert parameter.exists is spec.constraint.exists
        assert parameter.file_okay is spec.constraint.file_okay
        assert parameter.dir_okay is spec.constraint.dir_okay
        assert parameter.writable is spec.constraint.writable
        assert parameter.readable is spec.constraint.readable
        assert parameter.resolve_path is spec.constraint.resolve_path
        assert parameter.allow_dash is spec.constraint.allow_dash
        assert parameter.parser is expected_parser
        if expected_click_type is None:
            assert parameter.click_type is None
        else:
            assert isinstance(parameter.click_type, expected_click_type)


def test_runtime_materializes_factory_defaults_for_arguments_and_options() -> None:
    default = ParameterDefault.from_factory(
        DeferredTarget(
            "cadrumo.entrypoints.cli.tests.test_command_runtime",
            "public_default_factory",
        )
    )
    value = ValueContract(DeferredTarget("builtins", "str"))
    argument = _parameter(
        ArgumentSpec(
            name="item",
            value=value,
            default=default,
            help_key=None,
        )
    ).default
    option = _parameter(
        OptionSpec(
            name="item",
            declarations=("--item",),
            value=value,
            default=default,
            help_key=None,
        )
    ).default

    for parameter in (argument, option):
        assert parameter.default is None
        assert parameter.default_factory is not None
        assert parameter.default_factory() == public_default_factory()


def test_runtime_materializes_and_exercises_option_only_hooks() -> None:
    name_option = OptionSpec(
        name="name",
        declarations=("--name",),
        value=ValueContract(
            DeferredTarget("builtins", "str"),
            callback=DeferredTarget(
                "cadrumo.entrypoints.cli.tests.test_command_runtime",
                "public_option_callback",
            ),
            completion=DeferredTarget(
                "cadrumo.entrypoints.cli.tests.test_command_runtime",
                "public_option_completion",
            ),
        ),
        default=ParameterDefault.required(),
        help_key=TranslationKey("cli.root.language_help"),
        metavar="NAME",
        prompt_key=TranslationKey("cli.root.language_help"),
        confirmation_prompt_key=TranslationKey("cli.root.language_help"),
        envvar=("CADRUMO_TEST_NAME",),
        eager=True,
    )
    enabled_option = OptionSpec(
        name="enabled",
        declarations=("--enabled/--disabled",),
        value=ValueContract(DeferredTarget("builtins", "bool")),
        default=ParameterDefault.value(False),
        help_key=TranslationKey("cli.root.language_help"),
        is_flag=True,
        flag_value=True,
    )
    materialized = _parameter(name_option).default
    assert name_option.prompt_key is not None
    assert name_option.confirmation_prompt_key is not None
    assert materialized.param_decls == name_option.declarations
    assert materialized.prompt == tr(name_option.prompt_key.value)
    assert materialized.confirmation_prompt == tr(name_option.confirmation_prompt_key.value)
    assert materialized.envvar == list(name_option.envvar)
    assert materialized.is_eager is name_option.eager
    assert materialized.callback is public_option_callback
    assert materialized.shell_complete is public_option_completion

    graph = _graph()
    runtime_graph = CommandSpecGraph(
        tuple(
            replace(
                spec,
                parameters=(name_option, enabled_option),
                handler=LazyBinding.available(
                    DeferredTarget(
                        "cadrumo.entrypoints.cli.tests.test_command_runtime",
                        "public_option_behavior",
                    )
                ),
            )
            if spec.key == "greet"
            else spec
            for spec in graph.specs
        )
    )
    _SEEN_OPTION_RUNTIME.clear()

    result = CliRunner().invoke(
        build_command_app(runtime_graph),
        ["greet", "--enabled"],
        input="Ada\nAda\n",
    )

    assert result.exit_code == 0, result.output
    assert _SEEN_OPTION_RUNTIME == [("ADA", True)]
