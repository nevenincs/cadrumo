"""Service-owned provider administration and contained hosted-agent lifecycle."""

from __future__ import annotations

from threading import Thread
from typing import Any, override

from cadrumo.core.logging import get_logger

from .host.controller import (
    AgentHostError,
    AgentHostRefusal,
    AgentHostState,
    AgentReady,
)
from .host.store_lifecycle import (
    InvocationCancellation,
)
from .service_startup import AgentServiceStartup
from .service_support import (
    service_failure,
)

_LOGGER = get_logger("cadrumo_agent_service.service")


class AgentServiceScheduling(AgentServiceStartup):
    """Schedule startup and retirement under service ownership."""

    @override
    def _schedule_start(self) -> bool:
        """Hand a start to the start thread unless one is running; ``False`` once the service is closing."""
        with self._start_request_guard:
            if self._closing.is_set():
                return False
            if self._start_thread is None or not self._start_thread.is_alive():
                self._startup_cancellation = InvocationCancellation()
                self._start_thread = Thread(target=self._background_start, name="agent-service-start")
                self._start_thread.start()
        return True

    def _already_stopped(self) -> bool:
        start = self._start_thread
        preparation = self._preparation_runner
        return (
            self._controller is None
            and (start is None or not start.is_alive())
            and self._startup_cancellation is None
            and (preparation is None or preparation.settled)
        )

    @override
    def _admit_stop(self) -> dict[str, Any]:
        """Admit the tree's retirement and answer at once; the stopped event reports its end."""
        if self._closing.is_set():
            return {"kind": "refused", "code": "service_stopping"}
        if self.client.lease is None:
            return {"kind": "refused", "code": "signed_out"}
        self._auth_resume_valid = None
        if self._auth_attempt is not None:
            self._auth_attempt.cancel()
        cancellation = self._startup_cancellation
        if cancellation is not None:
            cancellation.cancel()
        controller = self._controller
        if controller is not None:
            controller.cancel_start()
        if self._already_stopped():
            return {"kind": "stopped"}
        if not self._schedule_stop():
            return {"kind": "refused", "code": "busy"}
        return {"kind": "accepted"}

    @override
    def _schedule_stop(self) -> bool:
        """Hand the tree's retirement to its own thread; ``False`` while one is already under way."""
        with self._start_request_guard:
            if self._stop_thread is not None and self._stop_thread.is_alive():
                return False
            self._stop_thread = Thread(target=self._background_stop, name="agent-service-stop")
            self._stop_thread.start()
        return True

    @override
    def _has_unsettled_tree(self) -> bool:
        controller = self._controller
        preparation = self._preparation_runner
        return (controller is not None and controller.state is AgentHostState.STOPPING) or (
            preparation is not None and not preparation.settled
        )

    def _background_stop(self) -> None:
        try:
            self.stop()
        except Exception as error:
            if not self._closing.is_set():
                self._emit(
                    service_failure(
                        AgentHostError(AgentHostRefusal.STORES_UNPREPARED) if self._has_unsettled_tree() else error
                    )
                )

    @override
    def _replace_superseded(self) -> bool:
        """Start a replacement for a ready tree whose generations moved on while the profile stays signed in.

        The start retires the superseded tree, which publishes ``stopped``, and
        then publishes the new tree's ready line or the refusal that kept it
        from starting, so the desktop never keeps showing a retired agent.
        """
        controller = self._controller
        if controller is None or not controller.superseded() or self._credentials.current_generations() is None:
            return False
        if self._auth_attempt is not None and self._auth_attempt.active:
            # The sign-in retires this tree itself and resumes the agent once it settles.
            return False
        return self._schedule_start()

    def _background_start(self) -> None:
        try:
            result = self.start()
        except Exception as error:
            result = service_failure(error)
        if result.get("event") != "agent_ready" and not self._closing.is_set():
            self._emit(result)

    @override
    def _ready_event(self, ready: AgentReady) -> dict[str, Any]:
        return {
            "event": "agent_ready",
            "gateway_port": ready.gateway_port,
            "agent_version": ready.agent_version,
            "hosting_contract": ready.hosting_contract,
            "workspace_root": str(self._workspace),
        }
