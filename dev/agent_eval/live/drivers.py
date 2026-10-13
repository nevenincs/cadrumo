"""Drive the packaged MCP server: a scripted client for the floor, or a haiku agent for the live lane.

Every driver records into one :class:`~.recorder.TrajectoryRecorder`, so the
scorer sees one ``LiveTrajectory`` whichever ran. The live agent is always
``claude-haiku-5-5``. It runs through the Anthropic API when
``ANTHROPIC_API_KEY`` is set, offering the model the server's tools and
nothing else; otherwise through the authenticated ``claude`` command line in
print mode with only the cadrumo server configured, no built-in tools, no
session persistence and no user settings. Each run has turn, token and spend
limits.

A scenario may run in phases. Between two phases the harness acts as the
person (revoking a key, locking the profile, signing out, letting the sign-in
lapse) and the agent then continues. Through the API the conversation simply
continues; the command line starts a fresh print-mode session for the next
phase, because it keeps no session.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from dev.packaging.command_execution import run_command

from .outcome import UnavailableError
from .recorder import TrajectoryRecorder

HAIKU_MODEL: Final = "claude-haiku-5-5"
"""The one declared model id; the run records the id the provider reports beside it."""

HAIKU_USD_PER_INPUT_TOKEN: Final = 0.10 / 1_000_000
HAIKU_USD_PER_OUTPUT_TOKEN: Final = 0.50 / 1_000_000
"""Published first-party rates for prompts up to 100K tokens; used only to stop a run that overspends."""

MCP_SERVER_NAME: Final = "cadrumo"
_CLI_TOOL_PREFIX: Final = f"mcp__{MCP_SERVER_NAME}__"
_SETTLE_SECONDS: Final = 300.0
_COLD_START_SECONDS: Final = 120.0
ACTOR: Final = "Synthetic Person"


class DriverKind(StrEnum):
    """Which driver ran a session."""

    SCRIPTED = "scripted"
    ANTHROPIC_API = "anthropic_api"
    CLAUDE_CLI = "claude_cli"


DEFAULT_MAX_USD: Final = 1.00
"""Spend bound per run; the 2026-10-12 haiku runs cost about 0.03 USD each."""


@dataclass(frozen=True, slots=True)
class Limits:
    """Per-run bounds on the agent's turns, tokens, spend and wall time."""

    max_turns: int = 80
    max_tokens: int = 4_000_000
    max_usd: float = DEFAULT_MAX_USD
    max_seconds: float = 1_200.0


@dataclass(slots=True)
class DriverReport:
    """What a driver did, for the receipt: never a verdict."""

    driver: DriverKind
    model_requested: str = HAIKU_MODEL
    model_reported: str = ""
    turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    stop_reasons: list[str] = field(default_factory=list)
    limit_hit: str = ""
    phases_completed: int = 0

    def spend(self) -> float:
        """The spend so far, reported by the provider where it reports it, else from token counts."""
        estimate = self.input_tokens * HAIKU_USD_PER_INPUT_TOKEN + self.output_tokens * HAIKU_USD_PER_OUTPUT_TOKEN
        return max(self.cost_usd, estimate)


@dataclass(frozen=True, slots=True)
class McpLaunch:
    """How to start the packaged MCP server: never a secret, only the profile and a key reference."""

    command: str
    arguments: tuple[str, ...]
    environment: Mapping[str, str]
    cwd: Path


BetweenPhases = Callable[[int], Awaitable[None]]
"""The person's act before phase ``n`` (counted from 1)."""


def select_driver(ambient: Mapping[str, str]) -> DriverKind:
    """The API when its key is present, otherwise the authenticated ``claude`` command line, otherwise unavailable."""
    if bool(ambient.get("ANTHROPIC_API_KEY")):
        return DriverKind.ANTHROPIC_API
    if shutil.which("claude", path=ambient.get("PATH")) is not None:
        return DriverKind.CLAUDE_CLI
    raise UnavailableError(
        "model_credential_missing", "neither ANTHROPIC_API_KEY nor an installed `claude` command line is available"
    )


