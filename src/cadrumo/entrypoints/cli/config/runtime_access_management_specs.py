"""Import-light CLI declarations for runtime-owned profile access controls."""

from __future__ import annotations

from cadrumo.application.operator_surface.command_ports import CommandNodeKind, ProfileAuthenticationPosture

from ..command_spec import (
    ArgumentSpec,
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    MachineSecretChannelKind,
    MachineSecretFieldSpec,
    MachineSecretSpec,
    MachineSecretVariantSpec,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from ._spec_policies import PROFILE_DESTRUCTIVE, PROFILE_READ

_LANGUAGE = OptionSpec(
    name="output_language",
    declarations=("--output-language", "--language"),
    value=ValueContract(DeferredTarget("....core.external_constants", "OutputLanguage", __package__)),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.auth.output_language_help"),
)
_SECRETS_STDIN = OptionSpec(
    name="secrets_stdin",
    declarations=("--secrets-stdin",),
    value=ValueContract(DeferredTarget("builtins", "bool")),
    default=ParameterDefault.value(False),
    help_key=TranslationKey("cli.config.custody.secrets_stdin_help"),
    is_flag=True,
    flag_value=True,
    machine_secret_channel=MachineSecretChannelKind.STDIN,
)
_SECRETS_FD = OptionSpec(
    name="secrets_fd",
    declarations=("--secrets-fd",),
    value=ValueContract(DeferredTarget("builtins", "int")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.custody.secrets_fd_help"),
    machine_secret_channel=MachineSecretChannelKind.FILE_DESCRIPTOR,
)
_UUID = ValueContract(DeferredTarget("uuid", "UUID"))


def _result(name: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget(".runtime_access_management_payloads", name, __package__),
        identity=identity,
    )


def _handler(name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget(".runtime_access_management", name, __package__))


RUNTIME_ACCESS_MANAGEMENT_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "config_profile_automation",
        "config_profile",
        "automation",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.config.profile.automation.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=PROFILE_READ,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "config_profile_sessions",
        "config_profile",
        "sessions",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.profile.sessions.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_LANGUAGE,),
        policy=PROFILE_READ,
        handler=_handler("profile_sessions"),
        result_schema=_result("ConfigProfileSessionsResult", "config.profile.sessions"),
    ),
    CommandSpec(
        "config_profile_automation_list",
        "config_profile_automation",
        "list",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.profile.automation.list.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_LANGUAGE,),
        policy=PROFILE_READ,
        handler=_handler("automation_list"),
        result_schema=_result("ConfigProfileAutomationListResult", "config.profile.automation.list"),
    ),
    CommandSpec(
        "config_profile_automation_create",
        "config_profile_automation",
        "create",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.profile.automation.create.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_SECRETS_STDIN, _SECRETS_FD, _LANGUAGE),
        policy=PROFILE_DESTRUCTIVE,
        handler=LazyBinding.available(DeferredTarget(".runtime_automation_request", "automation_create", __package__)),
        result_schema=_result("ConfigProfileAutomationCreateResult", "config.profile.automation.create"),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "proposal",
                    (MachineSecretFieldSpec("proposal"),),
                    DeferredTarget(".runtime_automation_request", "AutomationCreateInput", __package__),
                ),
            )
        ),
        profile_authentication=ProfileAuthenticationPosture.SELF_AUTHENTICATING,
    ),
    CommandSpec(
        "config_profile_automation_change",
        "config_profile_automation",
        "change",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.profile.automation.change.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="kind",
                value=ValueContract(DeferredTarget("builtins", "str"), choices=("rotate", "renew", "change_scope")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.config.profile.automation.change.kind_help"),
            ),
            _SECRETS_STDIN,
            _SECRETS_FD,
            _LANGUAGE,
        ),
        policy=PROFILE_DESTRUCTIVE,
        handler=LazyBinding.available(DeferredTarget(".runtime_automation_request", "automation_change", __package__)),
        result_schema=_result("ConfigProfileAutomationChangeResult", "config.profile.automation.change"),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "proposal",
                    (MachineSecretFieldSpec("proposal"),),
                    DeferredTarget(".runtime_automation_request", "AutomationChangeInput", __package__),
                ),
            )
        ),
        profile_authentication=ProfileAuthenticationPosture.RESUME_FALLBACK,
    ),
    CommandSpec(
        "config_profile_automation_inspect",
        "config_profile_automation",
        "inspect",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.profile.automation.inspect.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="request_id",
                value=_UUID,
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.config.profile.automation.inspect.request_help"),
            ),
            _LANGUAGE,
        ),
        policy=PROFILE_READ,
        handler=_handler("automation_inspect"),
        result_schema=_result("ConfigProfileAutomationInspectResult", "config.profile.automation.inspect"),
    ),
    CommandSpec(
        "config_profile_automation_approve",
        "config_profile_automation",
        "approve",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.profile.automation.approve.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="request_id",
                value=_UUID,
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.config.profile.automation.approve.request_help"),
            ),
            OptionSpec(
                name="review_digest",
                declarations=("--review-digest",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.config.profile.automation.approve.digest_help"),
            ),
            _SECRETS_STDIN,
            _SECRETS_FD,
            _LANGUAGE,
        ),
        policy=PROFILE_DESTRUCTIVE,
        handler=_handler("automation_approve"),
        result_schema=_result("ConfigProfileAutomationDecisionResult", "config.profile.automation.approve"),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "password",
                    (MachineSecretFieldSpec("passphrase"),),
                    DeferredTarget(".runtime_access_management", "AutomationApprovalSecrets", __package__),
                ),
            )
        ),
    ),
    CommandSpec(
        "config_profile_automation_decline",
        "config_profile_automation",
        "decline",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.profile.automation.decline.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="request_id",
                value=_UUID,
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.config.profile.automation.decline.request_help"),
            ),
            OptionSpec(
                name="review_digest",
                declarations=("--review-digest",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.config.profile.automation.decline.digest_help"),
            ),
            _LANGUAGE,
        ),
        policy=PROFILE_DESTRUCTIVE,
        handler=_handler("automation_decline"),
        result_schema=_result("ConfigProfileAutomationDecisionResult", "config.profile.automation.decline"),
    ),
    CommandSpec(
        "config_profile_automation_deny",
        "config_profile_automation",
        "deny",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.profile.automation.deny.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="kind",
                value=ValueContract(DeferredTarget("builtins", "str"), choices=("key", "grant", "all")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.config.profile.automation.deny.kind_help"),
            ),
            ArgumentSpec(
                name="target_id",
                value=_UUID,
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.profile.automation.deny.target_help"),
            ),
            _LANGUAGE,
        ),
        policy=PROFILE_DESTRUCTIVE,
        handler=_handler("automation_deny"),
        result_schema=_result("ConfigProfileAutomationDenyResult", "config.profile.automation.deny"),
    ),
    CommandSpec(
        "config_profile_lock",
        "config_profile",
        "lock",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.profile.lock.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="all_sessions",
                declarations=("--all",),
                value=ValueContract(DeferredTarget("builtins", "bool")),
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.config.profile.lock.all_help"),
                is_flag=True,
                flag_value=True,
            ),
            OptionSpec(
                name="session",
                declarations=("--session",),
                value=_UUID,
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.profile.lock.session_help"),
            ),
            _LANGUAGE,
        ),
        policy=PROFILE_DESTRUCTIVE,
        handler=_handler("profile_lock"),
        result_schema=_result("ConfigProfileLockResult", "config.profile.lock"),
    ),
    CommandSpec(
        "config_profile_resume",
        "config_profile",
        "resume",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.profile.resume.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="grant",
                declarations=("--grant",),
                value=_UUID,
                default=ParameterDefault.value(()),
                help_key=TranslationKey("cli.config.profile.resume.grant_help"),
                multiple=True,
            ),
            _SECRETS_STDIN,
            _SECRETS_FD,
            _LANGUAGE,
        ),
        policy=PROFILE_DESTRUCTIVE,
        handler=_handler("profile_resume"),
        result_schema=_result("ConfigProfileResumeResult", "config.profile.resume"),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "password",
                    (MachineSecretFieldSpec("passphrase"),),
                    DeferredTarget(".runtime_access_management", "ProfileResumeSecrets", __package__),
                ),
            )
        ),
        profile_authentication=ProfileAuthenticationPosture.SELF_AUTHENTICATING,
    ),
)

__all__ = ["RUNTIME_ACCESS_MANAGEMENT_COMMAND_SPECS"]
