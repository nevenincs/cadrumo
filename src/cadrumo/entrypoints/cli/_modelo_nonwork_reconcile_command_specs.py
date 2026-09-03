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
from ._modelo_nonwork_common_command_parameters import (
    _optional_text_argument,
    _optional_text_option,
    _optional_whole_number_option,
)
from .command_spec import (
    ArgumentSpec,
    CommandNodeKind,
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
    _optional_text_argument("work_unit_id", "cli.app.modelo.reconcile.work_unit_id_help"),
    _optional_text_option("modelo", ("--modelo",), "cli.app.modelo.work.modelo_help"),
    _optional_whole_number_option("year", ("--year",), "cli.app.modelo.work.year_help"),
    _optional_text_option("period", ("--period",), "cli.app.modelo.work.period_help"),
    _optional_text_option("revision", ("--revision",), "cli.app.modelo.work.revision_help"),
    _optional_text_option("bucket_id", ("--bucket-id",), "cli.app.modelo.work.bucket_id_help"),
    _optional_text_option("actor", ("--by",), "cli.app.modelo.work.actor_help"),
)

MODELO_NONWORK_RECONCILE_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_modelo_reconcile_pull",
        parent_key="app_modelo_reconcile",
        token="pull",
        kind=CommandNodeKind.LEAF,
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
        kind=CommandNodeKind.LEAF,
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
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.reconcile.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _optional_text_option(
                "work_unit_id", ("--work-unit-id",), "cli.app.modelo.reconcile.list_work_unit_id_help"
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
