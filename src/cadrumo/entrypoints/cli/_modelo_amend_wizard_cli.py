# ruff: noqa: E501 - localized guidance and tabular wire lines are atomic
"""Behavior handler for the guided ``aeat app modelo work amend-wizard`` command.

An operator discovers a mistake in an already-filed return and knows "casilla 01 was
wrong, it should have been 1100" in plain language, not the raw
``--from-filing-record ... --kind ... --reason ... --set 01=1100`` flag
grammar ``work amend`` demands. The wizard resolves the work unit's current
AEAT-attested filing record, shows every one of its casilla values, asks which
casillas changed and what the corrected value is for each, confirms the legal
amendment kind and a free-text reason, then calls the exact same
:func:`~application.modelo.amend_modelo_revision` composition path
``work amend`` uses. The wizard is a guided front end over that one write
path, not a second one (``aeat-architecture-boundaries``).

The baseline casilla values the wizard displays are read from the filing
record's :class:`~domain.modelos.CalculationRevision`, so the operator
edits the exact attested figures rather than a re-computed draft.

Once the amendment is filed, the wizard points the operator at the existing
``aeat app modelo export`` verb for the fichero-BOE artefact; it never writes
an export file itself, mirroring how ``work wizard`` hands off to
``work calculate`` rather than re-deriving casilla values.

A real interactive terminal is required: the prompting is the flow
substrate's line frontend (:class:`~cadrumo.application.flows.line_frontend.LineFlowFrontend`)
over the one flow engine, so the non-TTY / Windows-no-console detection and
the translated refusal are the substrate's single implementation rather than
a re-derived copy of it, and the operator gets the engine's review surface
(re-edit by number, restart, submit) before the amendment is filed. The
amendment is asked in two rounds: a CHECKBOX
selection page over the filing record's casilla ids, then a second definition
carrying one DECIMAL page per selected casilla, the amendment-kind SELECT
(restricted to the kinds the period legally permits), and the required reason.

The prompt *copy* comes from the resolved registry snapshot — a casilla
number and label, not a static translation-catalogue key — so each question
is projected into a :class:`FlowDefinition` page whose copy slots are
schema-field references resolved by this module's registered copy source
against the per-run registry-derived table. The definition carries
references only; the registry stays the copy authority.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import typer
from pydantic import BaseModel

from ...application.flows.copy import register_copy_source
from ...application.flows.definition import CopyRef, FlowChoice, FlowCondition, FlowDefinition, FlowPage, FlowSection
from ...application.flows.engine import FlowState
from ...application.flows.line_frontend import LineFlowFrontend
from ...application.modelo import (
    AmendmentComplementariaLiabilityDecreaseError,
    AmendmentEvidenceMissingError,
    AmendmentKindNotPermittedError,
    AmendmentM303RectificativaMotiveError,
    AmendmentOverrideCasillaError,
    AmendmentTargetStateError,
    AmendmentVerificationRefusedError,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloRecordNotFoundError,
    WorkUnitNotFoundError,
    amend_modelo_revision,
    amendment_evidence_missing_precondition,
    get_calculation_revision,
    get_filing_record,
    registry_casillas_for_registry_scope,
)
from ...core import STRICT_FROZEN_CONFIG, Modelo, Period, permitted_amendment_kind_values
from ...core.decimal import try_parse_canonical_decimal
from ...core.external_constants import OutputLanguage
from ...core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from ...core.i18n import tr
from ...domain.calculations.registry import RegistrySnapshotError
from ...domain.modelos import (
    CalculationRevisionAmendmentKind,
    M303RectificativaMotive,
    m303_rectificativa_motive_is_applicable,
)
from ._common import activate_subcommand_output_language, emit_envelope
from ._modelo_amend_wizard_payloads import AmendWizardCorrectedCasillaPayload, WorkAmendWizardResult
from ._modelo_behavior_support import require_active_profile, resolve_work_unit_for_cli
from ._modelo_cli_support import bad_parameter_from_error, resolve_default_actor
from ._modelo_rendering import filing_record_lines

if TYPE_CHECKING:
    from ...domain.modelos import CalculationRevision, ModeloRecord, WorkUnit
__all__ = ["work_amend_wizard"]


class _AmendWizardAnswers(BaseModel):
    """Empty typed shell: the wizard reads answers off the flow state directly."""

    model_config = STRICT_FROZEN_CONFIG


_COPY_NAMESPACE = "modelo-amend"
_ACTIVE_RUNS: dict[str, dict[str, str]] = {}
"Per-run registry-derived copy tables, keyed by an opaque run token.\n\nEach wizard invocation owns one table for its whole lifetime — both the\nselection round and the values/kind/reason round append into the same\ntable. Every reference embeds its run token\n(``modelo-amend:<run-token>:<slot>``), so the registered resolver reads only\nthe addressed run's table: two interleaved runs in one embedding process never\nclear each other's entries, and each table is dropped at its own run end rather\nthan accumulating for the process lifetime. Values are the registry snapshot's\nlocalized labels and help plus the baseline casilla figures; the resolver\nreturns ``None`` outside the namespace so other domains' schema-field resolvers\nget their turn.\n"
_SELECTION_PAGE_ID = "selection"
_KIND_PAGE_ID = "amendment-kind"
_MOTIVE_PAGE_ID = "m303-rectificativa-motive"
_REASON_PAGE_ID = "reason"


def _resolve_amend_wizard_copy(ref: str) -> str | None:
    prefix = f"{_COPY_NAMESPACE}:"
    if not ref.startswith(prefix):
        return None
    run_token, _, _ = ref[len(prefix) :].partition(":")
    table = _ACTIVE_RUNS.get(run_token)
    return table.get(ref) if table is not None else None


register_copy_source(CopyRefKind.SCHEMA_FIELD, _resolve_amend_wizard_copy)


def _copy_ref(run_token: str, slot: str) -> str:
    return f"{_COPY_NAMESPACE}:{run_token}:{slot}"


def _value_page_id(casilla_id: str) -> str:
    return f"value:{casilla_id}"


@dataclass(frozen=True, slots=True)
class _AmendWizardDeps:
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None]
    require_active_profile: Callable[[], None]
    resolve_work_unit_for_cli: Callable[..., Any]
    resolve_default_actor: Callable[[], str]
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter]


deps = _AmendWizardDeps(
    activate_output_language=activate_subcommand_output_language,
    require_active_profile=require_active_profile,
    resolve_work_unit_for_cli=resolve_work_unit_for_cli,
    resolve_default_actor=resolve_default_actor,
    bad_parameter_from_error=bad_parameter_from_error,
)


def run_modelo_work_amend_wizard(
    *,
    deps: _AmendWizardDeps,
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
    if unit.current_filing_record_id is None:
        raise deps.bad_parameter_from_error(
            ModeloRecordNotFoundError(
                translated_message="cli.app.modelo.work.amend_wizard_no_current_filing",
                context={"work_unit_id": unit.work_unit_id},
            )
        )
    try:
        baseline = get_filing_record(unit.current_filing_record_id)
    except ModeloRecordNotFoundError as exc:
        raise deps.bad_parameter_from_error(exc) from exc
    if baseline.external_evidence is None:
        raise AmendmentEvidenceMissingError(
            context={
                "work_unit_id": unit.work_unit_id,
                "filing_record_id": baseline.filing_record_id,
                "external_evidence_present": False,
            },
            precondition_failure=amendment_evidence_missing_precondition(
                work_unit_id=unit.work_unit_id,
                filing_record_id=baseline.filing_record_id,
            ),
        ) from None
    try:
        casilla_rows = _baseline_casilla_rows(unit)
    except RegistrySnapshotError as exc:
        raise deps.bad_parameter_from_error(exc) from exc
    baseline_revision: CalculationRevision = get_calculation_revision(baseline.calculation_revision_id)
    amendable = _amendable_rows(casilla_rows, baseline_revision)
    if not amendable:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.amend_wizard_no_corrections",
                default="No casilla was corrected; the amendment wizard needs at least one changed value.",
            )
        )
    run_token = uuid4().hex
    _ACTIVE_RUNS[run_token] = {}
    try:
        selected = _prompt_selection(
            amendable=amendable, baseline_revision=baseline_revision, unit=unit, run_token=run_token
        )
        if not selected:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.amend_wizard_no_corrections",
                    default="No casilla was corrected; the amendment wizard needs at least one changed value.",
                )
            )
        corrections, amendment_kind, motive, reason = _prompt_values_kind_reason(
            selected=selected,
            baseline_revision=baseline_revision,
            modelo=str(baseline.modelo),
            period=baseline.period,
            run_token=run_token,
        )
    finally:
        _ACTIVE_RUNS.pop(run_token, None)
    overrides = {row.casilla_id: value for row, _previous, value in corrections}
    try:
        from ...adapters.persistence.profile.justificante import JustificanteRepository

        record = amend_modelo_revision(
            from_filing_record_id=baseline.filing_record_id,
            overrides=overrides,
            amendment_kind=amendment_kind,
            m303_rectificativa_motive=motive,
            reason=reason,
            actor=actor or deps.resolve_default_actor(),
            justificante_repository=JustificanteRepository(),
        )
    except (
        ModeloRecordNotFoundError,
        AmendmentEvidenceMissingError,
        AmendmentTargetStateError,
        AmendmentOverrideCasillaError,
        AmendmentVerificationRefusedError,
        AmendmentKindNotPermittedError,
        AmendmentM303RectificativaMotiveError,
        AmendmentComplementariaLiabilityDecreaseError,
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        WorkUnitNotFoundError,
    ) as exc:
        raise deps.bad_parameter_from_error(exc) from exc
    _emit_amend_wizard_result(
        ctx,
        record=record,
        unit=unit,
        amendment_kind=amendment_kind,
        m303_rectificativa_motive=motive,
        reason=reason,
        corrections=corrections,
    )


def _baseline_casilla_rows(unit: WorkUnit) -> tuple[Any, ...]:
    """Return every casilla the registry declares for the unit's revision, for display."""
    report = registry_casillas_for_registry_scope(
        str(unit.modelo), filing_year=unit.filing_year, period=unit.period.registry_token
    )
    return tuple(report.rows)


