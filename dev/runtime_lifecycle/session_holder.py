"""Own real runtime holders through a bounded, correlated person channel."""

from __future__ import annotations

import asyncio
import struct
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from cadrumo.core.async_cleanup import await_cancellation_complete

from .async_holder_process import AsyncPipeOwner
from .caller_owned_root import AcceptanceError, require
from .holder_protocol import (
    as_desktop_holder,
    decode_holder_line,
    encode_holder_command,
    holder_launch,
    validate_holder_identity,
    validate_holder_reply,
    wipe_password,
)

_PASSWORD_FRAME_LIMIT = 4096
_COMMAND_FRAME_LIMIT = 16_384
_STARTUP_SECONDS = 30.0
# Grace for stdin to settle and the child to exit on its own after EOF; also bounds thread joins.
_CLOSE_SECONDS = 10.0
# Bound for the OS to report that an ended child has exited and closed its stderr, after
# close lets it exit or terminates or kills it. It is separate from the exit grace because a
# short or refused grace must not shorten reaping.
_REAP_SECONDS = 10.0
_WRITE_SECONDS = 30.0
_STDERR_CHUNK_BYTES = 4096
# The leading arguments that start the runtime console script as a role of the desktop image.
_RUNTIME_ROLE = ("--role", "runtime")


class AsyncRuntimeSessionHolder:
    """Asynchronously own a generic-process runtime holder and correlate every reply."""

    def __init__(self) -> None:
        """Start unbound and assign the owned pipe process in ``start``."""
        self.identity: dict[str, Any] = {}
        # The unsolicited ending the runtime reported, `session_retired` or `session_refused`.
        self.ended: str | None = None
        self._owner: AsyncPipeOwner | None = None
        self._lock = asyncio.Lock()
        self._closed = False
        self._closing = False

    @classmethod
    async def start(
        cls,
        runtime: Path,
        *,
        profile_id: UUID,
        environment: Mapping[str, str],
        password: bytearray | None = None,
        frontend: Literal["desktop", "cli"] = "desktop",
    ) -> AsyncRuntimeSessionHolder:
        """Start native receipt admission or explicit development password admission."""
        holder = cls()
        try:
            executable, arguments = holder_launch(runtime, profile_id, environment, password)
            if frontend == "cli":
                arguments = (*arguments, "--frontend", "cli")
            else:
                executable, arguments = as_desktop_holder(executable, arguments)

            async def assign_owner() -> None:
                holder._owner = await AsyncPipeOwner.launch(executable, arguments, environment)

            await await_cancellation_complete(assign_owner(), task_name="runtime-session-holder-launch")
            if password is not None:
                owner = holder._owner
                if owner is None:
                    raise AcceptanceError("runtime holder process unavailable")
                await owner.write(struct.pack("!I", len(password)) + password)
            owner = holder._owner
            if owner is None:
                raise AcceptanceError("runtime holder process unavailable")
            holder.identity = decode_holder_line(await owner.read_line(_STARTUP_SECONDS))
            validate_holder_identity(holder.identity, profile_id)
            return holder
        except BaseException as primary:
            try:
                await holder.close()
            except BaseException as cleanup:
                raise BaseExceptionGroup("runtime holder startup and cleanup failed", [primary, cleanup]) from primary
            raise
        finally:
            wipe_password(password)

    async def _receive(self, seconds: float = _STARTUP_SECONDS) -> dict[str, Any]:
        if self._owner is None:
            raise AcceptanceError("runtime holder process unavailable")
        return decode_holder_line(await self._owner.read_line(seconds))

    async def command(self, action: str, **fields: Any) -> dict[str, Any]:
        """Submit one generic command and require its exact correlation identity."""
        async with self._lock:
            require(not self._closed and not self._closing, "runtime holder is already closed")
            owner = self._owner
            if owner is None:
                raise AcceptanceError("runtime holder process unavailable")
            request_id, encoded = encode_holder_command(action, fields)
            await owner.write(encoded)
            reply = await self._receive()
            if reply.get("kind") in {"session_retired", "session_refused"}:
                self.ended = str(reply["kind"])
                await self._close_locked()
                raise AcceptanceError("the original human holder retired or refused the command")
            validate_holder_reply(
                reply,
                request_id=request_id,
                action=action,
                fields=fields,
                identity=self.identity,
            )
            return reply

    @property
    def exit_code(self) -> int | None:
        """Return the holder process's exit code once it has exited on its own."""
        return None if self._owner is None else self._owner.process.returncode

    async def close(self) -> None:
        """Close stdin and settle the holder process with bounded termination escalation."""
        await await_cancellation_complete(self._close_with_lock(), task_name="runtime-session-holder-close")

    async def _close_with_lock(self) -> None:
        async with self._lock:
            await self._close_locked()

    async def _close_locked(self) -> None:
        if self._closed:
            return
        self._closing = True
        try:
            if self._owner is not None:
                await self._owner.close()
        finally:
            self._closing = False
        self._closed = True
