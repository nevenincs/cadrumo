"""Import-light authority for the property and lease doors under ``config profile``."""

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
_PAYLOADS = "..config_rental_payloads"
_PARENT = "config_profile"


def _option(name: str, declaration: str, help_key: str, *, required: bool = False) -> OptionSpec:
    return OptionSpec(
        name,
        (declaration,),
        TEXT_VALUE,
        ParameterDefault.required() if required else ParameterDefault.value(None),
        translation_key(help_key),
        multiple=not required,
    )


_LANGUAGE = OptionSpec(
    "output_language",
    ("--output-language", "--language"),
    _LANG,
    ParameterDefault.value(None),
    translation_key("cli.config.auth.output_language_help"),
)


def _row_argument(family: str) -> ArgumentSpec:
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


def _leaf(
    family: str,
    token: str,
    result: str,
    policy: ExecutionPolicySpec,
    parameters: tuple[ArgumentSpec | OptionSpec, ...] = (),
) -> CommandSpec:
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
            DeferredTarget(_PAYLOADS, result, __package__),
            identity=f"config.profile.{family}.{token}",
        ),
    )


def _family(family: str, noun: str, *, extra: tuple[CommandSpec, ...] = ()) -> tuple[CommandSpec, ...]:
    value = _option("value", "--value", f"cli.config.profile.{family}.value_help")
    clear = _option("clear", "--clear", f"cli.config.profile.{family}.clear_help")
    return (
        _group(family),
        _leaf(family, "add", f"ConfigProfile{noun}AddResult", ENCRYPTED_WRITE, (value,)),
        _leaf(family, "edit", f"ConfigProfile{noun}EditResult", ENCRYPTED_WRITE, (_row_argument(family), value, clear)),
        _leaf(family, "list", f"ConfigProfile{noun}ListResult", ENCRYPTED_READ),
        _leaf(family, "remove", f"ConfigProfile{noun}RemoveResult", ENCRYPTED_DESTRUCTIVE, (_row_argument(family),)),
        *extra,
    )


_END = _leaf(
    "arrendamiento",
    "end",
    "ConfigProfileArrendamientoEndResult",
    ENCRYPTED_WRITE,
    (
        _row_argument("arrendamiento"),
        ArgumentSpec(
            "fecha",
            TEXT_VALUE,
            ParameterDefault.required(),
            translation_key("cli.config.profile.arrendamiento.end_fecha_help"),
        ),
    ),
)

RENTAL_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    *_family("arrendamiento", "Arrendamiento", extra=(_END,)),
    *_family("inmueble", "Inmueble"),
)

__all__ = ["RENTAL_COMMAND_SPECS"]
