"""Application-level registry workflow errors."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from cadrumo.application.operator_actions.models import PreconditionVerdict
from cadrumo.application.operator_actions.preconditions import no_action_precondition_verdict
from cadrumo.core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome


class RegistryPreconditionCondition(StrEnum):
    """Stable terminal conditions observed by registry application surfaces."""

    DIFF_REVISION_SELECTION_UNAMBIGUOUS = "registry.diff.revision_selection.unambiguous"
    DIFF_REVISION_AVAILABLE = "registry.diff.revision.available"
    EDITION_MODELO_DECLARED = "registry.edition.modelo.declared"
    EDITION_REVISION_DECLARED = "registry.edition.revision.declared"
    FILED_STATE_CASILLA_ID_CANONICAL = "registry.filed_state.casilla_id.canonical"
    FILED_STATE_CASILLA_DECLARED = "registry.filed_state.casilla.declared"
    CONFORMANCE_CLASSIFICATION_ROW_PRESENT = "registry.conformance.classification_row.present"
    CONFORMANCE_GROUNDING_ROW_PRESENT = "registry.conformance.grounding_row.present"
    MANUAL_SECTION_STRUCTURE_AVAILABLE = "registry.manuals.section_structure.available"
    MANUAL_SECTION_DECLARED = "registry.manuals.section.declared"
    TOPIC_OUTPUT_LANGUAGE_SUPPORTED = "registry.topics.output_language.supported"
    CITATION_REFERENCE_AVAILABLE = "registry.citations.reference.available"
    MANUAL_ID_SUPPORTED = "registry.manuals.id.supported"
    MANUAL_RULE_KIND_SUPPORTED = "registry.manuals.rule_kind.supported"


def registry_terminal_refusal(
    *,
    condition: RegistryPreconditionCondition,
    context: Mapping[str, object],
    facts: Mapping[str, str | int | bool],
    provenance: ActionEvidenceProvenance,
    outcome: NoRecoveryOutcome,
    translated_message: str | None = None,
) -> RegistryApplicationInputError:
    """Attach one caller-classified no-action terminal verdict to a registry refusal."""
    return RegistryApplicationInputError(
        context=context,
        translated_message=translated_message,
        precondition_verdict=no_action_precondition_verdict(
            condition_id=condition.value,
            facts=facts,
            provenance=provenance,
            outcome=outcome,
        ),
    )


class RegistryApplicationError(Exception):
    """Development-only refusal emitted while composing registry conformance."""

    def __init__(
        self,
        *,
        context: Mapping[str, object],
        precondition_verdict: PreconditionVerdict,
        translated_message: str | None = None,
    ) -> None:
        self.context = dict(context)
        self.precondition_verdict = precondition_verdict
        self.translated_message = translated_message
        super().__init__(translated_message or precondition_verdict.condition_id)


class RegistryApplicationInputError(RegistryApplicationError):
    """Raised when registry application input cannot be executed."""


__all__ = [
    "RegistryApplicationError",
    "RegistryApplicationInputError",
    "RegistryPreconditionCondition",
    "registry_terminal_refusal",
]
