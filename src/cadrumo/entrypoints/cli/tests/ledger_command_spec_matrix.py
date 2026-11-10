"""Expected-matrix builders and projections for the ledger command-spec contract tests."""

from __future__ import annotations

from typing import Final

from cadrumo.entrypoints.cli.command_targets import resolve_deferred_target
from cadrumo_client.commands.parameters import ArgumentSpec, ParameterSpec
from cadrumo_client.commands.spec import CommandSpec

_NO_VALUE_HOOKS: Final[tuple[object, ...]] = (None, None, None, None)
DEFAULT_CONSTRAINT: Final[tuple[object, ...]] = (
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
    False,
)
NON_BLANK_CONSTRAINT_CONTRACT: Final[tuple[object, ...]] = (*DEFAULT_CONSTRAINT[:-1], True)
_NO_TRANSPORT: Final[tuple[str, ...]] = ("none", "not_applicable", "not_applicable")

REQUIRED_DEFAULT: Final[tuple[object, ...]] = ("REQUIRED", None, None)
NONE_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", None, None)
EMPTY_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", "", None)
FALSE_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", False, None)
EMPTY_TUPLE_DEFAULT: Final[tuple[object, ...]] = ("LITERAL", (), None)

GROUP_INVOCATION_CONTRACT: Final[tuple[object, ...]] = (False, True, False, True, False, False, None, None)
_LEAF_INVOCATION_CONTRACT: Final[tuple[object, ...]] = (False, False, False, True, False, False, "ctx", None)

NO_RESULT_SCHEMA_CONTRACT: Final[tuple[str, None, None, None]] = ("not-supported", None, None, None)


def expected_argument(
    name: str,
    help_key: str,
    *,
    annotation: str = "builtins:str",
    default: tuple[object, ...] = REQUIRED_DEFAULT,
    value_hooks: tuple[object, ...] = _NO_VALUE_HOOKS,
    choices: tuple[str, ...] = (),
    metavar: str | None = None,
    show_default: bool = True,
    hidden: bool = False,
    constraint: tuple[object, ...] = DEFAULT_CONSTRAINT,
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


def expected_option(
    name: str,
    declaration: str,
    help_key: str,
    *,
    annotation: str = "builtins:str",
    default: tuple[object, ...] = NONE_DEFAULT,
    value_hooks: tuple[object, ...] = _NO_VALUE_HOOKS,
    choices: tuple[str, ...] = (),
    metavar: str | None = None,
    show_default: bool = True,
    hidden: bool = False,
    constraint: tuple[object, ...] = DEFAULT_CONSTRAINT,
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


type _ExpectedResultSchema = tuple[str, str | None, str | None, str | None]
type ExpectedCommand = tuple[
    str,
    str,
    str,
    str,
    str,
    None,
    tuple[object, ...],
    tuple[tuple[object, ...], ...],
    str,
    str | None,
    _ExpectedResultSchema,
]


def expected_result_schema(
    state: str,
    target: str | None,
    identity: str | None,
    *,
    reason_key: str | None = None,
) -> _ExpectedResultSchema:
    """Build a complete expected ResultSchemaSpec projection from literal facts."""
    return (state, target, reason_key, identity)


def expected_command(
    key: str,
    parent_key: str,
    token: str,
    kind: str,
    help_key: str,
    write_route: str,
    handler: str | None,
    result_schema: _ExpectedResultSchema,
    parameters: tuple[tuple[object, ...], ...] = (),
    *,
    invocation: tuple[object, ...] = _LEAF_INVOCATION_CONTRACT,
) -> ExpectedCommand:
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


TARGET = "target"


def _target_identity(target: object | None) -> str | None:
    """Project a deferred target or translation key to its stable identity."""
    if target is None:
        return None
    identity = getattr(target, "identity", None)
    if identity is None:
        identity = getattr(target, "value", None)
    return identity if isinstance(identity, str) else None


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
        constraint.non_blank,
    )


def _transport_contract(parameter: ParameterSpec) -> tuple[str, ...]:
    return (parameter.transport_locus.value, parameter.transport_shape.value, parameter.transport_role.value)


def parameter_contract(parameter: ParameterSpec) -> tuple[object, ...]:
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


def literal_contract(command: CommandSpec) -> tuple[object, ...]:
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
        tuple(parameter_contract(parameter) for parameter in command.parameters),
        command.policy.write_route.value,
        handler,
        _result_schema_contract(command),
    )


def assert_live_targets_match_expected(spec: CommandSpec, expected: ExpectedCommand) -> None:
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
