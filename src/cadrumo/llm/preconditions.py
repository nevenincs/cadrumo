"""LLM-owned terminal refusal identities and fact-only verdict construction.

The LLM package owns refusals about dispatch, model output, and the transient
consent token.  These are deliberately distinct from provisioning's hardware
and installed-dependency decisions: a full on-host slot, an omitted off-host
model, and malformed model output are not memory-headroom predicates.  Each
outcome is terminal because this package has no safe way to bind an executable
CLI action from those observations.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING

from ..core import ActionEvidenceProvenance, NoRecoveryOutcome

if TYPE_CHECKING:
    from ..application.operator_actions import PreconditionVerdict


class LLMPreconditionCondition(StrEnum):
    """Closed failed-condition identities owned by LLM dispatch and readers."""

    COLUMN_MAPPING_HEADERS_PRESENT = "llm.column_mapping.headers_present"
    COLUMN_MAPPING_RESPONSE_PARSEABLE = "llm.column_mapping.response_parseable"
    COLUMN_MAPPING_RESPONSE_SCHEMA_VALID = "llm.column_mapping.response_schema_valid"
    EVIDENCE_IMAGES_PRESENT = "llm.evidence.images_present"
    EVIDENCE_OFF_HOST_DISPATCH_PERMITTED = "llm.evidence.off_host_dispatch_permitted"
    EVIDENCE_RESPONSE_JSON_OBJECT = "llm.evidence.response_json_object"
    EVIDENCE_RESPONSE_SCHEMA_VALID = "llm.evidence.response_schema_valid"
    EVIDENCE_TEXT_PRESENT = "llm.evidence.text_present"
    EVIDENCE_TOKEN_BOUND = "llm.evidence.token_bound"  # noqa: S105
    EVIDENCE_TOKEN_EPHEMERAL = "llm.evidence.token_ephemeral"  # noqa: S105
    EVIDENCE_TRANSCRIPTION_NONEMPTY = "llm.evidence.transcription_nonempty"
    LOCAL_INFERENCE_SLOT_AVAILABLE = "llm.local_inference.slot_available"
    OFF_HOST_MODEL_NAMED = "llm.off_host_model.named"
    PROMPT_DEFINITION_ID_VALID = "llm.prompt_definition.id_valid"
    PROVIDER_CREDENTIALS_PRESENT = "llm.provider.credentials_present"
    PROVIDER_SELECTION_VALID = "llm.provider.selection_valid"
    REQUEST_PROMPT_NONEMPTY = "llm.request.prompt_nonempty"
    VISION_INPUT_SUPPORTED = "llm.vision.input_supported"


LLMPreconditionFact = str | int | bool
"""Locale-neutral scalar fact allowed in an LLM terminal verdict."""


def llm_no_recovery_verdict(
    condition: LLMPreconditionCondition,
    *,
    facts: Mapping[str, LLMPreconditionFact],
    provenance: ActionEvidenceProvenance,
    outcome: NoRecoveryOutcome = NoRecoveryOutcome.OPERATOR_DECISION,
) -> PreconditionVerdict:
    """Build one fact-only terminal LLM outcome at the application boundary.

    The import is deferred because application modules consume :mod:`cadrumo.llm`;
    importing the application carrier while defining this package would close that
    cycle.  The returned object is nevertheless the canonical application-owned
    verdict type used by the shared CLI resolver.
    """
    from ..application.operator_actions import no_action_precondition_verdict

    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=provenance,
        outcome=outcome,
    )


__all__ = ["LLMPreconditionCondition", "llm_no_recovery_verdict"]
