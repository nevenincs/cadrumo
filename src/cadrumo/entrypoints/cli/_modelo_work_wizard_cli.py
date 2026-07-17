"""Typer registration for the guided ``aeat app modelo work wizard`` command.

An operator knows "gross income" and "deductible expenses" in plain language, not
that Modelo 130 casilla ``06`` is "Retenciones e ingresos a cuenta". The
wizard walks a work unit's *outstanding* manual-input surface —
``input_kind = "manual"`` casillas plus any binding or relation the registry
still needs (the same set ``aeat app modelo bindings list --missing``
surfaces) — one question at a time, showing each item's official label, help
text, and legal grounding before asking for a value. Every value the operator
confirms then flows through the exact same
:func:`~application.modelo.calculate_modelo_work_revision` composition
path that ``aeat app modelo work calculate`` uses (via
:func:`~._modelo_cli_support.work_calculate_input_bundle_from_cli`); the
wizard is a guided front end over that one calculation path, not a second one
(``composition-service-no-parallel-write-path``).

Ledger-bound and computed casillas are never prompted: the ledger
auto-derivation (``one-aggregation-path-pull-equals-calculate``) and the
registry formula engine already populate them, exactly as a bare
``work calculate`` would. The wizard's job is only the residual manual
surface a bare calculate call would otherwise reject with a bindings-missing
refusal.

A real interactive terminal is required:
:class:`_QuestionaryTextPrompter` reuses the exact non-TTY / Windows-no-console
detection :class:`~application.wizard.QuestionaryPrompter` applies for
the profile setup wizard, and raises the same translated
:class:`~application.wizard.WizardUnsupportedConsoleError`.
Prompt copy is dynamic
(the casilla number and label come from the resolved registry snapshot, not a
static translation-catalogue key), so this module does not reuse the wizard
package's ``WizardQuestion`` model — that model's ``prompt`` field is a static
``Translatable`` catalogue key with no interpolation support, the wrong shape
for a runtime-discovered casilla label.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any, Protocol, runtime_checkable

import typer

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
from ...application.wizard import WizardUnsupportedConsoleError
from ...core.external_constants import OutputLanguage
from ...core.i18n import output_language, tr
from ...core.json_contract import Notice
from ...domain.calculations.registry import InputKind, RegistrySnapshotError, RegistryValidationError
from ...domain.user_profile import ProfileNotFoundError
from ._modelo_cli_support import MISSING_INPUT_TRANSLATED_MESSAGES, work_calculate_input_bundle_from_cli
from ._modelo_rendering import advisory_notice, calculation_revision_lines, calculation_revision_payload
from ._modelo_work_wizard_payloads import WizardPromptedCasillaPayload, WorkWizardResult

if TYPE_CHECKING:
    from ...application.modelo import ModeloWorkCalculationServiceResult
    from ...domain.modelos import WorkUnit


@runtime_checkable
class _TextAnswerPrompter(Protocol):
    """Capability protocol for collecting one free-text answer to a dynamic prompt.

    Deliberately narrower than
    :class:`~application.wizard.Prompter`: the wizard's questions are
    always plain-text casilla/binding/relation values, and the prompt text
    itself is built from a runtime-resolved registry label rather than a
    static translation-catalogue key, so it takes an already-rendered
    ``prompt`` string rather than a
    :class:`~application.wizard._models.WizardQuestion`.
    """

    def ask_text(self, prompt: str, *, help_text: str | None) -> str: ...


class _QuestionaryTextPrompter:
    """Production prompter: renders ``prompt`` with ``questionary.text``.

    Reuses the exact console-support detection
    :class:`~application.wizard.QuestionaryPrompter` applies (non-TTY
    stdin, Windows no-console-buffer) so a non-interactive host refuses with
    the same translated
    :class:`~application.wizard.WizardUnsupportedConsoleError`
    the profile setup wizard raises, rather than hanging or crashing with a
    raw ``questionary``/``prompt_toolkit`` traceback.
    """

    def _ensure_interactive_environment(self) -> None:
        if not sys.stdin.isatty():
            raise WizardUnsupportedConsoleError(translated_message="wizard.errors.unsupported_console")
        try:
            from prompt_toolkit.output.defaults import create_output

            output = create_output(always_prefer_tty=True)
            output.flush()
        except OSError as exc:
            raise WizardUnsupportedConsoleError(translated_message="wizard.errors.unsupported_console") from exc

    def ask_text(self, prompt: str, *, help_text: str | None) -> str:
        import questionary

        self._ensure_interactive_environment()
        if help_text:
            print(help_text)  # noqa: T201 - operator-facing wizard help line, not a debug print
        try:
            result = questionary.text(prompt, default="").ask()
        except OSError as exc:
            raise WizardUnsupportedConsoleError(translated_message="wizard.errors.unsupported_console") from exc
        if result is None:
            return ""
        return str(result)


@dataclass(frozen=True, slots=True)
class _WizardDeps:
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None]
    require_active_profile: Callable[[], None]
    resolve_work_unit_for_cli: Callable[..., Any]
    resolve_default_actor: Callable[[], str]
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter]


@dataclass(frozen=True, slots=True)
class _WizardStep:
    """One outstanding question the wizard asks, resolved to a CLI input channel."""

    channel: str  # "casilla" | "binding" | "relation"
    key: str
    casilla_id: str
    number: str
    label: str
    help_text: str | None
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


_WorkUnitIdArg = Annotated[str | None, typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help"))]
_ModeloOpt = Annotated[str | None, typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help"))]
_YearOpt = Annotated[int | None, typer.Option("--year", help=tr("cli.app.modelo.work.year_help"))]
_PeriodOpt = Annotated[str | None, typer.Option("--period", help=tr("cli.app.modelo.work.period_help"))]
_RevisionOpt = Annotated[str | None, typer.Option("--revision", help=tr("cli.app.modelo.work.revision_help"))]
_BucketIdOpt = Annotated[str | None, typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help"))]
_ActorOpt = Annotated[str | None, typer.Option("--by", help=tr("cli.app.modelo.work.actor_help"))]


# KWARGS-ANY-RATIONALE-cli: resolve_work_unit_for_cli is a CLI resolver callback injected by the command registrar
def register_work_wizard_commands(
    work_app: typer.Typer,
    *,
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None],
    require_active_profile: Callable[[], None],
    resolve_work_unit_for_cli: Callable[
        ..., Any
    ],  # KWARGS-ANY-RATIONALE-cli-callback: work-unit resolver callback injected by the command registrar
    resolve_default_actor: Callable[[], str],
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
) -> None:
    """Register the guided ``work wizard`` command on the modelo work app."""
    deps = _WizardDeps(
        activate_output_language=activate_output_language,
        require_active_profile=require_active_profile,
        resolve_work_unit_for_cli=resolve_work_unit_for_cli,
        resolve_default_actor=resolve_default_actor,
        bad_parameter_from_error=bad_parameter_from_error,
    )

    @work_app.command("wizard", help=tr("cli.app.modelo.work.wizard_help"))
    def work_wizard(
        ctx: typer.Context,
        work_unit_id: _WorkUnitIdArg = None,
        modelo: _ModeloOpt = None,
        year: _YearOpt = None,
        period: _PeriodOpt = None,
        revision: _RevisionOpt = None,
        bucket_id: _BucketIdOpt = None,
        actor: _ActorOpt = None,
        output_language_opt: Annotated[
            OutputLanguage | None,
            typer.Option("--output-language", help=tr("cli.app.modelo.work.output_language_help")),
        ] = None,
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
            deps=deps,
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
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )

    active_prompter = _QuestionaryTextPrompter()
    try:
        steps = _outstanding_wizard_steps(unit)
    except RegistrySnapshotError as exc:
        raise deps.bad_parameter_from_error(exc) from exc
    prompted = list(_run_wizard_steps(active_prompter, steps))

    for _attempt in range(_MAX_MISSING_INPUT_RETRIES):
        casilla_overrides = [f"{step.key}={value}" for step, value in prompted if step.channel == "casilla"]
        binding_overrides = [f"{step.key}={value}" for step, value in prompted if step.channel == "binding"]
        relation_overrides = [f"{step.key}={value}" for step, value in prompted if step.channel == "relation"]

        calculation_inputs = work_calculate_input_bundle_from_cli(
            work_unit_id=unit.work_unit_id,
            casilla=casilla_overrides or None,
            binding=binding_overrides or None,
            relation=relation_overrides or None,
            row=None,
            borrador_snapshot_id=None,
            prestacion_inss_exenta=None,
            meses_trabajo_con_hijo_menor_3=None,
            rescate_plan_pensiones_capital=None,
            rescate_plan_pensiones_aportaciones_pre_2007=None,
            rescate_plan_pensiones_aportaciones_totales=None,
            sal_beneficio_neto=None,
            sal_reserva_dotada=None,
            sal_capital_social=None,
            autoconsumo_promotor_base=None,
        )

        try:
            calculation_result = calculate_modelo_work_revision(
                work_unit_id=unit.work_unit_id,
                actor=actor or deps.resolve_default_actor(),
                inputs=calculation_inputs,
            )
        except RegistryValidationError as exc:
            follow_up = _follow_up_step_for_missing_input(exc)
            if follow_up is None:
                raise deps.bad_parameter_from_error(exc) from exc
            answer = _run_wizard_steps(active_prompter, (follow_up,))
            prompted.extend(answer)
            continue
        except (
            WorkUnitNotFoundError,
            WorkUnitMutationRefusedError,
            CalculationRegistryUnavailableError,
            Modelo100BorradorBindingError,
            ModeloIvaWalletReconciliationBlocked,
        ) as exc:
            raise deps.bad_parameter_from_error(exc) from exc
        else:
            _emit_wizard_result(ctx, calculation_result, tuple(prompted))
            return

    # Exhausted the retry budget: surface the last registry refusal rather
    # than looping silently. Structurally unreachable in practice (a
    # calculation converges in at most one follow-up prompt per distinct
    # unsatisfied binding/relation), kept as a defensive ceiling so a
    # pathological registry state fails loudly instead of hanging the
    # operator's terminal.
    raise typer.BadParameter(
        tr(
            "cli.app.modelo.work.wizard_retry_exhausted",
            default=(
                "The wizard could not resolve every calculation input after "
                "{limit} follow-up prompts. Run `aeat app modelo work calculate` "
                "directly and supply the remaining --binding / --relation values by hand."
            ),
            limit=_MAX_MISSING_INPUT_RETRIES,
        ),
    )


#: Binding ``source`` kinds a wizard may legitimately ask an operator to fill
#: in with a raw ``--binding KEY=VALUE`` override. Every other source kind
#: self-resolves on the shared calculation path exactly as a bare
#: ``work calculate`` resolves it, and ``_missing_binding_guidance``
#: (``_modelo.py``) refuses a caller ``--binding`` override for most of
#: them:
#:
#: * ``LEDGER_BINDING_SOURCE_KINDS`` (and the remaining aggregation-mesh
#:   sources such as ``retenciones_aggregation``) read the bucket-scoped
#:   ledger; overriding them with ``--binding`` is a hard refusal
#:   (``errors.error.error_modelo_aggregation_binding``).
#: * ``previous_filing`` resolves from a prior filed revision, or defaults to
#:   an "absent-by-design" zero when no prior period exists (the same
#:   auto-default a bare ``work calculate`` applies) — never operator-supplied.
#: * ``relation_prefill`` is supplied through ``--relation``, not
#:   ``--binding``; those rows are asked through the ``relation`` channel
#:   below, driven off each row's declared ``relation_inputs`` rather than
#:   its ``source`` value.
#: * ``constant_value`` carries a literal value; ``bindings list --missing``
#:   already excludes it and this filter mirrors that exclusion.
#: * ``borrador`` / ``iva_wallet_decision`` are pre-mesh decisions with no
#:   registry binding declaration an operator could target.
#:
#: ``manual_input`` and ``profile`` (when the profile fact is not already
#: resolvable, per :func:`_profile_resolved_binding_ids`) are the only
#: sources left that genuinely need an operator-typed value.
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
        str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period.registry_token,
        input_kind=InputKind.MANUAL,
    )
    lang = output_language()
    casilla_steps = tuple(
        _WizardStep(
            channel="casilla",
            key=row.casilla_id,
            casilla_id=row.casilla_id,
            number=row.number,
            label=row.localized_labels.get(lang, row.label),
            help_text=row.localized_help.get(lang),
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
                            default=(
                                "Fed by registry relation {binding_id}; supply the cross-period "
                                "or cross-modelo value this relation carries."
                            ),
                        ),
                        legal_refs=tuple(row.legal_refs),
                        source_refs=tuple(row.source_refs),
                    ),
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
            ),
        )
    return (*casilla_steps, *tuple(binding_steps))


#: Upper bound on missing-input follow-up prompts per wizard invocation. Each
#: retry resolves exactly one distinct unsatisfied binding/relation the
#: registry engine reports, so this is a defensive ceiling, not an expected
#: iteration count — M130 never needs more than one (the prior-year IRPF net
#: income carry, when no local Modelo 100 filing exists to auto-resolve it).
_MAX_MISSING_INPUT_RETRIES = 12


def _follow_up_step_for_missing_input(error: RegistryValidationError) -> _WizardStep | None:
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
    """
    if error.translated_message not in MISSING_INPUT_TRANSLATED_MESSAGES:
        return None
    context = error.context or {}
    if error.translated_message == "errors.calc.relation_value_missing":
        relation_id = context.get("relation_id")
        if not isinstance(relation_id, str):
            return None
        return _WizardStep(
            channel="relation",
            key=relation_id,
            casilla_id=relation_id,
            number=relation_id,
            label=relation_id,
            help_text=tr(
                "cli.app.modelo.work.wizard_relation_help",
                binding_id=relation_id,
                default=(
                    "Fed by registry relation {binding_id}; supply the cross-period "
                    "or cross-modelo value this relation carries."
                ),
            ),
            legal_refs=(),
            source_refs=(),
        )
    binding_id = context.get("binding_id")
    if not isinstance(binding_id, str):
        return None
    return _WizardStep(
        channel="binding",
        key=binding_id,
        casilla_id=binding_id,
        number=binding_id,
        label=binding_id,
        help_text=None,
        legal_refs=(),
        source_refs=(),
    )


