"""Import-light production authority for the config profile command family."""

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
    LiteralValue,
    MachineSecretChannelKind,
    MachineSecretConditionSpec,
    MachineSecretFieldSpec,
    MachineSecretPresence,
    MachineSecretSpec,
    MachineSecretVariantSpec,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    RecoveryHandoffSpec,
    ResultSchemaSpec,
    SchemaState,
    TuiCapability,
    ValueContract,
)
from ..command_spec import translation_key as _key
from ._spec_policies import (
    BOOTSTRAP_DESTRUCTIVE,
    BOOTSTRAP_WRITE,
    CALCULATION_READ,
    ENCRYPTED_DESTRUCTIVE,
    ENCRYPTED_READ,
    ENCRYPTED_WRITE,
    GOOGLE_WRITE,
    LIVE_PROFILE_WRITE,
    PROFILE_DESTRUCTIVE,
    PROFILE_READ,
    STATE_FREE,
)

_PATH = ValueContract(DeferredTarget("pathlib", "Path"))
_LANG = ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage"))
_CAPABILITY = ValueContract(DeferredTarget("cadrumo.core.capabilities", "ServiceCapability"))
_TOGGLE = ValueContract(
    DeferredTarget("builtins", "str"),
    choices=("on", "off"),
)


# Every dynamically resolved handler module is named here as a WHOLE dotted path.
# The path used to be built with an f-string, which meant no static reader -- grep,
# the import-hygiene scan, or a dead-code sweep -- could see the edge, so all of
# these modules read as orphaned while backing live verbs. A wrong key now raises
# at spec-build time instead of failing lazily on first invocation.
_HANDLER_MODULES: Final[dict[str, str]] = {
    "_archive_cli": "cadrumo.entrypoints.cli.config._archive_cli",
    "_archive_reconcile": "cadrumo.entrypoints.cli.config._archive_reconcile",
    "_bucket_history": "cadrumo.entrypoints.cli.config._bucket_history",
    "_capabilities_cli": "cadrumo.entrypoints.cli.config._capabilities_cli",
    "_censo_transport": "cadrumo.entrypoints.cli.config._censo_transport",
    "_complete_setup_cli": "cadrumo.entrypoints.cli.config._complete_setup_cli",
    "_descendiente": "cadrumo.entrypoints.cli.config.descendiente",
    "_google": "cadrumo.entrypoints.cli.config.google",
    "_manager_dispatch": "cadrumo.entrypoints.cli.config._manager_dispatch",
    "_profile_delete": "cadrumo.entrypoints.cli.config._profile_delete",
    "_profile_inspect": "cadrumo.entrypoints.cli.config._profile_inspect",
    "_profile_repeatable_row": "cadrumo.entrypoints.cli.config._profile_repeatable_row",
    "_restore_cli": "cadrumo.entrypoints.cli.config._restore_cli",
}


def _handler(module: str, name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget(_HANDLER_MODULES[module], name))


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
    transport_locus: TransportLocus = TransportLocus.NONE,
    transport_shape: TransportShape = TransportShape.NOT_APPLICABLE,
    transport_role: TransportRole = TransportRole.NOT_APPLICABLE,
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
        transport_locus=transport_locus,
        transport_shape=transport_shape,
        transport_role=transport_role,
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
        CommandNodeKind.GROUP,
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
    recovery_handoff: RecoveryHandoffSpec | None = None,
    profile_target_parameter: str | None = None,
    tui_capability: TuiCapability = TuiCapability.NOT_IMPLEMENTED,
) -> CommandSpec:
    return CommandSpec(
        key,
        parent,
        token,
        CommandNodeKind.LEAF,
        _key(help_key),
        None,
        InvocationSpec(context_parameter="ctx"),
        parameters,
        policy,
        _handler(module, handler),
        _schema(schema_module, schema_name, key.replace("_", ".")),
        machine_secret=machine_secret,
        recovery_handoff=recovery_handoff,
        profile_target_parameter=profile_target_parameter,
        tui_capability=tui_capability,
    )