def _amendable_rows(casilla_rows: tuple[Any, ...], baseline_revision: CalculationRevision) -> tuple[Any, ...]:
    """Return the registry rows that carry a baseline value, in casilla-number order.

    These are exactly the casillas the operator may amend: every casilla the
    attested baseline actually declares a value for. The order is stable
    (casilla number) so the CHECKBOX choices and the follow-up value pages
    read top-to-bottom like the printed return.
    """
    return tuple(
        row
        for row in sorted(casilla_rows, key=lambda r: r.number)
        if row.casilla_id in baseline_revision.casilla_values
    )


def _run_flow(definition: FlowDefinition) -> FlowState:
    """Drive one CLI flow through the frontend-neutral line projection.

    The CLI consumes the application substrate's line frontend directly; its
    environment guard preserves the canonical typed refusal on a
    non-interactive or unsupported console.
    """
    state, _projection = LineFlowFrontend(definition).run(mode=FlowMode.CREATE)
    return state


def _prompt_selection(
    *, amendable: tuple[Any, ...], baseline_revision: CalculationRevision, unit: WorkUnit, run_token: str
) -> tuple[Any, ...]:
    """Ask which casillas changed through a single CHECKBOX page.

    The checkbox lists every baseline casilla value; each choice's label is
    the casilla number, its localized label, and its current attested value,
    so the operator selects the ones that changed. A blank selection (no box
    ticked) reads back as an empty tuple, exactly as the one-shot prompt's
    empty answer did — the caller turns that into the no-corrections refusal.
    """
    definition = _selection_definition(
        amendable=amendable, baseline_revision=baseline_revision, unit=unit, run_token=run_token
    )
    state = _run_flow(definition)
    return _selected_rows(amendable=amendable, unit=unit, state=state)


