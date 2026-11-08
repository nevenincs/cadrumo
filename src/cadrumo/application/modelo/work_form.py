"""Build the editor form of one modelo work target from the review and the declared layout.

:func:`build_modelo_work_form` is a pure join. It reads the canonical work
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
    FormPlacementKind,
)
from ...domain.modelos.calculation_revision import CalculationRevision
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from .calculation_note_gate import NO_SOURCE_DISAGREEMENT_RESOLUTIONS, SourceDisagreementResolutions
from .calculation_notes import UNWORKED_BOX_REASONS
from .edit_models import (
    ModeloEditPermittedSurfaceEntryV1,
)
from .work_form_answers import answer_fields
from .work_form_context import WorkFormContext
from .work_form_counts import count_work_form_fields
from .work_form_credits import withholding_credits
from .work_form_declaration_facts import ModeloFormDeadline, ModeloFormEditClosure, year_projection
from .work_form_errors import ModeloWorkFormLayoutError
from .work_form_field_projection import project_casilla_field
from .work_form_inspection import (
    build_inspection_only_form,
    project_aeat_data,
    project_filing_summary,
    project_settlement_result,
    result_casilla_ids,
)
from .work_form_layout import LayoutWalker
from .work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormInspectionReason,
    ModeloFormLayoutProvenance,
    ModeloFormPage,
    ModeloFormScalar,
    ModeloFormUnplacedField,
    ModeloWorkForm,
    section_fields,
)
from .work_form_notes import (
    NoteSource,
    collect_note_sources,
    project_calculation_notes,
    project_verification_issues,
)
from .work_form_outline import form_outline
from .work_form_source_groups import worded_source_groups
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
) -> ModeloWorkForm:
    """Join one work review with its revision's declared layout into a classified editor form.

    ``entered_casilla_ids`` and ``overridden_binding_ids`` are the operator's own
    recorded entries on the current revision; ``None`` means the revision does
    not record them, which is different from recording none. ``permitted_surface``
    is the current edit admission's surface, or ``None`` when no admission is
    available, in which case nothing is offered for editing. A declaration
    recorded as filed offers nothing for editing whatever the admission says,
    because changing it starts a correction.

    ``deadline`` is the resolved filing deadline, and ``aeat_data_imported_at``
    when the AEAT tax data the revision replays was imported; the caller reads
    both, since neither is a fact of the review or the layout.

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
    sources = collect_note_sources(
        revision,
        calculation_diagnostics,
        screen_outdated=calculation_screen_outdated,
        filed_before_grade_cap=calculation_filed_before_grade_cap,
    )
    context = WorkFormContext(
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
    )
    held = calculation_diagnostics is not None
    inspection = _inspection_only_for_unusable_layout(
        layout,
        context,
        snapshot,
        deadline=deadline,
        aeat_data_imported_at=aeat_data_imported_at,
        notes=(sources, held),
    )
    if inspection is not None:
        return _worded(inspection)
    if layout is None:
        raise ValueError("usable form layout is absent")
    usable_layout = layout
    pages, working, unplaced = _project_layout(
        usable_layout, context, producer_values=producer_values, profile_binding_values=profile_binding_values
    )
    form_fields = [field for page in pages for section in page.sections for field in section_fields(section)]
    laid_out = [*form_fields, *working, *(item.field for item in unplaced)]
    answers = list(answer_fields(usable_layout, context, laid_out))
    every_field = [*laid_out, *answers]
    form = _assemble_work_form(
        review=review,
        snapshot=snapshot,
        layout=usable_layout,
        context=context,
        pages=pages,
        working=working,
        unplaced=unplaced,
        answers=answers,
        every_field=every_field,
        language=language,
        entered_casilla_ids=entered_casilla_ids,
        deadline=deadline,
        aeat_data_imported_at=aeat_data_imported_at,
        sources=sources,
        held=held,
    )
    return _worded(form)


def _inspection_only_for_unusable_layout(
    layout: FormLayoutDefinition | None,
    context: WorkFormContext,
    snapshot: RegistrySnapshot,
    *,
    deadline: ModeloFormDeadline | None,
    aeat_data_imported_at: datetime | None,
    notes: tuple[tuple[NoteSource, ...], bool],
) -> ModeloWorkForm | None:
    if layout is None:
        reason = ModeloFormInspectionReason.LAYOUT_ABSENT
    elif layout.revision_id != snapshot.revision.id:
        reason = ModeloFormInspectionReason.LAYOUT_FOR_ANOTHER_REVISION
    else:
        return None
    return build_inspection_only_form(
        context,
        snapshot,
        reason,
        deadline=deadline,
        aeat_data_imported_at=aeat_data_imported_at,
        notes=notes,
    )