_PAYLOADS = "cadrumo.entrypoints.cli.config_payloads"
_PAYLOADS_ARCHIVE_RECONCILE = "cadrumo.entrypoints.cli.config._archive_reconcile_payloads"
_PAYLOADS_ARCHIVE_PUSH = "cadrumo.entrypoints.cli.config._archive_push_payloads"
_CONFIG = "cadrumo.entrypoints.cli.config"
#: Both wizard result schemas are defined in this module. The package
#: namespace above it is inert and re-exports nothing, so naming the package
#: leaves the spec pointing at an attribute that does not exist.
_WIZARD = "cadrumo.application.wizard.results"

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


#: Wizard axes whose answer validator accepts the enum's exact member value and
#: nothing else, so the closed set can be declared at the Typer boundary and click
#: renders it on a parse failure. ``iva-regime`` is deliberately absent: its
#: validator upper-cases the token before constructing the enum, so it accepts
#: lowercase input a Choice would refuse.
_WIZARD_ENUM_FIELDS: dict[str, ValueContract] = {
    "entity-type": ValueContract(DeferredTarget("cadrumo.domain.contribuyente.entity_type", "EntityType")),
    "legal-entity-form": ValueContract(DeferredTarget("cadrumo.domain.contribuyente.entity_type", "LegalEntityForm")),
    "irpf-estimation-regime": ValueContract(DeferredTarget("cadrumo.domain.deadlines.models", "IrpfEstimationRegime")),
    "irpf-special-regime": ValueContract(DeferredTarget("cadrumo.domain.deadlines.models", "IrpfSpecialRegime")),
    "fiscal-residency": ValueContract(DeferredTarget("cadrumo.domain.contribuyente.renta_codes", "FiscalResidency")),
}


def _wizard_option(token: str) -> OptionSpec:
    name = token.replace("-", "_")
    help_key = f"wizard.setup.flags.{token}.help"
    if token == "output-language":  # noqa: S105 - CLI token, not a credential
        return _option(name, ("--output-language",), _LANG, help_key)
    if token in _WIZARD_CONFIRM_FIELDS:
        return _option(
            name,
            (f"--{token}", f"--no-{token}"),
            FLAG_VALUE,
            help_key,
            flag=True,
        )
    if token in _WIZARD_CHECKBOX_FIELDS:
        return _option(name, (f"--{token}",), TEXT_VALUE, help_key, default=(), multiple=True)
    enum_contract = _WIZARD_ENUM_FIELDS.get(token)
    if enum_contract is not None:
        return _option(name, (f"--{token}",), enum_contract, help_key)
    return _option(name, (f"--{token}",), TEXT_VALUE, help_key)


