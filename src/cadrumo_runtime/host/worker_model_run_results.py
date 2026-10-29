"""Typed model-run response projection and secret-text cleanup."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from cadrumo.application.operations.models import OperationIdentity
from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunHeader,
    ModelRunLane,
    ModelRunOutcome,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunRoleSelection,
    encode_model_run_body,
)

ModelRunCall = Callable[
    [OperationIdentity, str | None, ModelRunHeader | None, bytearray, float],
    Awaitable[tuple[ModelRunOutcome, bytearray]],
]
_MODEL_RUN_LOOKUP_SECONDS = 30.0
_MODEL_RUN_ANSWER_MARGIN_SECONDS = 130.0


async def model_run_lookup(run: ModelRunCall, identity: OperationIdentity, role: str) -> ModelRunLane | ModelRunRefusal:
    """Ask the profile's agent service which lane and model it would use for ``role``."""
    outcome, text = await run(identity, role, None, bytearray(), _MODEL_RUN_LOOKUP_SECONDS)
    text[:] = bytes(len(text))
    if outcome.lane is not None:
        return outcome.lane
    return ModelRunRefusal(code=outcome.refusal or ModelRunRefusalCode.RUN_FAILED)


async def model_run_selections(
    run: ModelRunCall, identity: OperationIdentity
) -> tuple[ModelRunRoleSelection, ...] | ModelRunRefusal:
    """Ask the profile's agent service for every role's selection state; nothing in it is secret."""
    outcome, text = await run(identity, None, None, bytearray(), _MODEL_RUN_LOOKUP_SECONDS)
    text[:] = bytes(len(text))
    if outcome.selections is not None:
        return outcome.selections
    return ModelRunRefusal(code=outcome.refusal or ModelRunRefusalCode.RUN_FAILED)


async def model_run_result(
    run: ModelRunCall, identity: OperationIdentity, header: ModelRunHeader, body: ModelRunBody
) -> ModelRunOutput | ModelRunRefusal:
    """Have the profile's agent service run one tool-less request for this running operation."""
    answer_seconds = header.deadline_seconds + _MODEL_RUN_ANSWER_MARGIN_SECONDS
    outcome, text = await run(identity, header.role, header, encode_model_run_body(body), answer_seconds)
    try:
        return model_run_output(outcome, text)
    finally:
        text[:] = bytes(len(text))


def model_run_output(outcome: ModelRunOutcome, text: bytearray) -> ModelRunOutput | ModelRunRefusal:
    """Turn the service's answer to a run into its output, refusing an answer that is not a run's."""
    if outcome.refusal is not None:
        return ModelRunRefusal(code=outcome.refusal)
    served = outcome.served
    if served is None:
        return ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED)
    try:
        reply = text.decode("utf-8")
    except UnicodeDecodeError:
        return ModelRunRefusal(code=ModelRunRefusalCode.OUTPUT_INVALID)
    return ModelRunOutput(
        text=reply,
        provider_id=served.provider_id,
        transport=served.transport,
        model=served.model,
        agent_version=served.agent_version,
    )
