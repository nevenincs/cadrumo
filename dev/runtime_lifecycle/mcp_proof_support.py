"""MCP attendance and local-model support for built-package development proofs."""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import subprocess
import time
from collections.abc import AsyncGenerator, Callable, Generator, Mapping, Sequence
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

import anyio
import httpx
import psutil
from anyio.abc import ObjectReceiveStream, ObjectSendStream
from mcp import ClientSession
from mcp.shared.message import SessionMessage
from mcp.types import JSONRPCMessage
from pydantic import TypeAdapter

from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_path
from dev.runtime_lifecycle.caller_owned_root import AcceptanceError, Programs, Receipt, require
from dev.runtime_lifecycle.session_holder import RuntimeSessionHolder

from .proof_support import ProcessIdentity, verified_relay

_CALL_SECONDS = 150
_OLLAMA_URL = "http://127.0.0.1:11434"
_LOCAL_TEXT_MODEL = "qwen3:1.7b"
_JSONRPC_MESSAGE_ADAPTER = TypeAdapter(JSONRPCMessage)


@dataclass(slots=True)
class McpSession:
    """One packaged ``cadrumo-mcp`` process and its MCP client session."""

    client: ClientSession
    relay_image: Path
    invocation: ProcessIdentity
    calls: list[str] = field(default_factory=list)

    async def call(self, tool: str, arguments: Mapping[str, object]) -> tuple[bool, dict[str, Any]]:
        """Call one tool and return whether it was an error and its structured content."""
        self.calls.append(tool)
        result = await asyncio.wait_for(self.client.call_tool(tool, dict(arguments)), timeout=_CALL_SECONDS)
        content = result.structured_content if isinstance(result.structured_content, dict) else {}
        return bool(result.is_error), content


@asynccontextmanager
async def mcp_session(
    programs: Programs, environment: Mapping[str, str], directory: Path, *arguments: str
) -> AsyncGenerator[McpSession]:
    """Run the packaged MCP server over stdio for the life of the block."""
    identities: list[ProcessIdentity] = []
    with open(os.devnull, "w", encoding="utf-8") as errors:
        async with (
            owned_stdio(
                str(programs.mcp),
                arguments,
                environment=environment,
                cwd=directory,
                errors=errors,
                on_spawn=lambda pid: identities.append(ProcessIdentity.capture(pid)),
            ) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream, read_timeout_seconds=None) as client,
        ):
            await client.initialize()
            yield McpSession(client, programs.mcp.resolve(strict=True), identities[0])


