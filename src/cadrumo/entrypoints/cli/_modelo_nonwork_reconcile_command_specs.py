"""Authored CommandSpec declarations for the Modelo non-work reconcile family."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from typing import Final

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from ._modelo_nonwork_command_spec_policies import (
    _BROWSER_MODEL_WRITE,
    _MODEL_HANDOFF,
    _MODEL_READ,
)
from .command_spec import (
    ArgumentSpec,
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

RECONCILE_TARGET_PARAMETERS: Final[tuple[ArgumentSpec | OptionSpec, ...]] = (
    ArgumentSpec(
        name="work_unit_id",
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.modelo.reconcile.work_unit_id_help"),
    ),
    OptionSpec(
        name="modelo",
        declarations=("--modelo",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.modelo.work.modelo_help"),
        multiple=False,
        is_flag=False,
        flag_value=None,
        constraint=ParameterConstraint(),
    ),
    OptionSpec(
        name="year",
        declarations=("--year",),
        value=ValueContract(DeferredTarget("builtins", "int")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.modelo.work.year_help"),
        multiple=False,
        is_flag=False,
        flag_value=None,
        constraint=ParameterConstraint(),
    ),
    OptionSpec(
        name="period",
        declarations=("--period",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.modelo.work.period_help"),
        multiple=False,
        is_flag=False,
        flag_value=None,
        constraint=ParameterConstraint(),
    ),
    OptionSpec(
        name="revision",
        declarations=("--revision",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.modelo.work.revision_help"),
        multiple=False,
        is_flag=False,
        flag_value=None,
        constraint=ParameterConstraint(),
    ),
    OptionSpec(
        name="bucket_id",
        declarations=("--bucket-id",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.modelo.work.bucket_id_help"),
        multiple=False,
        is_flag=False,
        flag_value=None,
        constraint=ParameterConstraint(),
    ),
    OptionSpec(
        name="actor",
        declarations=("--by",),
        value=ValueContract(DeferredTarget("builtins", "str")),
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.app.modelo.work.actor_help"),
        multiple=False,
        is_flag=False,
        flag_value=None,
        constraint=ParameterConstraint(),
    ),
)

MODELO_NONWORK_RECONCILE_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_modelo_reconcile_pull",
        parent_key="app_modelo_reconcile",
        token="pull",
        kind="leaf",
        help_key=TranslationKey("cli.app.modelo.reconcile.pull_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=RECONCILE_TARGET_PARAMETERS,
        policy=_BROWSER_MODEL_WRITE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_reconcile_cli", "reconcile_pull_verb")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._payloads_modelo_reconcile", "ModeloReconcileResult"),
            identity="modelo.reconcile.pull",
        ),
    ),
    CommandSpec(
        key="app_modelo_reconcile_import",
        parent_key="app_modelo_reconcile",
        token="import",
        kind="leaf",
        help_key=TranslationKey("cli.app.modelo.reconcile.import_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            RECONCILE_TARGET_PARAMETERS[0],
            OptionSpec(
                name="file",
                declarations=("--file",),
                value=ValueContract(DeferredTarget("pathlib", "Path")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.modelo.reconcile.file_path_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            *RECONCILE_TARGET_PARAMETERS[1:],
            OptionSpec(
                name="kind",
                declarations=("--kind",),
                value=ValueContract(
                    DeferredTarget(
                        "cadrumo.application.modelo.reconciliation_records", "ModeloReconciliationEvidenceKind"
                    )
                ),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.reconcile.file_kind_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
        ),
        policy=_MODEL_HANDOFF,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_reconcile_cli", "reconcile_file_verb")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._payloads_modelo_reconcile", "ModeloReconcileResult"),
            identity="modelo.reconcile.import",
        ),
    ),
    CommandSpec(
        key="app_modelo_reconcile_list",
        parent_key="app_modelo_reconcile",
        token="list",
        kind="leaf",
        help_key=TranslationKey("cli.app.modelo.reconcile.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="work_unit_id",
                declarations=("--work-unit-id",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.reconcile.list_work_unit_id_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
        ),
        policy=_MODEL_READ,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_reconcile_cli", "reconcile_list_verb")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads_m036", "ModeloReconciliationHistoryResult"),
            identity="modelo.reconcile.list",
        ),
    ),
)

__all__ = ["MODELO_NONWORK_RECONCILE_COMMAND_SPECS"]
