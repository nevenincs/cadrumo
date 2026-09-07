"""Authored CommandSpec declarations for the Modelo non-work work amend family."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._modelo_nonwork_command_spec_policies import _INTERACTIVE_MODEL_WRITE
from ._modelo_work_command_specs import _ADDRESS, _LANGUAGE, _a, _o
from .command_spec import (
    CommandNodeKind,
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    TuiCapability,
)

MODELO_NONWORK_WORK_AMEND_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_modelo_work_amend_wizard",
        parent_key="app_modelo_work",
        token="amend-wizard",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.work.amend_wizard_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _a("work_unit_id"),
            *_ADDRESS,
            _o("actor", "--by"),
            _o("output_language_opt", "--output-language", _LANGUAGE, help_name="output_language"),
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
        tui_capability=TuiCapability.NOT_IMPLEMENTED,
    ),
)

__all__ = ["MODELO_NONWORK_WORK_AMEND_COMMAND_SPECS"]
