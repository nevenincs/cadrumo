"""Root options and the profile secret shared by every executable root.

The ``aeat`` root and the ``cadrumo-runtime`` root both select a profile,
admit its authentication secret and control output the same way. Each root
keeps its own order and its own extra options; the shared declarations and
the profile-authentication secret contract are defined once here.
"""

from __future__ import annotations

from .parameters import OptionSpec
from .secret_contracts import MachineSecretFieldSpec, ProfileSecretChannelKind, ProfileSecretSpec
from .shared_contracts import (
    FLAG_VALUE,
    TEXT_VALUE,
    WHOLE_NUMBER_VALUE,
    DeferredTarget,
    ParameterDefault,
    TranslationKey,
    ValueContract,
)

__all__ = ["ROOT_OUTPUT_OPTIONS", "ROOT_PROFILE_OPTIONS", "profile_authentication_secret"]


def _root_flag(name: str, declaration: str, help_key: str) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=(declaration,),
        value=FLAG_VALUE,
        default=ParameterDefault.value(False),
        help_key=TranslationKey(help_key),
        is_flag=True,
        flag_value=True,
    )


ROOT_PROFILE_OPTIONS: tuple[OptionSpec, ...] = (
    OptionSpec(
        name="profile",
        declarations=("--profile",),
        value=TEXT_VALUE,
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.root.profile_help"),
    ),
    OptionSpec(
        name="profile_secrets_stdin",
        declarations=("--profile-secrets-stdin",),
        value=FLAG_VALUE,
        default=ParameterDefault.value(False),
        help_key=TranslationKey("cli.config.custody.profile_secrets_stdin_help"),
        is_flag=True,
        flag_value=True,
        profile_secret_channel=ProfileSecretChannelKind.STDIN,
    ),
    OptionSpec(
        name="profile_secrets_fd",
        declarations=("--profile-secrets-fd",),
        value=WHOLE_NUMBER_VALUE,
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.config.custody.profile_secrets_fd_help"),
        profile_secret_channel=ProfileSecretChannelKind.FILE_DESCRIPTOR,
    ),
    OptionSpec(
        name="profile_auth_method",
        declarations=("--profile-auth-method",),
        value=ValueContract(DeferredTarget("builtins", "str"), choices=("password", "api-key")),
        default=ParameterDefault.value("password"),
        help_key=TranslationKey("cli.config.custody.profile_auth_method_help"),
    ),
    OptionSpec(
        name="profile_credential_ref",
        declarations=("--profile-credential-ref",),
        value=ValueContract(DeferredTarget("uuid", "UUID")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.config.custody.profile_credential_ref_help"),
    ),
)
"""Profile selection and its authentication-secret channels, in declaration order."""

ROOT_OUTPUT_OPTIONS: tuple[OptionSpec, ...] = (
    OptionSpec(
        name="format_",
        declarations=("--format",),
        value=ValueContract(DeferredTarget("cadrumo.core.output_rendering", "OutputFormat")),
        default=ParameterDefault.value("text"),
        help_key=TranslationKey("cli.root.format_help"),
    ),
    _root_flag("quiet", "--quiet", "cli.root.quiet_help"),
    _root_flag("verbose", "--verbose", "cli.root.verbose_help"),
    _root_flag("debug", "--debug", "cli.root.debug_help"),
)
"""Output format and verbosity controls, in declaration order."""


def profile_authentication_secret(windows_handle_bootstrap: str) -> ProfileSecretSpec:
    """Return the root profile-authentication secret contract.

    ``windows_handle_bootstrap`` names the executable's own isolated HANDLE
    dispatcher module, which differs per root.
    """
    return ProfileSecretSpec(
        fields=(MachineSecretFieldSpec("profile_passphrase"), MachineSecretFieldSpec("api_key")),
        model=DeferredTarget("cadrumo_client.commands.profile_authentication", "ProfileAuthenticationSecrets"),
        windows_handle_bootstrap=windows_handle_bootstrap,
    )
