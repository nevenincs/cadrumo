"""The refusals of a brought-in filing or local observation, each carrying the door of its cause."""

from __future__ import annotations

from collections.abc import Mapping

from ...core.operator_action_enums import ActionEvidenceProvenance
from .action_errors import ExternalModeloImportError, ModeloLocalObservationError
from .filing_import_refusal_profiles import (
    FILING_IMPORT_REFUSAL_SPECS,
    IMPORT_ACTION_ID,
    PROFILE_EDIT_ACTION_ID,
    FilingImportRefusalCause,
    scenario_id,
)
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario

_IMPORT_ARGUMENTS = ("evidence_kind", "evidence_reference_id", "work_unit_id")


def filing_import_failure(
    cause: FilingImportRefusalCause,
    *,
    action_arguments: Mapping[str, str] | None = None,
) -> ModeloPreconditionFailure:
    """Build the declared verdict of ``cause``.

    The filing-record import binds the arguments the refusal site knows and
    leaves the others to the operator; the profile edit leaves the profile to
    the operator; any other cause names no action.
    """
    spec = FILING_IMPORT_REFUSAL_SPECS[cause]
    known: dict[str, str] = {}
    missing: tuple[str, ...] = ()
    if spec.action_id == IMPORT_ACTION_ID:
        known = {name: value for name, value in (action_arguments or {}).items() if name in _IMPORT_ARGUMENTS}
        missing = tuple(name for name in _IMPORT_ARGUMENTS if name not in known)
    elif spec.action_id == PROFILE_EDIT_ACTION_ID:
        missing = ("profile_name",)
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=spec.leaf,
        scenario_id=scenario_id(cause),
        evidence_id=f"{spec.leaf}.{cause.value}",
        evidence_values={spec.sound: False},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        action_argument_values=known or None,
        missing_action_arguments=missing,
    )


def external_import_refusal(
    cause: FilingImportRefusalCause,
    *,
    translated_message: str,
    context: Mapping[str, object] | None = None,
    action_arguments: Mapping[str, str] | None = None,
) -> ExternalModeloImportError:
    """Return the external filing import refusal for ``cause`` with its served words and door."""
    return ExternalModeloImportError(
        translated_message=translated_message,
        context=context,
        precondition_failure=filing_import_failure(cause, action_arguments=action_arguments),
    )


def local_observation_refusal(
    cause: FilingImportRefusalCause,
    *,
    translated_message: str | None = None,
    message: str | None = None,
    context: Mapping[str, object] | None = None,
) -> ModeloLocalObservationError:
    """Return the local observation refusal for ``cause`` with its words and door."""
    return ModeloLocalObservationError(
        message,
        translated_message=translated_message,
        context=context,
        precondition_failure=filing_import_failure(cause),
    )


__all__ = ["external_import_refusal", "filing_import_failure", "local_observation_refusal"]
