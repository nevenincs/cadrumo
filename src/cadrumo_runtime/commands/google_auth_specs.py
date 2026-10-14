"""Import-light production command authority for the config Google family."""

from __future__ import annotations

from typing import Final

from cadrumo.core.transport_locus import TransportLocus, TransportRole, TransportShape
from cadrumo_client.commands.parameters import ArgumentSpec, OptionSpec
from cadrumo_client.commands.shared_contracts import (
    DeferredTarget,
    LazyBinding,
    LiteralValue,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
)
from cadrumo_client.commands.shared_contracts import translation_key as _key
from cadrumo_client.commands.spec import CommandSpec, ExecutionPolicySpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind, ProfileAuthenticationPosture
from cadrumo_runtime.commands.spec_policies import (
    GOOGLE_DESTRUCTIVE,
    GOOGLE_READ,
    GOOGLE_WRITE,
    state_free_group_spec,
)

# Every dynamically resolved handler module is named here as a WHOLE dotted path.
# The path used to be built with an f-string, which meant no static reader -- grep,
# the import-boundary checker, or a dead-code sweep -- could see the edge, so all of
# these modules read as orphaned while backing live verbs. A wrong key now raises
# at spec-build time instead of failing lazily on first invocation.
_HANDLER_MODULES: Final[dict[str, str]] = {
    "_google": ".google",
    "_google_folder": "._google_folder",
    "_google_folder_payloads": "._google_folder_payloads",
    "_google_payloads": "cadrumo_client.commands.google_payloads",
}


def _handler(module: str, name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget(_HANDLER_MODULES[module], name, __package__))


def _schema(module: str, name: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget(_HANDLER_MODULES[module], name, __package__),
        identity=identity,
    )


def _option(
    name: str,
    declarations: tuple[str, ...],
    value: ValueContract,
    help_key: str,
    *,
    required: bool = False,
    default: LiteralValue | tuple[LiteralValue, ...] = None,
    flag: bool = False,
    multiple: bool = False,
    minimum: int | None = None,
    maximum: int | None = None,
    transport_locus: TransportLocus = TransportLocus.NONE,
    transport_shape: TransportShape = TransportShape.NOT_APPLICABLE,
    transport_role: TransportRole = TransportRole.NOT_APPLICABLE,
) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=value,
        default=ParameterDefault.required() if required else ParameterDefault.value(default),
        help_key=_key(help_key),
        is_flag=flag,
        flag_value=True if flag else None,
        multiple=multiple,
        constraint=ParameterConstraint(minimum=minimum, maximum=maximum),
        transport_locus=transport_locus,
        transport_shape=transport_shape,
        transport_role=transport_role,
    )


def _leaf(
    key: str,
    parent: str,
    token: str,
    help_key: str,
    module: str,
    handler: str,
    schema_module: str,
    schema_name: str,
    policy: ExecutionPolicySpec,
    parameters: tuple[ArgumentSpec | OptionSpec, ...] = (),
    *,
    identity: str | None = None,
) -> CommandSpec:
    return CommandSpec(
        key=key,
        parent_key=parent,
        token=token,
        kind=CommandNodeKind.LEAF,
        help_key=_key(help_key),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=parameters,
        policy=policy,
        handler=_handler(module, handler),
        result_schema=_schema(schema_module, schema_name, identity or key.replace("_", ".")),
        profile_authentication=ProfileAuthenticationPosture.RESUME_FALLBACK,
    )


RUNTIME_GOOGLE_AUTH_COMMAND_SPECS = (
    state_free_group_spec("config_google", "config", "google", "cli.config.google.help"),
    _leaf(
        "config_google_login",
        "config_google",
        "login",
        "cli.config.google.login_help",
        "_google",
        "google_login",
        "_google_payloads",
        "GoogleLoginResult",
        GOOGLE_WRITE,
    ),
    _leaf(
        "config_google_status",
        "config_google",
        "status",
        "cli.config.google.status_help",
        "_google",
        "google_status",
        "_google_payloads",
        "GoogleStatusResult",
        GOOGLE_READ,
    ),
    _leaf(
        "config_google_logout",
        "config_google",
        "logout",
        "cli.config.google.logout_help",
        "_google",
        "google_logout",
        "_google_payloads",
        "GoogleLogoutResult",
        GOOGLE_DESTRUCTIVE,
    ),
)


__all__ = ["RUNTIME_GOOGLE_AUTH_COMMAND_SPECS"]