def _selection_definition(
    *, amendable: tuple[Any, ...], baseline_revision: CalculationRevision, unit: WorkUnit, run_token: str
) -> FlowDefinition:
    """Project the amendable casillas into a one-page CHECKBOX selection flow."""
    table = _ACTIVE_RUNS[run_token]
    summary_lines = "\n".join(
        f"  {row.number}\t{row.label}\t{baseline_revision.casilla_values.get(row.casilla_id, Decimal('0'))}"
        for row in amendable
    )
    prompt_ref = _copy_ref(run_token, "sel:prompt")
    table[prompt_ref] = tr(
        "cli.app.modelo.work.amend_wizard_select_prompt",
        modelo=str(unit.modelo),
        year=unit.filing_year,
        period=unit.period.registry_token,
        summary=summary_lines,
        default="Filed {modelo} {year} {period} — current values:\n{summary}\nWhich casillas changed? (select the ones to correct, none to abort)",
    )
    choices: list[FlowChoice] = []
    for row in amendable:
        previous = baseline_revision.casilla_values.get(row.casilla_id, Decimal("0"))
        label_ref = _copy_ref(run_token, f"sel:choice:{row.casilla_id}")
        table[label_ref] = f"{row.number} ({row.label}): {previous}"
        choices.append(FlowChoice(value=row.casilla_id, label=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=label_ref)))
    page = FlowPage(
        id=_SELECTION_PAGE_ID,
        widget=FlowWidgetKind.CHECKBOX,
        prompt=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=prompt_ref),
        choices=tuple(choices),
        required=False,
        answer_type=str,
    )
    help_key = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="cli.app.modelo.work.amend_wizard_help")
    return FlowDefinition(
        id="modelo-work-amend-wizard-selection",
        title=help_key,
        description=help_key,
        sections=(FlowSection(id="selection", title=help_key, items=(page,)),),
        answers_model=_AmendWizardAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


def _selected_rows(*, amendable: tuple[Any, ...], unit: WorkUnit, state: FlowState) -> tuple[Any, ...]:
    """Map the CHECKBOX answer back to the selected registry rows, in flow order."""
    raw = state.answers.get(_SELECTION_PAGE_ID, "")
    selected_ids = [token for token in raw.split(",") if token]
    rows_by_id = {row.casilla_id: row for row in amendable}
    selected: list[Any] = []
    for casilla_id in selected_ids:
        row = rows_by_id.get(casilla_id)
        if row is None:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.amend_wizard_unknown_casilla",
                    token=casilla_id,
                    modelo=str(unit.modelo),
                    year=unit.filing_year,
                    period=unit.period.registry_token,
                    default="Casilla {token!r} is not part of the filed {modelo} {year} {period} return; choose from the listed casilla numbers.",
                )
            )
        selected.append(row)
    return tuple(selected)


