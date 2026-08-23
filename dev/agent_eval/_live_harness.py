"""Live subagent-persona harness: drive the real console, capture the trajectory.

Capabilities are measured by LIVE
subagent personas — a language-model (or scripted) driver plays a harness
persona over a REAL MCP client session against the REAL ``cadrumo-mcp`` server,
and every ``tools/call`` round-trip, narration, and elicitation exchange is
captured verbatim as a :class:`LiveTrajectory` for scoring against the golden
scenarios with the faithfulness and confirmation checks applied to OBSERVED
calls, not caller-injected verdicts.

Boundary note: this module never imports the MCP server layer
(``cadrumo_harness.mcp``). The server is a SUBPROCESS reached over stdio through
the ``mcp`` client SDK (a lazy, extra-gated import mirroring the server's own
posture), and the tool-name → registry-command-key mapping is caller-supplied —
the caller (a test, which may import ``cadrumo_harness.mcp``) builds it from the
same descriptor source the server serves, preserving the injection pattern the
runner's docstring documents for every other dimension.

The driver is injectable behind :class:`PersonaDriver`:

- :class:`ScriptedPersonaDriver` replays a fixed action sequence — the
  deterministic floor a CI gate can run without any model in the loop.
- :class:`AnthropicPersonaDriver` is the live subagent persona: a lazy,
  extra-gated Anthropic tool-use loop seeded with the shipped operator rules,
  the persona document, and the scenario's skill, exactly the context a real
  operator session would carry.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, ClassVar, Protocol

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.external_constants import UTF_8_ENCODING as _UTF_8

from ._models import (
    ElicitationAction,
    LiveElicitationRecord,
    LiveNarrationRecord,
    LiveToolCallRecord,
    LiveTrajectory,
)

if TYPE_CHECKING:  # pragma: no cover - typing-only imports
    from anthropic.types import MessageParam, ToolParam
    from mcp import ClientSession

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

_MCP_INSTALL_HINT = (
    "the live harness requires the MCP client SDK; install the harness distribution: pip install cadrumo-harness"
)
_ANTHROPIC_INSTALL_HINT = (
    "the Anthropic persona driver requires the anthropic SDK; install the extra: pip install 'cadrumo[anthropic]'"
)


class LiveHarnessError(RuntimeError):
    """Raised when the live harness cannot run (missing extra, dead server, driver fault)."""

    __bare_base_rationale__: ClassVar[str] = (
        "agent-harness live-eval scaffolding runtime error; intentionally a plain RuntimeError (a "
        "harness-boundary execution signal), not an operator-facing registry-bound filing error"
    )


class LiveToolSpec(BaseModel):
    """One tool as advertised by the live server's ``tools/list``."""

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    description: str = ""
    input_schema_json: str = "{}"


class LiveCallTool(BaseModel):
    """Driver action: invoke one tool with JSON-serialisable arguments."""

    model_config = _STRICT_FROZEN

    tool_name: str = Field(min_length=1)
    arguments_json: str = "{}"


class LiveNarrate(BaseModel):
    """Driver action: produce operator-facing narration for the preceding result."""

    model_config = _STRICT_FROZEN

    step: str = ""
    text: str = Field(min_length=1)


class LiveFinish(BaseModel):
    """Driver action: the persona is done; close the session."""

    model_config = _STRICT_FROZEN


PersonaAction = LiveCallTool | LiveNarrate | LiveFinish


class PersonaDriver(Protocol):
    """The injectable persona playing the session.

    ``start`` receives the advertised tool set once, before the first action.
    ``next_action`` receives the record of the previous tool call (``None``
    before the first) and returns the next action; the harness stops on
    :class:`LiveFinish` or when ``max_actions`` is exhausted.
    """

    async def start(self, tools: tuple[LiveToolSpec, ...]) -> None: ...  # pragma: no cover - protocol

    async def next_action(self, last: LiveToolCallRecord | None) -> PersonaAction: ...  # pragma: no cover


#: The submitted-form-data value shape the MCP ``ElicitResult.content`` field
#: accepts on the wire (``mcp.types.ElicitResult.content``): strings, numbers,
#: booleans, or arrays of strings.
ElicitationContentValue = str | int | float | bool | list[str] | None


class ElicitationResponder(Protocol):
    """Decides one elicitation exchange: the action and (on accept) the content."""

    def __call__(
        self,
        message: str,
        requested_schema: Mapping[str, object],
    ) -> tuple[ElicitationAction, Mapping[str, ElicitationContentValue] | None]: ...  # pragma: no cover - protocol


def decline_all_elicitations(
    message: str,
    requested_schema: Mapping[str, object],
) -> tuple[ElicitationAction, Mapping[str, ElicitationContentValue] | None]:
    """The safe default responder: decline every server-initiated question.

    Returns:
        A :class:`ElicitationAction`.
    """
    return (ElicitationAction.DECLINE, None)