def _text_of(reply: Any) -> str:
    parts = [getattr(item, "text", "") for item in getattr(reply, "content", ()) if getattr(item, "type", "") == "text"]
    text = "\n".join(part for part in parts if part)
    structured = getattr(reply, "structured_content", None)
    return text or (json.dumps(structured, sort_keys=True) if structured is not None else "")


class RecordedTools:
    """The MCP tools of one session, every call recorded."""

    def __init__(self, session: ClientSession, recorder: TrajectoryRecorder) -> None:
        """Bind a live client session to the recorder."""
        self._session = session
        self.recorder = recorder

    async def tools(self) -> list[dict[str, Any]]:
        """The tools the server offers, as plain name, description and input schema."""
        listed = await self._session.list_tools()
        return [
            {"name": tool.name, "description": tool.description or "", "input_schema": dict(tool.input_schema)}
            for tool in listed.tools
        ]

    async def call(self, name: str, arguments: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str, bool]:
        """Call one tool and record it; a transport failure is recorded as an error result."""
        started = time.monotonic()
        try:
            reply = await self._session.call_tool(name, dict(arguments))
        except Exception as error:  # a failed round-trip is evidence, recorded like any other reply
            text = f"{type(error).__name__}: {error}"
            self.recorder.record_call(
                name, arguments, text, is_error=True, duration_ms=int((time.monotonic() - started) * 1000)
            )
            return None, text, True
        text = _text_of(reply)
        is_error = bool(getattr(reply, "is_error", False))
        self.recorder.record_call(
            name, arguments, text, is_error=is_error, duration_ms=int((time.monotonic() - started) * 1000)
        )
        structured = getattr(reply, "structured_content", None)
        return (structured if isinstance(structured, dict) else None), text, is_error


@asynccontextmanager
async def mcp_session(launch: McpLaunch, stderr_path: Path) -> AsyncGenerator[ClientSession]:
    """Start the packaged MCP server over stdio and hand back an initialized client session.

    The server's standard error goes to a file inside the run directory, which
    teardown removes; it is never part of a capture.
    """
    parameters = StdioServerParameters(
        command=launch.command, args=list(launch.arguments), env=dict(launch.environment), cwd=launch.cwd
    )
    with stderr_path.open("w", encoding="utf-8") as errors:
        async with (
            stdio_client(parameters, errlog=errors) as (reader, writer),
            ClientSession(reader, writer, read_timeout_seconds=_SETTLE_SECONDS) as session,
        ):
            await session.initialize()
            yield session


# --- the scripted floor -------------------------------------------------------------------------------------------


@dataclass(slots=True)
class ScriptedRun:
    """How far the scripted client got, and the refusal that stopped it if one did."""

    completed: bool = False
    stopped_at: str = ""
    refusal: str = ""
    work_unit_id: str = ""


class _RefusedError(Exception):
    def __init__(self, step: str, code: str) -> None:
        super().__init__(f"{step}: {code}")
        self.step, self.code = step, code


def _started(submitted: Mapping[str, Any] | None) -> bool:
    if not (submitted is not None and submitted):
        return False
    start = submitted.get("start")
    return bool(
        submitted.get("outcome") == "submitted"
        and isinstance(start, dict)
        and start.get("kind") == "operation_acknowledged"
    )


async def _settle(tools: RecordedTools, definition_id: str, arguments: dict[str, Any]) -> Mapping[str, Any]:
    """Submit one operation, wait for it to settle, and return its released projection or raise the refusal."""
    submitted, text, _ = await tools.call("execute", arguments)
    if submitted is None or not _started(submitted):
        code = (submitted or {}).get("code") or (submitted or {}).get("outcome") or text[:120]
        raise _RefusedError(definition_id, str(code))
    operation_id = submitted["receipt"]["operation_id"]
    observation = {"operation_id": operation_id, "after_cursor": 0, "page_limit": 32}
    deadline = time.monotonic() + _SETTLE_SECONDS
    while True:
        observed, _, _ = await tools.call("observe", {"observation": observation})
        if (observed is not None and observed) and observed.get("outcome") == "reply":
            projection = observed["reply"]["observation"]["projection"]
            if projection.get("lifecycle") == "terminal":
                break
        if time.monotonic() >= deadline:
            raise _RefusedError(definition_id, "settle_timeout")
        await anyio.sleep(0.2)
    released, text, _ = await tools.call("result", {"result": {"operation_id": operation_id}})
    document = (released or {}).get("document") or {}
    if document.get("outcome") != "success":
        detail = (released or {}).get("error_detail") or {}
        code = detail.get("error_code") or projection.get("refusal_ref") or projection.get("failure_error_code")
        raise _RefusedError(definition_id, str(code or projection.get("terminal_condition") or text[:120]))
    return document["projection"]


