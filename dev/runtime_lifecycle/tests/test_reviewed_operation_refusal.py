"""The reviewed-operation proof tells a review it cannot prove from one the product contradicts."""

from __future__ import annotations

import json

import pytest

from cadrumo.adapters.outbound.llm.errors import LLMConfigError
from cadrumo.adapters.outbound.llm.preconditions import LLMPreconditionCondition, llm_no_recovery_verdict
from cadrumo.adapters.outbound.llm.providers.agent import model_run_refusal_error
from cadrumo.application.operations.error_detail import build_operation_error_detail
from cadrumo.core.model_roles import ModelRole
from cadrumo.core.operator_action_enums import ActionEvidenceProvenance
from cadrumo_client.contracts.model_runs import ModelRunRefusal, ModelRunRefusalCode

from ..reviewed_operation import unprovable_review_refusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: The run admits no agent service and stores no selection, so only these two refusals are expected of it.
_ABSENT_SERVICE_OR_SELECTION = frozenset({ModelRunRefusalCode.SERVICE_UNAVAILABLE, ModelRunRefusalCode.NO_SELECTION})


def _stopped_review(error: Exception) -> dict[str, object]:
    """The MCP ``result`` reply of a review stopped by ``error``, with the detail the operation records for it."""
    detail = build_operation_error_detail(error)
    reply: dict[str, object] = {"outcome": "reply", "code": "operation_not_successful"}
    if detail is not None:
        reply["error_detail"] = json.loads(detail.model_dump_json())
    return reply


@pytest.mark.parametrize("code", list(ModelRunRefusalCode))
def test_only_an_absent_service_or_selection_leaves_the_review_unproven(code: ModelRunRefusalCode) -> None:
    error = model_run_refusal_error(ModelRunRefusal(code=code), role=ModelRole.TEXT_EXTRACTION)

    classified = unprovable_review_refusal(_stopped_review(error))

    assert classified == (code if code in _ABSENT_SERVICE_OR_SELECTION else None)


def test_a_refusal_fact_under_another_condition_is_a_contradiction() -> None:
    """The fact counts only on the verdict of a refused model run, not wherever the key appears."""
    verdict = llm_no_recovery_verdict(
        LLMPreconditionCondition.AGENT_MODEL_ROLE_NAMED,
        facts={"model_run_refusal": ModelRunRefusalCode.NO_SELECTION.value},
        provenance=ActionEvidenceProvenance.APPLICATION_STATE,
    )
    error = LLMConfigError(context={"provider": "AGENT"}, precondition_verdict=verdict)

    assert unprovable_review_refusal(_stopped_review(error)) is None


def test_a_stopped_review_with_no_recorded_detail_is_a_contradiction() -> None:
    assert unprovable_review_refusal({"outcome": "reply", "code": "operation_not_successful"}) is None
    assert unprovable_review_refusal({"error_detail": {"precondition_verdict_json": "not json"}}) is None
