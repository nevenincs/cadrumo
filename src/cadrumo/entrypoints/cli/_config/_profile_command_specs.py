"""Import-light production authority for the config profile command family."""

from __future__ import annotations

from .._command_spec import (
    ArgumentSpec,
    CommandSpec,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    LiteralValue,
    MachineSecretChannelKind,
    MachineSecretConditionSpec,
    MachineSecretFieldSpec,
    MachineSecretSpec,
    MachineSecretVariantSpec,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from ._spec_policies import (
    BOOTSTRAP_DESTRUCTIVE,
    BOOTSTRAP_WRITE,
    CALCULATION_READ,
    ENCRYPTED_DESTRUCTIVE,
    ENCRYPTED_READ,
    ENCRYPTED_WRITE,
    LIVE_PROFILE_WRITE,
    PROFILE_READ,
    STATE_FREE,
)

_BOOL = ValueContract(DeferredTarget("builtins", "bool"))
_INT = ValueContract(DeferredTarget("builtins", "int"))
_PATH = ValueContract(DeferredTarget("pathlib", "Path"))
_STR = ValueContract(DeferredTarget("builtins", "str"))
_LANG = ValueContract(DeferredTarget("cadrumo.core", "OutputLanguage"))
_CAPABILITY = ValueContract(DeferredTarget("cadrumo.core", "ServiceCapability"))
_TOGGLE = ValueContract(
    DeferredTarget("builtins", "str"),
    choices=("on", "off"),
)


def _key(value: str) -> TranslationKey:
    return TranslationKey(value)


def _handler(module: str, name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget(f"cadrumo.entrypoints.cli._config.{module}", name))


def _schema(module: str, name: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(SchemaState.TARGET, DeferredTarget(module, name), identity=identity)


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
    constraint: ParameterConstraint = ParameterConstraint(),
    machine_secret_channel: MachineSecretChannelKind | None = None,
) -> OptionSpec:
    return OptionSpec(
        name,
        declarations,
        value,
        ParameterDefault.required() if required else ParameterDefault.value(default),
        _key(help_key),
        is_flag=flag,
        flag_value=True if flag else None,
        multiple=multiple,
        constraint=constraint,
        machine_secret_channel=machine_secret_channel,
    )


_LANGUAGE = _option(
    "output_language", ("--output-language", "--language"), _LANG, "cli.config.auth.output_language_help"
)


def _argument(name: str, value: ValueContract, help_key: str, *, required: bool = True) -> ArgumentSpec:
    return ArgumentSpec(
        name,
        value,
        ParameterDefault.required() if required else ParameterDefault.value(None),
        _key(help_key),
    )


def _group(key: str, parent: str, token: str, help_key: str) -> CommandSpec:
    return CommandSpec(
        key,
        parent,
        token,
        "group",
        _key(help_key),
        None,
        InvocationSpec(no_args_is_help=True),
        (),
        STATE_FREE,
        None,
        ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
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
    machine_secret: MachineSecretSpec | None = None,
    *,
    profile_target_parameter: str | None = None,
) -> CommandSpec:
    return CommandSpec(
        key,
        parent,
        token,
        "leaf",
        _key(help_key),
        None,
        InvocationSpec(context_parameter="ctx"),
        parameters,
        policy,
        _handler(module, handler),
        _schema(schema_module, schema_name, key.replace("_", ".")),
        machine_secret=machine_secret,
        profile_target_parameter=profile_target_parameter,
    )


_PAYLOADS = "cadrumo.entrypoints.cli._config_payloads"
_CONFIG = "cadrumo.entrypoints.cli._config"
_WIZARD = "cadrumo.application.wizard"

_WIZARD_CONFIRM_FIELDS = frozenset(
    """new-entity-first-two-profit-periods ley-49-2002-option-declared
    ley-49-2002-renunciation-declared iva-roi-enrolled iva-oss-enrolled
    iva-group-member-enrolled iva-group-dominant-entity-enrolled iva-sii-enrolled
    iva-redeme-enrolled iva-intracommunity-operations-exceed-50000-eur
    iva-cash-accounting-regime-enrolled iva-voluntary-sii-enrolled
    iva-hydrocarbon-deposit-advance-payment-deduction-entitled enrollment-large-company
    enrollment-public-administration-budget-gt-6000000 spouse-non-resident-irpf
    spouse-eu-eea-resident family-descendants-eu-eea-deduction family-minor-children-in-unit
    has-employees pays-professionals-with-retencion art109-activity-income-withholding-ge-70pct
    pays-rent-with-retencion pays-capital-income-with-retencion does-intracomunitario
    third-party-transactions-above-347-threshold bienes-extranjero-above-threshold
    monedas-virtuales-extranjero-above-threshold llm-vision google-export""".split()  # noqa: SIM905 - compact immutable declaration table
)
_WIZARD_CHECKBOX_FIELDS = frozenset({"irpf-income-categories"})
_WIZARD_FIELDS = """output-language entity-type legal-entity-form tax-id name surnames legal-name
fiscal-residency country-of-fiscal-residence representante-fiscal-nif representante-fiscal-nombre
tax-residence-jurisdiction-scope tax-residence-ccaa address-postcode irpf-income-categories activity
activity-start-date incn-prior-12-months new-entity-first-two-profit-periods ley-49-2002-option-declared
ley-49-2002-option-date ley-49-2002-renunciation-declared ley-49-2002-renunciation-date iva-regime
iva-m303-regime-composition iva-roi-enrolled iva-oss-enrolled iva-group-member-enrolled
iva-group-dominant-entity-enrolled iva-sii-enrolled iva-redeme-enrolled
iva-intracommunity-operations-exceed-50000-eur iva-cash-accounting-regime-enrolled
iva-voluntary-sii-enrolled iva-hydrocarbon-deposit-advance-payment-deduction-entitled
enrollment-large-company enrollment-public-administration-budget-gt-6000000 taxation-type taxpayer-sex
taxpayer-marital-status situacion-familiar taxpayer-marriage-date taxpayer-birth-date taxpayer-disability-grade
taxpayer-death-date spouse-tax-id spouse-name spouse-surnames spouse-birth-date spouse-sex
spouse-disability-grade spouse-non-resident-irpf spouse-eu-eea-resident spouse-eu-eea-country
family-descendants-eu-eea-deduction family-minor-children-in-unit has-employees
pays-professionals-with-retencion art109-activity-income-withholding-ge-70pct pays-rent-with-retencion
pays-capital-income-with-retencion modelo-111-no-retenciones-periods irpf-estimation-regime
objective-estimation-modulos-iae-epigraph objective-estimation-modulos-module-1-units
objective-estimation-modulos-module-2-units objective-estimation-modulos-module-3-units
objective-estimation-modulos-module-4-units objective-estimation-modulos-module-5-units
objective-estimation-modulos-module-6-units objective-estimation-modulos-module-7-units irpf-special-regime
irpf-special-regime-start-date does-intracomunitario third-party-transactions-above-347-threshold
bienes-extranjero-above-threshold monedas-virtuales-extranjero-above-threshold llm-vision google-export notes""".split()  # noqa: SIM905 - ordered declaration table


def _wizard_option(token: str) -> OptionSpec:
    name = token.replace("-", "_")
    help_key = f"wizard.setup.flags.{token}.help"
    if token == "output-language":  # noqa: S105 - CLI token, not a credential
        return _option(name, ("--output-language",), _LANG, help_key)
    if token in _WIZARD_CONFIRM_FIELDS:
        return _option(
            name,
            (f"--{token}", f"--no-{token}"),
            _BOOL,
            help_key,
            flag=True,
        )
    if token in _WIZARD_CHECKBOX_FIELDS:
        return _option(name, (f"--{token}",), _STR, help_key, default=(), multiple=True)
    return _option(name, (f"--{token}",), _STR, help_key)


_WIZARD_BASE_PARAMETERS: tuple[ArgumentSpec | OptionSpec, ...] = (
    _argument("profile_name", _STR, "cli.config.setup.profile_name_help", required=False),
    _option("quiet", ("--quiet",), _BOOL, "cli.config.setup.quiet_help", default=False, flag=True),
    _option(
        "accept_defaults",
        ("--accept-defaults",),
        _BOOL,
        "cli.config.setup.accept_defaults_help",
        default=False,
        flag=True,
    ),
    *(_wizard_option(token) for token in _WIZARD_FIELDS),
)
_WIZARD_CREATE_PARAMETERS = (
    *_WIZARD_BASE_PARAMETERS,
    _option(
        "secrets_stdin",
        ("--secrets-stdin",),
        _BOOL,
        "cli.config.custody.secrets_stdin_help",
        default=False,
        flag=True,
        machine_secret_channel=MachineSecretChannelKind.STDIN,
    ),
    _option(
        "secrets_fd",
        ("--secrets-fd",),
        _INT,
        "cli.config.custody.secrets_fd_help",
        machine_secret_channel=MachineSecretChannelKind.FILE_DESCRIPTOR,
    ),
)

PROFILE_COMMAND_SPECS = (
    _group("config_profile", "config", "profile", "cli.config.profile.help"),
    _group("config_profile_archive", "config_profile", "archive", "cli.config.profile.archive.help"),
    _group("config_profile_capabilities", "config_profile", "capabilities", "cli.config.profile.capabilities.help"),
    _group("config_profile_censo", "config_profile", "censo", "cli.config.profile.censo.help"),
    CommandSpec(
        "config_profile_descendiente",
        "config_profile",
        "descendiente",
        "group",
        _key("cli.config.profile.descendiente.help"),
        None,
        InvocationSpec(
            invoke_without_command=True,
            context_parameter="ctx",
            terminal_behavior="executable",
        ),
        (_LANGUAGE,),
        ENCRYPTED_READ,
        _handler("_descendiente", "descendiente_door"),
        _schema(
            "cadrumo.entrypoints.cli._config_descendiente_payloads",
            "ConfigProfileDescendienteListResult",
            "config.profile.descendiente",
        ),
    ),
    _leaf(
        "config_profile_archive_export",
        "config_profile_archive",
        "export",
        "cli.config.profile.archive.export_help",
        "_archive_cli",
        "archive_export",
        _PAYLOADS,
        "ConfigProfileArchiveExportResult",
        BOOTSTRAP_WRITE,
        (
            _argument("name", _STR, "cli.config.profile.archive.export_name_help"),
            _option(
                "output",
                ("--output",),
                _PATH,
                "cli.config.profile.archive.export_out_help",
                required=True,
                constraint=ParameterConstraint(dir_okay=False, writable=True),
            ),
            _LANGUAGE,
        ),
    ),
    _leaf(
        "config_profile_archive_inspect",
        "config_profile_archive",
        "inspect",
        "cli.config.profile.archive.inspect_help",
        "_archive_cli",
        "archive_inspect",
        _PAYLOADS,
        "ConfigProfileArchiveInspectResult",
        PROFILE_READ,
        (
            _option(
                "file",
                ("--file",),
                _PATH,
                "cli.config.profile.archive.inspect_path_help",
                required=True,
                constraint=ParameterConstraint(exists=True, dir_okay=False),
            ),
            _LANGUAGE,
        ),
    ),
    _leaf(
        "config_profile_capabilities_show",
        "config_profile_capabilities",
        "show",
        "cli.config.profile.capabilities.show_help",
        "_capabilities_cli",
        "capabilities_show",
        f"{_CONFIG}._capabilities_payloads",
        "CapabilitiesShowResult",
        ENCRYPTED_READ,
    ),
    _leaf(
        "config_profile_capabilities_set",
        "config_profile_capabilities",
        "set",
        "cli.config.profile.capabilities.set_help",
        "_capabilities_cli",
        "capabilities_set",
        f"{_CONFIG}._capabilities_payloads",
        "CapabilitySetResult",
        ENCRYPTED_WRITE,
        (
            _argument("capability", _CAPABILITY, "cli.config.profile.capabilities.capability_help"),
            _argument("state", _TOGGLE, "cli.config.profile.capabilities.state_help"),
        ),
    ),
    _leaf(
        "config_profile_censo_file",
        "config_profile_censo",
        "file",
        "cli.config.profile.censo.file_help",
        "_censo_file",
        "censo_file",
        f"{_CONFIG}._censo_payloads",
        "CensoFileIngestResult",
        ENCRYPTED_WRITE,
        (
            _option(
                "file",
                ("--file",),
                _PATH,
                "cli.config.profile.censo.file_option_help",
                required=True,
                constraint=ParameterConstraint(exists=True, dir_okay=False),
            ),
            _option("apply", ("--apply",), _BOOL, "cli.config.profile.censo.apply_help", default=False, flag=True),
        ),
    ),
    _leaf(
        "config_profile_censo_pull",
        "config_profile_censo",
        "pull",
        "cli.config.profile.censo.pull_help",
        "_censo_file",
        "censo_pull",
        f"{_CONFIG}._censo_payloads",
        "CensoPullResult",
        LIVE_PROFILE_WRITE,
        (_option("apply", ("--apply",), _BOOL, "cli.config.profile.censo.apply_help", default=False, flag=True),),
    ),
    _leaf(
        "config_profile_complete_setup",
        "config_profile",
        "complete-setup",
        "cli.config.profile.complete_setup.help",
        "_complete_setup_cli",
        "profile_complete_setup",
        f"{_CONFIG}._complete_setup_payloads",
        "ProfileCompleteSetupResult",
        ENCRYPTED_WRITE,
    ),
    _leaf(
        "config_profile_create",
        "config_profile",
        "create",
        "cli.config.profile.create_help",
        "_manager_dispatch",
        "profile_create",
        _WIZARD,
        "ConfigProfileCreateResult",
        BOOTSTRAP_WRITE,
        _WIZARD_CREATE_PARAMETERS,
        MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "passphrase",
                    (
                        MachineSecretFieldSpec("passphrase"),
                        MachineSecretFieldSpec("passphrase_confirmation"),
                    ),
                    DeferredTarget(
                        "cadrumo.entrypoints.cli._config._scripted_registration",
                        "ProfileCreationSecrets",
                    ),
                ),
            )
        ),
    ),
    _leaf(
        "config_profile_delete",
        "config_profile",
        "delete",
        "cli.config.profile.delete.help",
        "_profile_delete",
        "config_profile_delete",
        _PAYLOADS,
        "ConfigProfileDeleteResult",
        BOOTSTRAP_DESTRUCTIVE,
        (
            _argument("name", _STR, "cli.config.profile.delete.name_help"),
            _option("yes", ("--yes",), _BOOL, "cli.config.profile.delete.yes_help", default=False, flag=True),
            _LANGUAGE,
        ),
    ),
    _leaf(
        "config_profile_descendiente_add",
        "config_profile_descendiente",
        "add",
        "cli.config.profile.descendiente.add_help",
        "_descendiente",
        "descendiente_add",
        "cadrumo.entrypoints.cli._config_descendiente_payloads",
        "ConfigProfileDescendienteAddResult",
        ENCRYPTED_WRITE,
        (
            _option(
                "descendiente",
                ("--descendiente",),
                _STR,
                "cli.config.profile.descendiente.add_flag_help",
                required=True,
                multiple=True,
            ),
            _LANGUAGE,
        ),
    ),
    _leaf(
        "config_profile_descendiente_list",
        "config_profile_descendiente",
        "list",
        "cli.config.profile.descendiente.list_help",
        "_descendiente",
        "descendiente_list",
        "cadrumo.entrypoints.cli._config_descendiente_payloads",
        "ConfigProfileDescendienteListResult",
        ENCRYPTED_READ,
        (_LANGUAGE,),
    ),
    _leaf(
        "config_profile_descendiente_remove",
        "config_profile_descendiente",
        "remove",
        "cli.config.profile.descendiente.remove_help",
        "_descendiente",
        "descendiente_remove",
        "cadrumo.entrypoints.cli._config_descendiente_payloads",
        "ConfigProfileDescendienteRemoveResult",
        ENCRYPTED_DESTRUCTIVE,
        (_argument("index", _INT, "cli.config.profile.descendiente.remove_index_help"), _LANGUAGE),
    ),
    _leaf(
        "config_profile_edit",
        "config_profile",
        "edit",
        "cli.config.profile.edit_help",
        "_manager_dispatch",
        "profile_edit",
        _WIZARD,
        "ConfigProfileEditResult",
        ENCRYPTED_WRITE,
        _WIZARD_BASE_PARAMETERS,
    ),
    _leaf(
        "config_profile_history",
        "config_profile",
        "history",
        "cli.config.profile.history_help",
        "_bucket_history",
        "profile_history",
        "cadrumo.entrypoints.cli._config_bucket_history_payloads",
        "BucketHistoryResult",
        ENCRYPTED_READ,
        (
            _argument("profile", _STR, "cli.config.profile.history_bucket_id_help", required=False),
            _option("event_type", ("--event-type",), _STR, "cli.config.profile.history_event_type_help", multiple=True),
            _option("since", ("--since",), _STR, "cli.config.profile.history_since_help"),
            _option("until", ("--until",), _STR, "cli.config.profile.history_until_help"),
            _option("object_id", ("--object-id",), _STR, "cli.config.profile.history_object_id_help"),
            _option("actor", ("--actor",), _STR, "cli.config.profile.history_actor_help"),
            _LANGUAGE,
        ),
        profile_target_parameter="profile",
    ),
    _leaf(
        "config_profile_preflight",
        "config_profile",
        "preflight",
        "cli.config.profile.preflight_help",
        "_profile_inspect",
        "config_profile_preflight",
        _PAYLOADS,
        "ConfigProfilePreflightResult",
        CALCULATION_READ,
        (
            _option("modelo", ("--modelo",), _STR, "cli.config.profile.preflight_modelo_help", required=True),
            _option(
                "filing_year", ("--filing-year",), _INT, "cli.config.profile.preflight_filing_year_help", required=True
            ),
            _option("period", ("--period",), _STR, "cli.config.profile.preflight_period_help", required=True),
            _option("revision_id", ("--revision-id",), _STR, "cli.config.profile.preflight_revision_id_help"),
            _LANGUAGE,
        ),
    ),
    _leaf(
        "config_profile_restore",
        "config_profile",
        "restore",
        "cli.config.profile.restore.help",
        "_restore_cli",
        "profile_restore",
        _PAYLOADS,
        "ConfigProfileRestoreResult",
        BOOTSTRAP_WRITE,
        (
            _argument("label", _STR, "cli.config.profile.restore.label_help"),
            _option(
                "file",
                ("--file",),
                _PATH,
                "cli.config.profile.restore.file_help",
                required=True,
                constraint=ParameterConstraint(exists=True),
            ),
            _option(
                "artifact",
                ("--artifact",),
                _PATH,
                "cli.config.profile.restore.artifact_help",
                constraint=ParameterConstraint(exists=True, dir_okay=False),
            ),
            _option(
                "secrets_stdin",
                ("--secrets-stdin",),
                _BOOL,
                "cli.config.custody.secrets_stdin_help",
                default=False,
                flag=True,
                machine_secret_channel=MachineSecretChannelKind.STDIN,
            ),
            _option(
                "secrets_fd",
                ("--secrets-fd",),
                _INT,
                "cli.config.custody.secrets_fd_help",
                machine_secret_channel=MachineSecretChannelKind.FILE_DESCRIPTOR,
            ),
            _LANGUAGE,
        ),
        MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "passphrase",
                    (MachineSecretFieldSpec("passphrase"),),
                    DeferredTarget("cadrumo.entrypoints.cli._config._restore_cli", "RestorePassphraseSecrets"),
                    MachineSecretConditionSpec("artifact", "absent"),
                ),
                MachineSecretVariantSpec(
                    "recovery",
                    (MachineSecretFieldSpec("recovery_secret"),),
                    DeferredTarget("cadrumo.entrypoints.cli._config._restore_cli", "RestoreRecoverySecrets"),
                    MachineSecretConditionSpec("artifact", "present"),
                ),
            )
        ),
    ),
    _leaf(
        "config_profile_show",
        "config_profile",
        "show",
        "cli.config.profile.show_help",
        "_profile_inspect",
        "config_profile_show",
        _PAYLOADS,
        "ConfigProfileShowResult",
        ENCRYPTED_READ,
        (_argument("name", _STR, "cli.config.profile.show_name_help", required=False), _LANGUAGE),
        profile_target_parameter="name",
    ),
    _leaf(
        "config_profile_validate",
        "config_profile",
        "validate",
        "cli.config.profile.validate_help",
        "_profile_inspect",
        "config_profile_validate",
        _PAYLOADS,
        "ConfigProfileValidateResult",
        CALCULATION_READ,
        (_argument("name", _STR, "cli.config.profile.validate_name_help", required=False), _LANGUAGE),
        profile_target_parameter="name",
    ),
)

__all__ = ["PROFILE_COMMAND_SPECS"]