def _wizard_corrected_amount(state: FlowState, casilla_id: str) -> Decimal:
    """Read one corrected casilla amount back off the flow state.

    The DECIMAL widget's shape validation already admitted only a
    canonical-grammar amount and canonicalised it to ``str(Decimal)``, so this
    re-read is defence in depth against a widget contract change rather than the
    boundary itself. It uses the same uncapped grammar the widget applies, so a
    value the widget accepted can never hard-refuse here — a refusal at the end
    of a collected flow would be a refusal at the wrong surface.
    """
    raw = (state.answers.get(_value_page_id(casilla_id)) or "").strip()
    parsed = try_parse_canonical_decimal(raw)
    if parsed is None:
        raise typer.BadParameter(tr("cli.app.modelo.work.set_not_decimal", value=raw))
    return parsed


def _prompt_values_kind_reason(
    *, selected: tuple[Any, ...], baseline_revision: CalculationRevision, modelo: str, period: Period, run_token: str
) -> tuple[
    tuple[tuple[Any, Decimal, Decimal], ...], CalculationRevisionAmendmentKind, M303RectificativaMotive | None, str
]:
    """Ask the corrected value per selected casilla, the amendment kind, and the reason.

    A single second-round definition carries one DECIMAL page per selected
    casilla (showing its current value), the amendment-kind SELECT restricted
    to the kinds the period legally permits, and the required free-text
    reason. Values are read back off the engine state; the DECIMAL widget's
    shape validation guarantees each corrected value already parses as a
    finite :class:`~decimal.Decimal`, and the SELECT guarantees the kind is
    one the period permits.
    """
    definition = _values_kind_reason_definition(
        selected=selected, baseline_revision=baseline_revision, modelo=modelo, period=period, run_token=run_token
    )
    state = _run_flow(definition)
    corrections: list[tuple[Any, Decimal, Decimal]] = []
    for row in selected:
        previous = baseline_revision.casilla_values.get(row.casilla_id, Decimal("0"))
        corrections.append((row, previous, _wizard_corrected_amount(state, row.casilla_id)))
    amendment_kind = CalculationRevisionAmendmentKind((state.answers.get(_KIND_PAGE_ID) or "").strip())
    raw_motive = (state.answers.get(_MOTIVE_PAGE_ID) or "").strip()
    motive = M303RectificativaMotive(raw_motive) if raw_motive else None
    reason = (state.answers.get(_REASON_PAGE_ID) or "").strip()
    if not reason:
        raise typer.BadParameter(tr("cli.app.modelo.work.amend_wizard_reason_required"))
    return (tuple(corrections), amendment_kind, motive, reason)


