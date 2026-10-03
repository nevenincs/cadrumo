"""Guided Modelo inputs over authenticated worker discovery and calculation."""

from __future__ import annotations

from uuid import UUID

import typer
from pydantic import ValidationError

from ...application.flows.errors import FlowError
from ...application.flows.line_frontend import LineFlowFrontend
from ...application.modelo.action_errors import modelo_work_wizard_retry_exhausted_precondition
from ...application.modelo.calculation_request_fields import ModeloCalculationInputFieldsV1, ModeloCalculationOverride
from ...application.modelo.wizard_attempt_operation import (
    ModeloWorkWizardAttemptCalculated,
    ModeloWorkWizardAttemptRequest,
)
from ...application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateCallerContext,
    ModeloWorkCalculatePublicResultV2,
    ModeloWorkCalculateRequest,
)
from ...application.modelo.work_wizard import (
    ModeloWorkWizardRun,
    ModeloWorkWizardStep,
    open_modelo_work_wizard_from_steps,
)
from ...core.external_constants import OutputLanguage
from ...core.flows import FlowMode
from ...core.i18n.render import output_language as current_output_language
from ...core.i18n.render import tr
from ...core.json_contract import Notice
from ...core.operations import OperationTerminalCondition
from ._modelo_cli_support import resolve_actor_option
from ._modelo_rendering import source_diagnostic_notice, source_diagnostic_notice_text
from ._modelo_work_wizard_payloads import WizardPromptedCasillaPayload, WorkWizardResult
from .common import activate_subcommand_output_language, attach_cli_policy_verdict, emit_envelope
from .errors import CliRefusedBoundaryError
from .registered_operation_errors import invalid_completion_error
from .runtime_modelo_calculation import calculation_snapshot_lines, calculation_snapshot_payload
from .runtime_modelo_metadata import read_modelo_work_unit
from .runtime_modelo_work_wizard import read_modelo_work_wizard_context, run_modelo_work_wizard_attempt

_MAX_MISSING_INPUT_RETRIES = 12


def _run_wizard_steps(
    wizard: ModeloWorkWizardRun, steps: tuple[ModeloWorkWizardStep, ...]
) -> tuple[tuple[ModeloWorkWizardStep, str], ...]:
    """Use the canonical flow; an empty prompt set needs no interactive terminal."""
    if not steps:
        return ()
    state, _projection = LineFlowFrontend(wizard.definition_for(steps)).run(mode=FlowMode.CREATE)
    return wizard.answer_pairs(state, steps=steps)


def _wizard_calculation_inputs(prompted: list[tuple[ModeloWorkWizardStep, str]]) -> ModeloCalculationInputFieldsV1:
    """Carry operator text unchanged to the worker's canonical input validator."""
    answers = {(step.channel, step.key): value for step, value in prompted}
    return ModeloCalculationInputFieldsV1(
        casilla_overrides=tuple(
            ModeloCalculationOverride(key=key, value=value)
            for (channel, key), value in answers.items()
            if channel == "casilla"
        ),
        binding_overrides=tuple(
            ModeloCalculationOverride(key=key, value=value)
            for (channel, key), value in answers.items()
            if channel == "binding"
        ),
        relation_overrides=tuple(
            ModeloCalculationOverride(key=key, value=value)
            for (channel, key), value in answers.items()
            if channel == "relation"
        ),
    )