@asynccontextmanager
async def owned_stdio(
    command: str,
    arguments: Sequence[str],
    *,
    environment: Mapping[str, str],
    cwd: Path,
    errors: TextIO,
    on_spawn: Callable[[int], None] | None = None,
) -> AsyncGenerator[tuple[ObjectReceiveStream[SessionMessage | Exception], ObjectSendStream[SessionMessage]]]:
    """Connect public MCP streams to one explicitly spawned, retained native process."""
    read_sender, reader = anyio.create_memory_object_stream[SessionMessage | Exception](0)
    writer, write_receiver = anyio.create_memory_object_stream[SessionMessage](0)
    async with await anyio.open_process(
        [command, *arguments], env=dict(environment), cwd=cwd, stderr=errors
    ) as process:
        try:
            require(process.stdin is not None and process.stdout is not None, "MCP pipes unavailable")
            stdin, stdout = process.stdin, process.stdout
            if stdin is None or stdout is None:
                raise AcceptanceError("MCP pipes unavailable")
            if on_spawn is not None:
                on_spawn(process.pid)

            async def receive() -> None:
                pending = b""
                async with read_sender:
                    while True:
                        try:
                            chunk = await stdout.receive(65536)
                        except anyio.EndOfStream:
                            require(not pending, "MCP exited with an incomplete frame")
                            return
                        pending += chunk
                        require(len(pending) <= 1_048_576, "MCP frame exceeds the transport bound")
                        while b"\n" in pending:
                            line, pending = pending.split(b"\n", 1)
                            try:
                                message = SessionMessage(_JSONRPC_MESSAGE_ADAPTER.validate_json(line))
                            except ValueError as error:
                                await read_sender.send(error)
                            else:
                                await read_sender.send(message)

            async def send() -> None:
                async with write_receiver:
                    async for message in write_receiver:
                        encoded = message.message.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8")
                        require(len(encoded) <= 1_048_576, "MCP command exceeds the transport bound")
                        await stdin.send(encoded + b"\n")

            async with anyio.create_task_group() as group:
                group.start_soon(receive)
                group.start_soon(send)
                try:
                    yield reader, writer
                finally:
                    group.cancel_scope.cancel()
        finally:
            with anyio.CancelScope(shield=True):
                if process.stdin is not None:
                    with suppress(anyio.BrokenResourceError, anyio.ClosedResourceError):
                        await process.stdin.aclose()
                with anyio.move_on_after(10):
                    await process.wait()
                if process.returncode is None:
                    with suppress(ProcessLookupError):
                        process.terminate()
                    with anyio.move_on_after(10):
                        await process.wait()
                if process.returncode is None:
                    with suppress(ProcessLookupError):
                        process.kill()
                    with anyio.move_on_after(10):
                        await process.wait()
                    require(process.returncode is not None, "owned MCP process could not be reaped")
                await reader.aclose()
                await writer.aclose()


async def ask_and_decide(
    holder: RuntimeSessionHolder, session: McpSession, *, approve: bool, receipt: Receipt, step: str
) -> tuple[bool, dict[str, Any]]:
    """Approve one verified relay's pending ask through correlated runtime commands."""
    call = asyncio.create_task(session.call("describe", {"definition_id": "user-profile.view"}))
    deadline = time.monotonic() + _CALL_SECONDS
    try:
        while True:
            inventory = await asyncio.to_thread(holder.command, "attendance_inventory")
            require(inventory.get("kind") == "attendance_inventory", "runtime returned no attendance inventory")
            candidates = inventory.get("candidates")
            if not isinstance(candidates, list):
                raise AcceptanceError("runtime attendance inventory has no candidate list")
            owned = [
                item
                for item in candidates
                if isinstance(item, dict)
                and type(item.get("process_id")) is int
                and verified_relay(item["process_id"], session.relay_image, session.invocation)
            ]
            require(len(owned) <= 1, "multiple owned relays ask on one proof connection")
            if owned:
                ask = owned[0]
                require(isinstance(ask.get("attendance_id"), str), "runtime candidate omitted its ask identity")
                decision = await asyncio.to_thread(
                    holder.command, "attendance_decision", attendance_id=ask["attendance_id"], approve=approve
                )
                require(
                    decision.get("kind") == "attendance_decided" and decision.get("approved") is approve,
                    "runtime attendance decision differs from the person's answer",
                )
                is_error, content = await call
                receipt.record(
                    step, process_id_verified=True, approved=approve, call_error=is_error, code=content.get("code")
                )
                return is_error, content
            if call.done():
                await call
                raise AcceptanceError("the relay answered before the person's attendance decision")
            require(time.monotonic() < deadline, "runtime recorded no ask from the owned relay")
            await asyncio.sleep(0.25)
    finally:
        if not call.done():
            call.cancel()
            with suppress(asyncio.CancelledError):
                await call


def model_store(chosen: Path | None) -> Path:
    """Return the Ollama model store to read: the chosen one, else Cadrumo's own.

    Cadrumo's Ollama processes keep their weights in the storage root's
    model member, so that member is the store this proof reads by default.
    """
    return chosen if chosen is not None else storage_path(StorageCategory.OLLAMA_MODELS)


