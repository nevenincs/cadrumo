"""Time-bounded search of person-supplied patterns, in a child that can be ended.

Every search of a pattern a person wrote goes through :func:`first_matching_patterns`,
which runs one batch in one contained child of :mod:`cadrumo.core.pattern_search_worker`
and kills it when the batch outruns its budget. An overrun is a typed answer, not a
failure of the caller; a child that cannot be started or contained is a separate
failure, because nothing here falls back to searching in this process.

The child answers pattern by pattern: a text leaves the batch at the first pattern
that finds it, so each pattern reads exactly the texts a row-by-row first match
would give it, and an overrun names the pattern that was running.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Any, Final, cast

from .child_console import child_console_creation_flags
from .config import load_settings
from .package_interpreter import isolated_interpreter_command
from .storage_environment import ChildEnvironmentProfile, child_environment
from .storage_taxonomy import StorageCategory
from .storage_taxonomy_locations import storage_path

_WORKER_MODULE: Final = "cadrumo.core.pattern_search_worker"

PATTERN_SEARCH_BASE_SECONDS: Final = 2.0
"""What one batch may spend however small: far beyond any sound pattern on a ledger's descriptions."""

PATTERN_SEARCH_SECONDS_PER_SEARCH: Final = 0.00005
"""What each pattern-on-text pair adds, far above a plain search's microsecond, so a large ledger is no overrun."""

PATTERN_SEARCH_MAX_SECONDS: Final = 30.0
"""The most any batch may take, whatever its size."""

_START_SECONDS: Final = 30.0
"""How long a child may take to start and take the request: a saturated host, not the pattern's doing."""

_SETTLE_SECONDS: Final = 2.0
_CHILD_CPU_SECONDS: Final = 60
_CHILD_MEMORY_BYTES: Final = 1024 * 1024 * 1024


class PatternSearchOverrunError(Exception):
    """A pattern outran the batch's budget, or the child's memory; the child has been ended."""

    def __init__(self, pattern_index: int) -> None:
        """Name the pattern that was running, by its place in the batch."""
        super().__init__("a pattern search did not finish within its bound")
        self.pattern_index = pattern_index


class PatternSearchUnreadableError(Exception):
    """The child's ``re`` could not read a pattern."""

    def __init__(self, pattern_index: int) -> None:
        """Name the unreadable pattern, by its place in the batch."""
        super().__init__("a pattern could not be read")
        self.pattern_index = pattern_index


class PatternSearchUnavailableError(Exception):
    """The child could not be started, contained or understood, so nothing was searched."""


def pattern_search_budget_seconds(*, patterns: int, texts: int) -> float:
    """Return the seconds a batch of this size may run."""
    return min(
        PATTERN_SEARCH_BASE_SECONDS + patterns * texts * PATTERN_SEARCH_SECONDS_PER_SEARCH, PATTERN_SEARCH_MAX_SECONDS
    )