def _drive_wizard_calculation(
    *, ctx: typer.Context, wizard: ModeloWorkWizardRun, actor: str | None, language: OutputLanguage
) -> None:
    resolved_actor = resolve_actor_option(actor)
    prompted = list(_run_wizard_steps(wizard, wizard.steps))
    for attempt in range(_MAX_MISSING_INPUT_RETRIES):
        completed = run_modelo_work_wizard_attempt(
            ctx,
            ModeloWorkWizardAttemptRequest(
                profile_id=UUID(wizard.unit.bucket_id),
                output_language=language,
                calculation=ModeloWorkCalculateRequest(
                    work_unit_id=wizard.unit.work_unit_id,
                    actor=resolved_actor,
                    caller_context=ModeloWorkCalculateCallerContext.EXPLICIT,
                    inputs=_wizard_calculation_inputs(prompted),
                ),
            ),
        )
        outcome = completed.projection.outcome
        if isinstance(outcome, ModeloWorkWizardAttemptCalculated):
            try:
                _emit_wizard_result(ctx, outcome.result, tuple(prompted), language=language)
            except ValidationError as error:
                raise invalid_completion_error(completed) from error
            return
        if attempt + 1 == _MAX_MISSING_INPUT_RETRIES:
            failure = modelo_work_wizard_retry_exhausted_precondition(
                work_unit_id=wizard.unit.work_unit_id, retry_limit=_MAX_MISSING_INPUT_RETRIES
            )
            raise attach_cli_policy_verdict(
                CliRefusedBoundaryError(
                    tr("cli.app.modelo.work.wizard_retry_exhausted", limit=_MAX_MISSING_INPUT_RETRIES),
                    context={
                        "operation_id": completed.operation_id,
                        "effect": completed.effect.value,
                        "terminal_condition": "succeeded",
                    },
                ),
                verdict=failure.verdict,
            )
        # Only a completed typed prepublication outcome permits another answer.
        # Transport uncertainty and later calculation errors propagate unchanged.
        try:
            prompted.extend(_run_wizard_steps(wizard, (outcome.step,)))
        except FlowError as error:
            error.context = {
                **(error.context or {}),
                "operation_id": completed.operation_id,
                "effect": completed.effect.value,
                "terminal_condition": OperationTerminalCondition.SUCCEEDED.value,
            }
            raise


def _emit_wizard_result(
    ctx: typer.Context,
    calculation_result: ModeloWorkCalculatePublicResultV2,
    prompted: tuple[tuple[ModeloWorkWizardStep, str], ...],
    *,
    language: OutputLanguage,
) -> None:
    snapshot = calculation_result.calculation
    saved_confirmation = tr(
        "cli.app.modelo.work.wizard_saved",
        revision_id=snapshot.calculation_revision_id,
        state=snapshot.state.value,
    )
    prompted_payload = tuple(
        WizardPromptedCasillaPayload(
            casilla_id=step.casilla_id,
            number=step.number,
            label=step.label,
            channel=step.channel,
            key=step.key,
            value=value,
            legal_refs=step.legal_refs,
            source_refs=step.source_refs,
            help_text=step.help_text,
        )
        for step, value in prompted
    )
    result = WorkWizardResult.model_validate(
        {
            "saved": True,
            "saved_confirmation": saved_confirmation,
            **calculation_snapshot_payload(snapshot, language=language).model_dump(mode="python"),
            "prompted_casillas": prompted_payload,
        }
    )
    lines = [
        "operation\tmodelo.work.wizard",
        *calculation_snapshot_lines(snapshot, language=language),
        *(f"prompted\t{step.number}\t{step.channel}\t{value}" for step, value in prompted),
        saved_confirmation,
    ]
    advisories = calculation_result.advisories
    notices: list[Notice] = [
        source_diagnostic_notice(
            diagnostic, code="modelo.work.wizard.source_advisory", boxes=advisories.to_printed_boxes()
        )
        for diagnostic in advisories.to_diagnostics()
    ]
    lines.extend(source_diagnostic_notice_text(notice) for notice in notices)
    emit_envelope(ctx, command="modelo.work.wizard", result=result, lines=lines, notices=notices or None)


def work_wizard(
    ctx: typer.Context,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    actor: str | None = None,
    output_language_opt: OutputLanguage | None = None,
) -> None:
    """Prompt for authenticated missing inputs and calculate in bound worker custody."""
    activate_subcommand_output_language(ctx, output_language_opt)
    selected = read_modelo_work_unit(
        ctx,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    language = OutputLanguage(current_output_language())
    discovered = read_modelo_work_wizard_context(
        ctx,
        profile_id=UUID(selected.bucket_id),
        work_unit_id=selected.work_unit_id,
        output_language=language,
    )
    with open_modelo_work_wizard_from_steps(discovered.unit.to_work_unit(), steps=discovered.steps) as wizard:
        _drive_wizard_calculation(ctx=ctx, wizard=wizard, actor=actor, language=language)


__all__ = ["work_wizard"]