def accept_all_confirmations(
    message: str,
    requested_schema: Mapping[str, object],
) -> tuple[ElicitationAction, Mapping[str, ElicitationContentValue] | None]:
    """A scenario responder that accepts every confirmation with empty content.

    Use only in scenarios that deliberately exercise the post-confirmation
    path; the scorer still records every exchange for confirmation-honesty
    assertions.

    Returns:
        A :class:`ElicitationAction`.
    """
    return (ElicitationAction.ACCEPT, {})


class ScriptedPersonaDriver:
    """Replays a fixed action sequence — the deterministic, model-free floor."""

    def __init__(self, actions: Sequence[PersonaAction]) -> None:
        self._actions = list(actions)
        self._cursor = 0
        self.tools: tuple[LiveToolSpec, ...] = ()

    async def start(self, tools: tuple[LiveToolSpec, ...]) -> None:
        self.tools = tools

    async def next_action(self, last: LiveToolCallRecord | None) -> PersonaAction:
        if self._cursor >= len(self._actions):
            return LiveFinish()
        action = self._actions[self._cursor]
        self._cursor += 1
        return action


class AnthropicPersonaDriver:
    """The live subagent persona: an Anthropic tool-use loop over the session's tools.

    Seeded with the operating context a real session carries — the shipped
    operator rules, the persona document, and the scenario's skill — and the
    user brief describing the taxpayer's ask. Each ``next_action`` advances
    the model one content block: a ``tool_use`` block becomes
    :class:`LiveCallTool`, a text block becomes :class:`LiveNarrate`, and an
    ``end_turn`` stop with no pending blocks becomes :class:`LiveFinish`.
    """

    def __init__(
        self,
        *,
        system_prompt: str,
        user_brief: str,
        model: str,
        max_model_turns: int = 16,
        max_tokens: int = 2048,
    ) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise LiveHarnessError(_ANTHROPIC_INSTALL_HINT) from exc
        self._client = anthropic.AsyncAnthropic()
        self._model = model
        self._max_tokens = max_tokens
        self._max_model_turns = max_model_turns
        self._turns = 0
        self._system = system_prompt
        self._messages: list[MessageParam] = [{"role": "user", "content": user_brief}]
        self._tool_defs: list[ToolParam] = []
        self._pending: list[PersonaAction] = []
        self._open_tool_use_id: str | None = None
        self._open_tool_name: str | None = None

    async def start(self, tools: tuple[LiveToolSpec, ...]) -> None:
        self._tool_defs = [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": json.loads(spec.input_schema_json),
            }
            for spec in tools
        ]

    async def next_action(self, last: LiveToolCallRecord | None) -> PersonaAction:
        if self._open_tool_use_id is not None:
            if last is None:
                raise LiveHarnessError("driver expected a tool result for the open tool_use block")
            self._messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": self._open_tool_use_id,
                            "content": last.result_text,
                            "is_error": last.is_error,
                        },
                    ],
                },
            )
            self._open_tool_use_id = None
            self._open_tool_name = None
        if self._pending:
            return self._pop_pending()
        if self._turns >= self._max_model_turns:
            return LiveFinish()
        self._turns += 1
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=self._system,
            messages=self._messages,
            tools=self._tool_defs,
        )
        self._messages.append({"role": "assistant", "content": response.content})
        last_step = self._open_tool_name or ""
        for block in response.content:
            if block.type == "text" and block.text.strip():
                self._pending.append(LiveNarrate(step=last_step, text=block.text))
            elif block.type == "tool_use":
                self._pending.append(
                    LiveCallTool(
                        tool_name=block.name,
                        arguments_json=json.dumps(block.input, ensure_ascii=False, sort_keys=True),
                    ),
                )
                self._open_tool_use_id = block.id
                self._open_tool_name = block.name
                break
        if not self._pending:
            return LiveFinish()
        return self._pop_pending()

    def _pop_pending(self) -> PersonaAction:
        return self._pending.pop(0)


def _result_text(result: object) -> str:
    content = getattr(result, "content", None) or ()
    parts: list[str] = []
    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(parts)


