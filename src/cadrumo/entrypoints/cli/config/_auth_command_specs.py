"""Import-light production authority for the config authentication family."""

from __future__ import annotations

from typing import Final

from ....core.transport_locus import TransportLocus, TransportRole, TransportShape
from ..command_spec import (
    FLAG_VALUE,
    TEXT_VALUE,
    WHOLE_NUMBER_VALUE,
    ArgumentSpec,
    CommandNodeKind,
    CommandSpec,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    MachineSecretChannelKind,
    MachineSecretFieldSpec,
    MachineSecretSpec,
    MachineSecretVariantSpec,
    OptionSpec,
    ParameterDefault,
    TuiCapability,
    ValueContract,
)
from ..command_spec import translation_key as _key
from ._command_spec_schema import config_payload_schema as _schema
from ._spec_policies import ENCRYPTED_DESTRUCTIVE, ENCRYPTED_READ, ENCRYPTED_WRITE, state_free_group_spec

_PATH = ValueContract(DeferredTarget("pathlib", "Path"))
_OUTPUT_LANGUAGE = ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage"))
_PHONE_STATE = ValueContract(DeferredTarget("cadrumo.application.auth.diagnostics", "AuthDiagnosticPhoneState"))


def _option(
    name: str,
    declarations: tuple[str, ...],
    value: ValueContract,
    help_key: str,
    *,
    required: bool = False,
    flag: bool = False,
    multiple: bool = False,
    machine_secret_channel: MachineSecretChannelKind | None = None,
    transport_locus: TransportLocus = TransportLocus.NONE,
    transport_shape: TransportShape = TransportShape.NOT_APPLICABLE,
    transport_role: TransportRole = TransportRole.NOT_APPLICABLE,
) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=value,
        default=ParameterDefault.required() if required else ParameterDefault.value(False if flag else None),
        help_key=_key(help_key),
        is_flag=flag,
        flag_value=True if flag else None,
        multiple=multiple,
        machine_secret_channel=machine_secret_channel,
        transport_locus=transport_locus,
        transport_shape=transport_shape,
        transport_role=transport_role,
    )


_OUTPUT_LANGUAGE_OPTION = _option(
    "output_language",
    ("--output-language", "--language"),
    _OUTPUT_LANGUAGE,
    "cli.config.auth.output_language_help",
)


# Every dynamically resolved handler module is named here as a WHOLE dotted path.
# The path used to be built with an f-string, which meant no static reader -- grep,
# the import-hygiene scan, or a dead-code sweep -- could see the edge, so all of
# these modules read as orphaned while backing live verbs. A wrong key now raises
# at spec-build time instead of failing lazily on first invocation.
_HANDLER_MODULES: Final[dict[str, str]] = {
    "_apoderado": "cadrumo.entrypoints.cli.config._apoderado",
    "_auth": "cadrumo.entrypoints.cli.config._auth",
    "_auth_diagnostics": "cadrumo.entrypoints.cli.config._auth_diagnostics",
    "_certificate": "cadrumo.entrypoints.cli.config._certificate",
}


def _handler(module: str, name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget(_HANDLER_MODULES[module], name))


def _leaf(
    key: str,
    parent: str,
    token: str,
    help_key: str,
    module: str,
    handler: str,
    schema: str,
    policy: ExecutionPolicySpec,
    parameters: tuple[ArgumentSpec | OptionSpec, ...] = (),
    machine_secret: MachineSecretSpec | None = None,
    *,
    tui_capability: TuiCapability = TuiCapability.NOT_IMPLEMENTED,
) -> CommandSpec:
    return CommandSpec(
        key=key,
        parent_key=parent,
        token=token,
        kind=CommandNodeKind.LEAF,
        help_key=_key(help_key),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(*parameters, _OUTPUT_LANGUAGE_OPTION),
        policy=policy,
        handler=_handler(module, handler),
        result_schema=_schema(schema, key.replace("_", ".")),
        machine_secret=machine_secret,
        tui_capability=tui_capability,
    )


_PROVIDER = _option("provider", ("--provider",), TEXT_VALUE, "cli.config.auth.provider_help")
_NAME_REGISTER = _option(
    "name", ("--name",), TEXT_VALUE, "cli.config.auth.certificate.register.name_help", required=True
)


