"""The agent gateway's record of a read a run is parked on, and the release that lets it through."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from http.client import HTTPConnection, HTTPException
from typing import Any, Final, override
from urllib.parse import quote

from ..providers.application.attachment_releases import (
    AttachmentGateway,
    GatewayAnswer,
    PendingRead,
    ReleaseAction,
    StoredDocument,
)
from .agent_background_runs import HOST_ADMISSION_HEADER, BackgroundRunEndpoint

_READ_TOOL: Final = "read_attachment"
_DESCRIPTION: Final = re.compile(
    r'Permission required: read_attachment; attachment: ("(?:[^"\\]|\\.)*")(; page images)?'
)
_SECONDS: Final = 3.0
"""Each exchange's bound: the person's administration request has five in all."""
_RESPONSE_MAX_BYTES: Final = 16 * 1024 * 1024


def _read_description(description: object) -> tuple[str, ReleaseAction] | None:
    """Read the agent's own wording of the request; it escapes the name it was given."""
    if not isinstance(description, str):
        return None
    match = _DESCRIPTION.fullmatch(description)
    if match is None:
        return None
    name: object = json.loads(match.group(1))
    if not isinstance(name, str):
        return None
    return (name, "page_images") if match.group(2) else (name, "document_text")


class GatewayAttachments(AttachmentGateway):
    """Read a run's parked request and release it, with the host token only this service holds."""

    def __init__(
        self,
        *,
        endpoint: Callable[[], BackgroundRunEndpoint | None],
        bearer: bytearray,
        host_token: bytearray,
    ) -> None:
        """Bind the ready agent's endpoint and the two secrets the service owns."""
        self._endpoint = endpoint
        self._bearer = bearer
        self._host_token = host_token

    @override
    def pending_read(self, run_id: str, request_id: str) -> PendingRead | None:
        """Return the read only when the agent itself reports the run parked on it."""
        status, status_body = self._exchange("GET", f"/v1/runs/{quote(run_id, safe='')}")
        history_status, history = self._exchange("GET", f"/v1/runs/{quote(run_id, safe='')}/history")
        if status != 200 or history_status != 200:
            return None
        pending = (history.get("state") or {}).get("pending_permissions") or []
        request = next((held for held in pending if held.get("request_id") == request_id), None)
        if request is None or request.get("tool_call") != _READ_TOOL or request.get("tool_server") is not None:
            return None
        described = _read_description(request.get("description"))
        selection = status_body.get("selection") or {}
        conversation = status_body.get("conversation_id")
        provider, transport, model = selection.get("provider"), selection.get("transport"), selection.get("model")
        if (
            described is None
            or not isinstance(conversation, str)
            or not isinstance(provider, str)
            or not isinstance(transport, str)
            or not isinstance(model, str)
        ):
            return None
        name, action = described
        return PendingRead(
            conversation_id=conversation, name=name, action=action, provider=provider, transport=transport, model=model
        )

    @override
    def document(self, conversation_id: str, name: str) -> StoredDocument | None:
        """Return the file's digest, type and size as the agent measures them now."""
        path = f"/v1/conversations/{quote(conversation_id, safe='')}/attachments/{quote(name, safe='')}"
        status, record = self._exchange("GET", path)
        if status != 200:
            return None
        digest, media_type, size = record.get("sha256"), record.get("media_type"), record.get("size_bytes")
        if not isinstance(digest, str) or not isinstance(media_type, str) or not isinstance(size, int):
            return None
        return StoredDocument(sha256=digest, media_type=media_type, size_bytes=size)

    @override
    def release(self, read: PendingRead, sha256: str, *, seconds: int) -> GatewayAnswer:
        """Ask the agent to admit this read; its answer is checked against the bytes it holds."""
        path = (
            f"/v1/conversations/{quote(read.conversation_id, safe='')}/attachments/{quote(read.name, safe='')}/release"
        )
        body: dict[str, object] = {
            "sha256": sha256,
            "provider": read.lane,
            "model": read.model,
            "action": read.action,
            "expires_in_seconds": seconds,
        }
        status, _ = self._exchange("PUT", path, body=body, host=True)
        if status == 204:
            return GatewayAnswer.RELEASED
        return GatewayAnswer.CHANGED if status in {404, 409} else GatewayAnswer.UNAVAILABLE

    @override
    def withdraw(self, conversation_id: str) -> None:
        """Take back the conversation's unread releases; each expires by itself if this fails."""
        self._exchange("DELETE", f"/v1/conversations/{quote(conversation_id, safe='')}/attachment-releases", host=True)

    def _exchange(
        self, method: str, path: str, *, body: dict[str, object] | None = None, host: bool = False
    ) -> tuple[int, dict[str, Any]]:
        endpoint = self._endpoint()
        if endpoint is None or not self._bearer or not self._host_token:
            return 0, {}
        headers = {"Authorization": "Bearer " + self._bearer.decode("ascii"), "Accept": "application/json"}
        if host:
            headers[HOST_ADMISSION_HEADER] = self._host_token.decode("ascii")
        encoded = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            encoded = json.dumps(body).encode("utf-8")
        connection = HTTPConnection("127.0.0.1", endpoint.port, timeout=_SECONDS)
        try:
            connection.request(method, path, body=encoded, headers=headers)
            response = connection.getresponse()
            payload = response.read(_RESPONSE_MAX_BYTES + 1)
            status = response.status
        except (OSError, HTTPException):
            return 0, {}
        finally:
            connection.close()
        if len(payload) > _RESPONSE_MAX_BYTES:
            return 0, {}
        try:
            decoded = json.loads(payload) if payload else {}
        except ValueError:
            return 0, {}
        return status, decoded if isinstance(decoded, dict) else {}


__all__ = ["GatewayAttachments"]
