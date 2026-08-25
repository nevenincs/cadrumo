"""Authored CommandSpec declarations for the Modelo non-work work amend family."""

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
    TuiCapability,
    ValueContract,
)
from ._modelo_nonwork_command_spec_policies import _INTERACTIVE_MODEL_WRITE

MODELO_NONWORK_WORK_AMEND_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_modelo_work_amend_wizard",
        parent_key="app_modelo_work",
        token="amend-wizard",
        kind="leaf",
        help_key=TranslationKey("cli.app.modelo.work.amend_wizard_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="work_unit_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.work.work_unit_id_help"),
            ),
            OptionSpec(
                name="modelo",
                declarations=("--modelo",),
                value=ValueContract(
                    DeferredTarget("builtins", "str"),
                    click_type=DeferredTarget("cadrumo.entrypoints.cli._common", "MODELO_CODE_CHOICE"),
                ),
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
            OptionSpec(
                name="output_language_opt",
                declarations=("--output-language",),
                value=ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.work.output_language_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
        ),
        policy=_INTERACTIVE_MODEL_WRITE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_amend_wizard_cli", "work_amend_wizard")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_amend_wizard_payloads", "WorkAmendWizardResult"),
            identity="modelo.work.amend_wizard",
        ),
        tui_capability=TuiCapability.AVAILABLE,
    ),
)

__all__ = ["MODELO_NONWORK_WORK_AMEND_COMMAND_SPECS"]
