"""Import-light production authority for the manual provider sign-in verb."""

from __future__ import annotations

from cadrumo_client.commands.language_options import OUTPUT_LANGUAGE_OPTION
from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.shared_contracts import (
    FLAG_VALUE,
    TEXT_VALUE,
    DeferredTarget,
    LazyBinding,
    ParameterDefault,
    TranslationKey,
)
from cadrumo_client.commands.spec import CommandSpec, ExecutionPolicySpec, InvocationSpec
from cadrumo_client.commands.spec_schema import config_payload_schema
from cadrumo_client.contracts.command_ports import CommandNodeKind, CommandWriteRoute

# The agent runs as a child that owns the terminal; the verb reads no profile data itself.
_POLICY = ExecutionPolicySpec(
    capabilities=frozenset({"subprocess"}),
    side_effects=frozenset({"local-state"}),
    performance="interactive",
    write_route=CommandWriteRoute.NONE,
)

CONFIG_PROVIDER_LOGIN_COMMAND_SPECS = (
    CommandSpec(
        "config_provider_login",
        "config",
        "provider-login",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provider_login.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="provider",
                declarations=("--provider",),
                value=TEXT_VALUE,
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.config.provider_login.provider_help"),
            ),
            OptionSpec(
                name="device",
                declarations=("--device",),
                value=FLAG_VALUE,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.config.provider_login.device_help"),
                is_flag=True,
                flag_value=True,
            ),
            OptionSpec(
                name="profile",
                declarations=("--profile",),
                value=TEXT_VALUE,
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.provider_login.profile_help"),
            ),
            OUTPUT_LANGUAGE_OPTION,
        ),
        policy=_POLICY,
        handler=LazyBinding.available(DeferredTarget(".provider_login_cli", "config_provider_login", __package__)),
        result_schema=config_payload_schema("ConfigProviderLoginResult", "config.provider_login"),
    ),
)

__all__ = ["CONFIG_PROVIDER_LOGIN_COMMAND_SPECS"]
