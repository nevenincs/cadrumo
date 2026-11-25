"""Classify one declaration's form into the facts its filing state rests on, once, for every read.

:func:`summarize_work_form` is the single owner of a form's filing facts: what
each box holds and where it stands, what every page asks, the check's findings
and the calculation's notes with the boxes they name, the settlement result and
the full field of each box that states it. The filing-state read stops here;
the form read presents the same summary (:func:`~.work_form.build_modelo_work_form`).
"""

from __future__ import annotations

from collections.abc import Callable

from ...domain.calculations.registry.schema_form_layouts import FormLayoutDefinition
from ...domain.modelos.verification_report import ModeloVerificationFinding
from .work_form_context import WorkFormContext
from .work_form_counts import count_work_form_fields
from .work_form_declaration_facts import ModeloFormDeadline, ModeloFormEditClosure, ModeloFormExport
from .work_form_facts import (
    ModeloFormDetailFacts,
    ModeloFormFieldFacts,
    ModeloFormPageFacts,
    ModeloFormRecordBlock,
    ModeloWorkFormSummary,
)
from .work_form_field_projection import facts_casilla_id
from .work_form_field_vocabulary import ModeloFormCasillaAddressV1
from .work_form_findings import ModeloFormIssue
from .work_form_inspection import (
    inspection_facts,
    inspection_presenter,
    project_filing_summary,
    project_settlement_result,
    result_casilla_ids,
)
from .work_form_layout_facts import layout_presenter, walk_layout_facts
from .work_form_models import ModeloFormField, ModeloFormInspectionReason
from .work_form_next_step import stated_result_casilla_ids
from .work_form_notes import NoteSource, project_calculation_notes, project_verification_issues


def inspection_reason(
    layout: FormLayoutDefinition | None, context: WorkFormContext
) -> ModeloFormInspectionReason | None:
    """Why the form can only be inspected, when its revision has no usable declared layout; ``None`` when it has."""
    if layout is None:
        return ModeloFormInspectionReason.LAYOUT_ABSENT
    if layout.revision_id != context.snapshot.revision.id:
        return ModeloFormInspectionReason.LAYOUT_FOR_ANOTHER_REVISION
    return None


def filed_issues(
    context: WorkFormContext, filed_findings: tuple[ModeloVerificationFinding, ...]
) -> tuple[ModeloFormIssue, ...]:
    """The caller's findings about a filed declaration, shown only while the form shows one."""
    return tuple(ModeloFormIssue(finding=finding) for finding in filed_findings) if context.filed else ()


def summarize_work_form(
    context: WorkFormContext,
    layout: FormLayoutDefinition | None,
    *,
    notes: tuple[tuple[NoteSource, ...], bool],
    deadline: ModeloFormDeadline | None,
    last_export: ModeloFormExport | None,
    verification_out_of_date: bool,
    filed_findings: tuple[ModeloVerificationFinding, ...],
    calculation_sources_arrived: bool = False,
) -> ModeloWorkFormSummary:
    """Classify the form ``layout`` arranges, or, without a usable one, every casilla in official box order.

    ``notes`` are the latest calculation's note sources and whether this
    session ran it. ``last_export`` and ``verification_out_of_date`` are the
    loader's reads of the declaration's latest file and of whether the
    movements the last check read changed since, and
    ``calculation_sources_arrived`` its read of whether an earlier return the
    calculation found nothing of is held now.

    Raises:
        ModeloWorkFormLayoutError: the layout places a casilla the revision does
            not define, places one twice, or leaves one without a placement.
    """
    pages, details, present, alias_blocks, records = _classified(layout, context)
    every = (
        *(field for page in pages for field in page.fields),
        *details.working_figures,
        *details.unplaced,
        *details.answers,
    )
    review = context.review
    result = project_settlement_result(context, every)
    result_addresses = result_casilla_ids(context)
    return ModeloWorkFormSummary(
        modelo=review.modelo,
        filing_year=review.filing_year,
        period=review.period,
        registry_revision_id=context.snapshot.revision.id,
        work_unit_id=review.work_unit_id,
        calculation_revision_id=review.calculation_revision_id,
        language=context.language,
        pages=pages,
        details=details,
        counts=count_work_form_fields(every, filed=context.filed),
        result_addresses=result_addresses,
        result=result,
        issues=(*project_verification_issues(review, every), *filed_issues(context, filed_findings)),
        calculation_notes=project_calculation_notes(context, notes[0], every),
        calculation_notes_held=notes[1],
        verification=review.verification_outcome,
        verification_out_of_date=verification_out_of_date,
        filing=project_filing_summary(context),
        edit_closure=ModeloFormEditClosure.RECORDED_AS_FILED if context.filed else None,
        last_export=last_export,
        deadline=deadline,
        presented=_presented_results(every, stated_result_casilla_ids(result_addresses, result), present),
        alias_blocks=alias_blocks,
        records=records,
        calculation_sources_arrived=calculation_sources_arrived,
    )


def _classified(
    layout: FormLayoutDefinition | None, context: WorkFormContext
) -> tuple[
    tuple[ModeloFormPageFacts, ...],
    ModeloFormDetailFacts,
    Callable[[ModeloFormFieldFacts], ModeloFormField],
    frozenset[tuple[str, str, str]],
    tuple[ModeloFormRecordBlock, ...],
]:
    """The classified pages and details, how a box is presented, and the layout's repeats and tables of records.

    A usable layout's printed box numbers are recorded on ``context`` first, so
    every field either read presents names a box as the layout prints it.
    """
    if inspection_reason(layout, context) is not None or layout is None:
        no_repeats: frozenset[tuple[str, str, str]] = frozenset(())
        no_records: tuple[ModeloFormRecordBlock, ...] = ()
        return inspection_facts(context), ModeloFormDetailFacts(), inspection_presenter(context), no_repeats, no_records
    context.placed_boxes = {
        placement.casilla_id: placement.box_number
        for placement in layout.placements
        if placement.box_number is not None
    }
    walk, pages, details = walk_layout_facts(layout, context)
    return pages, details, layout_presenter(layout, context), frozenset(walk.alias_blocks), tuple(walk.records)


def _presented_results(
    every: tuple[ModeloFormFieldFacts, ...],
    wanted: frozenset[str],
    present: Callable[[ModeloFormFieldFacts], ModeloFormField],
) -> dict[str, ModeloFormField]:
    """The full field of each box that states the result, the first the form shows of each."""
    presented: dict[str, ModeloFormField] = {}
    for facts in every:
        if not isinstance(facts.address, ModeloFormCasillaAddressV1):
            continue
        casilla_id = facts_casilla_id(facts)
        if casilla_id in wanted and casilla_id not in presented:
            presented[casilla_id] = present(facts)
    return presented


__all__ = [
    "filed_issues",
    "inspection_reason",
    "summarize_work_form",
]
