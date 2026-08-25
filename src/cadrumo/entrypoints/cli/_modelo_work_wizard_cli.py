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
from uuid import uuid4

import typer
from pydantic import BaseModel, ValidationError

from ...adapters.inbound.tui import select_flow_frontend
from ...application.flows import (
    CopyRef,
    FlowDefinition,
    FlowPage,
    FlowRunAbandonedError,
    FlowSection,
    LineFlowFrontend,
    detect_frontend_capability,
    register_copy_source,
)
from ...application.modelo import (
    CalculationRegistryUnavailableError,
    Modelo100BorradorBindingError,
    ModeloIvaWalletReconciliationBlocked,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    calculate_modelo_work_revision,
    profile_resolvable_binding_ids,
    registry_bindings_for_scope,
    registry_casillas_for_registry_scope,
)
from ...core import STRICT_FROZEN_CONFIG
from ...core.external_constants import OutputLanguage
from ...core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from ...core.i18n import tr
from ...core.json_contract import Notice
from ...domain.calculations.registry import InputKind, RegistrySnapshotError, RegistryValidationError
from ...domain.user_profile import ProfileNotFoundError
from ._common import activate_subcommand_output_language
from ._errors import CliOutboundPayloadBoundaryError
from ._modelo_behavior_support import require_active_profile, resolve_work_unit_for_cli
from ._modelo_cli_support import (
    MISSING_INPUT_TRANSLATED_MESSAGES,
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
from ._modelo_work_wizard_payloads import WizardPromptChannel, WizardPromptedCasillaPayload, WorkWizardResult

if TYPE_CHECKING:
    from ...application.modelo import ModeloWorkCalculationServiceResult
    from ...domain.modelos import WorkUnit


class _ModeloWizardAnswers(BaseModel):
    """Empty typed shell: the wizard reads answers off the flow state directly."""

    model_config = STRICT_FROZEN_CONFIG


_COPY_NAMESPACE = "modelo-work"
_ACTIVE_RUNS: dict[str, dict[str, str]] = {}
"Per-run registry-derived copy tables, keyed by an opaque run token.\n\nEach wizard invocation owns one table for its whole lifetime. Every\nreference embeds its run token (``modelo-work:<run-token>:<step-key>:<facet>``),\nso the registered resolver reads only the addressed run's table: two\ninterleaved runs in one embedding process never clear each other's entries,\nand each table is dropped at its own run end rather than accumulating for the\nprocess lifetime. Values are the registry snapshot's localized labels and\nhelp; the resolver returns ``None`` outside the namespace so other domains'\nschema-field resolvers get their turn.\n"


def _resolve_modelo_wizard_copy(ref: str) -> str | None:
    prefix = f"{_COPY_NAMESPACE}:"
    if not ref.startswith(prefix):
        return None
    run_token, _, _ = ref[len(prefix) :].partition(":")
    table = _ACTIVE_RUNS.get(run_token)
    return table.get(ref) if table is not None else None


register_copy_source(CopyRefKind.SCHEMA_FIELD, _resolve_modelo_wizard_copy)


def _copy_ref_id(run_token: str, step: _WizardStep, facet: str) -> str:
    return f"{_COPY_NAMESPACE}:{run_token}:{_page_key(step)}:{facet}"


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


@dataclass(frozen=True, slots=True)
class _WizardStep:
    """One outstanding question the wizard asks, resolved to a CLI input channel."""

    channel: WizardPromptChannel
    key: str
    casilla_id: str
    number: str
    label: str
    help_text: str | None
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


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
        steps = _outstanding_wizard_steps(unit)
    except RegistrySnapshotError as exc:
        raise deps.bad_parameter_from_error(exc) from exc
    run_token = uuid4().hex
    _ACTIVE_RUNS[run_token] = {}
    try:
        _drive_wizard_calculation(deps=deps, ctx=ctx, unit=unit, steps=steps, actor=actor, run_token=run_token)
    finally:
        _ACTIVE_RUNS.pop(run_token, None)


def _drive_wizard_calculation(
    *,
    deps: _WizardDeps,
    ctx: typer.Context,
    unit: WorkUnit,
    steps: tuple[_WizardStep, ...],
    actor: str | None,
    run_token: str,
) -> None:
    resolved_actor = deps.resolve_actor_option(actor)
    prompted = list(_run_wizard_steps(steps, run_token=run_token))
    for _attempt in range(_MAX_MISSING_INPUT_RETRIES):
        calculation_result = _run_wizard_calculation_attempt(
            deps=deps, unit=unit, actor=resolved_actor, prompted=prompted, run_token=run_token
        )
        if calculation_result is None:
            continue
        _emit_wizard_result(ctx, calculation_result, tuple(prompted))
        return
    raise typer.BadParameter(
        tr(
            "cli.app.modelo.work.wizard_retry_exhausted",
            default="The wizard could not resolve every calculation input after {limit} follow-up prompts.",
            limit=_MAX_MISSING_INPUT_RETRIES,
        )
    )


def _wizard_calculation_inputs(unit: WorkUnit, prompted: list[tuple[_WizardStep, str]]) -> Any:
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
    *, deps: _WizardDeps, unit: WorkUnit, actor: str, prompted: list[tuple[_WizardStep, str]], run_token: str
) -> ModeloWorkCalculationServiceResult | None:
    calculation_inputs = _wizard_calculation_inputs(unit, prompted)
    try:
        return calculate_modelo_work_revision(work_unit_id=unit.work_unit_id, actor=actor, inputs=calculation_inputs)
    except RegistryValidationError as exc:
        follow_up = _follow_up_step_for_missing_input(exc, unit=unit)
        if follow_up is None:
            raise deps.bad_parameter_from_error(exc) from exc
        prompted.extend(_run_wizard_steps((follow_up,), run_token=run_token))
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


