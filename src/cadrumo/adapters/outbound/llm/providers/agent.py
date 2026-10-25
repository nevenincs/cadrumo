"""The provider adapter that hands a request to the agent service.

The agent service resolves the person's selected cadrumo-agent lane and model
for the request's role and runs it there, on any lane the provider catalog
offers, API or CLI. This adapter never sees a key: it builds one bounded run
request, sends it through the operation's model-run port, and returns the
run's final reply text.
"""

from __future__ import annotations

from typing import override

from cadrumo_client.contracts.model_runs import (
    ModelRunAttachment,
    ModelRunBody,
    ModelRunConsentBinding,
    ModelRunHeader,
    ModelRunLane,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
)

from .....application.operations.model_runs import ModelRunPort
from .....core.config_support import LLMProvider
from .....core.model_catalogue import ModelRole
from .....core.operator_action_enums import ActionEvidenceProvenance
from ..errors import LLMConfigError, LLMConsentError, LLMError, LLMProviderError
from ..preconditions import LLMPreconditionCondition, llm_no_recovery_verdict
from ..response_json import first_json_object
from .base import ProviderAdapter, ProviderCompletion, ProviderRequest

JSON_REASK_INSTRUCTION = (
    "Your previous reply contained no JSON object. Reply with exactly one JSON object and nothing else."
)
"""Appended to the prompt for the single re-ask a reply without a JSON object earns."""

_CONFIGURATION_REFUSALS = frozenset(
    {
        ModelRunRefusalCode.SERVICE_UNAVAILABLE,
        ModelRunRefusalCode.NOT_SIGNED_IN,
        ModelRunRefusalCode.PROFILE_LOCKED,
        ModelRunRefusalCode.NO_SELECTION,
        ModelRunRefusalCode.LANE_UNAVAILABLE,
        ModelRunRefusalCode.MODEL_NOT_INSTALLED,
        ModelRunRefusalCode.INPUT_NOT_SUPPORTED,
    }
)


def lane_model_label(lane: ModelRunLane) -> str:
    """Return the model identity records carry for an agent run: its lane and model together."""
    return f"{lane.provider_id}/{lane.transport}/{lane.model}"


def model_run_refusal_error(refusal: ModelRunRefusal, *, role: ModelRole) -> LLMError:
    """Return the typed error a consumer receives for a refused model run."""
    facts: dict[str, str | int | bool] = {"model_run_refusal": refusal.code.value, "model_role": role.value}
    verdict = llm_no_recovery_verdict(
        LLMPreconditionCondition.AGENT_MODEL_RUN_COMPLETED,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
    )
    context = {"provider": LLMProvider.AGENT.value, **facts}
    if refusal.code is ModelRunRefusalCode.CONSENT_MISSING:
        return LLMConsentError(context=context, precondition_verdict=verdict)
    if refusal.code in _CONFIGURATION_REFUSALS:
        return LLMConfigError(context=context, precondition_verdict=verdict)
    return LLMProviderError(context=context)


class AgentAdapter(ProviderAdapter):
    """Run one request on the lane the agent service resolved for its role.

    The lane was resolved, and any consent bound to it, before this adapter was
    built, so the service refuses the run if it would now use another lane.
    Whether the lane accepts the request's attachments was checked against the
    catalog before dispatch; the agent still refuses at admission what it cannot
    take.
    """

    provider = LLMProvider.AGENT
    supports_images = True

    def __init__(
        self,
        *,
        port: ModelRunPort,
        role: ModelRole,
        lane: ModelRunLane,
        consent: ModelRunConsentBinding | None,
        deadline_seconds: int,
        expects_json: bool,
    ) -> None:
        """Bind the adapter to one resolved lane."""
        self._port, self._role, self._lane = port, role, lane
        self._header = ModelRunHeader(role=role.value, deadline_seconds=deadline_seconds, consent=consent)
        self._expects_json = expects_json

    @override
    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        """Run the request, asking once more when a JSON reply carried no object."""
        body = ModelRunBody(
            system=request.system,
            prompt=request.prompt,
            attachments=tuple(
                ModelRunAttachment(media_type=image.media_type.value, base64_data=image.base64_data)
                for image in request.images
            ),
            max_output_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        output = await self._run(body)
        if self._expects_json and first_json_object(output.text) is None:
            reask = body.model_copy(update={"prompt": f"{body.prompt}\n\n{JSON_REASK_INSTRUCTION}"})
            output = await self._run(reask)
            if first_json_object(output.text) is None:
                raise model_run_refusal_error(ModelRunRefusal(code=ModelRunRefusalCode.OUTPUT_INVALID), role=self._role)
        served = ModelRunLane(provider_id=output.provider_id, transport=output.transport, model=output.model)
        return ProviderCompletion(
            text=output.text,
            model=lane_model_label(served),
            input_tokens=0,
            output_tokens=0,
        )

    async def _run(self, body: ModelRunBody) -> ModelRunOutput:
        result = await self._port.run(self._header, body)
        if isinstance(result, ModelRunRefusal):
            raise model_run_refusal_error(result, role=self._role)
        return result


__all__ = ["JSON_REASK_INSTRUCTION", "AgentAdapter", "lane_model_label", "model_run_refusal_error"]
