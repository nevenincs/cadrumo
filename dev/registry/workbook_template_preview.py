"""Generate human fictional forms from exact registry template selections."""

from cadrumo.application.storage.calc_sheets.engine import build_template_preview_plan
from cadrumo.application.storage.calc_sheets.form_workbook import add_template_preview_form
from cadrumo.application.storage.calc_sheets.records import (
    OperatorInputs,
    SheetExportPlan,
    SheetGuideContent,
    SheetTemplatePreviewMetadata,
)
from cadrumo.application.storage.calc_sheets.template_source import WorkbookTemplateSource
from cadrumo.core.config import override_settings
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

from .compiler.authority import compiled_bundled_authority


def build_fictional_template_workbook(
    source: WorkbookTemplateSource,
    *,
    operator_inputs: OperatorInputs,
    guide: SheetGuideContent,
) -> SheetExportPlan[SheetTemplatePreviewMetadata]:
    """Use the shared compiler and form design; input figures are explicitly fictional."""
    casillas = {casilla.id: casilla for casilla in source.revision.casillas}
    for item in operator_inputs.values:
        if item.casilla_id not in casillas:
            raise ValueError("fictional input names a casilla absent from the selected template")
        if casillas[item.casilla_id].formula is not None:
            raise ValueError("fictional input cannot replace a calculated casilla")
    with override_settings(cadrumo_output_language="es"), validating_governed_facts(compiled_bundled_authority()):
        plan = build_template_preview_plan(source, operator_inputs=operator_inputs, guide=guide)
        return add_template_preview_form(plan, source)
