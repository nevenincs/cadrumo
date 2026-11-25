"""Shared service refusal and catalog presentation helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.deadline_budget import OrchestrationTimeoutError, TimeoutPolicy

from .adapters.agent_programs import AgentProgramRefusalError
from .host.controller import AgentHostController, AgentHostError, AgentHostRefusal, AgentHostState
from .host.launcher_protocol import launcher_refusal_for, runtime_launcher_refusal_for
from .host.store_lifecycle import InvocationCancellation
from .providers.application.local_model_list import serves_engine_lane
from .providers.application.served_catalog import ModelDownload
from .providers.domain.record import LocalEngine

_LOGGER = get_logger("cadrumo_agent_service.service")

HOSTED_CERTIFICATION_CACHE_SECONDS = 5.0
LIFECYCLE_ADMISSION_SECONDS = 2.0
"""How long a request waits for tree lifecycle work, well inside the desktop's shortest exchange bound."""
ADMIN_READ_SECONDS = 3.0
"""How long a catalog request waits for its work before it is told the service is busy.

The work goes on, and a request in the next few seconds is served its result:
a cold catalog can take longer than an
administration exchange may hold one of the service's few slots. The bound
must exceed the agent's own bound on one provider probe plus the service's
work around the read, or a cold catalog whose slowest probe runs to its bound
is told busy every time; it stays well inside the desktop's six-second
catalog exchange."""
PROFILE_READ_SECONDS = 4.0
"""How long one read of the profile's settings may take, inside the desktop's six-second attachment exchange."""
ADMIN_READ_FRESH_SECONDS = 5.0
"""How long a finished catalog read is served to the requests that follow it."""
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


CANCEL_PERSON_SIGNED_OUT = "person signed out"
CANCEL_SERVICE_STOPPING = "service stopping"
CANCEL_STOP_REQUESTED = "stop requested"


def name_cancel_cause(error: BaseException, cancellation: InvocationCancellation) -> None:
    """Record on a cancelled start's refusal why its cancellation was raised, when the canceller said."""
    if isinstance(error, AgentHostError) and error.reason is AgentHostRefusal.CANCELLED:
        error.cancel_cause = cancellation.cause


def service_failure(error: Exception) -> dict[str, Any]:
    """Keep typed launch refusals and log only bounded operational metadata."""
    if isinstance(error, OrchestrationTimeoutError):
        return {"event": "refused", "code": "agent_timeout"}
    if isinstance(error, AgentHostError):
        code = launcher_refusal_for(error).value
        if error.reason is AgentHostRefusal.CANCELLED and error.cancel_cause is not None:
            # A cancellation with a known cause is expected behaviour, not a refusal to investigate.
            _LOGGER.info("agent startup cancelled: %s", error.cancel_cause)
        else:
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

    return {
        **document,
        "providers": [_with_model_download(lane, provider_field) for lane in cast(list[object], lanes) if kept(lane)],
    }


_ENGINE_LANES = frozenset(engine.value for engine in LocalEngine)


def _with_model_download(lane: object, provider_field: str) -> object:
    """Stamp ``model_download`` on a lane and leave ``installed`` only on a local engine's models."""
    if not isinstance(lane, dict):
        return lane
    fields = dict(cast(dict[str, object], lane))
    local = fields.get(provider_field) in _ENGINE_LANES
    fields["model_download"] = (ModelDownload.REQUIRED if local else ModelDownload.NONE).value
    if not local and "catalog" in fields:
        fields["catalog"] = _without_installed(fields.get("catalog"))
    return fields


def _without_installed(catalog: object) -> object:
    """Drop ``installed`` from a hosted lane's catalog models; a catalog without a model list is kept as served."""
    models = catalog.get("models") if isinstance(catalog, dict) else None
    if not isinstance(catalog, dict) or not isinstance(models, list):
        return catalog
    return {
        **cast(dict[str, object], catalog),
        "models": [_model_without_installed(model) for model in cast(list[object], models)],
    }


def _model_without_installed(model: object) -> object:
    if not isinstance(model, dict):
        return model
    return {key: value for key, value in cast(dict[str, object], model).items() if key != "installed"}


class HeldLaneLog:
    """Log why each lane the picker serves cannot be chosen, once for each change.

    The window words a held lane from its health axes alone, so every axis that
    holds it, the catalogue state and the agent's own reasons are logged when a
    lane becomes held or its cause changes, and once when it is selectable again.
    The agent serves these values publicly; none names a credential or a path.
    """

    def __init__(self) -> None:
        """Start with no lane logged."""
        self._held: dict[tuple[str, str], tuple[object, ...]] = {}

    def observe(self, document: dict[str, Any]) -> None:
        """Log the lanes of a served ``document`` whose cause changed since the last one."""
        lanes: object = document.get("providers")
        if not isinstance(lanes, list):
            return
        for lane in cast(list[object], lanes):
            if isinstance(lane, dict):
                self._observe_lane(cast(dict[str, object], lane))

    def _observe_lane(self, lane: dict[str, object]) -> None:
        key = (str(lane.get("provider_id")), str(lane.get("transport")))
        health = lane.get("health")
        if not isinstance(health, dict):
            return
        axes = cast(dict[str, object], health)
        if axes.get("selectable") is True:
            if self._held.pop(key, None) is not None:
                _LOGGER.info("agent picker lane selectable provider=%s transport=%s", *key)
            return
        catalog = lane.get("catalog")
        state = cast(dict[str, object], catalog).get("state") if isinstance(catalog, dict) else None
        status = cast(dict[str, object], state).get("status") if isinstance(state, dict) else None
        cause = (
            axes.get("configured"),
            axes.get("transport"),
            axes.get("authentication"),
            axes.get("catalog"),
            axes.get("admission"),
            status,
            tuple(cast(list[object], axes.get("reasons") or [])),
        )
        if self._held.get(key) == cause:
            return
        self._held[key] = cause
        _LOGGER.info(
            "agent picker lane held provider=%s transport=%s configured=%s transport_health=%s "
            "authentication=%s catalog=%s admission=%s catalog_state=%s reasons=%s",
            *key,
            *cause[:6],
            "; ".join(str(reason) for reason in cause[6]),
        )
