"""Behavior handler for the guided ``aeat app modelo work amend-wizard`` command.

An operator discovers a mistake in an already-filed return and knows "casilla 01 was
wrong, it should have been 1100" in plain language, not the raw
``--from-filing-record ... --kind ... --reason ... --set 01=1100`` flag
grammar ``work amend`` demands. The wizard resolves the work unit's current
AEAT-attested filing record, shows every one of its casilla values, asks which
casillas changed and what the corrected value is for each, confirms the legal
amendment kind and a free-text reason, then calls the exact same
:func:`~application.modelo.amendment_actions.amend_modelo_revision` composition path
``work amend`` uses. The wizard is a guided front end over that one write
path, not a second one (``aeat-architecture-boundaries``).

The runtime worker supplies the filing record, its persisted calculation
snapshot, and the matching registry casilla rows under one authority capture.

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

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import typer
from pydantic import BaseModel

from ...application.flows.copy import register_copy_source
from ...application.flows.definition import CopyRef, FlowChoice, FlowCondition, FlowDefinition, FlowPage, FlowSection
from ...application.flows.engine import FlowState
from ...application.flows.line_frontend import LineFlowFrontend
from ...application.modelo.action_errors import (
    AmendmentEvidenceMissingError,
    ModeloRecordNotFoundError,
    amendment_evidence_missing_precondition,
)
from ...application.modelo.amendment_context_operation import (
    ModeloWorkAmendmentContextProjection,
    ModeloWorkAmendmentContextRequest,
)
from ...application.modelo.amendment_projection import ModeloWorkAmendPublicResultV2
from ...application.modelo.work_amend_contracts import (
    ModeloWorkAmendBaseline,
    ModeloWorkAmendOverride,
    ModeloWorkAmendRequest,
)
from ...application.operations.public_scalar import PublicDecimal
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.external_constants import OutputLanguage
from ...core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.query_reports import ModeloCasillaRow
from ...domain.modelos.calculation_revision_amendment import (
    CalculationRevisionAmendmentKind,
    M303RectificativaMotive,
)
from ._modelo_amend_wizard_payloads import AmendWizardCorrectedCasillaPayload, WorkAmendWizardResult
from ._modelo_cli_support import bad_parameter_from_error, resolve_actor_option
from ._modelo_rendering import filing_record_lines
from .common import activate_subcommand_output_language, emit_envelope, no_active_profile_refusal
from .runtime_modelo_amendment import read_modelo_work_amendment_context, run_modelo_work_amendment
from .runtime_modelo_metadata import read_modelo_work_unit
from .runtime_profile_binding import require_profile_client

if TYPE_CHECKING:
    from ...domain.modelos.filing_record import ModeloRecord
    from ...domain.modelos.work_unit import WorkUnit
__all__ = ["work_amend_wizard"]


class _AmendWizardAnswers(BaseModel):
    """Empty typed shell: the wizard reads answers off the flow state directly."""

    model_config = STRICT_FROZEN_CONFIG


_COPY_NAMESPACE = "modelo-amend"
_ACTIVE_RUNS: dict[str, dict[str, str]] = {}
(
    "Per-run registry-derived copy tables, keyed by an opaque run token.\n\n"
    "Each wizard invocation owns one table for its whole lifetime — both the\n"
    "selection round and the values/kind/reason round append into the same\n"
    "table. Every reference embeds its run token\n"
    "(``modelo-amend:<run-token>:<slot>``), so the registered resolver reads only\n"
    "the addressed run's table: two interleaved runs in one embedding process never\n"
    "clear each other's entries, and each table is dropped at its own run end rather\n"
    "than accumulating for the process lifetime. Values are the registry snapshot's\n"
    "localized labels and help plus the baseline casilla figures; the resolver\n"
    "returns ``None`` outside the namespace so other domains' schema-field resolvers\n"
    "get their turn.\n"
)
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
class _AmendWizardTarget:
    """The target coordinates for the amendment-only workflow."""

    work_unit_id: str | None
    modelo: str | None
    year: int | None
    period: str | None
    revision: str | None
    bucket_id: str | None


def run_modelo_work_amend_wizard(
    *,
    ctx: typer.Context,
    target: _AmendWizardTarget,
    actor: str | None,
    output_language_opt: OutputLanguage | None,
) -> None:
    activate_subcommand_output_language(ctx, output_language_opt)
    unit = read_modelo_work_unit(
        ctx=ctx,
        work_unit_id=target.work_unit_id,
        modelo=target.modelo,
        year=target.year,
        period=target.period,
        revision=target.revision,
        bucket_id=target.bucket_id,
    )
    if unit.current_filing_record_id is None:
        raise bad_parameter_from_error(
            ModeloRecordNotFoundError(
                translated_message="cli.app.modelo.work.amend_wizard_no_current_filing",
                context={"work_unit_id": unit.work_unit_id},
            )
        )
    profile_id = resolve_active_bucket_id()
    if profile_id is None:
        raise no_active_profile_refusal()
    client = require_profile_client(ctx, expected_profile_id=UUID(profile_id))
    context_projection = read_modelo_work_amendment_context(
        client,
        ModeloWorkAmendmentContextRequest(profile_id=client.profile_id, filing_record_id=unit.current_filing_record_id),
    ).projection
    if not isinstance(context_projection, ModeloWorkAmendmentContextProjection) or _amendment_context_scope_invalid(
        context_projection, unit
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    baseline = context_projection.record
    unit = context_projection.unit.to_work_unit()
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
    baseline_values = _baseline_values(context_projection)
    amendable = _amendable_rows(context_projection.casilla_rows, baseline_values)
    if not amendable:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.amend_wizard_no_corrections",
            )
        )
    run_token = uuid4().hex
    _ACTIVE_RUNS[run_token] = {}
    try:
        selected = _prompt_selection(
            amendable=amendable, baseline_values=baseline_values, unit=unit, run_token=run_token
        )
        if not selected:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.amend_wizard_no_corrections",
                )
            )
        corrections, amendment_kind, motive, reason = _prompt_values_kind_reason(
            selected=selected,
            baseline_values=baseline_values,
            modelo=str(baseline.modelo),
            permitted_amendment_kinds=context_projection.permitted_amendment_kinds,
            m303_rectificativa_motive_applicable=context_projection.m303_rectificativa_motive_applicable,
            run_token=run_token,
        )
    finally:
        _ACTIVE_RUNS.pop(run_token, None)
    request = ModeloWorkAmendRequest(
        baseline=ModeloWorkAmendBaseline(from_filing_record_id=baseline.filing_record_id),
        amendment_kind=amendment_kind,
        overrides=tuple(
            ModeloWorkAmendOverride(casilla_id=row.casilla_id, value=str(value))
            for row, _previous, value in corrections
        ),
        reason=reason,
        m303_rectificativa_motive=motive,
        actor=resolve_actor_option(actor),
    )
    amended = run_modelo_work_amendment(client, request, work_unit_id=unit.work_unit_id).projection
    if not isinstance(amended, ModeloWorkAmendPublicResultV2):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    _emit_amend_wizard_result(
        ctx,
        record=amended.record.to_record(),
        amendment_kind=amended.amendment_kind,
        m303_rectificativa_motive=amended.m303_rectificativa_motive,
        reason=reason,
        corrections=corrections,
    )


def _baseline_values(context: ModeloWorkAmendmentContextProjection) -> dict[str, Decimal]:
    """Read exact persisted decimal values without reconstructing a revision."""
    values: dict[str, Decimal] = {}
    for fact in context.calculation.casilla_values:
        if not isinstance(fact.value, PublicDecimal):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        values[fact.key] = Decimal(fact.value.decimal)
    return values


def _amendable_rows(
    casilla_rows: tuple[ModeloCasillaRow, ...], baseline_values: Mapping[str, Decimal]
) -> tuple[ModeloCasillaRow, ...]:
    """Return the registry rows that carry a baseline value, in casilla-number order.

    These are exactly the casillas the operator may amend: every casilla the
    attested baseline actually declares a value for. The order is stable
    (casilla number) so the CHECKBOX choices and the follow-up value pages
    read top-to-bottom like the printed return.
    """
    return tuple(row for row in sorted(casilla_rows, key=lambda r: r.number) if row.casilla_id in baseline_values)


def _run_flow(definition: FlowDefinition) -> FlowState:
    """Drive one CLI flow through the frontend-neutral line projection.

    The CLI consumes the application substrate's line frontend directly; its
    environment guard preserves the canonical typed refusal on a
    non-interactive or unsupported console.
    """
    state, _projection = LineFlowFrontend(definition).run(mode=FlowMode.CREATE)
    return state


def _prompt_selection(
    *, amendable: tuple[ModeloCasillaRow, ...], baseline_values: Mapping[str, Decimal], unit: WorkUnit, run_token: str
) -> tuple[ModeloCasillaRow, ...]:
    """Ask which casillas changed through a single CHECKBOX page.

    The checkbox lists every baseline casilla value; each choice's label is
    the casilla number, its localized label, and its current attested value,
    so the operator selects the ones that changed. A blank selection (no box
    ticked) reads back as an empty tuple, exactly as the one-shot prompt's
    empty answer did — the caller turns that into the no-corrections refusal.
    """
    definition = _selection_definition(
        amendable=amendable, baseline_values=baseline_values, unit=unit, run_token=run_token
    )
    state = _run_flow(definition)
    return _selected_rows(amendable=amendable, unit=unit, state=state)


def _selection_definition(
    *, amendable: tuple[ModeloCasillaRow, ...], baseline_values: Mapping[str, Decimal], unit: WorkUnit, run_token: str
) -> FlowDefinition:
    """Project the amendable casillas into a one-page CHECKBOX selection flow."""
    table = _ACTIVE_RUNS[run_token]
    summary_lines = "\n".join(f"  {row.number}\t{row.label}\t{baseline_values[row.casilla_id]}" for row in amendable)
    prompt_ref = _copy_ref(run_token, "sel:prompt")
    table[prompt_ref] = tr(
        "cli.app.modelo.work.amend_wizard_select_prompt",
        modelo=str(unit.modelo),
        year=unit.filing_year,
        period=unit.period.registry_token,
        summary=summary_lines,
    )
    choices: list[FlowChoice] = []
    for row in amendable:
        previous = baseline_values[row.casilla_id]
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


def _selected_rows(
    *, amendable: tuple[ModeloCasillaRow, ...], unit: WorkUnit, state: FlowState
) -> tuple[ModeloCasillaRow, ...]:
    """Map the CHECKBOX answer back to the selected registry rows, in flow order."""
    raw = state.answers.get(_SELECTION_PAGE_ID, "")
    selected_ids = [token for token in raw.split(",") if token]
    rows_by_id = {row.casilla_id: row for row in amendable}
    selected: list[ModeloCasillaRow] = []
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
    *,
    selected: tuple[ModeloCasillaRow, ...],
    baseline_values: Mapping[str, Decimal],
    modelo: str,
    permitted_amendment_kinds: tuple[CalculationRevisionAmendmentKind, ...],
    m303_rectificativa_motive_applicable: bool,
    run_token: str,
) -> tuple[
    tuple[tuple[ModeloCasillaRow, Decimal, Decimal], ...],
    CalculationRevisionAmendmentKind,
    M303RectificativaMotive | None,
    str,
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
        selected=selected,
        baseline_values=baseline_values,
        modelo=modelo,
        permitted_amendment_kinds=permitted_amendment_kinds,
        m303_rectificativa_motive_applicable=m303_rectificativa_motive_applicable,
        run_token=run_token,
    )
    state = _run_flow(definition)
    corrections: list[tuple[ModeloCasillaRow, Decimal, Decimal]] = []
    for row in selected:
        previous = baseline_values[row.casilla_id]
        corrections.append((row, previous, _wizard_corrected_amount(state, row.casilla_id)))
    amendment_kind = CalculationRevisionAmendmentKind((state.answers.get(_KIND_PAGE_ID) or "").strip())
    raw_motive = (state.answers.get(_MOTIVE_PAGE_ID) or "").strip()
    motive = M303RectificativaMotive(raw_motive) if raw_motive else None
    reason = (state.answers.get(_REASON_PAGE_ID) or "").strip()
    if not reason:
        raise typer.BadParameter(tr("cli.app.modelo.work.amend_wizard_reason_required"))
    return (tuple(corrections), amendment_kind, motive, reason)


def _values_kind_reason_definition(
    *,
    selected: tuple[ModeloCasillaRow, ...],
    baseline_values: Mapping[str, Decimal],
    modelo: str,
    permitted_amendment_kinds: tuple[CalculationRevisionAmendmentKind, ...],
    m303_rectificativa_motive_applicable: bool,
    run_token: str,
) -> FlowDefinition:
    """Project the corrected-value, amendment-kind, and reason questions into one flow.

    The SELECT uses kinds projected under the same worker authority capture
    as the baseline. The amendment writer reasserts the legal guard.
    """
    table = _ACTIVE_RUNS[run_token]
    pages = _correction_value_pages(
        selected=selected, baseline_values=baseline_values, run_token=run_token, table=table
    )
    pages.append(_amendment_kind_page(permitted_kinds=permitted_amendment_kinds, run_token=run_token, table=table))
    motive_page = _m303_motive_page(
        modelo=modelo,
        m303_rectificativa_motive_applicable=m303_rectificativa_motive_applicable,
        run_token=run_token,
        table=table,
    )
    if motive_page is not None:
        pages.append(motive_page)
    pages.append(_amendment_reason_page(run_token=run_token, table=table))
    return _amendment_correction_definition(pages)


def _correction_value_pages(
    *,
    selected: tuple[ModeloCasillaRow, ...],
    baseline_values: Mapping[str, Decimal],
    run_token: str,
    table: dict[str, str],
) -> list[FlowPage]:
    pages: list[FlowPage] = []
    for row in selected:
        previous = baseline_values[row.casilla_id]
        prompt_ref = _copy_ref(run_token, f"val:{row.casilla_id}:prompt")
        table[prompt_ref] = tr(
            "cli.app.modelo.work.amend_wizard_value_prompt",
            number=row.number,
            label=row.label,
            previous_value=str(previous),
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


def _value_help_ref(*, row: ModeloCasillaRow, run_token: str, table: dict[str, str]) -> str | None:
    if not row.help_text:
        return None
    help_ref = _copy_ref(run_token, f"val:{row.casilla_id}:help")
    table[help_ref] = row.help_text
    return help_ref


def _amendment_kind_page(
    *, permitted_kinds: tuple[CalculationRevisionAmendmentKind, ...], run_token: str, table: dict[str, str]
) -> FlowPage:
    kind_choices = tuple(
        _amendment_kind_choice(kind=kind, run_token=run_token, table=table) for kind in permitted_kinds
    )
    kind_prompt_ref = _copy_ref(run_token, "kind:prompt")
    table[kind_prompt_ref] = tr(
        "cli.app.modelo.work.amend_wizard_kind_prompt",
        choices=", ".join(repr(kind.value) for kind in permitted_kinds),
    )
    kind_help_ref = _copy_ref(run_token, "kind:help")
    table[kind_help_ref] = tr(
        "cli.app.modelo.work.amend_wizard_kind_help",
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
    *, modelo: str, m303_rectificativa_motive_applicable: bool, run_token: str, table: dict[str, str]
) -> FlowPage | None:
    if modelo != "303" or not m303_rectificativa_motive_applicable:
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
        "cli.app.modelo.work.amend_wizard_reason_prompt",
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
    amendment_kind: CalculationRevisionAmendmentKind,
    m303_rectificativa_motive: M303RectificativaMotive | None,
    reason: str,
    corrections: tuple[tuple[ModeloCasillaRow, Decimal, Decimal], ...],
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

    Resolve the work unit and its current filing through registered runtime
    reads, prompt from the worker's pinned calculation and casilla snapshot,
    then submit the same typed amendment operation as ``work amend``.
    """
    run_modelo_work_amend_wizard(
        ctx=ctx,
        target=_AmendWizardTarget(
            work_unit_id=work_unit_id,
            modelo=modelo,
            year=year,
            period=period,
            revision=revision,
            bucket_id=bucket_id,
        ),
        actor=actor,
        output_language_opt=output_language_opt,
    )


def _amendment_context_scope_invalid(context_projection: ModeloWorkAmendmentContextProjection, unit: WorkUnit) -> bool:
    """Require the selected current filing record and work unit in the amendment context."""
    return (
        context_projection.unit.work_unit_id != unit.work_unit_id
        or context_projection.record.filing_record_id != unit.current_filing_record_id
    )
