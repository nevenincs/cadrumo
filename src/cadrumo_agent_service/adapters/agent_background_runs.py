"""cadrumo-agent's background requests, as the hosting service starts and reads them.

A background request is a run without tools, kept out of the run listings and
admitted only on the host's own token, which this service mints and hands to
the agent on its start frame. Each attachment is uploaded to the run's own
conversation first; the run starts with ``POST /v1/runs``; its reply is read
with ``GET /v1/runs/{id}/reply``, waiting there; and the run and its files are
then deleted. The reply text is the model's raw output: extracting the JSON it
should carry is the caller's.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from time import monotonic
from typing import Final, override
from urllib.parse import quote, urlencode
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, ValidationError

from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.model_runs import (
    MODEL_RUN_MAX_OUTPUT_BYTES,
    ModelRunBody,
    ModelRunLane,
    ModelRunOutput,
    ModelRunRefusal,
    ModelRunRefusalCode,
)

from ..providers.application.model_runs import BackgroundRunGateway
from ..providers.domain.catalog import BackgroundOption

_LOGGER = get_logger(__name__)

HOST_ADMISSION_HEADER: Final = "X-Host-Token"
EXCHANGE_SECONDS: Final = 10.0
"""How long one exchange that does not wait for the model may take."""
RUN_START_SECONDS: Final = 90.0
"""How long a run start may take: on a lane whose models run on this computer the agent loads the model first.

The agent bounds that load at 60 s, so the start is given that and a margin.
"""
REPLY_WAIT_MAX_SECONDS: Final = 300
"""The longest wait one reply read may ask the agent for."""
SETTLE_MARGIN_SECONDS: Final = 10
"""How long past its own deadline a run is given to settle and report."""
BACKGROUND_MIN_DEADLINE_SECONDS: Final = 5
BACKGROUND_MAX_DEADLINE_SECONDS: Final = 3600
_RESPONSE_MAX_BYTES: Final = 8 * 1024 * 1024

_EXTENSIONS: Final[Mapping[str, str]] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}
"""The attachment formats a background request puts into the model input, and the extension each is named with."""

_REFUSALS: Final[Mapping[str, ModelRunRefusalCode]] = {
    "background_not_admitted": ModelRunRefusalCode.SERVICE_UNAVAILABLE,
    "background_request_invalid": ModelRunRefusalCode.RUN_FAILED,
    "background_lane_unsupported": ModelRunRefusalCode.LANE_UNAVAILABLE,
    "input_not_supported": ModelRunRefusalCode.INPUT_NOT_SUPPORTED,
    "unknown_provider": ModelRunRefusalCode.LANE_UNAVAILABLE,
    "provider_not_executable": ModelRunRefusalCode.LANE_UNAVAILABLE,
    "provider_not_selectable": ModelRunRefusalCode.LANE_UNAVAILABLE,
    "provider_unavailable": ModelRunRefusalCode.LANE_UNAVAILABLE,
    "unknown_model": ModelRunRefusalCode.LANE_UNAVAILABLE,
    "model_not_installed": ModelRunRefusalCode.MODEL_NOT_INSTALLED,
    "model_does_not_fit": ModelRunRefusalCode.MODEL_DOES_NOT_FIT,
    "background_option_unsupported": ModelRunRefusalCode.OPTION_NOT_SUPPORTED,
}
"""The agent's admission refusals, in the closed set a tax worker reads.

``model_required`` and the effort codes are absent: a background request names
its model and no effort, so the agent cannot answer one with them.
"""

_START_UNAVAILABLE: Final = 503
"""The status the agent starts no run with while it is busy, draining or not ready; its detail carries no code."""

_OUTPUT_LIMIT_EXCEEDED: Final = "output_limit_exceeded"

_PROVIDER_CONDITIONS: Final[Mapping[str, ModelRunRefusalCode]] = {
    "model_does_not_fit": ModelRunRefusalCode.MODEL_DOES_NOT_FIT,
}
"""The provider conditions a failed run's reply names that a tax worker reads as their own refusal.

Every other condition is a failed run.
"""


@dataclass(frozen=True, slots=True)
class BackgroundRunEndpoint:
    """Where the profile's ready agent serves its gateway, and the workspace it runs in."""

    port: int
    workspace_root: Path


