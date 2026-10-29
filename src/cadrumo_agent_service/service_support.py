"""Shared service refusal and catalog presentation helpers."""

from __future__ import annotations

from typing import Any, cast

from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.deadline_budget import OrchestrationTimeoutError

from .adapters.agent_programs import AgentProgramRefusalError
from .host.controller import AgentHostController, AgentHostError, AgentHostState
from .host.launcher_protocol import launcher_refusal_for, runtime_launcher_refusal_for

_LOGGER = get_logger("cadrumo_agent_service.service")

HOSTED_CERTIFICATION_CACHE_SECONDS = 5.0
LIFECYCLE_ADMISSION_SECONDS = 2.0
"""How long a request waits for tree lifecycle work, well inside the desktop's shortest exchange bound."""
ADMIN_READ_SECONDS = 1.5
"""How long a catalog or status request waits for its work before it is told the service is busy.

The work goes on, and a request in the next few seconds is served its result:
a cold catalog or a provider's sign-in probe can take longer than an
administration exchange may hold one of the service's few slots."""
ADMIN_READ_FRESH_SECONDS = 5.0
"""How long a finished catalog or status read is served to the requests that follow it."""


def service_failure(error: Exception) -> dict[str, Any]:
    """Keep typed launch refusals and log only bounded operational metadata."""
    if isinstance(error, OrchestrationTimeoutError):
        return {"event": "refused", "code": "agent_timeout"}
    if isinstance(error, AgentHostError):
        code = launcher_refusal_for(error).value
        _LOGGER.warning(
            "agent startup refused reason=%s agent_code=%s",
            error.reason.value,
            error.agent_code,
        )
    elif isinstance(error, AgentProgramRefusalError):
        code = error.code.value
        _LOGGER.warning("agent program unavailable code=%s", code)
    elif isinstance(error, RefusalError):
        unavailable = runtime_launcher_refusal_for(error)
        code = "service_failed" if unavailable is None else unavailable.value
        _LOGGER.warning("agent runtime refused reason=%s", error.reason.value)
    else:
        code = "service_failed"
        _LOGGER.error("agent service failed error_type=%s", type(error).__name__)
    return {"event": "refused", "code": code}


def controller_is_ready(controller: AgentHostController) -> bool:
    """Read the controller's live state without inferring readiness from credentials."""
    return controller.state is AgentHostState.READY


def _lane_is_off(lane: object, turned_off: frozenset[tuple[str, str]], provider_field: str) -> bool:
    if not isinstance(lane, dict):
        return False
    fields = cast(dict[str, object], lane)
    return (fields.get(provider_field), fields.get("transport")) in turned_off


def without_lanes(
    document: dict[str, Any], turned_off: frozenset[tuple[str, str]], *, provider_field: str
) -> dict[str, Any]:
    """Return ``document`` without the lanes whose provider and transport are in ``turned_off``."""
    lanes: object = document.get("providers")
    if not isinstance(lanes, list):
        return document
    kept = [lane for lane in cast(list[object], lanes) if not _lane_is_off(lane, turned_off, provider_field)]
    return {**document, "providers": kept}
