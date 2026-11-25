"""Failed-precondition carriers of the comparison, resolution, solicitud and election refusals."""

from __future__ import annotations

from collections.abc import Mapping

from ...core.operator_action_enums import ActionEvidenceProvenance
from ..operator_actions.catalogue import lookup_action
from .action_errors import (
    ModeloPriorDomiciliationElectionRefusedError,
    amendment_evidence_missing_precondition,
)
from .declaration_refusal_profiles import (
    DECLARATION_REFUSAL_SPECS,
    DeclarationRefusalCause,
    scenario_id,
)
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario


def declaration_refusal_failure(
    cause: DeclarationRefusalCause,
    *,
    action_arguments: Mapping[str, str | int] | None = None,
    provenance: ActionEvidenceProvenance = ActionEvidenceProvenance.APPLICATION_STATE,
) -> ModeloPreconditionFailure:
    """Build the declared verdict of ``cause``.

    A cause that opens a catalogued action binds the arguments the refusal site
    knows and leaves the others to the operator; a cause that names no action
    carries none.
    """
    spec = DECLARATION_REFUSAL_SPECS[cause]
    known: dict[str, str | int] = {}
    missing: tuple[str, ...] = ()
    if spec.action_id is not None:
        declared = tuple(item.argument_name for item in lookup_action(spec.action_id).argument_specifications)
        known = {name: value for name, value in (action_arguments or {}).items() if name in declared}
        missing = tuple(name for name in dict.fromkeys(declared) if name not in known)
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=spec.leaf,
        scenario_id=scenario_id(cause),
        evidence_id=f"{spec.leaf}.{cause.value}",
        evidence_values={spec.sound: False},
        provenance=provenance,
        action_argument_values=known or None,
        missing_action_arguments=missing,
    )


def prior_domiciliation_refusal(
    cause: DeclarationRefusalCause,
    message: str | None = None,
    *,
    translated_message: str | None = None,
    context: Mapping[str, object] | None = None,
    action_arguments: Mapping[str, str | int] | None = None,
) -> ModeloPriorDomiciliationElectionRefusedError:
    """Return the prior-domiciliation election refusal for ``cause`` with its words and door."""
    return ModeloPriorDomiciliationElectionRefusedError(
        message,
        context=context,
        translated_message=translated_message,
        precondition_failure=declaration_refusal_failure(cause, action_arguments=action_arguments),
    )


def prior_domiciliation_baseline_unevidenced_refusal(
    message: str,
    *,
    work_unit_id: str,
    baseline_filing_record_id: str,
) -> ModeloPriorDomiciliationElectionRefusedError:
    """Return the refusal of a baseline filing AEAT has not attested, which importing its justificante settles."""
    return ModeloPriorDomiciliationElectionRefusedError(
        message,
        context={"baseline_filing_record_id": baseline_filing_record_id},
        precondition_failure=amendment_evidence_missing_precondition(
            subject_leaf_key="modelo.export",
            work_unit_id=work_unit_id,
            filing_record_id=baseline_filing_record_id,
        ),
    )


__all__ = [
    "declaration_refusal_failure",
    "prior_domiciliation_baseline_unevidenced_refusal",
    "prior_domiciliation_refusal",
]
