"""Import-light production authority for local-inference lifecycle commands."""

from __future__ import annotations

from cadrumo.application.operator_surface.command_ports import CommandNodeKind

from ..command_spec import (
    CommandSpec,
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
from ._spec_policies import ENCRYPTED_READ, LOCAL_READ, NETWORK_DESTRUCTIVE, NETWORK_WRITE, STATE_FREE

_MODEL = OptionSpec(
    name="model",
    declarations=("--model",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.provision.pull.model_help"),
)
_ROLE = OptionSpec(
    name="role",
    declarations=("--role",),
    value=ValueContract(DeferredTarget("....core.model_catalogue", "ModelRole", __package__)),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.provision.role_help"),
)


_CONFIRM = OptionSpec(
    name="confirm",
    declarations=("--confirm",),
    value=ValueContract(DeferredTarget("builtins", "bool")),
    default=ParameterDefault.value(False),
    help_key=TranslationKey("cli.config.provision.install.confirm_help"),
)
_REMOVE_MODEL = OptionSpec(
    name="model",
    declarations=("--model",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.provision.remove.model_help"),
)


def _handler(name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget(".provision_cli", name, __package__))


def _schema(name: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget(".provision_payloads", name, __package__),
        identity=identity,
    )


CONFIG_PROVISION_COMMAND_SPECS = (
    CommandSpec(
        "config_provision",
        "config",
        "provision",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.config.provision.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "config_provision_report",
        "config_provision",
        "report",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provision.report.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=ENCRYPTED_READ,
        handler=_handler("provision_report"),
        result_schema=_schema("ProvisionReportResult", "config.provision.report"),
    ),
    CommandSpec(
        "config_provision_pull",
        "config_provision",
        "pull",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provision.pull.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_MODEL, _ROLE),
        policy=NETWORK_WRITE,
        handler=_handler("provision_pull"),
        result_schema=_schema("ProvisionPullResult", "config.provision.pull"),
    ),
    CommandSpec(
        "config_provision_verify",
        "config_provision",
        "verify",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provision.verify.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="model",
                declarations=("--model",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.provision.verify.model_help"),
            ),
            _ROLE,
        ),
        policy=ENCRYPTED_READ,
        handler=_handler("provision_verify"),
        result_schema=_schema("ProvisionVerifyResult", "config.provision.verify"),
    ),
    CommandSpec(
        "config_provision_status",
        "config_provision",
        "status",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provision.status.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=LOCAL_READ,
        handler=_handler("provision_status"),
        result_schema=_schema("ProvisionStatusResult", "config.provision.status"),
    ),
    CommandSpec(
        "config_provision_install",
        "config_provision",
        "install",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provision.install.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_CONFIRM,),
        policy=NETWORK_WRITE,
        handler=_handler("provision_install"),
        result_schema=_schema("ProvisionInstallResult", "config.provision.install"),
    ),
    CommandSpec(
        "config_provision_start",
        "config_provision",
        "start",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provision.start.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=NETWORK_WRITE,
        handler=_handler("provision_start"),
        result_schema=_schema("ProvisionStartResult", "config.provision.start"),
    ),
    CommandSpec(
        "config_provision_remove",
        "config_provision",
        "remove",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provision.remove.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_REMOVE_MODEL, _ROLE),
        policy=NETWORK_DESTRUCTIVE,
        handler=_handler("provision_remove"),
        result_schema=_schema("ProvisionRemoveResult", "config.provision.remove"),
    ),
)


__all__ = ["CONFIG_PROVISION_COMMAND_SPECS"]