if sys.platform == "win32":
    from ctypes import wintypes

    from .windows_job_object import (
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
        JOB_OBJECT_LIMIT_ACTIVE_PROCESS,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        JOB_OBJECT_LIMIT_PROCESS_MEMORY,
        JOB_OBJECT_LIMIT_PROCESS_TIME,
        JOB_OBJECT_TIME_UNITS_PER_SECOND,
        JobObjectExtendedLimitInformation,
    )

    class _Containment:
        """A kill-on-close Job Object holding exactly the one child, ended with its last handle."""

        def __init__(self) -> None:
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            handle = self._kernel32.CreateJobObjectW(None, None)
            if not handle:
                raise PatternSearchUnavailableError("the pattern search job could not be created")
            self._handle: int = int(handle)
            information = JobObjectExtendedLimitInformation()
            information.BasicLimitInformation.PerProcessUserTimeLimit = (
                _CHILD_CPU_SECONDS * JOB_OBJECT_TIME_UNITS_PER_SECOND
            )
            information.BasicLimitInformation.ActiveProcessLimit = 1
            information.BasicLimitInformation.LimitFlags = (
                JOB_OBJECT_LIMIT_PROCESS_TIME
                | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
                | JOB_OBJECT_LIMIT_PROCESS_MEMORY
                | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            information.ProcessMemoryLimit = _CHILD_MEMORY_BYTES
            if not self._kernel32.SetInformationJobObject(
                wintypes.HANDLE(self._handle),
                JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                ctypes.byref(information),
                ctypes.sizeof(information),
            ):
                self.close()
                raise PatternSearchUnavailableError("the pattern search job could not be limited")

        def hold(self, process: subprocess.Popen[bytes]) -> None:
            """Put the child in the job and prove it is there before it is handed anything."""
            child = wintypes.HANDLE(int(cast(Any, process)._handle))
            contained = wintypes.BOOL(False)
            if (
                not self._kernel32.AssignProcessToJobObject(wintypes.HANDLE(self._handle), child)
                or not self._kernel32.IsProcessInJob(child, wintypes.HANDLE(self._handle), ctypes.byref(contained))
                or not contained.value
            ):
                raise PatternSearchUnavailableError("the pattern search child could not be contained")

        def end(self, process: subprocess.Popen[bytes]) -> None:
            """End the child and anything it became."""
            self.close()
            if process.poll() is None:
                process.kill()

        def close(self) -> None:
            if self._handle:
                self._kernel32.CloseHandle(wintypes.HANDLE(self._handle))
                self._handle = 0

    def _launch(neutral_root: Path) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            [*isolated_interpreter_command(), "-m", _WORKER_MODULE],
            cwd=neutral_root,
            env=_child_environment(neutral_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=child_console_creation_flags(),
        )

else:

    def _posix_limits() -> None:
        import resource

        limits = cast(Any, resource)
        # Darwin refuses a finite address-space limit; its batch stays bounded by the kill.
        if sys.platform != "darwin":
            limits.setrlimit(limits.RLIMIT_AS, (_CHILD_MEMORY_BYTES,) * 2)
        limits.setrlimit(limits.RLIMIT_CPU, (_CHILD_CPU_SECONDS,) * 2)
        limits.setrlimit(limits.RLIMIT_CORE, (0, 0))
        limits.setrlimit(limits.RLIMIT_FSIZE, (0, 0))
        limits.setrlimit(limits.RLIMIT_NOFILE, (16, 16))

    class _Containment:
        """The child's own session and resource limits; its CPU limit ends it if this process dies first."""

        def hold(self, process: subprocess.Popen[bytes]) -> None:
            """The session and limits were applied at launch."""

        def end(self, process: subprocess.Popen[bytes]) -> None:
            """End the child's whole session."""
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            if process.poll() is None:
                process.kill()

        def close(self) -> None:
            """Nothing outlives the session."""

    def _launch(neutral_root: Path) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            [*isolated_interpreter_command(), "-m", _WORKER_MODULE],
            cwd=neutral_root,
            env=_child_environment(neutral_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
            preexec_fn=_posix_limits,
        )


def _child_environment(neutral_root: Path) -> dict[str, str]:
    environment = child_environment(ChildEnvironmentProfile.STRICT, neutral_root / "state", base={})
    environment.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "HOME": str(neutral_root)})
    if sys.platform == "win32":
        environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        environment["USERPROFILE"] = str(neutral_root)
        # The child runs the base interpreter without ``site``; it finds this package through these roots.
        environment["PYTHONPATH"] = os.pathsep.join(entry for entry in sys.path if entry)
    return environment


class _ChildLines:
    """Read the child's lines on a thread, since a stalled child must not stall the reader's owner."""

    def __init__(self, stream: IO[bytes]) -> None:
        self.lines: list[dict[str, Any]] = []
        self.malformed = False
        self.ready = threading.Event()
        self.finished = threading.Event()
        self._stream = stream
        self.thread = threading.Thread(target=self._read, daemon=True, name="pattern-search-reader")
        self.thread.start()

    def _read(self) -> None:
        try:
            for line in self._stream:
                self.lines.append(json.loads(line))
                self.ready.set()
        except (OSError, ValueError):
            self.malformed = True
        finally:
            self.ready.set()
            self.finished.set()


def _write_request(stream: IO[bytes], request: bytes) -> None:
    # A child ended mid-request breaks this pipe; its supervisor already knows why.
    with contextlib.suppress(OSError, ValueError):
        stream.write(request)
        stream.close()


