"""Contained agent trees reached only through private standard pipes."""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from typing import BinaryIO

from ...application.agent_host.controller import AgentHostError, AgentHostRefusal, AgentProcess
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .windows_process import WindowsOwnedProcess, WindowsProcessScope


class WindowsAgentProcess:
    """One agent tree in its own kill-on-close job."""

    def __init__(
        self,
        *,
        scope: WindowsProcessScope,
        process: WindowsOwnedProcess,
        standard_input: BinaryIO,
        standard_output: BinaryIO,
    ) -> None:
        """Take ownership of the job, the agent and both parent pipe ends."""
        self._scope = scope
        self._process = process
        self._input: BinaryIO | None = standard_input
        self._output = standard_output
        self._lines: Queue[bytes | BaseException] = Queue(maxsize=1)
        self._reader: Thread | None = None

    def write_input(self, data: bytearray) -> None:
        """Write and flush these bytes to the agent's standard input."""
        if self._input is None:
            raise BrokenPipeError
        view = memoryview(data)
        try:
            while view:
                written = self._input.write(view)
                if not written:
                    raise BrokenPipeError
                view = view[written:]
            self._input.flush()
        finally:
            view.release()

    def read_output_line(self, *, limit: int, timeout: float) -> bytes:
        """Return the agent's first standard-output line within the bound."""
        if self._reader is None:
            self._reader = Thread(target=self._read_line, args=(limit,), name="agent-ready-line", daemon=True)
            self._reader.start()
        try:
            result = self._lines.get(timeout=timeout)
        except Empty:
            raise TimeoutError from None
        if isinstance(result, BaseException):
            raise result
        return result

    def close_input(self) -> None:
        """Close standard input once: the agent's stop signal."""
        standard_input, self._input = self._input, None
        if standard_input is not None:
            standard_input.close()

    def wait(self, *, timeout: float) -> int | None:
        """Return the agent's exit status, or ``None`` while it still runs at the bound."""
        try:
            return self._process.wait(timeout=timeout)
        except RuntimeRefusalError as error:
            if error.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED:
                return None
            raise

    def terminate(self, *, timeout: float) -> None:
        """End every member of the job, then release the pipe ends."""
        try:
            self._scope.terminate(timeout=timeout)
        finally:
            self.close_input()
            self._output.close()

    def _read_line(self, limit: int) -> None:
        try:
            line = self._output.readline(limit + 1)
            if not line.endswith(b"\n") or len(line) > limit:
                raise EOFError
            self._lines.put(line)
        except BaseException as error:
            self._lines.put(error)


class WindowsAgentProcessLauncher:
    """Start each agent tree in a fresh kill-on-close job with private standard pipes."""

    def launch(
        self, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> AgentProcess:
        """Start the tree; its environment is exactly the one given, with no credential in it."""
        if sys.platform != "win32":
            raise AgentHostError(AgentHostRefusal.LAUNCH_FAILED)
        scope = WindowsProcessScope()
        try:
            process, standard_input, standard_output = scope.launch_with_standard_pipes(
                executable=executable, arguments=arguments, directory=directory, environment=environment
            )
        except BaseException:
            scope.terminate()
            raise
        return WindowsAgentProcess(
            scope=scope, process=process, standard_input=standard_input, standard_output=standard_output
        )