AUTH_COMMAND_SPECS = (
    state_free_group_spec("config_auth", "config", "auth", "cli.config.auth.help"),
    _leaf(
        "config_auth_providers",
        "config_auth",
        "providers",
        "cli.config.auth.providers_help",
        "_auth",
        "auth_providers",
        "AuthProvidersResult",
        ENCRYPTED_READ,
    ),
    _leaf(
        "config_auth_configure",
        "config_auth",
        "configure",
        "cli.config.auth.configure_help",
        "_auth",
        "auth_configure",
        "AuthConfigurePayload",
        ENCRYPTED_WRITE,
        (
            _option("provider", ("--provider",), TEXT_VALUE, "cli.config.auth.provider_help", required=True),
            _option(
                "file",
                ("--file",),
                _PATH,
                "cli.config.auth.file_help",
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
        ),
    ),
    _leaf(
        "config_auth_status",
        "config_auth",
        "status",
        "cli.config.auth.status_help",
        "_auth",
        "auth_status",
        "AuthStatusPayload",
        ENCRYPTED_READ,
        (_PROVIDER,),
    ),
    _leaf(
        "config_auth_test",
        "config_auth",
        "test",
        "cli.config.auth.test_help",
        "_auth",
        "auth_test",
        "AuthTestPayload",
        ENCRYPTED_READ,
        (_PROVIDER,),
    ),
    _leaf(
        "config_auth_login",
        "config_auth",
        "login",
        "cli.config.auth.login_help",
        "_auth",
        "auth_login",
        "AuthLoginPayload",
        ENCRYPTED_WRITE,
        (
            _PROVIDER,
            _option("fresh", ("--fresh",), FLAG_VALUE, "cli.config.auth.login_fresh_help", flag=True),
            _option("reset_lock", ("--reset-lock",), FLAG_VALUE, "cli.config.auth.login_reset_lock_help", flag=True),
        ),
    ),
    _leaf(
        "config_auth_logout",
        "config_auth",
        "logout",
        "cli.config.auth.logout_help",
        "_auth",
        "auth_logout",
        "AuthLogoutPayload",
        ENCRYPTED_WRITE,
        (
            _PROVIDER,
            _option("all_providers", ("--all",), FLAG_VALUE, "cli.config.auth.logout_all_help", flag=True),
        ),
    ),
    _leaf(
        "config_auth_reset",
        "config_auth",
        "reset",
        "cli.config.auth.reset_help",
        "_auth",
        "auth_reset",
        "AuthResetPayload",
        ENCRYPTED_DESTRUCTIVE,
        (
            _PROVIDER,
            _option("all_providers", ("--all",), FLAG_VALUE, "cli.config.auth.reset_all_help", flag=True),
            _option("yes", ("--yes",), FLAG_VALUE, "cli.config.auth.reset_yes_help", flag=True),
        ),
    ),
    state_free_group_spec("config_auth_diagnostics", "config_auth", "diagnostics", "cli.config.auth.diagnostics.help"),
    _leaf(
        "config_auth_diagnostics_list",
        "config_auth_diagnostics",
        "list",
        "cli.config.auth.diagnostics.list_help",
        "_auth_diagnostics",
        "auth_diagnostics_list",
        "AuthDiagnosticsListResult",
        ENCRYPTED_READ,
    ),
    _leaf(
        "config_auth_diagnostics_view",
        "config_auth_diagnostics",
        "view",
        "cli.config.auth.diagnostics.view_help",
        "_auth_diagnostics",
        "auth_diagnostics_view",
        "AuthDiagnosticsViewResult",
        ENCRYPTED_READ,
        (
            ArgumentSpec(
                "diagnostic_id", TEXT_VALUE, ParameterDefault.required(), _key("cli.config.auth.diagnostics.id_help")
            ),
        ),
    ),
    _leaf(
        "config_auth_diagnostics_report",
        "config_auth_diagnostics",
        "report",
        "cli.config.auth.diagnostics.report_help",
        "_auth_diagnostics",
        "auth_diagnostics_report",
        "AuthDiagnosticsReportResult",
        ENCRYPTED_WRITE,
        (
            ArgumentSpec(
                "diagnostic_id", TEXT_VALUE, ParameterDefault.required(), _key("cli.config.auth.diagnostics.id_help")
            ),
            _option(
                "phone_state",
                ("--phone-state",),
                _PHONE_STATE,
                "cli.config.auth.diagnostics.phone_state_help",
                required=True,
            ),
        ),
    ),
    state_free_group_spec("config_auth_apoderado", "config_auth", "apoderado", "cli.config.auth.apoderado.help"),
    _leaf(
        "config_auth_apoderado_status",
        "config_auth_apoderado",
        "status",
        "cli.config.auth.apoderado.status_help",
        "_apoderado",
        "apoderado_status",
        "ApoderadoStatusResult",
        ENCRYPTED_READ,
    ),
    _leaf(
        "config_auth_apoderado_configure",
        "config_auth_apoderado",
        "configure",
        "cli.config.auth.apoderado.configure_help",
        "_apoderado",
        "apoderado_configure",
        "ApoderadoConfigureResult",
        ENCRYPTED_WRITE,
        (
            _option(
                "represented_nif",
                ("--represented-nif",),
                TEXT_VALUE,
                "cli.config.auth.apoderado.configure.represented_nif_help",
            ),
            _option("scope", ("--scope",), TEXT_VALUE, "cli.config.auth.apoderado.configure.scope_help", multiple=True),
        ),
        tui_capability=TuiCapability.NOT_IMPLEMENTED,
    ),
    _leaf(
        "config_auth_apoderado_clear",
        "config_auth_apoderado",
        "clear",
        "cli.config.auth.apoderado.clear_help",
        "_apoderado",
        "apoderado_clear",
        "ApoderadoClearResult",
        ENCRYPTED_DESTRUCTIVE,
    ),
    _leaf(
        "config_auth_apoderado_check",
        "config_auth_apoderado",
        "check",
        "cli.config.auth.apoderado.check_help",
        "_apoderado",
        "apoderado_check",
        "ApoderadoCheckResult",
        ENCRYPTED_READ,
    ),
    state_free_group_spec(
        "config_auth_apoderado_scopes", "config_auth_apoderado", "scopes", "cli.config.auth.apoderado.scopes.help"
    ),
    _leaf(
        "config_auth_apoderado_scopes_list",
        "config_auth_apoderado_scopes",
        "list",
        "cli.config.auth.apoderado.scopes.list_help",
        "_apoderado",
        "apoderado_scopes_list",
        "ApoderadoScopesListResult",
        ENCRYPTED_READ,
    ),
    state_free_group_spec("config_auth_certificate", "config_auth", "certificate", "cli.config.auth.certificate.help"),
    _leaf(
        "config_auth_certificate_register",
        "config_auth_certificate",
        "register",
        "cli.config.auth.certificate.register_help",
        "_certificate",
        "certificate_register",
        "CertificateSourceMutationPayload",
        ENCRYPTED_WRITE,
        (
            _NAME_REGISTER,
            _option(
                "file",
                ("--file",),
                _PATH,
                "cli.config.auth.certificate.register.file_help",
                required=True,
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            _option(
                "friendly_name",
                ("--friendly-name",),
                TEXT_VALUE,
                "cli.config.auth.certificate.register.friendly_name_help",
            ),
        ),
    ),
    _leaf(
        "config_auth_certificate_list",
        "config_auth_certificate",
        "list",
        "cli.config.auth.certificate.list_help",
        "_certificate",
        "certificate_list",
        "CertificateSourceListPayload",
        ENCRYPTED_READ,
    ),
    _leaf(
        "config_auth_certificate_select",
        "config_auth_certificate",
        "select",
        "cli.config.auth.certificate.select_help",
        "_certificate",
        "certificate_select",
        "CertificateSourceMutationPayload",
        ENCRYPTED_WRITE,
        (_option("name", ("--name",), TEXT_VALUE, "cli.config.auth.certificate.select.name_help", required=True),),
    ),
    _leaf(
        "config_auth_certificate_remove",
        "config_auth_certificate",
        "remove",
        "cli.config.auth.certificate.remove_help",
        "_certificate",
        "certificate_remove",
        "CertificateSourceMutationPayload",
        ENCRYPTED_DESTRUCTIVE,
        (_option("name", ("--name",), TEXT_VALUE, "cli.config.auth.certificate.remove.name_help", required=True),),
    ),
    _leaf(
        "config_auth_certificate_check",
        "config_auth_certificate",
        "check",
        "cli.config.auth.certificate.check_help",
        "_certificate",
        "certificate_check",
        "CertificateSourceCheckPayload",
        ENCRYPTED_READ,
    ),
    state_free_group_spec(
        "config_auth_certificate_secret", "config_auth_certificate", "secret", "cli.config.auth.certificate.secret.help"
    ),
    _leaf(
        "config_auth_certificate_secret_set",
        "config_auth_certificate_secret",
        "set",
        "cli.config.auth.certificate.secret.set_help",
        "_certificate",
        "certificate_secret_set",
        "CertificateSourceSecretMutationPayload",
        ENCRYPTED_WRITE,
        (
            _option("name", ("--name",), TEXT_VALUE, "cli.config.auth.certificate.secret.set.name_help", required=True),
            _option(
                "secrets_stdin",
                ("--secrets-stdin",),
                FLAG_VALUE,
                "cli.config.custody.secrets_stdin_help",
                flag=True,
                machine_secret_channel=MachineSecretChannelKind.STDIN,
            ),
            _option(
                "secrets_fd",
                ("--secrets-fd",),
                WHOLE_NUMBER_VALUE,
                "cli.config.custody.secrets_fd_help",
                machine_secret_channel=MachineSecretChannelKind.FILE_DESCRIPTOR,
            ),
        ),
        MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "certificate",
                    (MachineSecretFieldSpec("certificate_passphrase"),),
                    DeferredTarget(
                        "cadrumo.entrypoints.cli.config._certificate",
                        "CertificateSecretSetSecrets",
                    ),
                ),
            )
        ),
    ),
    _leaf(
        "config_auth_certificate_secret_remove",
        "config_auth_certificate_secret",
        "remove",
        "cli.config.auth.certificate.secret.remove_help",
        "_certificate",
        "certificate_secret_remove",
        "CertificateSourceSecretMutationPayload",
        ENCRYPTED_DESTRUCTIVE,
        (
            _option(
                "name", ("--name",), TEXT_VALUE, "cli.config.auth.certificate.secret.remove.name_help", required=True
            ),
        ),
    ),
)


__all__ = ["AUTH_COMMAND_SPECS"]
