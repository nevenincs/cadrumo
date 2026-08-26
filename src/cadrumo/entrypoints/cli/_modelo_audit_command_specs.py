"""Import-light CommandSpec authority for the modelo audit family."""

from __future__ import annotations

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from ._command_spec import (
    ArgumentSpec,
    CommandSpec,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

_MODEL_READ = ExecutionPolicySpec(
    capabilities=frozenset({"encrypted-facts"}),
    side_effects=frozenset({"none"}),
    performance="local-io",
    write_route="none",
)
_MODEL_HANDOFF = ExecutionPolicySpec(
    capabilities=frozenset({"encrypted-facts", "filing"}),
    side_effects=frozenset({"local-state"}),
    performance="compute",
    write_route="profile-bound",
    handoff=True,
)
_METADATA = ExecutionPolicySpec(
    capabilities=frozenset({"state-free"}),
    side_effects=frozenset({"none"}),
    performance="metadata",
    write_route="none",
)
_STR = ValueContract(DeferredTarget("builtins", "str"))
_BOOL = ValueContract(DeferredTarget("builtins", "bool"))
_PATH = ValueContract(DeferredTarget("pathlib", "Path"))

MODELO_ROOT_COMMAND_SPEC = CommandSpec(
    key="app_modelo",
    parent_key="app",
    token="modelo",  # noqa: S106 - CLI operator token, not a credential
    kind="group",
    help_key=TranslationKey("cli.app.modelo.app_help"),
    short_help_key=None,
    invocation=InvocationSpec(no_args_is_help=True),
    parameters=(),
    policy=_METADATA,
    handler=None,
    result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
)


def _leaf(
    token: str,
    help_key: str,
    handler: str,
    schema_name: str,
    policy: ExecutionPolicySpec,
    parameters: tuple[ArgumentSpec | OptionSpec, ...],
) -> CommandSpec:
    key = f"app_modelo_audit_{token}"
    identity = f"modelo.audit.{token}"
    return CommandSpec(
        key=key,
        parent_key="app_modelo_audit",
        token=token,
        kind="leaf",
        help_key=TranslationKey(help_key),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=parameters,
        policy=policy,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._modelo_audit_cli", handler)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads", schema_name),
            identity=identity,
        ),
    )


_BUNDLE_ID = ArgumentSpec(
    name="bundle_id",
    value=_STR,
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.app.modelo.audit.bundle_id_help"),
)

MODELO_AUDIT_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_modelo_audit",
        parent_key="app_modelo",
        token="audit",  # noqa: S106 - CLI operator token, not a credential
        kind="group",
        help_key=TranslationKey("cli.app.modelo.audit.group_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=_METADATA,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    _leaf(
        "show",
        "cli.app.modelo.audit.show_help",
        "audit_show",
        "ModeloAuditShowResult",
        _MODEL_READ,
        (_BUNDLE_ID,),
    ),
    _leaf(
        "check",
        "cli.app.modelo.audit.check_help",
        "audit_check",
        "ModeloAuditCheckResult",
        _MODEL_READ,
        (_BUNDLE_ID,),
    ),
    _leaf(
        "export",
        "cli.app.modelo.audit.export_help",
        "audit_export",
        "ModeloAuditExportResult",
        _MODEL_HANDOFF,
        (
            _BUNDLE_ID,
            OptionSpec(
                name="output",
                declarations=("--output",),
                value=_PATH,
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.modelo.audit.output_help"),
                transport_locus=TransportLocus.LOCAL_OUT,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            OptionSpec(
                name="force_incomplete",
                declarations=("--force-incomplete",),
                value=_BOOL,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.app.modelo.audit.force_incomplete_help"),
                is_flag=True,
                flag_value=True,
            ),
        ),
    ),
)

__all__ = ["MODELO_AUDIT_COMMAND_SPECS", "MODELO_ROOT_COMMAND_SPEC"]
