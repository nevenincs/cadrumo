"""Project declared registry forms onto the shared, transport-neutral workbook.

The form is a read-only presentation of existing calculation cells. It never
reconstructs fiscal formulas, invents data, or infers official page structure.

:class:`CalculationRevision` holds the saved calculation and its evidence.
:class:`ModeloRevision` declares the form and its value contracts.
:class:`RegistrySnapshot` pins the registry declarations used by the projection.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from ....core.period import Period
from ....domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ....domain.calculations.registry.schema_form_layouts import (
    FormContextFieldBlock,
    FormLayoutDefinition,
    FormRepeatingGroupBlock,
)
from ....domain.modelos.calculation_revision import CalculationRevision
from ...export.review_form_data import ReviewSavedForm
from ...filing.export_producer import filing_producer_values
from ...filing.producer_snapshot import FilingProducerSnapshot
from ...modelo.work_form_context_values import form_context_value
from ...modelo.work_form_models import ModeloFormRepeatingRow, ModeloFormScalar
from ...modelo.work_form_records import saved_form_records
from .engine import registry_sha
from .errors import CalcSheetsEngineError
from .form_authority import form_binding_addresses, validate_form_layout
from .form_builder import FormBuilder
from .form_preview_context import preview_context
from .human_workbook import human_template_preview, human_workbook
from .records import (
    SheetAdministrativeFrame,
    SheetCellAddress,
    SheetColumnWidth,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFrozenView,
    SheetProtectedRange,
    SheetReviewMetadata,
    SheetTemplatePreviewMetadata,
    TabName,
)
from .template_source import WorkbookTemplateSource
from .theme import FORM_FONT_FAMILY, StyleRole


def _admit_scenario_form(
    metadata: SheetExportMetadata,
    tabs: tuple[TabName, ...],
    snapshot: RegistrySnapshot,
    revision: CalculationRevision | None,
) -> FormLayoutDefinition:
    if TabName.FORM in tabs:
        raise CalcSheetsEngineError("workbook already contains a form projection")
    if (
        metadata.modelo_id != snapshot.modelo.id
        or metadata.revision_id != snapshot.revision.id
        or metadata.filing_year != snapshot.filing_year
        or metadata.period.code != snapshot.period
    ):
        raise CalcSheetsEngineError("form snapshot does not match workbook coordinate")
    layouts = snapshot.revision.form_layouts
    if len(layouts) != 1:
        raise CalcSheetsEngineError("form projection requires exactly one declared revision layout")
    layout = layouts[0]
    validate_form_layout(layout, snapshot.revision)
    if metadata.registry_sha != registry_sha(snapshot):
        raise CalcSheetsEngineError("form snapshot content does not match workbook registry identity")
    if revision is not None and revision.registry_snapshot_ref != snapshot.snapshot_ref:
        raise CalcSheetsEngineError("saved repeating rows belong to another registry coordinate")

    return layout


def add_form_workbook[M: (SheetExportMetadata, SheetReviewMetadata)](
    plan: SheetExportPlan[M],
    snapshot: RegistrySnapshot,
    *,
    revision: CalculationRevision | None = None,
    producer_snapshot: FilingProducerSnapshot | None = None,
) -> SheetExportPlan[M]:
    """Add a complete registry-declared form, retaining original cell addresses.

    Scenario plans link to their existing inputs/calculations. Saved review
    plans are refused until their exact registry identity and value mapping
    can be verified. Missing figures stay visibly unknown. Generated layout
    provenance is always disclosed.

    The ``revision`` parameter uses :class:`CalculationRevision`, which holds the saved calculation and its evidence.
    The ``snapshot`` parameter uses :class:`RegistrySnapshot`, which pins
    the registry declarations used by the projection.
    """
    if isinstance(plan.metadata, SheetReviewMetadata):
        raise CalcSheetsEngineError("saved review baseline requires verified registry identity and value mapping")
    layout = _admit_scenario_form(plan.metadata, plan.tabs, snapshot, revision)

    def context(block: FormContextFieldBlock) -> ModeloFormScalar:
        return form_context_value(snapshot, block, producer_snapshot=producer_snapshot, revision=revision)

    def records(block: FormRepeatingGroupBlock) -> tuple[bool, tuple[ModeloFormRepeatingRow, ...]]:
        return saved_form_records(
            snapshot=snapshot,
            revision=revision,
            block=block,
            column_casillas=tuple(column.casilla_id for column in block.columns),
        )

    bindings = form_binding_addresses(plan, snapshot.revision)
    return _project_form(
        human_workbook(plan, snapshot),
        snapshot.revision,
        snapshot.modelo.id,
        snapshot.filing_period or plan.metadata.period,
        layout,
        bindings,
        context,
        records,
    )


def add_template_preview_form(
    plan: SheetExportPlan[SheetTemplatePreviewMetadata],
    source: WorkbookTemplateSource,
    *,
    illustrative_producer: FilingProducerSnapshot | None = None,
) -> SheetExportPlan[SheetTemplatePreviewMetadata]:
    """Render a fictional template without acquiring filing or saved-revision authority."""
    if illustrative_producer is not None and str(illustrative_producer.modelo) != source.modelo_id:
        raise CalcSheetsEngineError("illustrative form context belongs to another modelo")
    if TabName.FORM in plan.tabs:
        raise CalcSheetsEngineError("workbook already contains a form projection")
    if len(source.revision.form_layouts) != 1:
        raise CalcSheetsEngineError("form projection requires exactly one declared revision layout")
    layout = source.revision.form_layouts[0]
    validate_form_layout(layout, source.revision)
    bindings = form_binding_addresses(plan, source.revision)
    # This entry validates the full preview coordinate and digest before rendering.
    plan = human_template_preview(plan, source)
    illustrative_values = filing_producer_values(illustrative_producer) if illustrative_producer is not None else {}
    context = partial(preview_context, source, illustrative_values)

    return _project_form(
        plan,
        source.revision,
        source.modelo_id,
        source.preview_frame,
        layout,
        bindings,
        context,
        lambda block: (False, ()),
    )


def add_saved_review_form(
    plan: SheetExportPlan[SheetReviewMetadata],
    saved: ReviewSavedForm,
) -> SheetExportPlan[SheetReviewMetadata]:
    """Render original declared geometry with literal saved values and no recomputation."""
    if plan.metadata.kind != "calculation" or TabName.FORM in plan.tabs:
        raise CalcSheetsEngineError("saved form requires one calculation review without an existing form")
    snapshot = saved.rendering.registry_snapshot
    if len(snapshot.revision.form_layouts) != 1:
        raise CalcSheetsEngineError("saved form requires exactly one captured layout")
    layout = snapshot.revision.form_layouts[0]
    validate_form_layout(layout, snapshot.revision)
    contexts = {item.id: item.value for item in saved.contexts}
    records = {item.block_id: (item.known, item.rows) for item in saved.records}
    return _project_form(
        plan,
        snapshot.revision,
        snapshot.modelo.id,
        snapshot.filing_period or Period.from_year_and_code(snapshot.filing_year, snapshot.period),
        layout,
        {},
        lambda block: contexts.get(block.id),
        lambda block: records.get(block.id, (False, ())),
        saved_form=saved,
    )


def _project_form[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M],
    registry_revision: ModeloRevision,
    modelo_id: str,
    frame: Period | SheetAdministrativeFrame,
    layout: FormLayoutDefinition,
    bindings: dict[str, SheetCellAddress],
    context: Callable[[FormContextFieldBlock], ModeloFormScalar],
    records: Callable[[FormRepeatingGroupBlock], tuple[bool, tuple[ModeloFormRepeatingRow, ...]]],
    *,
    saved_form: ReviewSavedForm | None = None,
) -> SheetExportPlan[M]:
    builder = FormBuilder(plan, registry_revision, modelo_id, frame, layout, context, records, saved_form=saved_form)
    builder.binding_addresses = bindings
    builder.render()
    roles = {
        StyleRole.INPUT: StyleRole.FORM_INPUT,
        StyleRole.COMPUTED: StyleRole.FORM_COMPUTED,
        StyleRole.RESULT: StyleRole.FORM_RESULT,
        StyleRole.SECTION_BANNER: StyleRole.FORM_SECTION,
        StyleRole.HEADER: StyleRole.FORM_SECTION,
        StyleRole.BODY: StyleRole.FORM_LABEL,
    }
    updates = {
        "tabs": (TabName.FORM, *plan.tabs),
        "value_cells": (*plan.value_cells, *builder.values),
        "formula_cells": (*builder.guarded_calculations(), *builder.formulas),
        "merged_ranges": (*plan.merged_ranges, *builder.merges),
        "row_heights": (*plan.row_heights, *builder.heights),
        "styled_ranges": (
            *(r.model_copy(update={"role": roles.get(r.role, r.role)}) for r in plan.styled_ranges),
            *builder.styles,
        ),
        "font_family": FORM_FONT_FAMILY,
        "number_formats": (*plan.number_formats, *builder.formats),
        "column_widths": (
            *plan.column_widths,
            *(
                SheetColumnWidth(tab=TabName.FORM, column=i, width=width)
                for i, width in enumerate(builder.column_widths, 1)
            ),
        ),
        "frozen_views": (*plan.frozen_views, SheetFrozenView(tab=TabName.FORM, frozen_rows=4)),
        "protected_ranges": (
            *plan.protected_ranges,
            SheetProtectedRange(
                tab=TabName.FORM,
                start_row=1,
                end_row=builder.row,
                start_column=1,
                end_column=len(builder.column_widths),
                description="Formulario de consulta; los datos se modifican en las hojas de origen.",
            ),
        ),
    }
    return type(plan).model_validate({**dict(plan), **updates})


__all__ = ["add_form_workbook", "add_template_preview_form"]
