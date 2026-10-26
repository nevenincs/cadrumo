"""Replay a recorded components role conversation in place of the process, for the client's own logic.

A :class:`ReplayLaunch` writes a transcript the real role produced, line by
line, on a real pipe. After a ``review`` line it waits for the client's answer
before writing the rest, as the role does, and it records every byte the
client writes. Its exit status is the one recorded with the transcript unless
a test overrides it. Nothing here decides anything about a component.
"""

from __future__ import annotations

import io
import json
import os
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, override

DATA = Path(__file__).parent / "fixtures" / "components_role"
"""The recorded conversations of the ``components`` role, kept in step with its wire contract, with ``transcripts.json`` naming each command line."""
TRANSCRIPTS: dict[str, dict[str, Any]] = json.loads((DATA / "transcripts.json").read_text(encoding="utf-8"))


def transcript_lines(name: str) -> list[bytes]:
    """The recorded output lines of ``name``, newlines included."""
    return (DATA / f"{name}.jsonl").read_bytes().splitlines(keepends=True)


class _Input(io.RawIOBase):
    """The role's standard input: records what the client writes and wakes a waiting review."""

    def __init__(self) -> None:
        super().__init__()
        self.written = bytearray()
        self.answered = threading.Event()

    @override
    def writable(self) -> bool:
        return True

    @override
    def write(self, data: Any) -> int:
        chunk = bytes(data)
        self.written += chunk
        if b"\n" in chunk:
            self.answered.set()
        return len(chunk)

    @override
    def close(self) -> None:
        super().close()
        self.answered.set()


@dataclass
class ReplayLaunch:
    """One replayed role process."""

    lines: Sequence[bytes]
    status: int
    stall_after: int | None = None
    arguments: tuple[str, ...] = ()
    environment: Mapping[str, str] = field(default_factory=dict)
    ended: bool = False

    def __post_init__(self) -> None:
        read, write = os.pipe()
        self.standard_output: IO[bytes] = os.fdopen(read, "rb", buffering=0)
        self._writer = os.fdopen(write, "wb", buffering=0)
        self._input = _Input()
        self.standard_input: IO[bytes] = io.BufferedWriter(self._input)
        self._done = threading.Event()
        self._release = threading.Event()
        threading.Thread(target=self._write, daemon=True).start()

    @property
    def written(self) -> bytes:
        """Every byte the client wrote to the role's input."""
        return bytes(self._input.written)

    @property
    def input_closed(self) -> bool:
        """Whether the client closed the role's input."""
        return self._input.closed

    def _write(self) -> None:
        try:
            for index, line in enumerate(self.lines):
                if self.stall_after is not None and index == self.stall_after:
                    # A stalled role ends once its input closes, as a setup that loses its client does.
                    self._input.answered.clear()
                    while not (self._input.closed or self._release.is_set()):
                        self._input.answered.wait(0.05)
                    return
                self._writer.write(line)
                if json.loads(line).get("type") == "review":
                    self._input.answered.wait()
        except OSError:
            pass
        finally:
            self._writer.close()
            self._done.set()

    def wait(self, timeout: float) -> int | None:
        """The recorded exit status once every line is written."""
        return self.status if self._done.wait(timeout) else None

    def end(self) -> None:
        """Stop writing and release the pipe."""
        self.ended = True
        self._release.set()
        self._done.wait(5)
        self.standard_output.close()


@dataclass
class ReplayLauncher:
    """Starts a :class:`ReplayLaunch` of one transcript and keeps it for the test to inspect."""

    name: str
    status: int | None = None
    extra: Sequence[bytes] = ()
    stall_after: int | None = None
    only: int | None = None
    launches: list[ReplayLaunch] = field(default_factory=list)

    def __call__(
        self, image: Path, arguments: Sequence[str], environment: Mapping[str, str], directory: Path
    ) -> ReplayLaunch:
        del image, directory
        recorded = TRANSCRIPTS[self.name]
        launch = ReplayLaunch(
            lines=[*transcript_lines(self.name)[: self.only], *self.extra],
            status=recorded["exit"] if self.status is None else self.status,
            stall_after=self.stall_after,
            arguments=tuple(arguments),
            environment=dict(environment),
        )
        self.launches.append(launch)
        return launch

    @property
    def launch(self) -> ReplayLaunch:
        """The one launch this launcher made."""
        (launch,) = self.launches
        return launch
