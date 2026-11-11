"""The export's refusal for a field whose value the official record design cannot render."""

from __future__ import annotations

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.filing.errors import FilingExportFieldUnrenderableError
from .export_contracts import ModeloExportCommand, ModeloExportFieldUnrenderableError
from .preconditions import build_modelo_precondition_failure_for_scenario


def export_field_unrenderable_refusal(
    command: ModeloExportCommand, exc: FilingExportFieldUnrenderableError
) -> ModeloExportFieldUnrenderableError:
    """Report a design/value disagreement as an integrity defect, naming the field and casilla.

    The fault is in the export design the application carries, so the words
    say nothing was written and ask for no change to the filer's data.
    """
    context: dict[str, object] = {
        "calculation_revision_id": command.calculation_revision_id,
        "field_id": exc.field_id,
        "data_type": exc.data_type,
        "reason": exc.reason,
    }
    if exc.casilla_id is not None:
        context["casilla_id"] = exc.casilla_id
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.export",
        scenario_id="modelo.export.field.unrenderable",
        evidence_id="modelo.export.field",
        evidence_values={
            "calculation_revision_id": command.calculation_revision_id,
            "field_id": exc.field_id,
            "renderable": False,
        },
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )
    if exc.casilla_id is None:
        return ModeloExportFieldUnrenderableError(
            translated_message="errors.integrity.integrity_modelo_export_field_unrenderable_no_casilla",
            context=context,
            precondition_failure=failure,
        )
    return ModeloExportFieldUnrenderableError(context=context, precondition_failure=failure)
