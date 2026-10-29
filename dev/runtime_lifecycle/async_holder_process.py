"""Own an asyncio holder subprocess and its bounded pipes."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from pathlib import Path

from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo_client.transport.frame_io import MAXIMUM_FRAME_BYTES

from .caller_owned_root import AcceptanceError, require

_STARTUP_SECONDS = 30.0
_CLOSE_SECONDS = 10.0
_REAP_SECONDS = 10.0
_STDERR_CHUNK_BYTES = 4096


class AsyncPipeOwner:
    """Own an asyncio subprocess, its bounded standard streams and stderr drainer."""

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        """Retain the child and start draining its stderr."""
        self.process = process
        self._stderr_task = asyncio.create_task(self._drain_stderr(), name="runtime-session-holder-stderr")
        self._wait_task: asyncio.Task[int] | None = None
        self._closed = False

    @classmethod
    async def launch(cls, executable: Path, arguments: Sequence[str], environment: Mapping[str, str]) -> AsyncPipeOwner:
        """Start one exact image with private pipes and an explicit environment."""
        process = await asyncio.create_subprocess_exec(
            str(executable),
            *arguments,
            env=dict(environment),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=MAXIMUM_FRAME_BYTES + 2,
        )
        owner = cls(process)
        try:
            require(
                process.stdin is not None and process.stdout is not None and process.stderr is not None,
                "runtime holder pipes unavailable",
            )
        except BaseException as primary:
            try:
                await owner.close()
            except BaseException as cleanup:
                raise BaseExceptionGroup("holder pipe validation and cleanup failed", [primary, cleanup]) from primary
            raise
        return owner

    async def write(self, frame: bytes) -> None:
        """Write a complete command frame and bound pipe backpressure."""
        stream = self.process.stdin
        if stream is None:
            raise AcceptanceError("runtime holder stdin closed")
        stream.write(frame)
        try:
            await asyncio.wait_for(stream.drain(), timeout=_STARTUP_SECONDS)
        except TimeoutError as error:
            raise AcceptanceError("runtime holder input timed out") from error

    async def read_line(self, seconds: float) -> bytes:
        """Read one bounded stdout line or refuse the expired reply."""
        stream = self.process.stdout
        if stream is None:
            raise AcceptanceError("runtime holder stdout closed")
        try:
            return await asyncio.wait_for(stream.readline(), timeout=seconds)
        except TimeoutError as error:
            raise AcceptanceError("runtime holder reply timed out") from error
        except (asyncio.LimitOverrunError, ValueError) as error:
            raise AcceptanceError("runtime holder frame refused") from error

    async def _drain_stderr(self) -> None:
        stream = self.process.stderr
        if stream is None:
            return
        while await stream.read(_STDERR_CHUNK_BYTES):
            pass

    async def _wait(self, seconds: float) -> bool:
        if self._wait_task is None:
            self._wait_task = asyncio.create_task(self.process.wait(), name="runtime-session-holder-wait")
        try:
            await asyncio.wait_for(asyncio.shield(self._wait_task), timeout=seconds)
        except TimeoutError:
            return False
        return True

    async def close(self) -> None:
        """Close stdin, settle the exact child, escalate within bounds and finish stderr draining."""
        await await_cancellation_complete(self._close(), task_name="runtime-session-holder-close")

    async def _close(self) -> None:
        if self._closed:
            return
        failures: list[BaseException] = []
        stdin_settled = await self._close_stdin(failures)
        settled = await self._settle_process(failures)
        stderr_settled = await self._settle_stderr(failures)
        self._closed = settled and stdin_settled and stderr_settled and not failures
        if failures:
            raise BaseExceptionGroup("runtime holder process cleanup failed", failures)

    async def _close_stdin(self, failures: list[BaseException]) -> bool:
        """Settle stdin and retain every close failure."""
        stdin_settled = self.process.stdin is None
        stream = self.process.stdin
        if stream is not None:
            if not stream.is_closing():
                try:
                    stream.close()
                except BaseException as error:
                    failures.append(error)
            if stream.is_closing():
                try:
                    await asyncio.wait_for(stream.wait_closed(), timeout=_CLOSE_SECONDS)
                except (BrokenPipeError, ConnectionResetError):
                    stdin_settled = True
                except TimeoutError as error:
                    failure = AcceptanceError("runtime holder stdin did not close")
                    failure.__cause__ = error
                    failures.append(failure)
                except BaseException as error:
                    failures.append(error)
                else:
                    stdin_settled = True

        return stdin_settled

    async def _settle_process(self, failures: list[BaseException]) -> bool:
        """Give the child grace, terminate, kill and reap in that order."""
        settled = await self._wait_retaining_failure(_CLOSE_SECONDS, failures)
        if not settled:
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass
            except BaseException as error:
                failures.append(error)
            settled = await self._wait_retaining_failure(_REAP_SECONDS, failures)
        if not settled:
            try:
                self.process.kill()
            except ProcessLookupError:
                pass
            except BaseException as error:
                failures.append(error)
            settled = await self._wait_retaining_failure(_REAP_SECONDS, failures)
        if not settled:
            failures.append(AcceptanceError("runtime holder process could not be reaped"))

        return settled

    async def _wait_retaining_failure(self, seconds: float, failures: list[BaseException]) -> bool:
        """Record a wait failure without losing the process cleanup owner."""
        try:
            return await self._wait(seconds)
        except BaseException as error:
            failures.append(error)
            return False

    async def _settle_stderr(self, failures: list[BaseException]) -> bool:
        """Retain the original stderr drainer until it ends."""
        stderr_settled = False
        if self._stderr_task.done():
            if self._stderr_task.cancelled():
                failures.append(AcceptanceError("runtime holder stderr drainer was cancelled"))
            else:
                stderr_error = self._stderr_task.exception()
                if stderr_error is None:
                    stderr_settled = True
                else:
                    failures.append(stderr_error)
        else:
            try:
                await asyncio.wait_for(asyncio.shield(self._stderr_task), timeout=_REAP_SECONDS)
            except TimeoutError as error:
                failure = AcceptanceError("runtime holder stderr drainer did not stop")
                failure.__cause__ = error
                failures.append(failure)
            except BaseException as error:
                failures.append(error)
            else:
                stderr_settled = True

        return stderr_settled
