"""Import-light production authority for the ``config provision`` commands.

Component leaves submit operations through the signed-in profile's runtime
session. The quick check reads local files, full checks reach the network,
setup downloads into installation-wide storage and removal deletes from it.
Only the desktop sets up or removes the local AI.
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
_PROFILE: frozenset[Capability] = frozenset({"profile-custody"})
# Installation-wide component storage, which the engine changes and no profile holds.
_COMPONENT_STORAGE: frozenset[Capability] = frozenset({"components"})
# The engine's quick check: local files only, no network and no model load.
_COMPONENT_READ = ExecutionPolicySpec(
    frozenset({"profile-custody"}), frozenset({"none"}), "local-io", CommandWriteRoute.NONE
)
# The engine's full check reaches each item's hosts, launches the browser and asks each model one token.
_COMPONENT_CHECK = ExecutionPolicySpec(
    _PROFILE_FREE | _PROFILE, frozenset({"network"}), "external-io", CommandWriteRoute.NONE
)
# The engine's setup downloads and installs into installation-wide component storage.
_COMPONENT_SETUP = ExecutionPolicySpec(
    _PROFILE_FREE | _COMPONENT_STORAGE | _PROFILE,
    frozenset({"network", "local-state"}),
    "external-io",
    CommandWriteRoute.PROFILE_BOUND,
)
# The engine's removal deletes an item from component storage and reaches no network.
_COMPONENT_REMOVE = ExecutionPolicySpec(
    _COMPONENT_STORAGE | _PROFILE,
    frozenset({"local-state"}),
    "local-io",
    CommandWriteRoute.PROFILE_BOUND,
    destructive=True,
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

_REVIEW_OPERATION = ArgumentSpec(
    name="operation_id",
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.config.provision.review.operation_help"),
)
_REJECT = OptionSpec(
    name="reject",
    declarations=("--reject",),
    value=ValueContract(DeferredTarget("builtins", "bool")),
    default=ParameterDefault.value(False),
    help_key=TranslationKey("cli.config.provision.review.reject_help"),
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
        "config_provision_review",
        "config_provision",
        "review",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provision.review.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_REVIEW_OPERATION, _YES, _REJECT),
        policy=_COMPONENT_SETUP,
        handler=_handler("provision_review"),
        result_schema=_schema("ProvisionReviewResult", "config.provision.review"),
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
