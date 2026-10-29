"""Human presentation of scenario inputs without changing calculation addresses.

Machine identity stays in the in-memory plan. It is not shipped in cells,
comments or document properties. Missing display authority is a refusal, never
an invitation to prettify an internal identifier.

:class:`ModeloRevision` declares the form and its value contracts.
:class:`RegistrySnapshot` pins the registry declarations used by the projection.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from functools import partial

from ....core.period import Period
from ....domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ....domain.calculations.registry.schema_references import LegalReference, SourceReference
from .engine import registry_sha
from .errors import CalcSheetsEngineError
from .human_cells import human_row_sets, human_rows, project_existing_cells
from .human_labels import human_labels
from .human_layout import assemble_human_layout
from .human_support import render_evidence, render_guide, render_provenance
from .human_validation import (
    human_constraints,
    legal_reference_text,
    require_label,
    source_reference_text,
    validate_human_text,
)
from .records import (
    SheetAdministrativeFrame,
    SheetCellAddress,
    SheetExportMetadata,
    SheetExportPlan,
    SheetReviewMetadata,
    SheetTemplatePreviewMetadata,
    SheetValueCell,
    TabName,
)
from .template_source import WorkbookTemplateSource
from .workbook_exclusions import workbook_transport_controls


def human_workbook[M: (SheetExportMetadata, SheetReviewMetadata)](
    plan: SheetExportPlan[M], snapshot: RegistrySnapshot
) -> SheetExportPlan[M]:
    """Replace technical support surfaces, preserving all data and formula cells.

    The ``snapshot`` parameter uses :class:`RegistrySnapshot`, which pins
    the registry declarations used by the projection.
    """
    if isinstance(plan.metadata, SheetReviewMetadata):
        raise CalcSheetsEngineError("human form presentation requires a verified scenario plan")
    if plan.human_presentation:
        raise CalcSheetsEngineError("human workbook is already projected")
    if plan.metadata.registry_sha != registry_sha(snapshot):
        raise CalcSheetsEngineError("human workbook snapshot does not match the calculation authority")
    return _project_human_workbook(
        plan,
        revision=snapshot.revision,
        modelo_id=snapshot.modelo.id,
        frame=snapshot.filing_period or plan.metadata.period,
        legal_catalogue=snapshot.legal,
        source_catalogue=snapshot.sources,
        identity_digest=plan.metadata.registry_sha,
    )


def human_template_preview(
    plan: SheetExportPlan[SheetTemplatePreviewMetadata], source: WorkbookTemplateSource
) -> SheetExportPlan[SheetTemplatePreviewMetadata]:
    """Project a fictional template after checking its exact presentation identity."""
    if (
        plan.metadata.modelo_id != source.modelo_id
        or plan.metadata.revision_id != source.revision.id
        or plan.metadata.preview_year != source.preview_frame.filing_year
        or plan.metadata.preview_period != source.preview_frame.code
        or plan.metadata.template_digest != source.template_digest
    ):
        raise CalcSheetsEngineError("template source does not match workbook preview identity")
    return _project_human_workbook(
        plan,
        revision=source.revision,
        modelo_id=source.modelo_id,
        frame=source.preview_frame,
        legal_catalogue=source.legal,
        source_catalogue=source.sources,
        identity_digest=source.template_digest,
    )


def _project_human_workbook[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M],
    *,
    revision: ModeloRevision,
    modelo_id: str,
    frame: Period | SheetAdministrativeFrame,
    legal_catalogue: Mapping[str, LegalReference],
    source_catalogue: Mapping[str, SourceReference],
    identity_digest: str,
) -> SheetExportPlan[M]:
    """Shared presentation assembly; callers own production or preview admission."""
    if plan.human_presentation:
        raise CalcSheetsEngineError("human workbook is already projected")
    casillas = {c.id: c for c in revision.casillas}
    excluded = workbook_transport_controls(revision)
    if any(row.casilla_id in excluded for row in (*plan.evidence.contributor_rows, *plan.evidence.manual_entries)):
        raise CalcSheetsEngineError("workbook transport exclusion cannot discard recorded evidence")
    printed_boxes = {
        placement.casilla_id: placement.box_number
        for layout in revision.form_layouts
        for placement in layout.placements
    }
    labels = human_labels(revision, modelo_id, frame, plan)

    label = partial(require_label, labels)
    legal_text = partial(legal_reference_text, legal_catalogue)
    source_text = partial(source_reference_text, source_catalogue)

    rows = human_rows(plan, casillas, excluded)
    values = project_existing_cells(plan, revision, rows, excluded, printed_boxes, label)

    def emit(tab: TabName, row: int, items: tuple[str | Decimal | bool | None, ...]) -> None:
        for column, value in enumerate(items, 1):
            values.append(SheetValueCell(address=SheetCellAddress.at(tab, row, column), value=value, role="label"))

    render_guide(plan, modelo_id, frame, emit)
    render_provenance(revision, casillas, excluded, labels, emit, legal_text, source_text)
    evidence_formats = render_evidence(plan, casillas, emit, legal_text, source_text)

    constraints = human_constraints(plan.cell_constraints, casillas, excluded, legal_text)
    row_sets = human_row_sets(plan.row_sets, label)
    validate_human_text(plan, revision, values, identity_digest)
    return assemble_human_layout(plan, rows, values, constraints, row_sets, evidence_formats)