_WIZARD_BASE_PARAMETERS: tuple[ArgumentSpec | OptionSpec, ...] = (
    _argument("profile_name", TEXT_VALUE, "cli.config.setup.profile_name_help", required=False),
    _option("quiet", ("--quiet",), FLAG_VALUE, "cli.config.setup.quiet_help", default=False, flag=True),
    _option(
        "accept_defaults",
        ("--accept-defaults",),
        FLAG_VALUE,
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
        FLAG_VALUE,
        "cli.config.custody.secrets_stdin_help",
        default=False,
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
    _option(
        "recovery_handoff_fd",
        ("--recovery-handoff-fd",),
        WHOLE_NUMBER_VALUE,
        "cli.config.profile.create_recovery_handoff_fd_help",
    ),
    _option(
        "recovery_verification_fd",
        ("--recovery-verification-fd",),
        WHOLE_NUMBER_VALUE,
        "cli.config.profile.create_recovery_verification_fd_help",
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
        CommandNodeKind.GROUP,
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
        tui_capability=TuiCapability.NOT_IMPLEMENTED,
    ),
    _leaf(
        "config_profile_add_row",
        "config_profile",
        "add-row",
        "cli.config.profile.add_row.help",
        "_profile_repeatable_row",
        "profile_add_row",
        _PAYLOADS,
        "ConfigProfileAddRowResult",
        ENCRYPTED_WRITE,
        (
            _argument("section", TEXT_VALUE, "cli.config.profile.add_row.section_help"),
            _option(
                "value",
                ("--value",),
                TEXT_VALUE,
                "cli.config.profile.add_row.value_help",
                required=True,
                multiple=True,
            ),
            _LANGUAGE,
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
            _argument("name", TEXT_VALUE, "cli.config.profile.archive.export_name_help"),
            _option(
                "output",
                ("--output",),
                _PATH,
                "cli.config.profile.archive.export_out_help",
                required=True,
                constraint=ParameterConstraint(dir_okay=False, writable=True),
                transport_locus=TransportLocus.LOCAL_OUT,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            _LANGUAGE,
        ),
    ),
    _leaf(
        "config_profile_archive_push",
        "config_profile_archive",
        "push",
        "cli.config.profile.archive.push_help",
        "_google",
        "profile_archive_push",
        _PAYLOADS_ARCHIVE_PUSH,
        "ProfileArchivePushResult",
        GOOGLE_WRITE,
        (
            _option("namespace_filter", ("--namespace",), TEXT_VALUE, "cli.config.profile.archive.push_namespace_help"),
            _option(
                "limit",
                ("--limit",),
                WHOLE_NUMBER_VALUE,
                "cli.config.profile.archive.push_limit_help",
                constraint=ParameterConstraint(minimum=1),
            ),
            _option(
                "dry_run",
                ("--dry-run/--no-dry-run",),
                FLAG_VALUE,
                "cli.config.profile.archive.push_dry_run_help",
                default=False,
                flag=True,
            ),
        ),
    ),
    _leaf(
        "config_profile_archive_reconcile",
        "config_profile_archive",
        "reconcile",
        "cli.config.profile.archive.reconcile_help",
        "_archive_reconcile",
        "profile_archive_reconcile",
        _PAYLOADS_ARCHIVE_RECONCILE,
        "ProfileBundleReconcileResult",
        PROFILE_DESTRUCTIVE,
        (_LANGUAGE,),
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
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            _LANGUAGE,
        ),
    ),
    _leaf(
        "config_profile_capabilities_view",
        "config_profile_capabilities",
        "view",
        "cli.config.profile.capabilities.view_help",
        "_capabilities_cli",
        "capabilities_view",
        f"{_CONFIG}.capabilities_payloads",
        "CapabilitiesViewResult",
        ENCRYPTED_READ,
    ),
    _leaf(
        "config_profile_capabilities_set",
        "config_profile_capabilities",
        "set",
        "cli.config.profile.capabilities.set_help",
        "_capabilities_cli",
        "capabilities_set",
        f"{_CONFIG}.capabilities_payloads",
        "CapabilitySetResult",
        ENCRYPTED_WRITE,
        (
            _argument("capability", _CAPABILITY, "cli.config.profile.capabilities.capability_help"),
            _argument("state", _TOGGLE, "cli.config.profile.capabilities.state_help"),
        ),
    ),
    _leaf(
        "config_profile_censo_import",
        "config_profile_censo",
        "import",
        "cli.config.profile.censo.import_help",
        "_censo_transport",
        "censo_import",
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
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            _option("apply", ("--apply",), FLAG_VALUE, "cli.config.profile.censo.apply_help", default=False, flag=True),
        ),
    ),
    _leaf(
        "config_profile_censo_pull",
        "config_profile_censo",
        "pull",
        "cli.config.profile.censo.pull_help",
        "_censo_transport",
        "censo_pull",
        f"{_CONFIG}._censo_payloads",
        "CensoPullResult",
        LIVE_PROFILE_WRITE,
        (
            _option(
                "apply",
                ("--apply",),
                FLAG_VALUE,
                "cli.config.profile.censo.pull_apply_help",
                default=False,
                flag=True,
            ),
        ),
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
                        "cadrumo.entrypoints.cli.config._scripted_registration",
                        "ProfileCreationSecrets",
                    ),
                ),
            )
        ),
        recovery_handoff=RecoveryHandoffSpec(
            handoff_parameter="recovery_handoff_fd",
            handoff_direction="write",
            verification_parameter="recovery_verification_fd",
            verification_direction="read",
            required_together=True,
            json_fields=("recovery_mnemonic",),
            maximum_bytes=8192,
            strict_utf8_object=True,
            duplicate_extra_missing_fields_refused=True,
            descriptors_closed=True,
            reserved_descriptors=(0, 1, 2),
            descriptors_must_differ=True,
            collides_with_parameters=("secrets_fd",),
            windows_handle_bootstrap="cadrumo.entrypoints.cli._windows_profile_secret_bootstrap",
        ),
        tui_capability=TuiCapability.NOT_IMPLEMENTED,
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
            _argument("name", TEXT_VALUE, "cli.config.profile.delete.name_help"),
            _option("yes", ("--yes",), FLAG_VALUE, "cli.config.profile.delete.yes_help", default=False, flag=True),
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
                TEXT_VALUE,
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
        (_argument("index", WHOLE_NUMBER_VALUE, "cli.config.profile.descendiente.remove_index_help"), _LANGUAGE),
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
        tui_capability=TuiCapability.NOT_IMPLEMENTED,
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
            _argument("profile", TEXT_VALUE, "cli.config.profile.history_bucket_id_help", required=False),
            _option(
                "event_type", ("--event-type",), TEXT_VALUE, "cli.config.profile.history_event_type_help", multiple=True
            ),
            _option("since", ("--since",), TEXT_VALUE, "cli.config.profile.history_since_help"),
            _option("until", ("--until",), TEXT_VALUE, "cli.config.profile.history_until_help"),
            _option("object_id", ("--object-id",), TEXT_VALUE, "cli.config.profile.history_object_id_help"),
            _option("actor", ("--actor",), TEXT_VALUE, "cli.config.profile.history_actor_help"),
            _LANGUAGE,
        ),
        profile_target_parameter="profile",
    ),
    _leaf(
        "config_profile_archive_import",
        "config_profile_archive",
        "import",
        "cli.config.profile.archive.import_help",
        "_restore_cli",
        "profile_archive_import",
        _PAYLOADS,
        "ConfigProfileArchiveImportResult",
        BOOTSTRAP_WRITE,
        (
            _argument("label", TEXT_VALUE, "cli.config.profile.archive.import_label_help"),
            _option(
                "file",
                ("--file",),
                _PATH,
                "cli.config.profile.archive.import_file_help",
                required=True,
                constraint=ParameterConstraint(exists=True),
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            _option(
                "artifact",
                ("--artifact",),
                _PATH,
                "cli.config.profile.archive.import_artifact_help",
                constraint=ParameterConstraint(exists=True, dir_okay=False),
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.AUXILIARY,
            ),
            _option(
                "secrets_stdin",
                ("--secrets-stdin",),
                FLAG_VALUE,
                "cli.config.custody.secrets_stdin_help",
                default=False,
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
            _LANGUAGE,
        ),
        MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "passphrase",
                    (MachineSecretFieldSpec("passphrase"),),
                    DeferredTarget("cadrumo.entrypoints.cli.config._restore_cli", "RestorePassphraseSecrets"),
                    MachineSecretConditionSpec("artifact", MachineSecretPresence.ABSENT),
                ),
                MachineSecretVariantSpec(
                    "recovery",
                    (MachineSecretFieldSpec("recovery_secret"),),
                    DeferredTarget("cadrumo.entrypoints.cli.config._restore_cli", "RestoreRecoverySecrets"),
                    MachineSecretConditionSpec("artifact", MachineSecretPresence.PRESENT),
                ),
            )
        ),
    ),
    _leaf(
        "config_profile_view",
        "config_profile",
        "view",
        "cli.config.profile.view_help",
        "_profile_inspect",
        "config_profile_view",
        _PAYLOADS,
        "ConfigProfileViewResult",
        ENCRYPTED_READ,
        (_argument("name", TEXT_VALUE, "cli.config.profile.show_name_help", required=False), _LANGUAGE),
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
        (_argument("name", TEXT_VALUE, "cli.config.profile.validate_name_help", required=False), _LANGUAGE),
        profile_target_parameter="name",
    ),
)

__all__ = ["PROFILE_COMMAND_SPECS"]