def _values_kind_reason_definition(
    *, selected: tuple[Any, ...], baseline_revision: CalculationRevision, modelo: str, period: Period, run_token: str
) -> FlowDefinition:
    """Project the corrected-value, amendment-kind, and reason questions into one flow.

    The amendment-kind SELECT reads :func:`~core.permitted_amendment_kind_values`
    for ``modelo`` and ``period`` so the wizard only offers (and only accepts)
    the kinds legally available for this filing — it never offers
    ``rectificativa`` for a pre-adoption period, nor ``complementaria`` once
    the rectificativa has replaced it. ``amend_modelo_revision`` re-asserts the
    same guard downstream, so a kind outside the permitted set is refused there
    too if this SELECT is ever bypassed.
    """
    table = _ACTIVE_RUNS[run_token]
    pages = _correction_value_pages(
        selected=selected, baseline_revision=baseline_revision, run_token=run_token, table=table
    )
    pages.append(_amendment_kind_page(modelo=modelo, period=period, run_token=run_token, table=table))
    motive_page = _m303_motive_page(
        modelo=modelo, baseline_revision=baseline_revision, run_token=run_token, table=table
    )
    if motive_page is not None:
        pages.append(motive_page)
    pages.append(_amendment_reason_page(run_token=run_token, table=table))
    return _amendment_correction_definition(pages)


def _correction_value_pages(
    *, selected: tuple[Any, ...], baseline_revision: CalculationRevision, run_token: str, table: dict[str, str]
) -> list[FlowPage]:
    pages: list[FlowPage] = []
    for row in selected:
        previous = baseline_revision.casilla_values.get(row.casilla_id, Decimal("0"))
        prompt_ref = _copy_ref(run_token, f"val:{row.casilla_id}:prompt")
        table[prompt_ref] = tr(
            "cli.app.modelo.work.amend_wizard_value_prompt",
            number=row.number,
            label=row.label,
            previous_value=str(previous),
            default="Corrected value for casilla {number} ({label}), currently {previous_value}",
        )
        help_ref = _value_help_ref(row=row, run_token=run_token, table=table)
        pages.append(
            FlowPage(
                id=_value_page_id(row.casilla_id),
                widget=FlowWidgetKind.DECIMAL,
                prompt=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=prompt_ref),
                help=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=help_ref) if help_ref else None,
                required=True,
                answer_type=str,
            )
        )
    return pages