_WIZARD_PROMPTABLE_BINDING_SOURCES: frozenset[str] = frozenset({"manual_input", "profile"})


def _outstanding_wizard_steps(unit: WorkUnit) -> tuple[_WizardStep, ...]:
    """Return every outstanding manual casilla / binding / relation to prompt for.

    Two registry discovery surfaces feed the wizard's question set, the same
    two an operator would otherwise consult by hand before running
    ``work calculate``:

    * ``registry_casillas_for_registry_scope(input_kind=InputKind.MANUAL)`` —
      casillas the registry declares as operator-entered (never ledger-bound,
      never formula-computed).
    * ``registry_bindings_for_scope`` filtered to the rows whose ``source``
      is in :data:`_WIZARD_PROMPTABLE_BINDING_SOURCES` and that the profile
      does not already resolve, plus every row fed by one or more registry
      relations (asked through the ``relation`` channel,
      ``--relation RELATION_ID=VALUE``, regardless of the row's own
      ``source`` — the relation is what actually needs the value).

    Ledger-bound and computed casillas, and every self-resolving binding
    source (ledger aggregation, ``previous_filing``, pre-mesh decisions),
    are deliberately excluded: they are already populated by the ledger
    auto-derivation or the registry engine on the shared calculation path,
    exactly as a bare ``work calculate`` run would populate them. Prompting
    for one of them would either be redundant (the value is already known)
    or actively wrong (a caller override is a hard refusal for a
    ledger-aggregation binding).
    """
    casillas_report = registry_casillas_for_registry_scope(
        str(unit.modelo), filing_year=unit.filing_year, period=unit.period.registry_token, input_kind=InputKind.MANUAL
    )
    casilla_steps = tuple(
        _WizardStep(
            channel="casilla",
            key=row.casilla_id,
            casilla_id=row.casilla_id,
            number=row.number,
            label=row.label,
            help_text=row.help_text,
            legal_refs=tuple(row.legal_refs),
            source_refs=tuple(row.source_refs),
        )
        for row in casillas_report.rows
    )
    bindings_report = registry_bindings_for_scope(str(unit.modelo), period=unit.period)
    profile_resolved = _profile_resolved_binding_ids(unit)
    binding_steps: list[_WizardStep] = []
    for row in bindings_report.rows:
        if not getattr(row, "operator_input_required", True):
            continue
        if row.relation_inputs:
            for relation_id in row.relation_inputs:
                binding_steps.append(
                    _WizardStep(
                        channel="relation",
                        key=str(relation_id),
                        casilla_id=str(row.binding_id),
                        number=str(row.binding_id),
                        label=str(row.binding_id),
                        help_text=tr(
                            "cli.app.modelo.work.wizard_relation_help",
                            binding_id=str(row.binding_id),
                            default="Fed by registry relation {binding_id}; supply the cross-period or cross-modelo value this relation carries.",
                        ),
                        legal_refs=tuple(row.legal_refs),
                        source_refs=tuple(row.source_refs),
                    )
                )
            continue
        if row.source not in _WIZARD_PROMPTABLE_BINDING_SOURCES:
            continue
        if row.binding_id in profile_resolved:
            continue
        binding_steps.append(
            _WizardStep(
                channel="binding",
                key=str(row.binding_id),
                casilla_id=str(row.binding_id),
                number=str(row.binding_id),
                label=str(row.binding_id),
                help_text=None,
                legal_refs=tuple(row.legal_refs),
                source_refs=tuple(row.source_refs),
            )
        )
    return (*casilla_steps, *tuple(binding_steps))


