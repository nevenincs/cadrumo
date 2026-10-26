"""The provider adapter that hands a request to the agent service.

The agent service resolves the person's selected cadrumo-agent lane and model
for the request's role and runs it there, on any lane the provider catalog
offers, API or CLI. This adapter never sees a key: it builds one bounded run
request, sends it through the operation's model-run port, and returns the
run's final reply text.
"""

from __future__ import annotations

from typing import Final, override

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
from .....application.operator_actions.models import PreconditionVerdict
from .....application.provisioning_contracts import (
    LOCAL_AI_PROVISION_ACTION_ID,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
    provisioning_setup_verdict,
)
from .....core.config_support import LLMProvider
from .....core.model_roles import ModelRole
from .....core.operator_action_enums import ActionEvidenceProvenance
from ..errors import LLMConfigError, LLMConsentError, LLMContentionError, LLMError, LLMProviderError
from ..preconditions import LLMPreconditionCondition, llm_no_recovery_verdict
from ..response_json import first_json_object
from .base import ProviderAdapter, ProviderCompletion, ProviderRequest

JSON_REASK_INSTRUCTION = (
    "Your previous reply contained no JSON object. Reply with exactly one JSON object and nothing else."
)
"""Appended to the prompt for the single re-ask a reply without a JSON object earns."""

_NO_SELECTION_LOCALE_KEY: Final = "errors.refused.refused_llm_no_model_selected"
"""The refusal sentence for a role with no selected model: the person chooses one in the desktop app."""

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


def lane_model_label(lane: ModelRunLane | ModelRunOutput) -> str:
    """Return the model identity records carry for an agent run: its lane and model together."""
    return f"{lane.provider_id}/{lane.transport}/{lane.model}"


def model_run_refusal_verdict(refusal: ModelRunRefusal, *, role: ModelRole) -> PreconditionVerdict:
    """Return the typed verdict for a refused model run, naming its recovery where one is registered.

    A selected model the lane's local server does not hold is supplied by the
    local AI setup, so that refusal names it. A model the agent could not load
    with the memory free is the load-capacity refusal, a property of this
    computer that no setup changes. A role with no selection says so in a
    stable fact and names no action: the selection is made in the desktop app,
    which no command of ours performs. Every other refusal keeps a no-recovery
    verdict.
    """
    facts: dict[str, str | int | bool] = {"model_run_refusal": refusal.code.value, "model_role": role.value}
    if refusal.code is ModelRunRefusalCode.MODEL_DOES_NOT_FIT:
        return provisioning_no_recovery_verdict(
            ProvisioningPreconditionCondition.LOAD_CAPACITY_AVAILABLE, facts={**facts, "role": role.value}
        )
    if refusal.code is ModelRunRefusalCode.MODEL_NOT_INSTALLED:
        return provisioning_setup_verdict(
            ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED,
            facts={**facts, "role": role.value, "role_model_installed": False},
            action_id=LOCAL_AI_PROVISION_ACTION_ID,
        )
    if refusal.code is ModelRunRefusalCode.NO_SELECTION:
        facts |= {"role": role.value, "role_selection_required": True}
    return llm_no_recovery_verdict(
        LLMPreconditionCondition.AGENT_MODEL_RUN_COMPLETED,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
    )


def model_override_refusal_error(*, role: ModelRole) -> LLMConfigError:
    """Return the refusal for a request that names a model for ``role``.

    The model a role reads with is the person's selection for that role, held
    by the agent service. A run names a role, never a model, so a named model
    would be silently ignored if it were accepted. The name itself stays out of
    the refusal.
    """
    facts: dict[str, str | int | bool] = {"model_override_present": True, "model_role": role.value}
    return LLMConfigError(
        context=facts,
        precondition_verdict=llm_no_recovery_verdict(
            LLMPreconditionCondition.AGENT_MODEL_OVERRIDE_ABSENT,
            facts=facts,
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
        ),
    )


def refuse_vision_model_override(model: str | None) -> None:
    """Refuse a named vision model before anything is read; ``None`` passes.

    Raises:
        LLMConfigError: When ``model`` is given, even empty, with the
            ``llm.agent.model_override_absent`` verdict.
    """
    if model is not None:
        raise model_override_refusal_error(role=ModelRole.VISION_TRANSCRIPTION)


def model_run_refusal_error(refusal: ModelRunRefusal, *, role: ModelRole) -> LLMError:
    """Return the typed error a consumer receives for a refused model run."""
    verdict = model_run_refusal_verdict(refusal, role=role)
    context = {"provider": LLMProvider.AGENT.value, **verdict.evidence[0].values}
    if refusal.code is ModelRunRefusalCode.CONSENT_MISSING:
        return LLMConsentError(context=context, precondition_verdict=verdict)
    if refusal.code is ModelRunRefusalCode.MODEL_DOES_NOT_FIT:
        return LLMContentionError(context=context, precondition_verdict=verdict)
    if refusal.code is ModelRunRefusalCode.NO_SELECTION:
        return LLMConfigError(
            context=context, precondition_verdict=verdict, translated_message=_NO_SELECTION_LOCALE_KEY
        )
    if refusal.code in _CONFIGURATION_REFUSALS:
        return LLMConfigError(context=context, precondition_verdict=verdict)
    return LLMProviderError(context=context)


class AgentAdapter(ProviderAdapter):
    """Run one request on the lane the agent service resolved for its role.

    The lane was resolved, and any consent bound to it, before this adapter was
    built. Consent is bound only when the lane reads off-host, and the service
    refuses the run if it would now use another lane or an off-host lane
    without consent.
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
        return ProviderCompletion(
            text=output.text,
            model=lane_model_label(output),
            input_tokens=0,
            output_tokens=0,
        )

    async def _run(self, body: ModelRunBody) -> ModelRunOutput:
        result = await self._port.run(self._header, body)
        if isinstance(result, ModelRunRefusal):
            raise model_run_refusal_error(result, role=self._role)
        return result


__all__ = [
    "JSON_REASK_INSTRUCTION",
    "AgentAdapter",
    "lane_model_label",
    "model_override_refusal_error",
    "model_run_refusal_error",
    "model_run_refusal_verdict",
    "refuse_vision_model_override",
]
