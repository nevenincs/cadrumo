"""Build inspection-only and result projections for a Modelo work form."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .work_form_context import WorkFormContext

from collections.abc import Iterable
from datetime import datetime
from typing import Final

from ...core.casilla_id import CasillaId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_form_layouts import FormPageCondition
from .calculation_report import CalculationReportRowRole
from .caller_context import caller_context_of
from .work_form_counts import count_work_form_fields
from .work_form_field_projection import project_casilla_field
from .work_form_field_state import casilla_field_role
from .work_form_localization import localized_heading
from .work_form_models import (
    ModeloFormAeatData,
    ModeloFormCasillaAddressV1,
    ModeloFormDeadline,
    ModeloFormEditability,
    ModeloFormEditClosure,
    ModeloFormField,
    ModeloFormFieldBlock,
    ModeloFormFiling,
    ModeloFormInspectionReason,
    ModeloFormLayoutProvenance,
    ModeloFormPage,
    ModeloFormResult,
    ModeloFormSection,
    ModeloWorkForm,
)
from .work_form_notes import project_calculation_notes, project_verification_issues
from .work_form_result import settlement_result

_INSPECTION_PAGE_ID: Final[str] = "inspection"

_INSPECTION_HEADING_LOCALE_KEY: Final[str] = "application.modelo.work_form.inspection_heading"


def result_casilla_ids(context: WorkFormContext) -> tuple[CasillaId, ...]:
    """Return the review's casillas declared as settlement results, in review order."""
    return tuple(
        row.casilla_id for row in context.review.casillas if casilla_field_role(row) is CalculationReportRowRole.RESULT
    )


def project_settlement_result(context: WorkFormContext, fields: Iterable[ModeloFormField]) -> ModeloFormResult | None:
    """The settlement box, printed where the form shows it."""
    result = settlement_result(
        str(context.review.modelo), context.snapshot.revision, context.rows, context.review.period
    )
    if result is None:
        return None
    box = next(
        (
            field.box
            for field in fields
            if isinstance(field.address, ModeloFormCasillaAddressV1) and field.address.casilla_id == result.casilla_id
        ),
        None,
    )
    return result.model_copy(update={"box": box})


def project_aeat_data(context: WorkFormContext, imported_at: datetime | None) -> ModeloFormAeatData | None:
    """The AEAT tax data the current calculation replays, when it replays any."""
    revision = context.revision
    snapshot_id = None if revision is None else caller_context_of(revision).borrador_snapshot_id
    if revision is None or snapshot_id is None:
        return None
    return ModeloFormAeatData(
        snapshot_id=snapshot_id, imported_at=imported_at, binding_ids=tuple(revision.bindings_sourced_from_borrador)
    )


def project_filing_summary(context: WorkFormContext) -> ModeloFormFiling | None:
    """The recorded filing, when the current calculation is recorded as filed."""
    if not context.filed:
        return None
    return ModeloFormFiling(recorded_at=None if context.revision is None else context.revision.filed_at)


def _box_order(field: ModeloFormField) -> tuple[int, int, str]:
    box = field.box
    label = field.label.text
    return (0, int(box), label) if box is not None else (1, 0, label)


def build_inspection_only_form(
    context: WorkFormContext,
    snapshot: RegistrySnapshot,
    reason: ModeloFormInspectionReason,
    *,
    deadline: ModeloFormDeadline | None,
    aeat_data_imported_at: datetime | None,
    notes: tuple[tuple[tuple[str, str | None], ...], bool],
) -> ModeloWorkForm:
    """Show every casilla read-only in official box order when no usable layout exists."""
    fields = sorted(
        (
            project_casilla_field(casilla_id, context, None).model_copy(
                update={"editability": ModeloFormEditability.INFORMATIONAL, "not_writable_reason": None}
            )
            for casilla_id in context.rows
        ),
        key=_box_order,
    )
    blocks = tuple(ModeloFormFieldBlock(id=f"field-{index}", field=field) for index, field in enumerate(fields))
    heading = localized_heading(_INSPECTION_HEADING_LOCALE_KEY, None, _INSPECTION_PAGE_ID, context.language)
    section = ModeloFormSection(
        id=f"{_INSPECTION_PAGE_ID}.all",
        heading=heading,
        official_heading=None,
        blocks=blocks,
        counts=count_work_form_fields(fields, filed=context.filed),
    )
    page = ModeloFormPage(
        id=_INSPECTION_PAGE_ID,
        heading=heading,
        official_ref=None,
        condition=FormPageCondition.ALWAYS,
        applies=True,
        sections=(section,),
        counts=count_work_form_fields(fields, filed=context.filed),
    )
    review = context.review
    return ModeloWorkForm(
        modelo=review.modelo,
        filing_year=review.filing_year,
        period=review.period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id=str(review.work_unit_id),
        calculation_revision_id=None if review.calculation_revision_id is None else str(review.calculation_revision_id),
        language=context.language,
        layout_provenance=ModeloFormLayoutProvenance.INSPECTION_ONLY,
        inspection_reason=reason,
        pages=(page,),
        result_addresses=result_casilla_ids(context),
        counts=count_work_form_fields(fields, filed=context.filed),
        progress=review.progress,
        operator_entries_known=context.entered is not None,
        edit_admitted=False,
        verification=review.verification_outcome,
        issues=project_verification_issues(review, fields),
        calculation_notes=project_calculation_notes(context, notes[0], fields),
        calculation_notes_held=notes[1],
        result=project_settlement_result(context, fields),
        deadline=deadline,
        aeat_data=project_aeat_data(context, aeat_data_imported_at),
        filing=project_filing_summary(context),
        edit_closure=ModeloFormEditClosure.RECORDED_AS_FILED if context.filed else None,
    )