async def wait_for_admission(tools: RecordedTools) -> Mapping[str, Any]:
    """Read ``status`` until the server reports a session, or the cold-start bound passes.

    A server that has not yet resumed the sign-in answers ``session: none``
    with a denial, exactly as one that never will; only the bound tells them
    apart, as it does for a client.
    """
    deadline = time.monotonic() + _COLD_START_SECONDS
    while True:
        reply, _, _ = await tools.call("status", {})
        status: dict[str, Any] = reply or {}
        if status.get("session") not in {None, "", "none"} or time.monotonic() >= deadline:
            return status
        await anyio.sleep(5)


async def run_scripted(
    tools: RecordedTools,
    *,
    profile_id: str,
    rows: Sequence[Any],
    modelo: str,
    filing_year: int,
    period: str,
    casillas: Mapping[str, str],
    bindings: Mapping[str, str],
    export_path: Path,
    joint_return_elected: bool | None = None,
) -> ScriptedRun:
    """Prepare the declaration with the MCP tools alone, the way the parity test's agent does."""
    run = ScriptedRun()
    await wait_for_admission(tools)
    try:
        for row in rows:
            added = await _settle(
                tools,
                "ledger.add",
                {
                    "definition_id": "ledger.add",
                    "payload": {
                        "profile_id": profile_id,
                        "booked_date": row.booked_date,
                        "amount": row.amount,
                        "direction": row.direction,
                        "description": row.description,
                        "counterparty": row.counterparty,
                        "actor": ACTOR,
                    },
                },
            )
            await _settle(
                tools,
                "ledger.classify.single",
                {
                    "definition_id": "ledger.classify.single",
                    "payload": {
                        "profile_id": profile_id,
                        "transaction_id": added["transaction"]["transaction_id"],
                        "patch": dict(row.classification),
                        "patch_fields": sorted(row.classification),
                        "actor": ACTOR,
                    },
                },
            )
        created = await _settle(
            tools,
            "modelo.work.create",
            {
                "definition_id": "modelo.work.create",
                "payload": {
                    "profile_id": profile_id,
                    "modelo": modelo,
                    "period": {"filing_year": filing_year, "code": period},
                    "actor": ACTOR,
                },
            },
        )
        run.work_unit_id = created["outcome"]["unit"]["work_unit_id"]
        calculation: dict[str, Any] = {
            "work_unit_id": run.work_unit_id,
            "actor": ACTOR,
            "caller_context": "explicit",
            "inputs": {
                "casilla_overrides": [{"key": key, "value": value} for key, value in casillas.items()],
                "binding_overrides": [{"key": key, "value": value} for key, value in bindings.items()],
            },
        }
        if joint_return_elected is not None:
            # The answer a person gives with --joint-return-elected / --no-joint-return-elected.
            calculation["ordinary_m303_filing_evidence"] = {"joint_return_elected": joint_return_elected}
        await _settle(
            tools, "modelo.work.calculate", {"definition_id": "modelo.work.calculate", "payload": calculation}
        )
        for purpose, definition_id in (("verify", "modelo.work.verify"), ("export", "modelo.export")):
            selected = await _settle(
                tools,
                "modelo.work.revision",
                {
                    "definition_id": "modelo.work.revision",
                    "payload": {"profile_id": profile_id, "work_unit_id": run.work_unit_id, "default_for": purpose},
                },
            )
            payload: dict[str, Any] = {"calculation_revision_id": selected["calculation_revision_id"], "actor": ACTOR}
            if definition_id == "modelo.export":
                payload["output_path"] = str(export_path)
            await _settle(
                tools,
                definition_id,
                {"definition_id": definition_id, "payload": payload, "subject_ref": run.work_unit_id},
            )
    except _RefusedError as refused:
        run.stopped_at, run.refusal = refused.step, refused.code
        return run
    run.completed = True
    return run