class _Reply(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    status: str
    settled: bool
    background_request: bool
    reply: str | None = None
    failure_reason: str | None = None
    provider_condition: str | None = None
    provider: str | None = None
    transport: str | None = None
    model: str | None = None
    agent_version: str


class _GatewayUnreachableError(Exception):
    """The gateway could not be reached or answered outside its contract."""


class HostedBackgroundRuns(BackgroundRunGateway):
    """Run background requests on the profile's hosted agent through its gateway."""

    def __init__(
        self,
        *,
        endpoint: Callable[[], BackgroundRunEndpoint | None],
        bearer: bytearray,
        host_token: bytearray,
        run_ids: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        """Bind the ready agent's endpoint and the two secrets this service holds for its gateway.

        Both buffers stay owned, and wiped, by the service; a wiped one makes
        every run refuse as unavailable. ``run_ids`` names each new run.
        """
        self._endpoint = endpoint
        self._bearer = bearer
        self._host_token = host_token
        self._run_ids = run_ids

    @override
    def run(
        self, *, lane: ModelRunLane, body: ModelRunBody, deadline_seconds: int, options: tuple[BackgroundOption, ...]
    ) -> ModelRunOutput | ModelRunRefusal:
        """Upload the attachments, start the request, wait for its reply, then delete what it left.

        ``options`` are the reply options the lane honours. One ``body`` names
        and the lane does not honour is left out rather than sent: the agent
        refuses a request naming one, and each option only tunes a reply the
        caller validates anyway.
        """
        endpoint = self._endpoint()
        if endpoint is None or not self._bearer or not self._host_token:
            return ModelRunRefusal(code=ModelRunRefusalCode.SERVICE_UNAVAILABLE)
        files: list[tuple[str, str, bytes]] = []
        for index, attachment in enumerate(body.attachments, start=1):
            extension = _EXTENSIONS.get(attachment.media_type)
            if extension is None:
                return ModelRunRefusal(code=ModelRunRefusalCode.INPUT_NOT_SUPPORTED)
            data = base64.b64decode(attachment.base64_data, validate=True)
            files.append((f"input-{index}{extension}", hashlib.sha256(data).hexdigest(), data))
        run_id = self._run_ids()
        uploaded = False
        started = False
        try:
            for name, digest, data in files:
                uploaded = True
                refusal = self._upload(endpoint, run_id, name, digest, data)
                if refusal is not None:
                    return refusal
            bounded = min(max(deadline_seconds, BACKGROUND_MIN_DEADLINE_SECONDS), BACKGROUND_MAX_DEADLINE_SECONDS)
            refusal = self._start(endpoint, run_id, lane, body, files, bounded, options)
            if refusal is not None:
                return refusal
            started = True
            return self._settle(endpoint, run_id, lane, monotonic() + bounded + SETTLE_MARGIN_SECONDS)
        except _GatewayUnreachableError:
            return ModelRunRefusal(
                code=ModelRunRefusalCode.RUN_FAILED if started else ModelRunRefusalCode.SERVICE_UNAVAILABLE
            )
        finally:
            self._clean_up(endpoint, run_id, run=started, attachments=uploaded)

    def _upload(
        self, endpoint: BackgroundRunEndpoint, run_id: str, name: str, digest: str, data: bytes
    ) -> ModelRunRefusal | None:
        path = f"/v1/conversations/{run_id}/attachments/{quote(name)}"
        status, _ = self._exchange(
            endpoint,
            "PUT",
            path,
            body=data,
            headers={"Content-Type": "application/octet-stream", "X-Content-SHA256": digest},
            limit=64 * 1024,
        )
        if status in {200, 201}:
            return None
        _LOGGER.warning("agent background attachment refused status=%s", status)
        code = ModelRunRefusalCode.INPUT_NOT_SUPPORTED if status in {413, 415, 422} else ModelRunRefusalCode.RUN_FAILED
        return ModelRunRefusal(code=code)

    def _start(
        self,
        endpoint: BackgroundRunEndpoint,
        run_id: str,
        lane: ModelRunLane,
        body: ModelRunBody,
        files: list[tuple[str, str, bytes]],
        deadline_seconds: int,
        options: tuple[BackgroundOption, ...],
    ) -> ModelRunRefusal | None:
        named = {option.value: getattr(body, option.value) for option in options}
        request: dict[str, object] = {
            "run_id": run_id,
            "message": body.prompt,
            "agent": {
                "provider": lane.provider_id,
                "transport": lane.transport,
                "model": lane.model,
                "workspace_root": str(endpoint.workspace_root),
            },
            "background": {
                "system": body.system or "",
                "max_output_tokens": body.max_output_tokens,
                "deadline_seconds": deadline_seconds,
                **{name: value for name, value in named.items() if value is not None},
            },
        }
        if files:
            request["attachments"] = [{"name": name, "sha256": digest} for name, digest, _ in files]
        status, payload = self._exchange(
            endpoint,
            "POST",
            "/v1/runs",
            body=json.dumps(request).encode("utf-8"),
            headers={"Content-Type": "application/json", HOST_ADMISSION_HEADER: self._host_token.decode("ascii")},
            limit=_RESPONSE_MAX_BYTES,
            timeout=RUN_START_SECONDS,
        )
        if status in {200, 201}:
            return None
        _LOGGER.warning("agent background request refused status=%s code=%s", status, _refusal_code(payload))
        return ModelRunRefusal(code=start_refusal(status, payload))

    def _settle(
        self, endpoint: BackgroundRunEndpoint, run_id: str, lane: ModelRunLane, deadline: float
    ) -> ModelRunOutput | ModelRunRefusal:
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                return ModelRunRefusal(code=ModelRunRefusalCode.DEADLINE_EXCEEDED)
            wait = min(REPLY_WAIT_MAX_SECONDS, math.ceil(remaining))
            status, payload = self._exchange(
                endpoint,
                "GET",
                f"/v1/runs/{run_id}/reply?" + urlencode({"wait_seconds": wait}),
                limit=_RESPONSE_MAX_BYTES,
                timeout=wait + EXCHANGE_SECONDS,
            )
            if status != 200:
                return ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED)
            outcome = settled_reply_outcome(payload, lane)
            if outcome is not None:
                return outcome

    def _clean_up(self, endpoint: BackgroundRunEndpoint, run_id: str, *, run: bool, attachments: bool) -> None:
        """Delete the run and its files now; the agent sweeps whatever a failed delete leaves."""
        for wanted, path in ((run, f"/v1/runs/{run_id}"), (attachments, f"/v1/conversations/{run_id}/attachments")):
            if not wanted:
                continue
            try:
                status, _ = self._exchange(endpoint, "DELETE", path, limit=64 * 1024)
            except _GatewayUnreachableError:
                status = None
            if status not in {200, 204}:
                _LOGGER.info("agent background cleanup deferred status=%s", status)

    def _exchange(
        self,
        endpoint: BackgroundRunEndpoint,
        method: str,
        path: str,
        *,
        limit: int,
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = EXCHANGE_SECONDS,
    ) -> tuple[int, bytes]:
        if not self._bearer:
            raise _GatewayUnreachableError
        connection = HTTPConnection("127.0.0.1", endpoint.port, timeout=timeout)
        try:
            connection.request(
                method,
                path,
                body=body,
                headers={
                    "Authorization": "Bearer " + self._bearer.decode("ascii"),
                    "Accept": "application/json",
                    **(headers or {}),
                },
            )
            response = connection.getresponse()
            payload = response.read(limit + 1)
            if len(payload) > limit:
                raise _GatewayUnreachableError
            return response.status, payload
        except (HTTPException, OSError) as error:
            raise _GatewayUnreachableError from error
        finally:
            connection.close()


def start_refusal(status: int, payload: bytes) -> ModelRunRefusalCode:
    """Return the closed refusal a run start the agent answered with ``status`` and ``payload`` reads as.

    A coded refusal maps through :data:`_REFUSALS`. A ``503`` means the agent
    could not take a run now, whatever its detail says. Anything else is a
    failed run.
    """
    if status == _START_UNAVAILABLE:
        return ModelRunRefusalCode.SERVICE_UNAVAILABLE
    return _REFUSALS.get(_refusal_code(payload) or "", ModelRunRefusalCode.RUN_FAILED)


def _refusal_code(payload: bytes) -> str | None:
    try:
        document = json.loads(payload)
    except ValueError:
        return None
    detail = document.get("detail") if isinstance(document, dict) else None
    code = detail.get("code") if isinstance(detail, dict) else None
    return code if isinstance(code, str) else None


def settled_reply_outcome(payload: bytes, lane: ModelRunLane) -> ModelRunOutput | ModelRunRefusal | None:
    """Return what a run's reply read reads as, or ``None`` while the run has not settled.

    A reply outside the agent's contract is a failed run. A failed run whose
    ``provider_condition`` maps through :data:`_PROVIDER_CONDITIONS` reads as
    that refusal, so a model the agent could not fit mid-turn reads as the same
    refusal as one it could not fit at run start.
    """
    try:
        reply = _Reply.model_validate_json(payload)
    except ValidationError:
        return ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED)
    return _outcome(reply, lane) if reply.settled else None