@contextlib.contextmanager
def local_model(scratch: Path, models: Path) -> Generator[bool]:
    """Serve the local text model on the loopback port for the block; say whether it is available.

    A server this harness did not start is never used or stopped. Ollama's
    pruning of blobs it does not recognise is switched off, so an existing
    model store is only read.
    """
    try:
        httpx.get(f"{_OLLAMA_URL}/api/tags", timeout=1)
    except httpx.HTTPError:
        pass
    else:
        raise AcceptanceError("a model server already listens on the loopback port; this run uses only its own")
    found = shutil.which("ollama") or str(
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    )
    if not Path(found).is_file() or not models.is_dir():
        yield False
        return
    environment = {**os.environ, "OLLAMA_MODELS": str(models), "OLLAMA_HOST": "127.0.0.1:11434", "OLLAMA_NOPRUNE": "1"}
    with (scratch / "ollama.log").open("wb") as output:
        server = subprocess.Popen(  # noqa: S603 -- the installed local model server; no shell.
            [found, "serve"], env=environment, stdout=output, stderr=subprocess.STDOUT
        )
        try:
            deadline = time.monotonic() + 60
            tags = None
            while tags is None and time.monotonic() < deadline:
                require(server.poll() is None, "the owned local model server exited before readiness")
                with contextlib.suppress(httpx.HTTPError, ValueError):
                    tags = httpx.get(f"{_OLLAMA_URL}/api/tags", timeout=1).json()
                time.sleep(0.5)
            if not isinstance(tags, dict):
                raise AcceptanceError("the owned local model server did not reach readiness")
            names = {item.get("name") for item in tags.get("models", []) if isinstance(item, dict)}
            yield _LOCAL_TEXT_MODEL in names
        finally:
            # The server starts a model runner per loaded model; stopping only the server leaves it running.
            with suppress(psutil.Error):
                tree = [psutil.Process(server.pid), *psutil.Process(server.pid).children(recursive=True)]
                for process in tree:
                    with suppress(psutil.Error):
                        process.terminate()
                _gone, alive = psutil.wait_procs(tree, timeout=30)
                for process in alive:
                    with suppress(psutil.Error):
                        process.kill()
                psutil.wait_procs(alive, timeout=30)
            server.wait(timeout=30)


async def observe(session: McpSession, operation_id: str) -> dict[str, Any]:
    """Return the operation's current projection as the agent observes it."""
    is_error, observed = await session.call(
        "observe", {"observation": {"operation_id": operation_id, "after_cursor": 0, "page_limit": 32}}
    )
    require(not is_error, f"observe refused: {observed}")
    reply = observed.get("reply") or {}
    observation = reply.get("observation") if isinstance(reply, dict) else None
    projection = observation.get("projection") if isinstance(observation, dict) else None
    if not isinstance(projection, dict):
        raise AcceptanceError("runtime observation released no operation projection")
    return projection


async def execute(session: McpSession, definition_id: str, payload: Mapping[str, object]) -> str:
    """Submit and start a registered operation through MCP; return the operation id its receipt names."""
    is_error, submitted = await session.call(
        "execute", {"definition_id": definition_id, "payload": dict(payload), "start": True}
    )
    require(not is_error, f"{definition_id} refused: {submitted}")
    operation_id = (submitted.get("receipt") or {}).get("operation_id")
    require(isinstance(operation_id, str), f"{definition_id} named no operation: {submitted}")
    return str(operation_id)


async def settled(session: McpSession, operation_id: str) -> dict[str, Any]:
    """Wait until the operation's result is terminal and return it."""
    deadline = time.monotonic() + _CALL_SECONDS
    while True:
        is_error, result = await session.call("result", {"result": {"operation_id": operation_id}})
        document = result.get("document")
        if (
            not is_error
            and result.get("outcome") == "reply"
            and isinstance(document, dict)
            and document.get("code") != "operation_not_terminal"
        ):
            return result
        require(time.monotonic() < deadline, f"the operation did not settle: {result}")
        await asyncio.sleep(1)
