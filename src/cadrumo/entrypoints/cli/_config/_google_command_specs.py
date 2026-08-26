"""Import-light production command authority for the config Google family."""

from __future__ import annotations

from ....core.transport_locus import TransportLocus, TransportRole, TransportShape
from .._command_spec import (
    ArgumentSpec,
    CommandSpec,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    LiteralValue,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from ._spec_policies import (
    GOOGLE_CALCULATION_HANDOFF,
    GOOGLE_CALCULATION_READ,
    GOOGLE_CALCULATION_WRITE,
    GOOGLE_DESTRUCTIVE,
    GOOGLE_READ,
    GOOGLE_WRITE,
    STATE_FREE,
)

_BOOL = ValueContract(DeferredTarget("builtins", "bool"))
_INT = ValueContract(DeferredTarget("builtins", "int"))
_PATH = ValueContract(DeferredTarget("pathlib", "Path"))
_STR = ValueContract(DeferredTarget("builtins", "str"))
_CREDENTIAL_KIND = ValueContract(DeferredTarget("cadrumo.core", "GoogleCredentialSourceKind"))


def _key(value: str) -> TranslationKey:
    return TranslationKey(value)


def _handler(module: str, name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget(f"cadrumo.entrypoints.cli._config.{module}", name))


def _schema(module: str, name: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget(f"cadrumo.entrypoints.cli._config.{module}", name),
        identity=identity,
    )


def _group(key: str, parent: str, token: str, help_key: str) -> CommandSpec:
    return CommandSpec(
        key=key,
        parent_key=parent,
        token=token,
        kind="group",
        help_key=_key(help_key),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    )


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
    minimum: int | None = None,
    maximum: int | None = None,
    transport_locus: TransportLocus = TransportLocus.NONE,
    transport_shape: TransportShape = TransportShape.NOT_APPLICABLE,
    transport_role: TransportRole = TransportRole.NOT_APPLICABLE,
) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=value,
        default=ParameterDefault.required() if required else ParameterDefault.value(default),
        help_key=_key(help_key),
        is_flag=flag,
        flag_value=True if flag else None,
        multiple=multiple,
        constraint=ParameterConstraint(minimum=minimum, maximum=maximum),
        transport_locus=transport_locus,
        transport_shape=transport_shape,
        transport_role=transport_role,
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
) -> CommandSpec:
    return CommandSpec(
        key=key,
        parent_key=parent,
        token=token,
        kind="leaf",
        help_key=_key(help_key),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=parameters,
        policy=policy,
        handler=_handler(module, handler),
        result_schema=_schema(schema_module, schema_name, key.replace("_", ".")),
    )


_MODELO = _option("modelo", ("--modelo",), _STR, "cli.config.google.sync.calc.export.modelo_help", required=True)
_PERIOD = _option("period", ("--period",), _STR, "cli.config.google.sync.calc.export.period_help", required=True)
_YEAR = _option(
    "year",
    ("--year",),
    _INT,
    "cli.config.google.sync.calc.export.year_help",
    required=True,
    minimum=2000,
    maximum=2099,
)
_SPREADSHEET_ID = _option(
    "spreadsheet_id",
    ("--spreadsheet-id",),
    _STR,
    "cli.config.google.sync.calc.pull.spreadsheet_id_help",
    required=True,
    minimum=1,
    transport_locus=TransportLocus.REMOTE_HANDLE,
    transport_shape=TransportShape.NOT_APPLICABLE,
    transport_role=TransportRole.NOT_APPLICABLE,
)