def _outcome(reply: _Reply, lane: ModelRunLane) -> ModelRunOutput | ModelRunRefusal:
    if reply.status != "completed":
        condition = _PROVIDER_CONDITIONS.get(reply.provider_condition or "")
        if condition is not None:
            return ModelRunRefusal(code=condition)
        if reply.failure_reason is not None and reply.failure_reason.startswith(_OUTPUT_LIMIT_EXCEEDED):
            return ModelRunRefusal(code=ModelRunRefusalCode.OUTPUT_INVALID)
        return ModelRunRefusal(code=ModelRunRefusalCode.RUN_FAILED)
    if not reply.background_request or reply.reply is None:
        return ModelRunRefusal(code=ModelRunRefusalCode.OUTPUT_INVALID)
    if len(reply.reply.encode("utf-8")) > MODEL_RUN_MAX_OUTPUT_BYTES:
        return ModelRunRefusal(code=ModelRunRefusalCode.OUTPUT_INVALID)
    try:
        return ModelRunOutput(
            text=reply.reply,
            provider_id=reply.provider or lane.provider_id,
            transport=reply.transport or lane.transport,
            model=reply.model or lane.model,
            agent_version=reply.agent_version,
        )
    except ValidationError:
        return ModelRunRefusal(code=ModelRunRefusalCode.OUTPUT_INVALID)


__all__ = ["BackgroundRunEndpoint", "HostedBackgroundRuns", "settled_reply_outcome", "start_refusal"]
