"""Import-light builders for the profile record families under ``config profile``.

A record family is a repeatable profile section with its own door: a group named
after the family and the ``add``, ``edit``, ``list`` and ``remove`` leaves, each
bound to ``{family}_{token}`` in the family's handler module and to a typed
result schema in the family's payload module.
"""

from __future__ import annotations

from cadrumo_client.commands.execution_policies import (
    ENCRYPTED_DESTRUCTIVE,
    ENCRYPTED_READ,
    ENCRYPTED_WRITE,
    STATE_FREE,
)
from cadrumo_client.commands.parameters import ArgumentSpec, OptionSpec
from cadrumo_client.commands.shared_contracts import (
    TEXT_VALUE,
    WHOLE_NUMBER_VALUE,
    DeferredTarget,
    LazyBinding,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
    translation_key,
)
from cadrumo_client.commands.spec import CommandSpec, ExecutionPolicySpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind

_LANG = ValueContract(DeferredTarget("....core.external_constants", "OutputLanguage", __package__))
_PARENT = "config_profile"


def _option(name: str, declaration: str, help_key: str) -> OptionSpec:
    return OptionSpec(
        name,
        (declaration,),
        TEXT_VALUE,
        ParameterDefault.value(None),
        translation_key(help_key),
        multiple=True,
    )


_LANGUAGE = OptionSpec(
    "output_language",
    ("--output-language", "--language"),
    _LANG,
    ParameterDefault.value(None),
    translation_key("cli.config.auth.output_language_help"),
)


def record_row_argument(family: str) -> ArgumentSpec:
    """Return the required row-key argument of a family's leaf."""
    return ArgumentSpec(
        "row",
        WHOLE_NUMBER_VALUE,
        ParameterDefault.required(),
        translation_key(f"cli.config.profile.{family}.row_help"),
    )


def _group(family: str) -> CommandSpec:
    return CommandSpec(
        f"{_PARENT}_{family}",
        _PARENT,
        family,
        CommandNodeKind.GROUP,
        translation_key(f"cli.config.profile.{family}.help"),
        None,
        InvocationSpec(no_args_is_help=True),
        (),
        STATE_FREE,
        None,
        ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    )


def record_leaf(
    family: str,
    token: str,
    *,
    payloads: str,
    result: str,
    policy: ExecutionPolicySpec,
    parameters: tuple[ArgumentSpec | OptionSpec, ...] = (),
) -> CommandSpec:
    """Return one leaf of a family, bound to its handler and its result schema in ``payloads``."""
    parent = f"{_PARENT}_{family}"
    return CommandSpec(
        f"{parent}_{token}",
        parent,
        token,
        CommandNodeKind.LEAF,
        translation_key(f"cli.config.profile.{family}.{token}_help"),
        None,
        InvocationSpec(context_parameter="ctx"),
        (*parameters, _LANGUAGE),
        policy,
        LazyBinding.available(DeferredTarget(f".{family}", f"{family}_{token}", __package__)),
        ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(payloads, result, __package__),
            identity=f"config.profile.{family}.{token}",
        ),
    )


def record_family_specs(
    family: str, noun: str, *, payloads: str, extra: tuple[CommandSpec, ...] = ()
) -> tuple[CommandSpec, ...]:
    """Return the group and the four row leaves of one record family, then ``extra``."""
    value = _option("value", "--value", f"cli.config.profile.{family}.value_help")
    clear = _option("clear", "--clear", f"cli.config.profile.{family}.clear_help")
    row = record_row_argument(family)

    def leaf(
        token: str, policy: ExecutionPolicySpec, parameters: tuple[ArgumentSpec | OptionSpec, ...] = ()
    ) -> CommandSpec:
        result = f"ConfigProfile{noun}{token.capitalize()}Result"
        return record_leaf(family, token, payloads=payloads, result=result, policy=policy, parameters=parameters)

    return (
        _group(family),
        leaf("add", ENCRYPTED_WRITE, (value,)),
        leaf("edit", ENCRYPTED_WRITE, (row, value, clear)),
        leaf("list", ENCRYPTED_READ),
        leaf("remove", ENCRYPTED_DESTRUCTIVE, (row,)),
        *extra,
    )


__all__ = ["record_family_specs", "record_leaf", "record_row_argument"]
