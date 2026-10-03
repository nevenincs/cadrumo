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
  not be worked out, which then reads as not calculated rather than as zero, and
* whether the declaration is recorded as filed, which closes it to editing and
  leaves nothing counted as still to do.

"Entered by the filer" is only ever claimed from the operator's own recorded
entries. A revision that predates them has an unknown operator record, and a
value it holds for a box the filer types is never shown as entered. It is one
to confirm where it could under-declare, in a box verification requires or
when it is not zero; an optional box holding zero reads as optional and empty.
Either way the field says the value is unattributed, because a recalculation
returns it to what the calculation gives.

The form is total: every casilla of the revision appears exactly once, on a
page, among the working figures, or in the unplaced list with its reason. A
layout that would drop or repeat a casilla is refused rather than rendered.

See Also:
    :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
        The stored calculation head carrying values, provenance and lifecycle facts.
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
        The pinned registry snapshot supplying the selected modelo revision.
"""

from __future__ import annotations

from datetime import datetime
from typing import cast

from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_form_layouts import (
    FormLayoutDefinition,
    FormLayoutReviewState,
    FormPlacementKind,
)
from ...domain.modelos.calculation_revision import CalculationRevision
from ..aggregation.source_mesh import CalculationSourceDiagnostic
from .calculation_notes import UNWORKED_BOX_REASONS
from .edit_models import (
    ModeloEditPermittedSurfaceEntryV1,
)
from .work_form_context import WorkFormContext
from .work_form_counts import count_work_form_fields
from .work_form_errors import ModeloWorkFormLayoutError
from .work_form_field_projection import project_casilla_field
from .work_form_inspection import (
    build_inspection_only_form,
    project_aeat_data,
    project_calculation_notes,
    project_filing_summary,
    project_settlement_result,
    project_verification_issues,
    result_casilla_ids,
)
from .work_form_layout import LayoutWalker
from .work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormDeadline,
    ModeloFormEditClosure,
    ModeloFormField,
    ModeloFormInspectionReason,
    ModeloFormLayoutProvenance,
    ModeloFormPage,
    ModeloFormUnplacedField,
    ModeloWorkForm,
    section_fields,
)
from .work_form_notes import collect_note_sources
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

    ``calculation_diagnostics`` are the diagnostics the latest calculation
    raised, when this session ran it; ``None`` when it did not, in which case
    only the notes that persist with the calculation are known.

    Raises:
        ModeloWorkFormLayoutError: the layout places a casilla the revision does
            not define, places one twice, or leaves one without a placement.

    See Also:
        :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`
            The stored calculation head carrying values, provenance and lifecycle facts.
        :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            The pinned registry snapshot supplying the selected modelo revision.
    """
    sources = collect_note_sources(revision, calculation_diagnostics)
    context = WorkFormContext(
        review=review,
        snapshot=snapshot,
        revision=revision,
        permitted_surface=permitted_surface,
        entered_casilla_ids=entered_casilla_ids,
        overridden_binding_ids=overridden_binding_ids,
        language=language,
        unworked_casilla_ids=frozenset(
            casilla_id for reason, casilla_id in sources if reason in UNWORKED_BOX_REASONS and casilla_id is not None
        ),
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
        return inspection
    usable_layout = cast(FormLayoutDefinition, layout)
    pages, working, unplaced = _project_layout(usable_layout, context)
    form_fields = [field for page in pages for section in page.sections for field in section_fields(section)]
    every_field = [*form_fields, *working, *(item.field for item in unplaced)]
    return _assemble_work_form(
        review=review,
        snapshot=snapshot,
        layout=usable_layout,
        context=context,
        pages=pages,
        working=working,
        unplaced=unplaced,
        every_field=every_field,
        language=language,
        entered_casilla_ids=entered_casilla_ids,
        deadline=deadline,
        aeat_data_imported_at=aeat_data_imported_at,
        sources=sources,
        held=held,
    )


def _inspection_only_for_unusable_layout(
    layout: FormLayoutDefinition | None,
    context: WorkFormContext,
    snapshot: RegistrySnapshot,
    *,
    deadline: ModeloFormDeadline | None,
    aeat_data_imported_at: datetime | None,
    notes: tuple[tuple[tuple[str, str | None], ...], bool],
) -> ModeloWorkForm | None:
    if layout is None:
        reason = ModeloFormInspectionReason.LAYOUT_ABSENT
    elif str(layout.revision_id) != str(snapshot.revision.id):
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
    layout: FormLayoutDefinition, context: WorkFormContext
) -> tuple[tuple[ModeloFormPage, ...], list[ModeloFormField], list[ModeloFormUnplacedField]]:
    context.placed_boxes = {
        str(placement.casilla_id): placement.box_number
        for placement in layout.placements
        if placement.box_number is not None
    }
    walk = LayoutWalker(layout, context)
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
        casilla_id = str(placement.casilla_id)
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
        str(field.address.casilla_id) for field in working if isinstance(field.address, ModeloFormCasillaAddressV1)
    }
    placed |= {
        str(item.field.address.casilla_id)
        for item in unplaced
        if isinstance(item.field.address, ModeloFormCasillaAddressV1)
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
    every_field: list[ModeloFormField],
    language: OutputLanguage,
    entered_casilla_ids: frozenset[CasillaId] | None,
    deadline: ModeloFormDeadline | None,
    aeat_data_imported_at: datetime | None,
    sources: tuple[tuple[str, str | None], ...],
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
        work_unit_id=str(review.work_unit_id),
        calculation_revision_id=None if review.calculation_revision_id is None else str(review.calculation_revision_id),
        language=language,
        layout_provenance=provenance,
        seed_source=layout.seed_source,
        pages=pages,
        working_figures=tuple(working),
        unplaced=tuple(unplaced),
        result_addresses=result_casilla_ids(context),
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


__all__ = ["build_modelo_work_form"]
