"""The export's refusals for a field value the official record design cannot render or write."""

from __future__ import annotations

from collections.abc import Mapping

from ...core.filing_producer_key import FilingProducerKey
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...domain.filing.errors import (
    FilingExportCasillaValueRefusedError,
    FilingExportError,
    FilingExportFieldUnrenderableError,
    FilingExportIntegrityError,
    FilingExportProfileFactMissingError,
    FilingExportUnrepresentableCharacterError,
)
from ...domain.modelos.errors import ModeloError
from ..filing.export_xml_value_limits import is_xml_value_refusal
from ..filing.producer_profile_facts import (
    missing_producer_fact_names,
    missing_producer_fact_verdict,
    profile_facts_for_producer_key,
)
from ..filing.shared_owner_refusal import is_shared_owner_refusal
from ..operator_actions.models import PreconditionVerdict
from .action_errors import ModeloProfileReadinessError
from .export_contracts import (
    ModeloExportCasillaValueRefusedError,
    ModeloExportCommand,
    ModeloExportDesignIntegrityError,
    ModeloExportFieldUnrenderableError,
    ModeloExportUnrepresentableCharacterError,
)
from .preconditions import build_modelo_precondition_failure, build_modelo_precondition_failure_for_scenario
from .profile_readiness_gate import open_profile_path_step


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


def export_design_integrity_refusal(
    command: ModeloExportCommand, exc: FilingExportIntegrityError
) -> ModeloExportDesignIntegrityError:
    """Report a fault in the application's own export design as an integrity defect, keeping its served words.

    The refusal's words say what in the design disagrees; none asks for a
    change to the filer's data, because none repairs it.
    """
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.export",
        scenario_id="modelo.export.design.inconsistent",
        evidence_id="modelo.export.design",
        evidence_values={"calculation_revision_id": command.calculation_revision_id, "consistent": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )
    return ModeloExportDesignIntegrityError(
        translated_message=exc.translated_message,
        context={"calculation_revision_id": command.calculation_revision_id, **(exc.context or {})},
        precondition_failure=failure,
    )


def export_profile_fact_missing_refusal(
    command: ModeloExportCommand, exc: FilingExportProfileFactMissingError
) -> ModeloProfileReadinessError:
    """Refuse an export that needs a fact about the filer the profile does not state, keeping the refusal's door.

    The filing refusal carries the verdict that names the profile edit, or the
    operator decision where no profile question states the fact. This error
    keeps that verdict and the served words, adds the revision, and offers
    opening the first profile detail the fact is read from.
    """
    context = exc.context or {}
    verdict = exc.terminal_precondition_verdict
    profile_paths = profile_facts_for_producer_key(context.get("missing_producer_key"))
    return ModeloProfileReadinessError(
        translated_message=exc.translated_message,
        context={"calculation_revision_id": command.calculation_revision_id, **context},
        profile_precondition_verdict=verdict if isinstance(verdict, PreconditionVerdict) else None,
        next_step=open_profile_path_step(profile_paths[0]) if profile_paths else None,
    )


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


def export_casilla_value_refusal(
    command: ModeloExportCommand, exc: FilingExportCasillaValueRefusedError
) -> ModeloExportCasillaValueRefusedError:
    """Refuse a box value the design cannot write, with the door that states that box again.

    The served words say why the value cannot be written. The door binds the
    box; the export knows its calculation revision, not the work unit, so the
    operator names the work unit and the value.
    """
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.export",
        scenario_id="modelo.export.casilla_value.refused",
        evidence_id="modelo.export.casilla_value",
        evidence_values={
            "calculation_revision_id": command.calculation_revision_id,
            "casilla_id": exc.casilla_id,
            "writable": False,
        },
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        action_argument_values={"casilla_id": exc.casilla_id},
        missing_action_arguments=("work_unit_id", "value"),
    )
    return ModeloExportCasillaValueRefusedError(
        translated_message=exc.translated_message,
        context={"calculation_revision_id": command.calculation_revision_id, **(exc.context or {})},
        precondition_failure=failure,
    )


