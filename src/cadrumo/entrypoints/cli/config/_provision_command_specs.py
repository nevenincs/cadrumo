"""Import-light production authority for the ``config provision`` commands.

The component leaves (status, probe, verify, setup, browser, pull, remove) run
the native component engine's role, which reaches only installation-wide
components no profile holds, so they declare only profile-free capabilities and
run without a session: the quick check reads local files, a full check reaches
the network, a setup downloads into component storage and a removal deletes
from it. The local reader's report submits a registered operation through the
runtime in the signed-in profile's session, so its policy declares
installation storage beside the network rather than the profile-free set that
would skip the session.
"""

from __future__ import annotations

from cadrumo_client.commands.execution_policies import STATE_FREE
from cadrumo_client.commands.parameters import ArgumentSpec, OptionSpec
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

_STORAGE_AND_NETWORK: frozenset[Capability] = frozenset({"local-storage", "network"})
_PROFILE_FREE: frozenset[Capability] = frozenset({"network"})
# Installation-wide component storage, which the engine changes and no profile holds.
_COMPONENT_STORAGE: frozenset[Capability] = frozenset({"components"})
# The engine's quick check: local files only, no network and no model load.
_COMPONENT_READ = ExecutionPolicySpec(
    frozenset({"state-free"}), frozenset({"none"}), "local-io", CommandWriteRoute.NONE
)
# The engine's full check reaches each item's hosts, launches the browser and asks each model one token.
_COMPONENT_CHECK = ExecutionPolicySpec(_PROFILE_FREE, frozenset({"network"}), "external-io", CommandWriteRoute.NONE)
# The engine's setup downloads and installs into installation-wide component storage.
_COMPONENT_SETUP = ExecutionPolicySpec(
    _PROFILE_FREE | _COMPONENT_STORAGE, frozenset({"network", "local-state"}), "external-io", CommandWriteRoute.NONE
)
# The engine's removal deletes an item from component storage and reaches no network.
_COMPONENT_REMOVE = ExecutionPolicySpec(
    _COMPONENT_STORAGE, frozenset({"local-state"}), "local-io", CommandWriteRoute.NONE, destructive=True
)
# Reads installation storage and the network and changes nothing.
_SETUP_READ = ExecutionPolicySpec(_STORAGE_AND_NETWORK, frozenset({"none"}), "external-io", CommandWriteRoute.NONE)

_YES = OptionSpec(
    name="yes",
    declarations=("--yes",),
    value=ValueContract(DeferredTarget("builtins", "bool")),
    default=ParameterDefault.value(False),
    help_key=TranslationKey("cli.config.provision.yes_help"),
)
_ITEM = OptionSpec(
    name="item",
    declarations=("--item",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.provision.verify.item_help"),
)
_REMOVE_ITEM = ArgumentSpec(
    name="item",
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.config.provision.remove.item_help"),
)
_REMOVE_YES = OptionSpec(
    name="yes",
    declarations=("--yes",),
    value=ValueContract(DeferredTarget("builtins", "bool")),
    default=ParameterDefault.value(False),
    help_key=TranslationKey("cli.config.provision.remove.yes_help"),
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
        parameters=(_YES,),
        policy=_COMPONENT_SETUP,
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
        policy=_COMPONENT_CHECK,
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
        policy=_COMPONENT_READ,
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
        policy=_COMPONENT_CHECK,
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
        policy=_COMPONENT_SETUP,
        handler=_handler("provision_browser"),
        result_schema=_schema("ProvisionBrowserResult", "config.provision.browser"),
    ),
    CommandSpec(
        "config_provision_remove",
        "config_provision",
        "remove",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provision.remove.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_REMOVE_ITEM, _REMOVE_YES),
        policy=_COMPONENT_REMOVE,
        handler=_handler("provision_remove"),
        result_schema=_schema("ProvisionRemoveResult", "config.provision.remove"),
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
        policy=_COMPONENT_SETUP,
        handler=_handler("provision_setup"),
        result_schema=_schema("ProvisionSetupResult", "config.provision.setup"),
    ),
)


__all__ = ["CONFIG_PROVISION_COMMAND_SPECS"]
