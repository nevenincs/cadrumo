"""Shared service refusal and catalog presentation helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.deadline_budget import OrchestrationTimeoutError, TimeoutPolicy

from .adapters.agent_programs import AgentProgramRefusalError
from .host.controller import AgentHostController, AgentHostError, AgentHostState
from .host.launcher_protocol import launcher_refusal_for, runtime_launcher_refusal_for
from .providers.application.local_model_list import serves_engine_lane
from .providers.domain.record import LocalEngine

_LOGGER = get_logger("cadrumo_agent_service.service")

HOSTED_CERTIFICATION_CACHE_SECONDS = 5.0
LIFECYCLE_ADMISSION_SECONDS = 2.0
"""How long a request waits for tree lifecycle work, well inside the desktop's shortest exchange bound."""
ADMIN_READ_SECONDS = 3.0
"""How long a catalog or status request waits for its work before it is told the service is busy.

The work goes on, and a request in the next few seconds is served its result:
a cold catalog or a provider's sign-in probe can take longer than an
administration exchange may hold one of the service's few slots. The bound
must exceed the agent's own bound on one provider probe plus the service's
work around the read, or a cold catalog whose slowest probe runs to its bound
is told busy every time; it stays well inside the desktop's six-second
catalog exchange."""
ADMIN_READ_FRESH_SECONDS = 5.0
"""How long a finished catalog or status read is served to the requests that follow it."""
SERVED_CATALOG_READ_POLICY = TimeoutPolicy(timeout_seconds=6.0)
"""How long one read of the running agent's served catalog may take before it is refused as timed out.

The agent answers a catalog read in about its bound on one provider probe: it
probes every lane at once, reports a lane that has not answered as not
observed, and goes on building that lane's answer for the next read. A read
that takes longer is a hung or failing gateway, and abandoning it loses
nothing the agent has not kept. The read is made for a desktop exchange that
waits six seconds, and while it runs every other catalog request is told the
service is busy, so it is bounded at that exchange rather than at the
last-resort orchestration budget."""


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


def picker_lanes(
    document: dict[str, Any],
    engine: Callable[[], LocalEngine | None],
    turned_off: frozenset[tuple[str, str]],
    *,
    provider_field: str,
) -> dict[str, Any]:
    """Return ``document`` with the lanes a profile running ``engine()`` is served, less those in ``turned_off``.

    The engine rule is the one the provider settings and the local model lists
    are scoped by, so the picker offers the lanes they list. ``engine`` is read
    once, and only when the document lists a lane the rule could leave out.
    """
    lanes: object = document.get("providers")
    if not isinstance(lanes, list):
        return document
    selected: list[LocalEngine | None] = []

    def kept(lane: object) -> bool:
        if not isinstance(lane, dict):
            return True
        fields = cast(dict[str, object], lane)
        provider = fields.get(provider_field)
        if isinstance(provider, str) and not all(serves_engine_lane(provider, held) for held in LocalEngine):
            if not selected:
                selected.append(engine())
            if not serves_engine_lane(provider, selected[0]):
                return False
        return (provider, fields.get("transport")) not in turned_off

    return {**document, "providers": [lane for lane in cast(list[object], lanes) if kept(lane)]}
