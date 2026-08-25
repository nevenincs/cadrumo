"""Authored CommandSpec declarations for the Modelo non-work work preview family."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._command_spec import (
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
from ._modelo_nonwork_command_spec_policies import _CALCULATION_READ

MODELO_NONWORK_WORK_PREVIEW_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_modelo_work_preview_maritime_exemption",
        parent_key="app_modelo_work",
        token="preview-maritime-exemption",
        kind="leaf",
        help_key=TranslationKey("cli.app.modelo.work.preview_maritime_exemption_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="annual_salary",
                declarations=("--annual-salary",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.work.preview_maritime_exemption_annual_salary_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
            OptionSpec(
                name="qualifying_days",
                declarations=("--qualifying-days",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.work.preview_maritime_exemption_qualifying_days_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(minimum=1, maximum=365),
            ),
            OptionSpec(
                name="gross_navigation_income",
                declarations=("--gross-navigation-income",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.work.preview_maritime_exemption_gross_navigation_income_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
            OptionSpec(
                name="output_language",
                declarations=("--output-language",),
                value=ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage")),
                default=ParameterDefault.value(None),
                help_key=None,
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
        ),
        policy=_CALCULATION_READ,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_maritime_cli", "work_preview_maritime_exemption")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads", "WorkPreviewMaritimeExemptionResult"),
            identity="modelo.work.preview_maritime_exemption",
        ),
    ),
)

__all__ = ["MODELO_NONWORK_WORK_PREVIEW_COMMAND_SPECS"]