def _read_answer(lines: list[dict[str, Any]], texts: int, *, overran: bool) -> tuple[int | None, ...]:
    winners: list[int | None] = [None] * texts
    finished = 0
    closed = False
    for line in lines[1:]:
        if "finished" in line:
            finished += 1
            for position in line["hits"]:
                winners[position] = line["finished"]
        elif "unreadable" in line:
            raise PatternSearchUnreadableError(line["unreadable"])
        elif "exhausted" in line:
            raise PatternSearchOverrunError(line["exhausted"])
        elif "done" in line:
            closed = True
    if closed:
        return tuple(winners)
    if overran:
        raise PatternSearchOverrunError(finished)
    raise PatternSearchUnavailableError("the pattern search child ended without an answer")


def _search_in_child(
    process: subprocess.Popen[bytes],
    patterns: Sequence[str],
    texts: Sequence[str],
) -> tuple[int | None, ...]:
    if process.stdin is None or process.stdout is None:
        raise PatternSearchUnavailableError("the pattern search child has no pipes")
    answers = _ChildLines(process.stdout)
    # Starting is the host's cost, so the budget begins once the child can take the request.
    if not answers.ready.wait(_START_SECONDS) or not answers.lines:
        raise PatternSearchUnavailableError("the pattern search child did not start")
    # JSON's escapes carry every text exactly, a lone surrogate included.
    request = json.dumps({"patterns": list(patterns), "texts": list(texts)}).encode("ascii")
    writer = threading.Thread(
        target=_write_request, args=(process.stdin, request), daemon=True, name="pattern-search-writer"
    )
    writer.start()
    writer.join(_START_SECONDS)
    if writer.is_alive():
        raise PatternSearchUnavailableError("the pattern search child did not take the request")
    overran = not answers.finished.wait(pattern_search_budget_seconds(patterns=len(patterns), texts=len(texts)))
    if overran:
        return _end_overrun(process, answers, texts=len(texts))
    if answers.malformed:
        raise PatternSearchUnavailableError("the pattern search child answered out of protocol")
    return _read_answer(answers.lines, len(texts), overran=False)


def _end_overrun(process: subprocess.Popen[bytes], answers: _ChildLines, *, texts: int) -> tuple[int | None, ...]:
    # A kill only ends what is still running; the job's handle closes in the caller's cleanup.
    process.kill()
    answers.finished.wait(_SETTLE_SECONDS)
    return _read_answer(answers.lines, texts, overran=True)


def first_matching_patterns(patterns: Sequence[str], texts: Sequence[str]) -> tuple[int | None, ...]:
    """Answer, for each text, the index of the first pattern that finds it, or ``None``.

    Raises:
        PatternSearchOverrunError: The batch outran its budget; the running pattern is named.
        PatternSearchUnreadableError: The child's ``re`` could not read a pattern.
        PatternSearchUnavailableError: The bounded child could not run; nothing was searched.
    """
    if not patterns or not texts:
        return (None,) * len(texts)
    temporary_root = storage_path(StorageCategory.TEMPORARY_FILES, settings=load_settings())
    temporary_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(
        prefix="cadrumo-pattern-search-", dir=temporary_root, ignore_cleanup_errors=True
    ) as neutral:
        containment = _Containment()
        process: subprocess.Popen[bytes] | None = None
        try:
            try:
                process = _launch(Path(neutral))
                containment.hold(process)
            except (OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
                raise PatternSearchUnavailableError("the pattern search child could not be started") from error
            return _search_in_child(process, patterns, texts)
        finally:
            if process is None:
                containment.close()
            else:
                _settle(process, containment)


def _settle(process: subprocess.Popen[bytes], containment: _Containment) -> None:
    containment.end(process)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(_SETTLE_SECONDS)
    for stream in (process.stdin, process.stdout):
        if stream is not None:
            with contextlib.suppress(OSError, ValueError):
                stream.close()


__all__ = [
    "PATTERN_SEARCH_BASE_SECONDS",
    "PATTERN_SEARCH_MAX_SECONDS",
    "PATTERN_SEARCH_SECONDS_PER_SEARCH",
    "PatternSearchOverrunError",
    "PatternSearchUnavailableError",
    "PatternSearchUnreadableError",
    "first_matching_patterns",
    "pattern_search_budget_seconds",
]
