# ruff: noqa: E501
"""Behavior for the guided Modelo work wizard command.

An operator knows "gross income" and "deductible expenses" in plain language, not
that Modelo 130 casilla ``06`` is "Retenciones e ingresos a cuenta". The
wizard walks a work unit's *outstanding* manual-input surface —
``input_kind = "manual"`` casillas plus any binding or relation the registry
still needs (the same set the canonical bindings discovery action
surfaces) — one question at a time, showing each item's official label, help
text, and legal grounding before asking for a value. Every value the operator
confirms then flows through the exact same
:func:`~application.modelo.calculate_modelo_work_revision` composition
path that the canonical calculation action uses (via
:func:`~._modelo_cli_support.work_calculate_input_bundle_from_cli`); the
wizard is a guided front end over that one calculation path, not a second one
(``aeat-architecture-boundaries``).

Ledger-bound and computed casillas are never prompted: the ledger
auto-derivation (``aeat-calculation-aggregation``) and the
registry formula engine already populate them, exactly as a bare
``work calculate`` would. The wizard's job is only the residual manual
surface a bare calculate call would otherwise reject with a bindings-missing
refusal.

A real interactive terminal is required: the prompting is the flow
substrate's line-mode frontend
(:class:`~cadrumo.application.flows.LineFlowFrontend`) over the one flow
engine, so the non-TTY / Windows-no-console detection and the translated
refusal are the substrate's single implementation rather than a
re-derived copy of it, and the operator gets the engine's review surface
(re-edit by number, restart, submit) before any value is committed.

The prompt *copy* comes from the resolved registry snapshot — a casilla
number and label, not a static translation-catalogue key — so each
discovered question is projected into a :class:`FlowDefinition` page
whose copy slots are schema-field references resolved by this module's
registered copy source against the per-run registry-derived table. The
definition carries references only; the registry stays the copy
authority.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import typer
from pydantic import ValidationError

from ...application.flows import (
    LineFlowFrontend,
)
from ...application.modelo import (
    CalculationRegistryUnavailableError,
    Modelo100BorradorBindingError,
    ModeloIvaWalletReconciliationBlocked,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    calculate_modelo_work_revision,
    modelo_work_wizard_retry_exhausted_precondition,
)
from ...application.modelo.work_wizard import (
    ModeloWorkWizardRun,
    ModeloWorkWizardStep,
    modelo_work_wizard_follow_up_step,
    open_modelo_work_wizard,
)
from ...core.external_constants import OutputLanguage
from ...core.flows import FlowMode
from ...core.i18n import tr
from ...core.json_contract import Notice
from ...domain.calculations.registry import RegistrySnapshotError, RegistryValidationError
from ._common import activate_subcommand_output_language, attach_cli_policy_verdict, emit_envelope
from ._errors import CliOutboundPayloadBoundaryError, CliRefusedBoundaryError
from ._modelo_behavior_support import require_active_profile, resolve_work_unit_for_cli
from ._modelo_cli_support import (
    bad_parameter_from_error,
    resolve_actor_option,
    work_calculate_input_bundle_from_cli,
)
from ._modelo_rendering import (
    calculation_revision_lines,
    calculation_revision_payload,
    source_diagnostic_notice,
    source_diagnostic_notice_text,
)
from ._modelo_work_wizard_payloads import WizardPromptedCasillaPayload, WorkWizardResult

if TYPE_CHECKING:
    from ...application.modelo import ModeloWorkCalculationServiceResult
    from ...domain.modelos import WorkUnit


@dataclass(frozen=True, slots=True)
class _WizardDeps:
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None]
    require_active_profile: Callable[[], None]
    resolve_work_unit_for_cli: Callable[..., Any]
    resolve_actor_option: Callable[[str | None], str]
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter]


def _wizard_dependencies() -> _WizardDeps:
    return _WizardDeps(
        activate_output_language=activate_subcommand_output_language,
        require_active_profile=require_active_profile,
        resolve_work_unit_for_cli=resolve_work_unit_for_cli,
        resolve_actor_option=resolve_actor_option,
        bad_parameter_from_error=bad_parameter_from_error,
    )


def run_modelo_work_wizard(
    *,
    deps: _WizardDeps,
    ctx: typer.Context,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
    actor: str | None,
    output_language_opt: OutputLanguage | None,
) -> None:
    deps.activate_output_language(ctx, output_language_opt)
    deps.require_active_profile()
    unit = deps.resolve_work_unit_for_cli(
        work_unit_id=work_unit_id, modelo=modelo, year=year, period=period, revision=revision, bucket_id=bucket_id
    )
    try:
        with open_modelo_work_wizard(unit) as wizard:
            _drive_wizard_calculation(deps=deps, ctx=ctx, wizard=wizard, actor=actor)
    except RegistrySnapshotError as exc:
        raise deps.bad_parameter_from_error(exc) from exc


def _drive_wizard_calculation(
    *,
    deps: _WizardDeps,
    ctx: typer.Context,
    wizard: ModeloWorkWizardRun,
    actor: str | None,
) -> None:
    resolved_actor = deps.resolve_actor_option(actor)
    prompted = list(_run_wizard_steps(wizard, wizard.steps))
    for _attempt in range(_MAX_MISSING_INPUT_RETRIES):
        calculation_result = _run_wizard_calculation_attempt(
            deps=deps,
            wizard=wizard,
            actor=resolved_actor,
            prompted=prompted,
        )
        if calculation_result is None:
            continue
        _emit_wizard_result(ctx, calculation_result, tuple(prompted))
        return
    failure = modelo_work_wizard_retry_exhausted_precondition(
        work_unit_id=wizard.unit.work_unit_id,
        retry_limit=_MAX_MISSING_INPUT_RETRIES,
    )
    raise attach_cli_policy_verdict(
        CliRefusedBoundaryError(
            tr(
                "cli.app.modelo.work.wizard_retry_exhausted",
                default="The wizard could not resolve every calculation input after {limit} follow-up prompts.",
                limit=_MAX_MISSING_INPUT_RETRIES,
            )
        ),
        verdict=failure.verdict,
    )


def _wizard_calculation_inputs(unit: WorkUnit, prompted: list[tuple[ModeloWorkWizardStep, str]]) -> Any:
    casilla_overrides = [f"{step.key}={value}" for step, value in prompted if step.channel == "casilla"]
    binding_overrides = [f"{step.key}={value}" for step, value in prompted if step.channel == "binding"]
    relation_overrides = [f"{step.key}={value}" for step, value in prompted if step.channel == "relation"]
    return work_calculate_input_bundle_from_cli(
        work_unit_id=unit.work_unit_id,
        casilla=casilla_overrides or None,
        binding=binding_overrides or None,
        relation=relation_overrides or None,
        row=None,
        borrador_snapshot_id=None,
        prestacion_inss_exenta=None,
        rescate_plan_pensiones_capital=None,
        rescate_plan_pensiones_aportaciones_pre_2007=None,
        rescate_plan_pensiones_aportaciones_totales=None,
        sal_beneficio_neto=None,
        sal_reserva_dotada=None,
        sal_capital_social=None,
        autoconsumo_promotor_base=None,
    )


def _run_wizard_calculation_attempt(
    *,
    deps: _WizardDeps,
    wizard: ModeloWorkWizardRun,
    actor: str,
    prompted: list[tuple[ModeloWorkWizardStep, str]],
) -> ModeloWorkCalculationServiceResult | None:
    calculation_inputs = _wizard_calculation_inputs(wizard.unit, prompted)
    try:
        return calculate_modelo_work_revision(
            work_unit_id=wizard.unit.work_unit_id, actor=actor, inputs=calculation_inputs
        )
    except RegistryValidationError as exc:
        follow_up = modelo_work_wizard_follow_up_step(exc, unit=wizard.unit)
        if follow_up is None:
            raise deps.bad_parameter_from_error(exc) from exc
        prompted.extend(_run_wizard_steps(wizard, (follow_up,)))
        return None
    except WorkUnitMutationRefusedError:
        raise
    except (
        WorkUnitNotFoundError,
        CalculationRegistryUnavailableError,
        Modelo100BorradorBindingError,
        ModeloIvaWalletReconciliationBlocked,
    ) as exc:
        raise deps.bad_parameter_from_error(exc) from exc
    except ValidationError as exc:
        raise CliOutboundPayloadBoundaryError(exc) from exc


_MAX_MISSING_INPUT_RETRIES = 12


def _run_wizard_steps(
    wizard: ModeloWorkWizardRun,
    steps: tuple[ModeloWorkWizardStep, ...],
) -> tuple[tuple[ModeloWorkWizardStep, str], ...]:
    """Walk the outstanding steps through the interactive flow frontend.

    A work unit with no outstanding manual input needs no
    interactive console at all — nothing is constructed for an empty step
    set, so a ``--format json`` scripted caller with nothing left to fill
    in never hits the non-interactive refusal. Values are read back off the
    engine state per page key; a page the operator left blank reads as the
    empty string, exactly as the one-shot prompt did.
    """
    if not steps:
        return ()
    definition = wizard.definition_for(steps)
    state, _projection = LineFlowFrontend(definition).run(mode=FlowMode.CREATE)
    return wizard.answer_pairs(state, steps=steps)


def _emit_wizard_result(
    ctx: typer.Context,
    calculation_result: ModeloWorkCalculationServiceResult,
    prompted: tuple[tuple[ModeloWorkWizardStep, str], ...],
) -> None:
    calculation_revision = calculation_result.revision
    saved_confirmation = tr(
        "cli.app.modelo.work.wizard_saved",
        default="Saved as draft calculation revision %{revision_id} (state: %{state}). It is persisted and can be resumed later.",
        revision_id=calculation_revision.calculation_revision_id,
        state=calculation_revision.state.value,
    )
    prompted_payload = tuple(
        (
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
    )
    result = WorkWizardResult.model_validate(
        {
            "saved": True,
            "saved_confirmation": saved_confirmation,
            **calculation_revision_payload(calculation_revision).model_dump(
                mode="python",
                exclude={"source_provenance"},
            ),
            "prompted_casillas": prompted_payload,
        }
    )
    lines = [
        "operation\tmodelo.work.wizard",
        *calculation_revision_lines(calculation_revision),
        *(f"prompted\t{step.number}\t{step.channel}\t{value}" for step, value in prompted),
        saved_confirmation,
    ]
    notices: list[Notice] = []
    diagnostics = calculation_result.source_diagnostics
    if diagnostics:
        notices.extend(
            source_diagnostic_notice(diagnostic, code="modelo.work.wizard.source_advisory")
            for diagnostic in diagnostics
        )
        lines.extend(source_diagnostic_notice_text(notice) for notice in notices)
    emit_envelope(ctx, command="modelo.work.wizard", result=result, lines=lines, notices=notices or None)


__all__ = ["work_wizard"]


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
    """Walk the resolved work unit's outstanding manual inputs one at a time.

    Resolves (or reuses) a work unit exactly as ``work create`` does,
    lists its outstanding manual casillas and missing bindings/relations
    through the same registry discovery surface as
    ``bindings list --missing``, prompts for each one in turn (showing
    its official label, help text, and legal grounding), then calls
    :func:`calculate_modelo_work_revision` through the identical input
    bundle ``work calculate`` builds.
    """
    run_modelo_work_wizard(
        deps=_wizard_dependencies(),
        ctx=ctx,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        actor=actor,
        output_language_opt=output_language_opt,
    )