def _value_help_ref(*, row: Any, run_token: str, table: dict[str, str]) -> str | None:
    if not row.help_text:
        return None
    help_ref = _copy_ref(run_token, f"val:{row.casilla_id}:help")
    table[help_ref] = row.help_text
    return help_ref


def _amendment_kind_page(*, modelo: str, period: Period, run_token: str, table: dict[str, str]) -> FlowPage:
    permitted = permitted_amendment_kind_values(modelo, period)
    permitted_kinds = tuple(kind for kind in CalculationRevisionAmendmentKind if kind.value in permitted)
    kind_choices = tuple(
        _amendment_kind_choice(kind=kind, run_token=run_token, table=table) for kind in permitted_kinds
    )
    kind_prompt_ref = _copy_ref(run_token, "kind:prompt")
    table[kind_prompt_ref] = tr(
        "cli.app.modelo.work.amend_wizard_kind_prompt",
        choices=", ".join(repr(kind.value) for kind in permitted_kinds),
        default="Amendment kind ({choices})",
    )
    kind_help_ref = _copy_ref(run_token, "kind:help")
    table[kind_help_ref] = tr(
        "cli.app.modelo.work.amend_wizard_kind_help",
        default="complementaria adds to the prior tax due; sustitutiva fully replaces the prior filing; rectificativa is the unified correction mechanism for modelos whose orden implements it (e.g. Modelo 303 from filing year 2023). Only the kinds legally available for this filing's period are accepted.",
    )
    return FlowPage(
        id=_KIND_PAGE_ID,
        widget=FlowWidgetKind.SELECT,
        prompt=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=kind_prompt_ref),
        help=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=kind_help_ref),
        choices=kind_choices,
        required=True,
        answer_type=str,
    )


def _amendment_kind_choice(
    *, kind: CalculationRevisionAmendmentKind, run_token: str, table: dict[str, str]
) -> FlowChoice:
    kind_label_ref = _copy_ref(run_token, f"kind:choice:{kind.value}")
    table[kind_label_ref] = kind.value
    return FlowChoice(value=kind.value, label=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=kind_label_ref))


def _m303_motive_page(
    *, modelo: str, baseline_revision: CalculationRevision, run_token: str, table: dict[str, str]
) -> FlowPage | None:
    if modelo != Modelo.M303:
        return None
    filing_evidence = baseline_revision.filing_instance_evidence
    if filing_evidence is None:
        return None
    regimen_snapshot = filing_evidence.m303.regimen_simplificado.regimen_snapshot
    if not m303_rectificativa_motive_is_applicable(
        registry_revision_id=regimen_snapshot.registry_revision_id, record_design=regimen_snapshot.record_design
    ):
        return None
    motive_choices = tuple(
        _m303_motive_choice(motive=motive, run_token=run_token, table=table) for motive in M303RectificativaMotive
    )
    motive_prompt_ref = _copy_ref(run_token, "motive:prompt")
    table[motive_prompt_ref] = tr(
        "cli.app.modelo.work.amend_wizard_m303_rectificativa_motive_prompt",
        choices=", ".join(repr(motive.value) for motive in M303RectificativaMotive),
    )
    motive_help_ref = _copy_ref(run_token, "motive:help")
    table[motive_help_ref] = tr("cli.app.modelo.work.m303_rectificativa_motive_help")
    return FlowPage(
        id=_MOTIVE_PAGE_ID,
        widget=FlowWidgetKind.SELECT,
        prompt=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=motive_prompt_ref),
        help=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=motive_help_ref),
        choices=motive_choices,
        required=True,
        visible_when=FlowCondition(page_id=_KIND_PAGE_ID, equals=CalculationRevisionAmendmentKind.RECTIFICATIVA.value),
        answer_type=str,
    )