def _project_layout(
    layout: FormLayoutDefinition,
    context: WorkFormContext,
    *,
    producer_values: Mapping[FilingProducerKey, ModeloFormScalar] | None,
    profile_binding_values: Mapping[BindingId, ModeloFormScalar] | None,
) -> tuple[tuple[ModeloFormPage, ...], list[ModeloFormField], list[ModeloFormUnplacedField]]:
    context.placed_boxes = {
        placement.casilla_id: placement.box_number
        for placement in layout.placements
        if placement.box_number is not None
    }
    walk = LayoutWalker(layout, context, producer_values=producer_values, profile_binding_values=profile_binding_values)
    pages = tuple(walk.page(page) for page in layout.pages)
    working, unplaced = _project_other_placements(layout, context, walk)
    _ensure_layout_is_total(context, walk, working, unplaced)
    return pages, working, unplaced


def _project_other_placements(
    layout: FormLayoutDefinition, context: WorkFormContext, walk: LayoutWalker
) -> tuple[list[ModeloFormField], list[ModeloFormUnplacedField]]:
    working: list[ModeloFormField] = []
    unplaced: list[ModeloFormUnplacedField] = []
    for placement in layout.placements:
        casilla_id = placement.casilla_id
        if placement.kind is FormPlacementKind.WORKING_FIGURE:
            working.append(project_casilla_field(casilla_id, context, placement))
        elif placement.kind is FormPlacementKind.UNPLACED:
            unplaced.append(
                ModeloFormUnplacedField(
                    field=project_casilla_field(casilla_id, context, placement), reason=placement.unplaced_reason
                )
            )
        elif casilla_id not in walk.seen:
            raise ModeloWorkFormLayoutError(f"casilla {casilla_id!r} is placed on the form but no page shows it")
    return working, unplaced


def _ensure_layout_is_total(
    context: WorkFormContext,
    walk: LayoutWalker,
    working: list[ModeloFormField],
    unplaced: list[ModeloFormUnplacedField],
) -> None:
    placed = walk.seen | {
        field.address.casilla_id for field in working if isinstance(field.address, ModeloFormCasillaAddressV1)
    }
    placed |= {
        item.field.address.casilla_id for item in unplaced if isinstance(item.field.address, ModeloFormCasillaAddressV1)
    }
    missing = sorted(set(context.rows) - placed)
    if missing:
        raise ModeloWorkFormLayoutError(f"the layout gives no placement to casillas {missing[:10]!r}")


def _assemble_work_form(
    *,
    review: ModeloWorkReview,
    snapshot: RegistrySnapshot,
    layout: FormLayoutDefinition,
    context: WorkFormContext,
    pages: tuple[ModeloFormPage, ...],
    working: list[ModeloFormField],
    unplaced: list[ModeloFormUnplacedField],
    answers: list[ModeloFormField],
    every_field: list[ModeloFormField],
    language: OutputLanguage,
    entered_casilla_ids: frozenset[CasillaId] | None,
    deadline: ModeloFormDeadline | None,
    aeat_data_imported_at: datetime | None,
    sources: tuple[NoteSource, ...],
    held: bool,
) -> ModeloWorkForm:
    provenance = (
        ModeloFormLayoutProvenance.REVIEWED
        if layout.review.state is FormLayoutReviewState.REVIEWED
        else ModeloFormLayoutProvenance.GENERATED
    )
    return ModeloWorkForm(
        modelo=review.modelo,
        filing_year=review.filing_year,
        period=review.period,
        registry_revision_id=snapshot.revision.id,
        year_projection=year_projection(
            snapshot, modelo=str(review.modelo), period=review.period.registry_token, language=language
        ),
        work_unit_id=review.work_unit_id,
        calculation_revision_id=review.calculation_revision_id,
        language=language,
        layout_provenance=provenance,
        seed_source=layout.seed_source,
        pages=pages,
        outline=form_outline(
            layout.outline,
            pages,
            language,
            filed=context.filed,
            unplaced=tuple(unplaced),
            working_figures=tuple(working),
            answers=tuple(answers),
        ),
        working_figures=tuple(working),
        unplaced=tuple(unplaced),
        answers=tuple(answers),
        result_addresses=result_casilla_ids(context),
        withholding_credits=withholding_credits(tuple(every_field), snapshot.revision),
        counts=count_work_form_fields(every_field, filed=context.filed),
        progress=review.progress,
        operator_entries_known=entered_casilla_ids is not None,
        edit_admitted=context.surface is not None,
        verification=review.verification_outcome,
        issues=project_verification_issues(review, every_field),
        calculation_notes=project_calculation_notes(context, sources, every_field),
        calculation_notes_held=held,
        result=project_settlement_result(context, every_field),
        deadline=deadline,
        aeat_data=project_aeat_data(context, aeat_data_imported_at),
        filing=project_filing_summary(context),
        edit_closure=ModeloFormEditClosure.RECORDED_AS_FILED if context.filed else None,
    )


def _worded(form: ModeloWorkForm) -> ModeloWorkForm:
    """The form said in its language: every field's words, then where every value comes from."""
    worded = worded_form(form)
    return worded.model_copy(update={"source_groups": worded_source_groups(worded)})


__all__ = ["build_modelo_work_form"]