# --- the live agent through the Anthropic API -------------------------------------------------------------------


def _over(report: DriverReport, limits: Limits, started: float) -> str:
    if report.turns >= limits.max_turns:
        return "max_turns"
    if report.input_tokens + report.output_tokens >= limits.max_tokens:
        return "max_tokens"
    if report.spend() >= limits.max_usd:
        return "max_usd"
    if time.monotonic() - started >= limits.max_seconds:
        return "max_seconds"
    return ""


async def run_api_agent(
    tools: RecordedTools,
    *,
    system: str,
    phases: Sequence[str],
    limits: Limits,
    between: BetweenPhases | None = None,
) -> DriverReport:
    """Run the haiku agent over the server's tools through the Anthropic API, phase after phase."""
    import anthropic
    from anthropic.types import MessageParam, ToolParam, ToolResultBlockParam

    report = DriverReport(driver=DriverKind.ANTHROPIC_API)
    client = anthropic.AsyncAnthropic()
    offered = [
        ToolParam(name=tool["name"], description=tool["description"], input_schema=tool["input_schema"])
        for tool in await tools.tools()
    ]
    messages: list[MessageParam] = []
    started = time.monotonic()
    for index, prompt in enumerate(phases):
        if index and between is not None:
            await between(index)
        tools.recorder.begin_phase()
        messages.append({"role": "user", "content": prompt})
        while True:
            report.limit_hit = _over(report, limits, started)
            if report.limit_hit:
                return report
            response = await client.messages.create(
                model=HAIKU_MODEL, max_tokens=16_000, system=system, tools=offered, messages=messages
            )
            report.turns += 1
            report.model_reported = response.model
            report.input_tokens += response.usage.input_tokens
            report.output_tokens += response.usage.output_tokens
            report.stop_reasons.append(str(response.stop_reason))
            messages.append({"role": "assistant", "content": response.content})
            last_step = ""
            results: list[ToolResultBlockParam] = []
            for block in response.content:
                if block.type == "text":
                    tools.recorder.record_narration(block.text, step=last_step)
                elif block.type == "tool_use":
                    arguments: dict[str, Any] = dict(block.input)
                    _, text, is_error = await tools.call(block.name, arguments)
                    definition = arguments.get("definition_id")
                    last_step = definition if isinstance(definition, str) else ""
                    results.append(
                        ToolResultBlockParam(type="tool_result", tool_use_id=block.id, content=text, is_error=is_error)
                    )
            if response.stop_reason != "tool_use" or not results:
                break
            messages.append({"role": "user", "content": results})
        report.phases_completed = index + 1
    return report


# --- the live agent through the claude command line --------------------------------------------------------------


def _cli_environment(ambient: Mapping[str, str]) -> dict[str, str]:
    """The command line's own allow-listed environment: what it needs to find its sign-in, nothing else."""
    from .isolated_host import allowlisted_environment

    environment = allowlisted_environment(ambient)
    for name in ("TEMP", "TMP", "HOME"):
        if name in ambient:
            environment[name] = ambient[name]
    return environment


def _tool_name(name: str) -> str:
    return name.removeprefix(_CLI_TOOL_PREFIX)


def _tool_result_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    return json.dumps(content)


