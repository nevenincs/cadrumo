"""Answer the model runs the runtime announces to this service, off the connection's event reader.

The runtime pushes only a run id. Fetching the waiting request, running it and
sending the answer are ordinary requests on the service connection, so they
are made from worker threads here: the event reader that delivered the
announcement must not wait on itself.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Protocol
from uuid import UUID

from cadrumo.core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.model_runs import (
    MODEL_RUN_MAX_OUTPUT_BYTES,
    ModelRunBody,
    ModelRunHeader,
    ModelRunLane,
    ModelRunOutcome,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunRequested,
    ModelRunServed,
    decode_model_run_body,
)
from cadrumo_client.transport.service_client import InstalledServiceClient

_LOGGER = get_logger(__name__)

_CONCURRENT_RUNS = 4
"""Runs answered at once; a lookup is never queued behind more than this many runs."""


class ModelRuns(Protocol):
    """The profile's lane lookup and run, as the service's run service answers them."""

    def lookup(self, role: str) -> ModelRunLane | ModelRunRefusal:
        """Return the lane a run for ``role`` would use."""
        ...

    def run(self, header: ModelRunHeader, body: ModelRunBody) -> ModelRunOutput | ModelRunRefusal:
        """Run one request."""
        ...


class ModelRunRelay:
    """Fetch, answer and complete each announced run on a bounded pool of worker threads."""

    def __init__(self, *, client: InstalledServiceClient, runs: Callable[[], ModelRuns | None]) -> None:
        """Bind the relay to this service's connection and to the profile's run service, when it has one."""
        self._client = client
        self._runs = runs
        self._pool = ThreadPoolExecutor(max_workers=_CONCURRENT_RUNS, thread_name_prefix="agent-service-model-run")
        self._guard = Lock()
        self._closed = False

    def announce(self, event: ModelRunRequested) -> None:
        """Hand one announcement to a worker thread; called on the connection's event reader."""
        with self._guard:
            if self._closed:
                return
            self._pool.submit(self._answer, event.run_id)

    def close(self) -> None:
        """Stop taking announcements; a run already answering finishes or reaches its deadline."""
        with self._guard:
            self._closed = True
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _answer(self, run_id: UUID) -> None:
        try:
            fetched = self._client.model_run_fetch(run_id)
        except Exception as error:
            _log_failure("model_run_fetch_failed", error)
            return
        if fetched is None:
            return
        reply, body = fetched
        text = bytearray()
        try:
            outcome, text = self._outcome(reply.role, reply.header, body)
        finally:
            body[:] = bytes(len(body))
        try:
            self._client.model_run_complete(run_id, outcome, text)
        except Exception as error:
            _log_failure("model_run_complete_failed", error)
        finally:
            text[:] = bytes(len(text))

    def _outcome(self, role: str, header: ModelRunHeader | None, body: bytearray) -> tuple[ModelRunOutcome, bytearray]:
        runs = self._runs()
        if runs is None:
            return ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE), bytearray()
        try:
            if header is None:
                lane = runs.lookup(role)
                if isinstance(lane, ModelRunRefusal):
                    return ModelRunOutcome(refusal=lane.code), bytearray()
                return ModelRunOutcome(lane=lane), bytearray()
            result = runs.run(header, decode_model_run_body(body))
        except Exception as error:
            _log_failure("model_run_failed", error)
            return ModelRunOutcome(refusal=ModelRunRefusalCode.RUN_FAILED), bytearray()
        if isinstance(result, ModelRunRefusal):
            return ModelRunOutcome(refusal=result.code), bytearray()
        text = bytearray(result.text.encode("utf-8"))
        served = ModelRunServed(
            provider_id=result.provider_id,
            transport=result.transport,
            model=result.model,
            agent_version=result.agent_version,
        )
        if not text or len(text) > MODEL_RUN_MAX_OUTPUT_BYTES:
            text[:] = bytes(len(text))
            return ModelRunOutcome(refusal=ModelRunRefusalCode.OUTPUT_INVALID), bytearray()
        return ModelRunOutcome(served=served, text_byte_count=len(text)), text


def _log_failure(event: str, error: BaseException) -> None:
    diagnostic_event(_LOGGER, event, fields=diagnostic_error_fields(error), level=logging.WARNING, primary_error=error)


__all__ = ["ModelRunRelay"]
