"""Import-light production authority for local-inference lifecycle commands."""

from __future__ import annotations

from .._command_spec import (
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
from ._spec_policies import ENCRYPTED_READ, NETWORK_WRITE, STATE_FREE

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
    value=ValueContract(DeferredTarget("cadrumo.core", "ModelRole")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.provision.role_help"),
)


def _handler(name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._config._provision_cli", name))


def _schema(name: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget("cadrumo.entrypoints.cli._config._provision_payloads", name),
        identity=identity,
    )


CONFIG_PROVISION_COMMAND_SPECS = (
    CommandSpec(
        key="config_provision",
        parent_key="config",
        token="provision",  # noqa: S106 - CLI token, not a credential.
        kind="group",
        help_key=TranslationKey("cli.config.provision.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="config_provision_report",
        parent_key="config_provision",
        token="report",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.provision.report.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=ENCRYPTED_READ,
        handler=_handler("provision_report"),
        result_schema=_schema("ProvisionReportResult", "config.provision.report"),
    ),
    CommandSpec(
        key="config_provision_pull",
        parent_key="config_provision",
        token="pull",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.provision.pull.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_MODEL, _ROLE),
        policy=NETWORK_WRITE,
        handler=_handler("provision_pull"),
        result_schema=_schema("ProvisionPullResult", "config.provision.pull"),
    ),
    CommandSpec(
        key="config_provision_verify",
        parent_key="config_provision",
        token="verify",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
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
)


__all__ = ["CONFIG_PROVISION_COMMAND_SPECS"]