def export_design_fault_refusal(
    *, cause: str, calculation_revision_id: str | None = None
) -> ModeloExportDesignIntegrityError:
    """Report a guard only a caller or design fault reaches as the terminal integrity refusal, naming the cause.

    ``cause`` is a fixed description of the guard, never a value of the filer.
    """
    values: dict[str, str | bool] = {"consistent": False}
    context: dict[str, object] = {"cause": cause}
    if calculation_revision_id is not None:
        values["calculation_revision_id"] = calculation_revision_id
        context["calculation_revision_id"] = calculation_revision_id
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.export",
        scenario_id="modelo.export.design.inconsistent",
        evidence_id="modelo.export.design",
        evidence_values=values,
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )
    return ModeloExportDesignIntegrityError(context=context, precondition_failure=failure)


def export_taxpayer_name_missing_refusal() -> ModeloProfileReadinessError:
    """Refuse an export that states the filer's full name when the profile holds no name to compose it from.

    The door is the profile edit that names the surnames or the legal name, with
    the first of them offered as the detail to open.
    """
    producer_key = FilingProducerKey.TAXPAYER_SURNAMES_OR_LEGAL_NAME
    return ModeloProfileReadinessError(
        translated_message="application.filing.export.errors.producer_fact_required",
        context={
            "missing_producer_key": producer_key.value,
            "fact": missing_producer_fact_names(producer_key),
        },
        profile_precondition_verdict=missing_producer_fact_verdict(producer_key),
        next_step=open_profile_path_step(profile_facts_for_producer_key(producer_key)[0]),
    )


def _unwritable_box_refusal(
    command: ModeloExportCommand,
    exc: FilingExportError,
    *,
    scenario: str,
    action_argument_values: Mapping[str, str] | None = None,
    missing_action_arguments: tuple[str, ...] = (),
) -> ModeloExportCasillaValueRefusedError:
    failure = build_modelo_precondition_failure_for_scenario(
        subject_leaf_key="modelo.export",
        scenario_id=scenario,
        evidence_id="modelo.export.casilla_value",
        evidence_values={"calculation_revision_id": command.calculation_revision_id, "writable": False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        action_argument_values=action_argument_values,
        missing_action_arguments=missing_action_arguments,
    )
    return ModeloExportCasillaValueRefusedError(
        translated_message=exc.translated_message,
        context={"calculation_revision_id": command.calculation_revision_id, **(exc.context or {})},
        precondition_failure=failure,
    )


def export_schema_value_refusal(
    command: ModeloExportCommand, exc: FilingExportError
) -> ModeloExportCasillaValueRefusedError:
    """Refuse a value the official schema does not admit, naming the box and the door that states it again.

    A box of the declaration is stated again on its work unit, the export
    knowing the box and not the work unit or the value. A refused field that is
    no box of the declaration is the operator's decision, because no catalogued
    action reaches it.
    """
    context = exc.context or {}
    box = context.get("box")
    if isinstance(box, str) and box != context.get("field_id"):
        return _unwritable_box_refusal(
            command,
            exc,
            scenario="modelo.export.casilla_value.refused",
            action_argument_values={"casilla_id": box},
            missing_action_arguments=("work_unit_id", "value"),
        )
    return _unwritable_box_refusal(command, exc, scenario="modelo.export.schema_field.refused")


def export_shared_cells_refusal(
    command: ModeloExportCommand, exc: FilingExportError
) -> ModeloExportCasillaValueRefusedError:
    """Refuse boxes whose value the design would write into cells not confirmed to mean the same thing.

    The registry owner adjudicates the shared cells, so no catalogued action repairs it.
    """
    return _unwritable_box_refusal(command, exc, scenario="modelo.export.shared_cells.unadjudicated")


def export_field_level_refusal(command: ModeloExportCommand, exc: FilingExportError) -> ModeloError | None:
    """Return the refusal for a value the record design cannot write, or ``None`` for any other failure."""
    if isinstance(exc, FilingExportUnrepresentableCharacterError):
        return export_unrepresentable_character_refusal(command, exc)
    if isinstance(exc, FilingExportFieldUnrenderableError):
        return export_field_unrenderable_refusal(command, exc)
    if isinstance(exc, FilingExportIntegrityError) and exc.translated_message is not None:
        return export_design_integrity_refusal(command, exc)
    if isinstance(exc, FilingExportProfileFactMissingError):
        return export_profile_fact_missing_refusal(command, exc)
    if isinstance(exc, FilingExportCasillaValueRefusedError):
        return export_casilla_value_refusal(command, exc)
    if is_xml_value_refusal(exc):
        return export_schema_value_refusal(command, exc)
    if is_shared_owner_refusal(exc):
        return export_shared_cells_refusal(command, exc)
    return None
