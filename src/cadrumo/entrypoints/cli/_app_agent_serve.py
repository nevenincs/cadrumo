"""Serve the person's hosted agent for as long as standard input stays open: the launcher protocol's client.

The desktop host runs this command and speaks the launcher protocol with it
(:mod:`cadrumo.application.agent_host.launcher_protocol`):

* standard input carries one JSON line, ``{"bearer": "<gateway bearer>"}``, and
  then stays open; end of file means stop;
* standard output carries JSON lines only: ``agent_ready`` (with the gateway
  port, the agent version, the existing ``workspace_root`` runs use, and the
  lane), ``agent_refused`` with one closed code, and ``agent_stopped`` with
  its reason.

``--agent-source`` runs the agent from a cadrumo-agent source tree's own
environment; without it the runtime starts the agent packaged with it.

This process signs in only by resuming the person's stored sign-in, on the
agent host's frontend, and asks the runtime to start the agent for that one
session. The runtime owns the agent's process tree and its provider
credentials; this process never sees a provider key, and the bearer leaves it
only on the runtime's secret frame. Closing standard input, the session's end,
or this process's own end closes the connection, and the runtime stops the
agent with the session.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from threading import Event, Thread
from typing import Final, NoReturn
from uuid import UUID

import typer

from ...application.agent_host.launcher_protocol import LAUNCHER_LANE, AgentLauncherRefusal, AgentStoppedReason
from ...core.external_constants import OutputLanguage
from ...core.hashing import reject_duplicate_json_members
from .common import activate_subcommand_output_language as _activate_subcommand_output_language

_BEARER_LINE_MAX_BYTES: Final = 4 * 1024
_PLAIN_BYTES: Final = frozenset(range(0x21, 0x7F)) - {ord('"'), ord("\\")}


def app_agent_serve(
    ctx: typer.Context,
    agent_source: Path | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Start the hosted agent for the person's stored sign-in and hold it until standard input closes."""
    _activate_subcommand_output_language(ctx, output_language)
    bearer = _read_bearer_line()
    if bearer is None:
        _refuse(AgentLauncherRefusal.SERVICE_FAILED)
    try:
        if agent_source is not None and (not agent_source.is_absolute() or not agent_source.is_dir()):
            _refuse(AgentLauncherRefusal.SERVICE_ABSENT)
        _serve(bearer, agent_source)
    finally:
        bearer[:] = bytes(len(bearer))


def _serve(bearer: bytearray, agent_source: Path | None) -> None:
    from ...adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
    from ...adapters.local_runtime.runtime_client import open_installed_runtime_client
    from ...application.operations.registry import OperationFrontendProjection
    from ...application.runtime.agent_host import RuntimeAgentRefused
    from ...application.runtime.contracts import RuntimeRefusalError
    from ...application.user_profile.login_session import ProfileReceiptRefusedError
    from ...core.bucket_pointer import resolve_active_bucket_id

    profile = resolve_active_bucket_id()
    if profile is None:
        _refuse(AgentLauncherRefusal.SIGNED_OUT)
    try:
        client = asyncio.run(
            open_installed_runtime_client(profile_id=UUID(profile), frontend=OperationFrontendProjection.AGENT_HOST)
        )
    except (RuntimeRefusalError, RuntimeFrontendRefusedError, OSError):
        _refuse(AgentLauncherRefusal.RUNTIME_UNAVAILABLE)
    ended = Event()
    reason = AgentStoppedReason.SESSION_ENDED
    try:
        try:
            client.resume_receipt()
        except (ProfileReceiptRefusedError, RuntimeFrontendRefusedError):
            _refuse(AgentLauncherRefusal.SIGNED_OUT)
        session_ended = Event()
        client.subscribe_session_retirement(session_ended.set)
        try:
            reply = client.start_agent(bearer, agent_source=None if agent_source is None else str(agent_source))
        except RuntimeFrontendRefusedError:
            _refuse(AgentLauncherRefusal.SIGNED_OUT)
        if isinstance(reply, RuntimeAgentRefused):
            _refuse(reply.code)
        _event(
            "agent_ready",
            gateway_port=reply.gateway_port,
            agent_version=reply.agent_version,
            workspace_root=reply.workspace_root,
            lane=LAUNCHER_LANE,
        )
        input_closed = Event()
        Thread(target=_await_input_end, args=(input_closed, ended), name="agent-serve-input", daemon=True).start()
        Thread(target=_relay, args=(session_ended, ended), name="agent-serve-session", daemon=True).start()
        ended.wait()
        if input_closed.is_set():
            reason = AgentStoppedReason.INPUT_CLOSED
    except RuntimeRefusalError:
        _refuse(AgentLauncherRefusal.RUNTIME_UNAVAILABLE)
    finally:
        # Closing the connection ends the session; the runtime stops and reaps the agent with it.
        client.close()
    _event("agent_stopped", reason=reason.value)


def _read_bearer_line() -> bytearray | None:
    """Read the first standard-input line as the strict bearer object, refusing duplicates; never echo it."""
    raw = bytearray()
    while b"\n" not in raw and len(raw) <= _BEARER_LINE_MAX_BYTES:
        try:
            chunk = os.read(0, 1)
        except OSError:
            break
        if not chunk:
            break
        raw += chunk
    try:
        if len(raw) > _BEARER_LINE_MAX_BYTES or not raw.endswith(b"\n"):
            return None
        try:
            document = json.loads(raw, object_pairs_hook=reject_duplicate_json_members)
        except ValueError:
            return None
        if not isinstance(document, dict) or set(document) != {"bearer"} or not isinstance(document["bearer"], str):
            return None
        bearer = bytearray(document["bearer"], "utf-8")
        del document
        if not bearer or any(byte not in _PLAIN_BYTES for byte in bearer):
            bearer[:] = bytes(len(bearer))
            return None
        return bearer
    finally:
        raw[:] = bytes(len(raw))


def _await_input_end(input_closed: Event, ended: Event) -> None:
    """Hold standard input open; its end is the host's stop signal. Anything else it carries is ignored."""
    while True:
        try:
            chunk = os.read(0, 4096)
        except OSError:
            chunk = b""
        if not chunk:
            break
    input_closed.set()
    ended.set()


def _relay(session_ended: Event, ended: Event) -> None:
    session_ended.wait()
    ended.set()


def _refuse(code: AgentLauncherRefusal) -> NoReturn:
    _event("agent_refused", code=code.value)
    raise typer.Exit(1)


def _event(kind: str, **fields: object) -> None:
    sys.stdout.write(json.dumps({"event": kind, **fields}, separators=(",", ":")) + "\n")
    sys.stdout.flush()