GOOGLE_COMMAND_SPECS = (
    _group("config_google", "config", "google", "cli.config.google.help"),
    _leaf(
        "config_google_register",
        "config_google",
        "register",
        "cli.config.google.register_help",
        "_google",
        "google_register",
        "_google_payloads",
        "GoogleRegisterResult",
        GOOGLE_WRITE,
        (
            _option(
                "client_json",
                ("--client-json",),
                _PATH,
                "cli.config.google.client_json_help",
                required=True,
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
        ),
    ),
    _leaf(
        "config_google_login",
        "config_google",
        "login",
        "cli.config.google.login_help",
        "_google",
        "google_login",
        "_google_payloads",
        "GoogleLoginResult",
        GOOGLE_WRITE,
        (
            _option(
                "refresh_only",
                ("--refresh-only",),
                _BOOL,
                "cli.config.google.refresh_only_help",
                default=False,
                flag=True,
            ),
        ),
    ),
    _leaf(
        "config_google_status",
        "config_google",
        "status",
        "cli.config.google.status_help",
        "_google",
        "google_status",
        "_google_payloads",
        "GoogleStatusResult",
        GOOGLE_READ,
    ),
    _leaf(
        "config_google_logout",
        "config_google",
        "logout",
        "cli.config.google.logout_help",
        "_google",
        "google_logout",
        "_google_payloads",
        "GoogleLogoutResult",
        GOOGLE_DESTRUCTIVE,
    ),
    _group(
        "config_google_credential_source",
        "config_google",
        "credential-source",
        "cli.config.google.credential_source.help",
    ),
    _leaf(
        "config_google_credential_source_set",
        "config_google_credential_source",
        "set",
        "cli.config.google.credential_source.set_help",
        "_google_credential_source_cli",
        "google_credential_source_set",
        "_google_credential_source_payloads",
        "GoogleCredentialSourceSetResult",
        GOOGLE_WRITE,
        (
            _option(
                "kind", ("--kind",), _CREDENTIAL_KIND, "cli.config.google.credential_source.kind_help", required=True
            ),
            _option(
                "target_principal",
                ("--target-principal",),
                _STR,
                "cli.config.google.credential_source.target_principal_help",
            ),
            _option(
                "scopes",
                ("--scope",),
                _STR,
                "cli.config.google.credential_source.scope_help",
                multiple=True,
            ),
            _option(
                "delegates",
                ("--delegate",),
                _STR,
                "cli.config.google.credential_source.delegate_help",
                multiple=True,
            ),
            _option("subject", ("--subject",), _STR, "cli.config.google.credential_source.subject_help"),
            _option(
                "lifetime_seconds", ("--lifetime-seconds",), _INT, "cli.config.google.credential_source.lifetime_help"
            ),
        ),
    ),
    _leaf(
        "config_google_credential_source_show",
        "config_google_credential_source",
        "show",
        "cli.config.google.credential_source.show_help",
        "_google_credential_source_cli",
        "google_credential_source_show",
        "_google_credential_source_payloads",
        "GoogleCredentialSourceShowResult",
        GOOGLE_READ,
    ),
    _group("config_google_folder", "config_google", "folder", "cli.config.google.folder.help"),
    _leaf(
        "config_google_folder_set",
        "config_google_folder",
        "set",
        "cli.config.google.folder.set_help",
        "_google_folder",
        "google_folder_set",
        "_google_folder_payloads",
        "GoogleFolderSetResult",
        GOOGLE_WRITE,
        (
            ArgumentSpec(
                "folder_id",
                _STR,
                ParameterDefault.required(),
                _key("cli.config.google.folder.folder_id_help"),
                transport_locus=TransportLocus.REMOTE_HANDLE,
                transport_shape=TransportShape.NOT_APPLICABLE,
                transport_role=TransportRole.NOT_APPLICABLE,
            ),
        ),
    ),
    _leaf(
        "config_google_folder_get",
        "config_google_folder",
        "get",
        "cli.config.google.folder.get_help",
        "_google_folder",
        "google_folder_get",
        "_google_folder_payloads",
        "GoogleFolderGetResult",
        GOOGLE_READ,
    ),
    _group("config_google_sync", "config_google", "sync", "cli.config.google.sync.help"),
    _leaf(
        "config_google_sync_probe",
        "config_google_sync",
        "probe",
        "cli.config.google.sync.probe_help",
        "_google",
        "google_sync_probe",
        "_google_payloads",
        "GoogleSyncProbeResult",
        GOOGLE_READ,
        (
            _option(
                "read_only",
                ("--read-only/--no-read-only",),
                _BOOL,
                "cli.config.google.sync.probe_read_only_help",
                default=False,
                flag=True,
            ),
        ),
    ),
    _leaf(
        "config_google_sync_push",
        "config_google_sync",
        "push",
        "cli.config.google.sync.push_help",
        "_google",
        "google_sync_push",
        "_google_payloads",
        "GoogleSyncPushResult",
        GOOGLE_WRITE,
        (
            _option("namespace_filter", ("--namespace",), _STR, "cli.config.google.sync.push_namespace_help"),
            _option("limit", ("--limit",), _INT, "cli.config.google.sync.push_limit_help", minimum=1),
            _option(
                "dry_run",
                ("--dry-run/--no-dry-run",),
                _BOOL,
                "cli.config.google.sync.push_dry_run_help",
                default=False,
                flag=True,
            ),
        ),
    ),
    _group("config_google_sync_calc", "config_google_sync", "calc", "cli.config.google.sync.calc.help"),
    _leaf(
        "config_google_sync_calc_export",
        "config_google_sync_calc",
        "export",
        "cli.config.google.sync.calc.export_help",
        "_google_sync_calc",
        "google_sync_calc_export",
        "_google_payloads",
        "GoogleSyncCalcExportResult",
        GOOGLE_CALCULATION_HANDOFF,
        (
            _MODELO,
            _PERIOD,
            _YEAR,
            _option(
                "prefill_relations",
                ("--prefill-relations/--no-prefill-relations",),
                _BOOL,
                "cli.config.google.sync.calc.export.prefill_relations_help",
                default=False,
                flag=True,
            ),
            _option(
                "dry_run",
                ("--dry-run",),
                _BOOL,
                "cli.config.google.sync.calc.export.dry_run_help",
                default=False,
                flag=True,
            ),
        ),
    ),
    _leaf(
        "config_google_sync_calc_verify",
        "config_google_sync_calc",
        "verify",
        "cli.config.google.sync.calc.verify_help",
        "_google_sync_calc",
        "google_sync_calc_verify",
        "_google_payloads",
        "GoogleSyncCalcVerifyResult",
        GOOGLE_CALCULATION_READ,
        (
            _MODELO,
            _PERIOD,
            _YEAR,
            _option(
                "scenario_path",
                ("--scenario",),
                _PATH,
                "cli.config.google.sync.calc.verify.scenario_help",
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.AUXILIARY,
            ),
        ),
    ),
    _leaf(
        "config_google_sync_calc_pull",
        "config_google_sync_calc",
        "pull",
        "cli.config.google.sync.calc.pull_help",
        "_google_sync_calc",
        "google_sync_calc_pull",
        "_google_payloads",
        "GoogleSyncCalcPullResult",
        GOOGLE_CALCULATION_WRITE,
        (
            _MODELO,
            _PERIOD,
            _YEAR,
            _SPREADSHEET_ID,
            _option(
                "assemble_observations",
                ("--assemble-observations/--no-assemble-observations",),
                _BOOL,
                "cli.config.google.sync.calc.pull.assemble_observations_help",
                default=False,
                flag=True,
            ),
        ),
    ),
    _leaf(
        "config_google_sync_calc_compute",
        "config_google_sync_calc",
        "compute",
        "cli.config.google.sync.calc.compute_help",
        "_google_sync_calc",
        "google_sync_calc_compute",
        "_google_payloads",
        "GoogleSyncCalcComputeResult",
        GOOGLE_CALCULATION_WRITE,
        (
            _MODELO,
            _PERIOD,
            _YEAR,
            _option(
                "spreadsheet_id",
                ("--spreadsheet-id",),
                _STR,
                "cli.config.google.sync.calc.compute.spreadsheet_id_help",
                required=True,
                minimum=1,
                transport_locus=TransportLocus.REMOTE_HANDLE,
                transport_shape=TransportShape.NOT_APPLICABLE,
                transport_role=TransportRole.NOT_APPLICABLE,
            ),
        ),
    ),
)


__all__ = ["GOOGLE_COMMAND_SPECS"]
