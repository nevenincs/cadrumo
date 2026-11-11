"""The export's refusals for a field value the official record design cannot render or write."""

from __future__ import annotations

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.filing.errors import FilingExportFieldUnrenderableError, FilingExportUnrepresentableCharacterError
from .export_contracts import (
    ModeloExportCommand,
    ModeloExportFieldUnrenderableError,
    ModeloExportUnrepresentableCharacterError,
)
from .preconditions import build_modelo_precondition_failure, build_modelo_precondition_failure_for_scenario


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


def export_unrepresentable_character_refusal(
    command: ModeloExportCommand, exc: FilingExportUnrepresentableCharacterError
) -> ModeloExportUnrepresentableCharacterError:
    """Refuse a text value holding a character its record design cannot write, naming the slot and the character.

    Dropping or replacing the character would declare something else, so
    nothing is written. The value is shown as the record's rule wrote it,
    because it is what the filer recorded and has to find again.
    """
    context: dict[str, object] = {
        "calculation_revision_id": command.calculation_revision_id,
        "field_id": exc.field_id,
        "character": exc.character,
        "code_point": f"U+{ord(exc.character):04X}",
        "field_value": exc.rendered,
    }
    if exc.record_type is not None:
        context["record_type"] = exc.record_type
    failure = build_modelo_precondition_failure(
        subject_leaf_key="modelo.export",
        condition_id="modelo.export.text_value.writable",
        scenario_id="modelo.export.text_value.unrepresentable_character",
        evidence_id="modelo.export.text_value",
        evidence_values={
            "calculation_revision_id": command.calculation_revision_id,
            "field_id": exc.field_id,
            "code_point": f"U+{ord(exc.character):04X}",
        },
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )
    if exc.first_position is None or exc.field_length is None or exc.record_type is None:
        return ModeloExportUnrepresentableCharacterError(context=context, precondition_failure=failure)
    return ModeloExportUnrepresentableCharacterError(
        translated_message="application.modelo.errors.export_text_unrepresentable_character",
        context={
            **context,
            "first_position": exc.first_position,
            "last_position": exc.first_position + exc.field_length - 1,
        },
        precondition_failure=failure,
    )