def translate_cli_stream(lines: Sequence[str], recorder: TrajectoryRecorder, report: DriverReport) -> None:
    """Turn ``claude -p --output-format stream-json`` lines into recorded calls and narrations.

    A ``tool_use`` is held until its ``tool_result`` arrives, then recorded as
    one round-trip. Lines that are not JSON are ignored; they never reach a
    capture.
    """
    pending: dict[str, tuple[str, dict[str, Any], float]] = {}
    last_step = ""
    for position, line in enumerate(lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            report.model_reported = str(event.get("model", ""))
        elif kind == "assistant":
            message = event.get("message") or {}
            report.model_reported = str(message.get("model", report.model_reported))
            for block in message.get("content") or ():
                if block.get("type") == "text":
                    recorder.record_narration(str(block.get("text", "")), step=last_step)
                elif block.get("type") == "tool_use":
                    arguments = block.get("input") if isinstance(block.get("input"), dict) else {}
                    pending[str(block.get("id"))] = (_tool_name(str(block.get("name", ""))), arguments, position)
        elif kind == "user":
            for block in (event.get("message") or {}).get("content") or ():
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                name, arguments, _ = pending.pop(str(block.get("tool_use_id")), ("(unknown)", {}, position))
                recorder.record_call(
                    name,
                    arguments,
                    _tool_result_text(block.get("content")),
                    is_error=bool(block.get("is_error")),
                    duration_ms=0,
                )
                definition = arguments.get("definition_id")
                last_step = definition if isinstance(definition, str) else ""
        elif kind == "result":
            report.turns += int(event.get("num_turns") or 0)
            report.cost_usd += float(event.get("total_cost_usd") or 0.0)
            usage = event.get("usage") or {}
            report.input_tokens += int(usage.get("input_tokens") or 0)
            report.output_tokens += int(usage.get("output_tokens") or 0)
            report.stop_reasons.append(str(event.get("subtype", "")))
    for name, arguments, _ in pending.values():
        recorder.record_call(name, arguments, "", is_error=True, duration_ms=0)


def run_cli_agent(
    launch: McpLaunch,
    recorder: TrajectoryRecorder,
    *,
    system: str,
    phases: Sequence[str],
    limits: Limits,
    work_directory: Path,
    ambient: Mapping[str, str],
    between: Callable[[int], None] | None = None,
) -> DriverReport:
    """Run the haiku agent through the authenticated ``claude`` command line, one print-mode session per phase.

    The MCP configuration lives in a private directory inside the run and is
    removed with it. It names the packaged server, its arguments and its
    allow-listed environment, and nothing else.
    """
    report = DriverReport(driver=DriverKind.CLAUDE_CLI)
    executable = shutil.which("claude", path=ambient.get("PATH"))
    if executable is None:
        raise UnavailableError("model_credential_missing", "the `claude` command line is not installed")
    private = work_directory / "agent-cli"
    private.mkdir(parents=True, exist_ok=False)
    configuration = private / "mcp.json"
    configuration.write_text(
        json.dumps(
            {
                "mcpServers": {
                    MCP_SERVER_NAME: {
                        "type": "stdio",
                        "command": launch.command,
                        "args": list(launch.arguments),
                        "env": dict(launch.environment),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    started = time.monotonic()
    try:
        for index, prompt in enumerate(phases):
            if index and between is not None:
                between(index)
            recorder.begin_phase()
            report.limit_hit = _over(report, limits, started)
            if report.limit_hit:
                break
            completed = run_command(
                [
                    executable,
                    "-p",
                    "--model",
                    HAIKU_MODEL,
                    "--output-format",
                    "stream-json",
                    "--verbose",
                    "--strict-mcp-config",
                    "--mcp-config",
                    str(configuration),
                    "--tools=",
                    "--allowedTools",
                    f"mcp__{MCP_SERVER_NAME}",
                    "--no-session-persistence",
                    "--setting-sources",
                    "project",
                    "--max-turns",
                    str(max(1, limits.max_turns - report.turns)),
                    "--max-budget-usd",
                    f"{max(0.01, limits.max_usd - report.spend()):.2f}",
                    "--system-prompt",
                    system,
                ],
                cwd=private,
                environment=_cli_environment(ambient),
                timeout_seconds=max(1.0, limits.max_seconds - (time.monotonic() - started)),
                errors="replace",
                input_text=prompt,
            )
            translate_cli_stream(completed.stdout.splitlines(), recorder, report)
            if completed.returncode != 0 and not report.stop_reasons:
                report.stop_reasons.append(f"exit_{completed.returncode}")
            report.phases_completed = index + 1
    finally:
        shutil.rmtree(private, ignore_errors=True)
    return report


def ambient_environment() -> dict[str, str]:
    """This process's environment, read once; only the scrubber and the driver selection see all of it."""
    return dict(os.environ)
