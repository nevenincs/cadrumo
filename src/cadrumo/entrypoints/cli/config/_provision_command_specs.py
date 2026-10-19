"""Import-light production authority for the ``config provision`` commands.

Every leaf submits a registered operation through the runtime: the setup
status, setup and verification operations, or the local reader's actions
that download nothing. Each therefore runs in the signed-in profile's
session, so the policies below declare installation storage beside the
network rather than the profile-free pair that would skip the session.
"""

from __future__ import annotations

from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.shared_contracts import (
    DeferredTarget,
    LazyBinding,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from cadrumo_client.commands.spec import CommandSpec, ExecutionPolicySpec, InvocationSpec
from cadrumo_client.contracts.command_ports import Capability, CommandNodeKind, CommandWriteRoute

from ._spec_policies import STATE_FREE

_STORAGE_AND_NETWORK: frozenset[Capability] = frozenset({"local-storage", "network"})
# Reads installation storage and the network and changes nothing.
_SETUP_READ = ExecutionPolicySpec(_STORAGE_AND_NETWORK, frozenset({"none"}), "external-io", CommandWriteRoute.NONE)
# Exercises an item at the network (a refresh, a load) and records nothing locally.
_SETUP_EXERCISE = ExecutionPolicySpec(
    _STORAGE_AND_NETWORK, frozenset({"network"}), "external-io", CommandWriteRoute.NONE
)
_SETUP_WRITE = ExecutionPolicySpec(
    _STORAGE_AND_NETWORK, frozenset({"network", "local-state"}), "external-io", CommandWriteRoute.NONE
)
_SETUP_DESTRUCTIVE = ExecutionPolicySpec(
    _STORAGE_AND_NETWORK,
    frozenset({"network", "local-state"}),
    "external-io",
    CommandWriteRoute.NONE,
    destructive=True,
)

_MODEL = OptionSpec(
    name="model",
    declarations=("--model",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.provision.pull.model_help"),
)
_YES = OptionSpec(
    name="yes",
    declarations=("--yes",),
    value=ValueContract(DeferredTarget("builtins", "bool")),
    default=ParameterDefault.value(False),
    help_key=TranslationKey("cli.config.provision.yes_help"),
)
_ROLE = OptionSpec(
    name="role",
    declarations=("--role",),
    value=ValueContract(DeferredTarget("....core.model_catalogue", "ModelRole", __package__)),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.provision.role_help"),
)
_ITEM = OptionSpec(
    name="item",
    declarations=("--item",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.provision.verify.item_help"),
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
        policy=_SETUP_READ,
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
        parameters=(_MODEL, _YES),
        policy=_SETUP_WRITE,
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
        parameters=(_ITEM,),
        policy=_SETUP_EXERCISE,
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
        policy=_SETUP_READ,
        handler=_handler("provision_status"),
        result_schema=_schema("ProvisionStatusResult", "config.provision.status"),
    ),
    CommandSpec(
        "config_provision_probe",
        "config_provision",
        "probe",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provision.probe.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=_SETUP_EXERCISE,
        handler=_handler("provision_probe"),
        result_schema=_schema("ProvisionProbeResult", "config.provision.probe"),
    ),
    CommandSpec(
        "config_provision_browser",
        "config_provision",
        "browser",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provision.browser.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_YES,),
        policy=_SETUP_WRITE,
        handler=_handler("provision_browser"),
        result_schema=_schema("ProvisionBrowserResult", "config.provision.browser"),
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
        policy=_SETUP_WRITE,
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
        policy=_SETUP_DESTRUCTIVE,
        handler=_handler("provision_remove"),
        result_schema=_schema("ProvisionRemoveResult", "config.provision.remove"),
    ),
    CommandSpec(
        "config_provision_load",
        "config_provision",
        "load",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provision.load.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="model",
                declarations=("--model",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.provision.load.model_help"),
            ),
            _ROLE,
        ),
        policy=_SETUP_WRITE,
        handler=_handler("provision_load"),
        result_schema=_schema("ProvisionLoadResult", "config.provision.load"),
    ),
    CommandSpec(
        "config_provision_setup",
        "config_provision",
        "setup",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provision.setup.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_YES,),
        policy=_SETUP_WRITE,
        handler=_handler("provision_setup"),
        result_schema=_schema("ProvisionSetupResult", "config.provision.setup"),
    ),
)


__all__ = ["CONFIG_PROVISION_COMMAND_SPECS"]
