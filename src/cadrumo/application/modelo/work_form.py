"""Build the editor form of one modelo work target from the review and the declared layout.

:func:`build_modelo_work_form` is a pure join, presented over the summary
:func:`summarize_modelo_work_form` classifies. It reads the canonical work
review for values and origins, the revision's declared form layout for pages,
sections, grids and placements, the registry snapshot for localized labels,
help, required inputs and bindings, the current calculation revision for what
the filer explicitly cleared, for detail rows, for the AEAT draft it replays and
for its filing state, and the edit admission's permitted
surface for what may be written. It derives no layout: a revision without a
usable declared layout becomes an inspection-only form that says why.

Classification is decided once, here, so every frontend shows the same states:

* the origin of each value -- entered, imported, calculated, needed, not
  applicable, cleared, or held without proof anyone entered it -- and
* the editability of each address -- typed, overridden with a reason, fixed at
  its source, corrected in the profile, calculated, or fixed by the design,
* where each bound value comes from, named by its primary binding's family,
  with the earlier declaration a carry reads and the AEAT tax data an imported
  draft supplied,
* whether a box needs the filer's value, by the same rule verification checks,
* the one rate a printed rate box stands for, where its row's base binding
  declares exactly one, and the rate a box the design fixes prints, where its
  literal states a percentage or its export field declares the scale, never
  from a literal of zeros,
* for a repeating column the design leaves unnamed, the label of the box it
  shows, and for an input no box owns that feeds exactly one numbered box, the
  words "additional data for" that box,
* the settlement box and which way it settles,
* what the latest calculation noticed, on the same scale as the check's
  findings and without repeating one of them, and which box a note says could
  not be worked out, which then reads as not calculated rather than as zero,
* whether the declaration is recorded as filed, which closes it to editing and
  leaves nothing counted as still to do, and
* every answer the edit surface admits: a binding override no field of the
  layout takes becomes a field of its own among the answers, so a declaration
  never asks for a value the filer has nowhere to give, and
* the navigation outline: the layout's declared groups of sections, or one
  group per page, each with its headings, applicability and attention counts,
  and a group each for the unplaced casillas, the working figures and the
  answers, so that the form's counts are the sum of the outline's.

"Entered by the filer" is only ever claimed from the operator's own recorded
entries. A revision that predates them has an unknown operator record, and a
value it holds for a box the filer types is never shown as entered. It is one
to confirm where it could under-declare, in a box verification requires or
when it is not zero; an optional box holding zero reads as optional and empty.
Either way the field says the value is unattributed, because a recalculation
returns it to what the calculation gives.

The form is total: every casilla of the revision appears exactly once, on a
page, among the working figures, or in the unplaced list with its reason, and
every admitted binding override is taken by a field once. A
layout that would drop or repeat a casilla is refused rather than rendered.

See Also:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
        The stored calculation head carrying values, provenance and lifecycle facts.
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
        The pinned registry snapshot supplying the selected modelo revision.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.filing_producer_key import FilingProducerKey
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_form_layouts import (
    FormLayoutDefinition,
    FormLayoutReviewState,
)
from ...domain.iva.refund_eligibility import RedemeEnrolmentState
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.verification_report import ModeloVerificationFinding
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from .calculation_note_gate import NO_SOURCE_DISAGREEMENT_RESOLUTIONS, SourceDisagreementResolutions
from .calculation_notes import UNWORKED_BOX_REASONS
from .edit_models import (
    ModeloEditPermittedSurfaceEntryV1,
)
from .work_form_carry_attestation import form_carry_attestations
from .work_form_context import WorkFormContext
from .work_form_credits import withholding_credits, withholding_credits_heading
from .work_form_declaration_facts import ModeloFormDeadline, ModeloFormExport, year_projection
from .work_form_facts import ModeloWorkFormSummary
from .work_form_field_projection import facts_casilla_id, project_binding_field
from .work_form_field_vocabulary import ModeloFormScalar
from .work_form_inspection import build_inspection_only_form, project_aeat_data
from .work_form_layout import LayoutWalker
from .work_form_layout_facts import layout_presenter
from .work_form_models import (
    ModeloFormField,
    ModeloFormLayoutProvenance,
    ModeloFormPage,
    ModeloFormUnplacedField,
    ModeloWorkForm,
    section_fields,
)
from .work_form_notes import NoteSource, collect_note_sources
from .work_form_outline import form_outline
from .work_form_prior_value_attestation import form_prior_value_attestations
from .work_form_record_attention import with_record_attention
from .work_form_source_groups import worded_source_groups
from .work_form_summary import inspection_reason, summarize_work_form
from .work_form_wording import worded_form
from .work_review import ModeloWorkReview


def build_modelo_work_form(
    *,
    review: ModeloWorkReview,
    snapshot: RegistrySnapshot,
    layout: FormLayoutDefinition | None,
    revision: CalculationRevision | None,
    permitted_surface: tuple[ModeloEditPermittedSurfaceEntryV1, ...] | None,
    entered_casilla_ids: frozenset[CasillaId] | None,
    overridden_binding_ids: frozenset[BindingId] | None,
    language: OutputLanguage,
    deadline: ModeloFormDeadline | None = None,
    aeat_data_imported_at: datetime | None = None,
    calculation_diagnostics: tuple[CalculationSourceDiagnostic, ...] | None = None,
    element_names: Mapping[str, str] | None = None,
    calculation_screen_outdated: bool = False,
    calculation_filed_before_grade_cap: CasillaId | None = None,
    known_truths: Mapping[BindingId, bool] | None = None,
    producer_values: Mapping[FilingProducerKey, ModeloFormScalar] | None = None,
    profile_binding_values: Mapping[BindingId, ModeloFormScalar] | None = None,
    resolutions: SourceDisagreementResolutions = NO_SOURCE_DISAGREEMENT_RESOLUTIONS,
    redeme: RedemeEnrolmentState = RedemeEnrolmentState.UNSTATED,
    filed_findings: tuple[ModeloVerificationFinding, ...] = (),
    last_export: ModeloFormExport | None = None,
    verification_out_of_date: bool = False,
    calculation_sources_arrived: bool = False,
) -> ModeloWorkForm:
    """Join one work review with its revision's declared layout into a classified editor form.

    The form is its summary (:func:`summarize_modelo_work_form`) presented:
    every box, page and filing fact is classified there, and this adds each
    field's words and controls, the layout's structure and what only an
    editor reads.

    ``entered_casilla_ids`` and ``overridden_binding_ids`` are the operator's own
    recorded entries on the current revision; ``None`` means the revision does
    not record them, which is different from recording none. ``permitted_surface``
    is the current edit admission's surface, or ``None`` when no admission is
    available, in which case nothing is offered for editing. A declaration
    recorded as filed offers nothing for editing whatever the admission says,
    because changing it starts a correction.

    ``deadline`` is the resolved filing deadline, and ``aeat_data_imported_at``
    when the AEAT tax data the revision replays was imported; the caller reads
    both, since neither is a fact of the review or the layout. ``last_export``
    is the latest file exported for the declaration and
    ``verification_out_of_date`` whether the movements the last check read
    changed since; the caller reads both as well, and
    ``calculation_sources_arrived``, whether an earlier return a relation of
    ``revision`` found nothing of is held now, so working it out again would
    read it.

    ``element_names`` are the names the register's elements go by now, for the
    notes that speak of them.

    ``calculation_diagnostics`` are the diagnostics the latest calculation
    raised, when this session ran it; ``None`` when it did not, in which case
    only the notes that persist with the calculation are known.

    ``calculation_screen_outdated`` is the calculation-note gate's answer for
    ``revision`` (:func:`~.calculation_note_gate.calculation_screen_outdated`):
    when the gate would refuse it as stale, the form carries that one blocking
    note and offers a recalculation. ``calculation_filed_before_grade_cap`` is
    the gate's answer for a revision filed before screens existed
    (:func:`~.calculation_note_gate.calculation_filed_before_grade_cap`): the
    capped box whose figure keeps its export refused, so the form carries that
    blocking note and offers a recalculation in place of the recorded state.

    ``resolutions`` are the source disagreements the operator accepted. The
    form holds filing on a disagreement exactly as the gate does, so one a
    resolution covers is no longer held.

    ``redeme`` is the filer's stated inscription in the Registro de devolución
    mensual. The settlement result needs it to say whether a negative IVA
    result may be elected as a refund in this period or only carried forward;
    its default leaves the answer unstated rather than assuming one.

    ``filed_findings`` are what the caller found about a declaration recorded
    as filed since it was filed, such as profile facts it rested on that were
    edited. Verify returns a filed declaration's sealed report unchanged, so
    these reach the filer only here, after the report's own findings.

    ``known_truths`` are the yes-or-no facts already known for the filer, by
    boolean binding. They decide which guarded inputs the calculation is
    certain to refuse without (:func:`~.calculation_required_inputs.calculation_required_inputs`),
    so the form asks for those; without them it asks only for inputs no guard
    can skip.

    ``producer_values`` are admitted context facts supplied by the caller.
    Only a layout's declared context fields select them; they never replace
    saved casillas or binding edits. Omit current facts for a historical form.

    ``profile_binding_values`` are admitted current profile scalars for declared
    read-only binding context. They fill only a binding with no saved answer;
    saved empty, false and zero answers retain precedence.

    Raises:
        ModeloWorkFormLayoutError: the layout places a casilla the revision does
            not define, places one twice, or leaves one without a placement.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
        :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            The pinned registry snapshot supplying the selected modelo revision.
    """
    sources = _note_sources(
        revision, calculation_diagnostics, calculation_screen_outdated, calculation_filed_before_grade_cap
    )
    context = _work_form_context(
        review=review,
        snapshot=snapshot,
        revision=revision,
        permitted_surface=permitted_surface,
        entered_casilla_ids=entered_casilla_ids,
        overridden_binding_ids=overridden_binding_ids,
        language=language,
        sources=sources,
        element_names=element_names,
        known_truths=known_truths,
        resolutions=resolutions,
        redeme=redeme,
    )
    summary = summarize_work_form(
        context,
        layout,
        notes=(sources, calculation_diagnostics is not None),
        deadline=deadline,
        last_export=last_export,
        verification_out_of_date=verification_out_of_date,
        filed_findings=filed_findings,
        calculation_sources_arrived=calculation_sources_arrived,
    )
    reason = inspection_reason(layout, context)
    if reason is not None or layout is None:
        if reason is None:
            raise ValueError("usable form layout is absent")
        return _worded(
            build_inspection_only_form(summary, context, snapshot, reason, aeat_data_imported_at=aeat_data_imported_at)
        )
    return _worded(
        _projected_work_form(
            summary,
            layout=layout,
            context=context,
            producer_values=producer_values,
            profile_binding_values=profile_binding_values,
            aeat_data_imported_at=aeat_data_imported_at,
        )
    )


def summarize_modelo_work_form(
    *,
    review: ModeloWorkReview,
    snapshot: RegistrySnapshot,
    layout: FormLayoutDefinition | None,
    revision: CalculationRevision | None,
    entered_casilla_ids: frozenset[CasillaId] | None,
    overridden_binding_ids: frozenset[BindingId] | None,
    language: OutputLanguage,
    deadline: ModeloFormDeadline | None = None,
    calculation_diagnostics: tuple[CalculationSourceDiagnostic, ...] | None = None,
    element_names: Mapping[str, str] | None = None,
    calculation_screen_outdated: bool = False,
    calculation_filed_before_grade_cap: CasillaId | None = None,
    known_truths: Mapping[BindingId, bool] | None = None,
    resolutions: SourceDisagreementResolutions = NO_SOURCE_DISAGREEMENT_RESOLUTIONS,
    redeme: RedemeEnrolmentState = RedemeEnrolmentState.UNSTATED,
    filed_findings: tuple[ModeloVerificationFinding, ...] = (),
    last_export: ModeloFormExport | None = None,
    verification_out_of_date: bool = False,
    calculation_sources_arrived: bool = False,
) -> ModeloWorkFormSummary:
    """Classify one work review against its revision's declared layout, without presenting a field.

    It is the summary :func:`build_modelo_work_form` presents, taken from the
    same arguments, which mean what they mean there. Nothing it holds depends
    on what may be edited, so no edit surface is taken.

    Parameter types: ``snapshot`` (:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`),
    ``revision`` (:class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`).

    Raises:
        ModeloWorkFormLayoutError: the layout places a casilla the revision does
            not define, places one twice, or leaves one without a placement.
    """
    sources = _note_sources(
        revision, calculation_diagnostics, calculation_screen_outdated, calculation_filed_before_grade_cap
    )
    context = _work_form_context(
        review=review,
        snapshot=snapshot,
        revision=revision,
        permitted_surface=None,
        entered_casilla_ids=entered_casilla_ids,
        overridden_binding_ids=overridden_binding_ids,
        language=language,
        sources=sources,
        element_names=element_names,
        known_truths=known_truths,
        resolutions=resolutions,
        redeme=redeme,
    )
    return summarize_work_form(
        context,
        layout,
        notes=(sources, calculation_diagnostics is not None),
        deadline=deadline,
        last_export=last_export,
        verification_out_of_date=verification_out_of_date,
        filed_findings=filed_findings,
        calculation_sources_arrived=calculation_sources_arrived,
    )


def _note_sources(
    revision: CalculationRevision | None,
    calculation_diagnostics: tuple[CalculationSourceDiagnostic, ...] | None,
    screen_outdated: bool,
    filed_before_grade_cap: CasillaId | None,
) -> tuple[NoteSource, ...]:
    return collect_note_sources(
        revision,
        calculation_diagnostics,
        screen_outdated=screen_outdated,
        filed_before_grade_cap=filed_before_grade_cap,
    )


def _work_form_context(
    *,
    review: ModeloWorkReview,
    snapshot: RegistrySnapshot,
    revision: CalculationRevision | None,
    permitted_surface: tuple[ModeloEditPermittedSurfaceEntryV1, ...] | None,
    entered_casilla_ids: frozenset[CasillaId] | None,
    overridden_binding_ids: frozenset[BindingId] | None,
    language: OutputLanguage,
    sources: tuple[NoteSource, ...],
    element_names: Mapping[str, str] | None,
    known_truths: Mapping[BindingId, bool] | None,
    resolutions: SourceDisagreementResolutions,
    redeme: RedemeEnrolmentState,
) -> WorkFormContext:
    return WorkFormContext(
        review=review,
        snapshot=snapshot,
        revision=revision,
        permitted_surface=permitted_surface,
        entered_casilla_ids=entered_casilla_ids,
        overridden_binding_ids=overridden_binding_ids,
        language=language,
        unworked_casilla_ids=frozenset(
            casilla_id
            for reason, casilla_id, *_ in sources
            if reason in UNWORKED_BOX_REASONS and casilla_id is not None
        ),
        element_names=element_names,
        known_truths=known_truths,
        resolutions=resolutions,
        redeme=redeme,
    )


def _projected_work_form(
    summary: ModeloWorkFormSummary,
    *,
    layout: FormLayoutDefinition,
    context: WorkFormContext,
    producer_values: Mapping[FilingProducerKey, ModeloFormScalar] | None,
    profile_binding_values: Mapping[BindingId, ModeloFormScalar] | None,
    aeat_data_imported_at: datetime | None,
) -> ModeloWorkForm:
    """Present the summary's pages, working figures, unplaced casillas and answers at the layout's placements."""
    walk = LayoutWalker(
        layout, context, summary, producer_values=producer_values, profile_binding_values=profile_binding_values
    )
    pages = tuple(walk.page(page) for page in layout.pages)
    working, unplaced, answers = _presented_details(summary, layout, context)
    every_field = (
        *(field for page in pages for section in page.sections for field in section_fields(section)),
        *working,
        *(item.field for item in unplaced),
        *answers,
    )
    return _assemble_work_form(
        summary,
        layout=layout,
        context=context,
        pages=pages,
        working=working,
        unplaced=unplaced,
        answers=answers,
        every_field=every_field,
        aeat_data_imported_at=aeat_data_imported_at,
    )


def _presented_details(
    summary: ModeloWorkFormSummary, layout: FormLayoutDefinition, context: WorkFormContext
) -> tuple[tuple[ModeloFormField, ...], tuple[ModeloFormUnplacedField, ...], tuple[ModeloFormField, ...]]:
    """The summary's working figures, unplaced casillas, each with why the design leaves it off, and answers."""
    present = layout_presenter(layout, context)
    placements = {placement.casilla_id: placement for placement in layout.placements}
    details = summary.details
    working = tuple(present(facts) for facts in details.working_figures)
    unplaced = tuple(
        ModeloFormUnplacedField(field=present(facts), reason=placements[facts_casilla_id(facts)].unplaced_reason)
        for facts in details.unplaced
    )
    return working, unplaced, tuple(project_binding_field(facts, context) for facts in details.answers)