_MAX_MISSING_INPUT_RETRIES = 12


def _binding_grounding_lookup(unit: WorkUnit) -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """Return ``binding_id -> (legal_refs, source_refs)``, keyed by relation id too.

    A binding row's grounding is stored once and shared by every relation it
    feeds (:func:`_outstanding_wizard_steps` already does this for the
    pre-discovered relation steps), so a relation id resolves to its
    covering binding's grounding.
    """
    bindings_report = registry_bindings_for_scope(str(unit.modelo), period=unit.period)
    lookup: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    for row in bindings_report.rows:
        grounding = (tuple(row.legal_refs), tuple(row.source_refs))
        lookup[str(row.binding_id)] = grounding
        for relation_id in row.relation_inputs:
            lookup[str(relation_id)] = grounding
    return lookup


def _follow_up_step_for_missing_input(error: RegistryValidationError, *, unit: WorkUnit) -> _WizardStep | None:
    """Turn a missing-input registry refusal into one more wizard question.

    :func:`_outstanding_wizard_steps` pre-discovers every ``manual_input`` /
    unresolved-``profile`` casilla and binding, but a ``previous_filing``
    binding whose selector genuinely has no local prior filing to carry
    forward (as opposed to one the engine auto-defaults to zero
    "absent-by-design") is only detectable by attempting the calculation —
    the same discovery an operator makes by running ``work calculate`` and
    reading its refusal. Returns ``None`` for any registry-validation error
    that is not a recognised missing-input shape, so the caller re-raises
    the original refusal unchanged rather than looping on an unrelated
    error.

    The follow-up step's grounding is looked up from the same registry
    bindings report :func:`_outstanding_wizard_steps` reads, rather than left
    empty, so a wizard retry prompt carries the same ``legal_refs`` /
    ``source_refs`` parity every pre-discovered step already does.
    """
    if error.translated_message not in MISSING_INPUT_TRANSLATED_MESSAGES:
        return None
    context = error.context or {}
    grounding_lookup = _binding_grounding_lookup(unit)
    if error.translated_message == "errors.calc.relation_value_missing":
        relation_id = context.get("relation_id")
        if not isinstance(relation_id, str):
            return None
        legal_refs, source_refs = grounding_lookup.get(relation_id, ((), ()))
        return _WizardStep(
            channel="relation",
            key=relation_id,
            casilla_id=relation_id,
            number=relation_id,
            label=relation_id,
            help_text=tr(
                "cli.app.modelo.work.wizard_relation_help",
                binding_id=relation_id,
                default="Fed by registry relation {binding_id}; supply the cross-period or cross-modelo value this relation carries.",
            ),
            legal_refs=legal_refs,
            source_refs=source_refs,
        )
    binding_id = context.get("binding_id")
    if not isinstance(binding_id, str):
        return None
    legal_refs, source_refs = grounding_lookup.get(binding_id, ((), ()))
    return _WizardStep(
        channel="binding",
        key=binding_id,
        casilla_id=binding_id,
        number=binding_id,
        label=binding_id,
        help_text=None,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _profile_resolved_binding_ids(unit: WorkUnit) -> frozenset[str]:
    from ...core import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return frozenset[str]()
    try:
        return _text_frozenset(
            profile_resolvable_binding_ids(
                modelo=str(unit.modelo), bucket_id=bucket_id, filing_year=unit.filing_year, period=unit.period
            )
        )
    except (RegistrySnapshotError, RegistryValidationError, ProfileNotFoundError):
        return frozenset[str]()


def _text_frozenset(value: object) -> frozenset[str]:
    """Validate the application binding-id collection at the CLI boundary."""
    if not isinstance(value, (set, frozenset, tuple, list)):
        raise TypeError("binding-id projection must be a collection")
    values: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise TypeError("binding-id projection must contain text")
        values.add(item)
    return frozenset(values)


def _page_key(step: _WizardStep) -> str:
    return f"{step.channel}:{step.key}"


def _definition_from_steps(steps: tuple[_WizardStep, ...], *, run_token: str) -> FlowDefinition:
    """Project the discovered registry steps into a one-section flow definition.

    Each step becomes a free-text page whose prompt and help are
    schema-field references into the addressed run's copy table this
    module's registered resolver serves; the rendered strings are the
    registry snapshot's localized labels, so the definition itself carries
    no prose. Every reference embeds ``run_token`` so the run owns its
    entries; follow-up single-question rounds append to the same run
    table.
    """
    table = _ACTIVE_RUNS[run_token]
    pages: list[FlowPage] = []
    for step in steps:
        prompt_ref = _copy_ref_id(run_token, step, "prompt")
        table[prompt_ref] = tr(
            "cli.app.modelo.work.wizard_prompt",
            number=step.number,
            label=step.label,
            default="Casilla {number} ({label})",
        )
        help_ref: str | None = None
        if step.help_text:
            help_ref = _copy_ref_id(run_token, step, "help")
            table[help_ref] = step.help_text
        pages.append(
            FlowPage(
                id=_page_key(step),
                widget=FlowWidgetKind.TEXT,
                prompt=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=prompt_ref),
                help=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=help_ref) if help_ref else None,
                required=False,
                answer_type=str,
            )
        )
    help_key = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="cli.app.modelo.work.wizard_help")
    return FlowDefinition(
        id="modelo-work-wizard",
        title=help_key,
        description=help_key,
        sections=(FlowSection(id="manual-inputs", title=help_key, items=tuple(pages)),),
        answers_model=_ModeloWizardAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


def _run_wizard_steps(steps: tuple[_WizardStep, ...], *, run_token: str) -> tuple[tuple[_WizardStep, str], ...]:
    """Walk the outstanding steps through the interactive flow frontend.

    The frontend is the full-screen Textual app where the host can host
    it, degrading to the line-mode frontend where it cannot; the choice is
    the shared :func:`select_flow_frontend` primitive over
    :func:`detect_frontend_capability`, so every consumer selects in one
    place. A work unit with no outstanding manual input needs no
    interactive console at all — nothing is constructed for an empty step
    set, so a ``--format json`` scripted caller with nothing left to fill
    in never hits the non-interactive refusal. Values are read back off the
    engine state per page key; a page the operator left blank reads as the
    empty string, exactly as the one-shot prompt did.
    """
    if not steps:
        return ()
    definition = _definition_from_steps(steps, run_token=run_token)
    frontend = select_flow_frontend(definition, mode=FlowMode.CREATE, capability=detect_frontend_capability())
    if isinstance(frontend, LineFlowFrontend):
        state, _projection = frontend.run(mode=FlowMode.CREATE)
    else:
        frontend.run()
        if frontend.final_state is None:
            raise FlowRunAbandonedError(
                translated_message="errors.refused.refused_flow_run_abandoned", context={"flow_id": definition.id}
            )
        state = frontend.final_state
    return tuple((step, (state.answers.get(_page_key(step)) or "").strip()) for step in steps)


def _emit_wizard_result(
    ctx: typer.Context,
    calculation_result: ModeloWorkCalculationServiceResult,
    prompted: tuple[tuple[_WizardStep, str], ...],
) -> None:
    from ._common import _emit_envelope

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
    _emit_envelope(ctx, command="modelo.work.wizard", result=result, lines=lines, notices=notices or None)


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
