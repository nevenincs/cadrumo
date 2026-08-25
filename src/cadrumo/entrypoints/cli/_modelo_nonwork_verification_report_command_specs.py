"""Authored CommandSpec declarations for the Modelo non-work verification report family."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._command_spec import (
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
from ._modelo_nonwork_command_spec_policies import _MODEL_READ

MODELO_NONWORK_VERIFICATION_REPORT_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_modelo_verification_report_list",
        parent_key="app_modelo_verification_report",
        token="list",
        kind="leaf",
        help_key=TranslationKey("cli.app.modelo.verification_report.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="calculation_revision_id",
                declarations=("--calculation-revision-id",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.work.calculation_revision_id_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
        ),
        policy=_MODEL_READ,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_records_cli", "verification_report_list")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads", "VerificationReportListResult"),
            identity="modelo.verification_report.list",
        ),
    ),
    CommandSpec(
        key="app_modelo_verification_report_view",
        parent_key="app_modelo_verification_report",
        token="view",
        kind="leaf",
        help_key=TranslationKey("cli.app.modelo.verification_report.view_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="verification_report_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.modelo.verification_report.verification_report_id_help"),
            ),
        ),
        policy=_MODEL_READ,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_records_cli", "verification_report_show")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads", "VerificationReportShowResult"),
            identity="modelo.verification_report.view",
        ),
    ),
)

__all__ = ["MODELO_NONWORK_VERIFICATION_REPORT_COMMAND_SPECS"]