def _m303_motive_choice(*, motive: M303RectificativaMotive, run_token: str, table: dict[str, str]) -> FlowChoice:
    label_ref = _copy_ref(run_token, f"motive:choice:{motive.value}")
    table[label_ref] = motive.value
    return FlowChoice(value=motive.value, label=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=label_ref))


def _amendment_reason_page(*, run_token: str, table: dict[str, str]) -> FlowPage:
    reason_prompt_ref = _copy_ref(run_token, "reason:prompt")
    table[reason_prompt_ref] = tr(
        "cli.app.modelo.work.amend_wizard_reason_prompt", default="Reason for this amendment (kept in the audit trail)"
    )
    return FlowPage(
        id=_REASON_PAGE_ID,
        widget=FlowWidgetKind.TEXT,
        prompt=CopyRef(kind=CopyRefKind.SCHEMA_FIELD, ref=reason_prompt_ref),
        required=False,
        answer_type=str,
    )


def _amendment_correction_definition(pages: list[FlowPage]) -> FlowDefinition:
    help_key = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="cli.app.modelo.work.amend_wizard_help")
    return FlowDefinition(
        id="modelo-work-amend-wizard-corrections",
        title=help_key,
        description=help_key,
        sections=(FlowSection(id="corrections", title=help_key, items=tuple(pages)),),
        answers_model=_AmendWizardAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )


def _emit_amend_wizard_result(
    ctx: typer.Context,
    *,
    record: ModeloRecord,
    unit: WorkUnit,
    amendment_kind: CalculationRevisionAmendmentKind,
    m303_rectificativa_motive: M303RectificativaMotive | None,
    reason: str,
    corrections: tuple[tuple[Any, Decimal, Decimal], ...],
) -> None:
    from ._modelo_rendering import filing_record_payload

    corrected_payload = tuple(
        (
            AmendWizardCorrectedCasillaPayload(
                casilla_id=row.casilla_id,
                number=row.number,
                label=row.label,
                previous_value=str(previous_value),
                corrected_value=str(corrected_value),
                legal_refs=tuple(row.legal_refs),
                source_refs=tuple(row.source_refs),
            )
            for row, previous_value, corrected_value in corrections
        )
    )
    filing_payload = filing_record_payload(record).model_dump(mode="python")
    result = WorkAmendWizardResult.model_validate(
        {
            **filing_payload,
            "amendment_kind": amendment_kind,
            "m303_rectificativa_motive": m303_rectificativa_motive,
            "amendment_reason": reason,
            "corrected_casillas": corrected_payload,
        }
    )
    lines = [
        "operation\tmodelo.work.amend_wizard",
        f"amendment_kind\t{amendment_kind.value}",
        f"m303_rectificativa_motive\t{(m303_rectificativa_motive.value if m303_rectificativa_motive else '')}",
        *filing_record_lines(record),
        *(
            f"corrected\t{row.number}\t{previous_value}\t{corrected_value}"
            for row, previous_value, corrected_value in corrections
        ),
    ]
    emit_envelope(ctx, command="modelo.work.amend_wizard", result=result, lines=lines)


def work_amend_wizard(
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
    """Walk the resolved work unit's current AEAT-attested filing through a guided amendment.

    Resolves (or reuses) a work unit exactly as ``work create`` /
    ``work wizard`` do, loads its current filing record (the same
    :class:`~domain.modelos.ModeloRecord` ``work amend``
    requires — it must carry
    :class:`~domain.modelos.ExternalEvidence`), shows every
    baseline casilla value, prompts which casillas changed and their
    corrected values, confirms the amendment kind and reason, then
    calls :func:`~application.modelo.amend_modelo_revision`
    through the identical inputs ``work amend`` builds.
    """
    run_modelo_work_amend_wizard(
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