def _assemble_work_form(
    summary: ModeloWorkFormSummary,
    *,
    layout: FormLayoutDefinition,
    context: WorkFormContext,
    pages: tuple[ModeloFormPage, ...],
    working: tuple[ModeloFormField, ...],
    unplaced: tuple[ModeloFormUnplacedField, ...],
    answers: tuple[ModeloFormField, ...],
    every_field: tuple[ModeloFormField, ...],
    aeat_data_imported_at: datetime | None,
) -> ModeloWorkForm:
    review = context.review
    language = context.language
    provenance = (
        ModeloFormLayoutProvenance.REVIEWED
        if layout.review.state is FormLayoutReviewState.REVIEWED
        else ModeloFormLayoutProvenance.GENERATED
    )
    return ModeloWorkForm(
        modelo=summary.modelo,
        filing_year=summary.filing_year,
        period=summary.period,
        registry_revision_id=summary.registry_revision_id,
        year_projection=year_projection(
            context.snapshot, modelo=str(review.modelo), period=review.period.registry_token, language=language
        ),
        work_unit_id=summary.work_unit_id,
        calculation_revision_id=summary.calculation_revision_id,
        language=language,
        layout_provenance=provenance,
        seed_source=layout.seed_source,
        pages=with_record_attention(pages, summary.issues, recorded=context.filed or summary.filing is not None),
        outline=form_outline(
            layout.outline,
            pages,
            language,
            filed=context.filed,
            unplaced=unplaced,
            working_figures=working,
            answers=answers,
        ),
        working_figures=working,
        unplaced=unplaced,
        answers=answers,
        result_addresses=summary.result_addresses,
        withholding_credits=withholding_credits(every_field, context.snapshot.revision),
        withholding_credits_heading=withholding_credits_heading(every_field, language),
        counts=summary.counts,
        progress=review.progress,
        operator_entries_known=context.entered is not None,
        edit_admitted=context.surface is not None,
        verification=summary.verification,
        issues=summary.issues,
        calculation_notes=summary.calculation_notes,
        calculation_notes_held=summary.calculation_notes_held,
        result=summary.result,
        deadline=summary.deadline,
        aeat_data=project_aeat_data(context, aeat_data_imported_at),
        verification_out_of_date=summary.verification_out_of_date,
        calculation_sources_arrived=summary.calculation_sources_arrived,
        filing=summary.filing,
        last_export=summary.last_export,
        edit_closure=summary.edit_closure,
        carry_attestations=form_carry_attestations(context),
        prior_value_attestations=form_prior_value_attestations(context),
    )


def _worded(form: ModeloWorkForm) -> ModeloWorkForm:
    """The form said in its language: every field's words, then where every value comes from."""
    worded = worded_form(form)
    return worded.model_copy(update={"source_groups": worded_source_groups(worded)})


__all__ = ["build_modelo_work_form", "summarize_modelo_work_form"]