def _profile_resolved_binding_ids(unit: WorkUnit) -> frozenset[str]:
    from ...core import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return frozenset()
    try:
        return profile_resolvable_binding_ids(
            modelo=str(unit.modelo),
            bucket_id=bucket_id,
            filing_year=unit.filing_year,
            period=unit.period,
        )
    except (RegistrySnapshotError, RegistryValidationError, ProfileNotFoundError):
        return frozenset()


def _run_wizard_steps(
    prompter: _TextAnswerPrompter,
    steps: tuple[_WizardStep, ...],
) -> tuple[tuple[_WizardStep, str], ...]:
    """Ask ``prompter`` one question per outstanding step, in order.

    A work unit with no outstanding manual input needs no interactive
    console at all — the loop body never runs, so a ``--format json``
    scripted caller with nothing left to fill in never hits the
    non-interactive refusal.
    """
    answers: list[tuple[_WizardStep, str]] = []
    for step in steps:
        prompt_text = tr(
            "cli.app.modelo.work.wizard_prompt",
            number=step.number,
            label=step.label,
            default="Casilla {number} ({label})",
        )
        raw = prompter.ask_text(prompt_text, help_text=step.help_text)
        answers.append((step, raw.strip()))
    return tuple(answers)


def _emit_wizard_result(
    ctx: typer.Context,
    calculation_result: ModeloWorkCalculationServiceResult,
    prompted: tuple[tuple[_WizardStep, str], ...],
) -> None:
    from ._common import _emit_envelope

    calculation_revision = calculation_result.revision
    unit_for_modality = calculation_result.work_unit
    saved_confirmation = tr(
        "cli.app.modelo.work.wizard_saved",
        default=(
            "Saved as draft calculation revision %{revision_id} "
            "(state: %{state}). It is persisted and can be resumed later; "
            "list revisions with "
            "`aeat app modelo work revisions --modelo %{modelo} --year %{year} --period %{period}` "
            "and re-inspect this one with `aeat app modelo work revision %{revision_id}`."
        ),
        revision_id=calculation_revision.calculation_revision_id,
        state=calculation_revision.state.value,
        modelo=unit_for_modality.modelo,
        year=unit_for_modality.filing_year,
        period=unit_for_modality.period.registry_token,
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
            **calculation_revision_payload(calculation_revision).model_dump(mode="python"),
            "prompted_casillas": prompted_payload,
        },
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
            advisory_notice(
                "modelo.work.wizard.source_advisory",
                diagnostic.message,
                context={"reason": str(diagnostic.reason), "source_kind": diagnostic.source_kind},
            )
            for diagnostic in diagnostics
        )
    _emit_envelope(ctx, command="modelo.work.wizard", result=result, lines=lines, notices=notices or None)


__all__ = ["register_work_wizard_commands"]
