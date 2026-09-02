"""Authored CommandSpec declarations for the Modelo non-work m145 family."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from typing import Final

from ._modelo_nonwork_command_spec_policies import (
    _MODEL_HANDOFF,
    _MODEL_READ,
    _MODEL_WRITE,
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

M145_COMMUNICATION_RECORD_ID_PARAMETER: Final[ArgumentSpec] = ArgumentSpec(
    name="communication_record_id",
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.app.modelo.m145.communication_record_id_help"),
)

M145_ACTOR_PARAMETER: Final[OptionSpec] = OptionSpec(
    name="actor",
    declarations=("--by",),
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.app.modelo.m145.actor_help"),
    multiple=False,
    is_flag=False,
    flag_value=None,
    constraint=ParameterConstraint(),
)

M145_RECORD_ACTION_PARAMETERS: Final[tuple[ArgumentSpec | OptionSpec, ...]] = (
    M145_COMMUNICATION_RECORD_ID_PARAMETER,
    M145_ACTOR_PARAMETER,
)

MODELO_NONWORK_M145_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_modelo_m145_create",
        parent_key="app_modelo_m145",
        token="create",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.m145.create_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="year",
                declarations=("--year",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.modelo.m145.year_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
            OptionSpec(
                name="period",
                declarations=("--period",),
                value=ValueContract(
                    DeferredTarget("cadrumo.application.modelo.m145_communication_period", "M145CommunicationPeriod")
                ),
                default=ParameterDefault.value("comunicacion"),
                help_key=TranslationKey("cli.app.modelo.m145.period_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
            OptionSpec(
                name="casilla",
                declarations=("--casilla",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(()),
                help_key=TranslationKey("cli.app.modelo.m145.casilla_help"),
                multiple=True,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
            OptionSpec(
                name="note",
                declarations=("--note",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.m145.note_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
            M145_ACTOR_PARAMETER,
        ),
        policy=_MODEL_WRITE,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._modelo_m145_cli", "m145_create")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads_m145", "M145CommunicationRecordResult"),
            identity="modelo.m145.create",
        ),
    ),
    CommandSpec(
        key="app_modelo_m145_validate",
        parent_key="app_modelo_m145",
        token="validate",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.m145.validate_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(M145_COMMUNICATION_RECORD_ID_PARAMETER,),
        policy=_MODEL_READ,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._modelo_m145_cli", "m145_validate")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads_m145", "M145CommunicationValidationResultPayload"),
            identity="modelo.m145.validate",
        ),
    ),
    CommandSpec(
        key="app_modelo_m145_export",
        parent_key="app_modelo_m145",
        token="export",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.m145.export_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=M145_RECORD_ACTION_PARAMETERS,
        policy=_MODEL_HANDOFF,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._modelo_m145_cli", "m145_export")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads_m145", "M145CommunicationExportResultPayload"),
            identity="modelo.m145.export",
        ),
    ),
    CommandSpec(
        key="app_modelo_m145_mark_delivered_to_payer",
        parent_key="app_modelo_m145",
        token="mark-delivered-to-payer",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.m145.mark_delivered_to_payer_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=M145_RECORD_ACTION_PARAMETERS,
        policy=_MODEL_WRITE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_m145_cli", "m145_mark_delivered_to_payer")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads_m145", "M145CommunicationRecordResult"),
            identity="modelo.m145.mark_delivered_to_payer",
        ),
    ),
    CommandSpec(
        key="app_modelo_m145_mark_locally_completed",
        parent_key="app_modelo_m145",
        token="mark-locally-completed",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.m145.mark_locally_completed_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=M145_RECORD_ACTION_PARAMETERS,
        policy=_MODEL_WRITE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_m145_cli", "m145_mark_locally_completed")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads_m145", "M145CommunicationRecordResult"),
            identity="modelo.m145.mark_locally_completed",
        ),
    ),
)

__all__ = ["MODELO_NONWORK_M145_COMMAND_SPECS"]