async def run_live_session_async(
    server_command: Sequence[str],
    *,
    persona: str,
    session_id: str,
    driver: PersonaDriver,
    command_key_by_tool: Mapping[str, str],
    scenario: str = "",
    env: Mapping[str, str] | None = None,
    elicitation_responder: ElicitationResponder = decline_all_elicitations,
    max_actions: int = 64,
) -> LiveTrajectory:
    """Start the real server, drive one persona session, and capture the trajectory.

    Args:
        server_command: The argv that starts the server (e.g.
            ``("uv", "run", "--no-sync", "cadrumo-mcp")``); it is spawned as a
            subprocess and spoken to over stdio.
        persona: The harness persona the driver plays; exported to the server
            via ``CADRUMO_MCP_PERSONA`` so the persona-scope gate is live.
        session_id: Caller-supplied stable session identity (clock-free).
        driver: The persona driver (scripted or model-backed).
        command_key_by_tool: Caller-built mapping from advertised tool name to
            registry command key; tools outside it record an empty key.
        scenario: The golden scenario name this session runs, if any.
        env: Extra environment for the server subprocess.
        elicitation_responder: Decides every server-initiated elicitation.
        max_actions: Hard cap on driver actions, a runaway backstop.

    Returns:
        The captured :class:`LiveTrajectory`.
    """
    try:
        import mcp.types as mcp_types
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.session import ClientRequestContext
        from mcp.client.stdio import stdio_client
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise LiveHarnessError(_MCP_INSTALL_HINT) from exc

    tool_calls: list[LiveToolCallRecord] = []
    narrations: list[LiveNarrationRecord] = []
    elicitations: list[LiveElicitationRecord] = []

    async def _on_elicitation(
        context: ClientRequestContext,
        params: mcp_types.ElicitRequestParams,
    ) -> mcp_types.ElicitResult | mcp_types.ErrorData:
        message = str(getattr(params, "message", ""))
        schema = getattr(params, "requested_schema", None) or {}
        action, content = elicitation_responder(message, schema if isinstance(schema, Mapping) else {})
        elicitations.append(
            LiveElicitationRecord(
                message=message or "(empty elicitation message)",
                action=action,
                content_json=json.dumps(dict(content), ensure_ascii=False, sort_keys=True) if content else "",
            ),
        )
        if action is ElicitationAction.ACCEPT:
            return mcp_types.ElicitResult(action="accept", content=dict(content or {}))
        if action is ElicitationAction.DECLINE:
            return mcp_types.ElicitResult(action="decline")
        return mcp_types.ElicitResult(action="cancel")

    # StdioServerParameters.env REPLACES the subprocess environment; a bare
    # override dict would strip PATH and friends and the spawn hangs or dies.
    # Merge the parent environment with the caller's additions instead.
    merged_env = {**os.environ, **(env or {}), "CADRUMO_MCP_PERSONA": persona}
    params = StdioServerParameters(
        command=server_command[0],
        args=list(server_command[1:]),
        env=merged_env,
        encoding=_UTF_8,
    )
    async with stdio_client(params) as (read_stream, write_stream):
        session: ClientSession
        async with ClientSession(read_stream, write_stream, elicitation_callback=_on_elicitation) as session:
            await session.initialize()
            listed = await session.list_tools()
            specs = tuple(
                LiveToolSpec(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema_json=json.dumps(tool.input_schema or {}, ensure_ascii=False, sort_keys=True),
                )
                for tool in listed.tools
            )
            await driver.start(specs)

            last: LiveToolCallRecord | None = None
            for _ in range(max_actions):
                action = await driver.next_action(last)
                if isinstance(action, LiveFinish):
                    break
                if isinstance(action, LiveNarrate):
                    narrations.append(LiveNarrationRecord(step=action.step, text=action.text))
                    last = None
                    continue
                arguments = json.loads(action.arguments_json)
                started = time.monotonic()
                result = await session.call_tool(action.tool_name, arguments)
                duration_ms = int((time.monotonic() - started) * 1000)
                last = LiveToolCallRecord(
                    tool_name=action.tool_name,
                    command_key=command_key_by_tool.get(action.tool_name, ""),
                    arguments_json=action.arguments_json,
                    is_error=bool(getattr(result, "isError", False)),
                    result_text=_result_text(result),
                    duration_ms=duration_ms,
                )
                tool_calls.append(last)

    return LiveTrajectory(
        scenario=scenario,
        persona=persona,
        session_id=session_id,
        tool_calls=tuple(tool_calls),
        narrations=tuple(narrations),
        elicitations=tuple(elicitations),
    )


def run_live_session(
    server_command: Sequence[str],
    *,
    persona: str,
    session_id: str,
    driver: PersonaDriver,
    command_key_by_tool: Mapping[str, str],
    scenario: str = "",
    env: Mapping[str, str] | None = None,
    elicitation_responder: ElicitationResponder = decline_all_elicitations,
    max_actions: int = 64,
) -> LiveTrajectory:
    """Synchronous wrapper over :func:`run_live_session_async` for test callers.

    Returns:
        A :class:`LiveTrajectory`.
    """
    return asyncio.run(
        run_live_session_async(
            server_command,
            persona=persona,
            session_id=session_id,
            driver=driver,
            command_key_by_tool=command_key_by_tool,
            scenario=scenario,
            env=env,
            elicitation_responder=elicitation_responder,
            max_actions=max_actions,
        ),
    )


__all__ = [
    "AnthropicPersonaDriver",
    "ElicitationResponder",
    "LiveCallTool",
    "LiveFinish",
    "LiveHarnessError",
    "LiveNarrate",
    "LiveToolSpec",
    "PersonaAction",
    "PersonaDriver",
    "ScriptedPersonaDriver",
    "accept_all_confirmations",
    "decline_all_elicitations",
    "run_live_session",
    "run_live_session_async",
]
