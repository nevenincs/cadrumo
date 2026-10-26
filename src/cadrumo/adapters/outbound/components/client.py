"""Run one command of the native ``components`` role and decode what it says.

The client starts the built Cadrumo binary as ``--role components`` with no
console window, contained so that nothing it starts outlives the command: on
Windows in a kill-on-close job the child joins at creation, elsewhere in a
process group of its own. It gives the role this command line's storage root
and location and proxy settings, and nothing else of its own.

It reads the role's lines strictly (:mod:`.protocol`) and relays each event to
the caller. A review is answered by the caller's reviewer with an approval of
exactly the reviewed digest or a decline; with no reviewer it is declined. A
cancellation sends the role its cancel line, and leaving the call for any other
reason closes the role's input, which cancels a running setup. A setup of an
item another process is already setting up follows that setup: the caller sees
a ``following`` notice and the other setup's events, no review, and that
setup's result. Cancelling or leaving it stops only the following, with the
result ``busy``; a ``cancel`` command is the act that stops the followed setup.
The client decides nothing about a component: the result is the role's. It
never asks the role to plan, set up or remove the local AI, which only the
desktop sets up: such a request is refused before the role starts, and the
local AI is read and checked like any other item.

Where this build has no Cadrumo binary, or its role speaks another protocol or
plan contract version, :func:`not_in_this_build_result` is the answer: every
item is blocked as not in this build, as the role itself reports an item a
build cannot set up.
"""

from __future__ import annotations

import contextlib
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Final, Protocol

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ....application.dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemKind,
    DependencyState,
)
from ....core.storage_environment import ChildEnvironmentProfile, child_environment, configured_storage_root
from .protocol import (
    CANCEL_LINE,
    MAX_LINE_BYTES,
    ComponentsAnswer,
    ComponentsCommand,
    ComponentsContractMismatchError,
    ComponentsDecline,
    ComponentsEvent,
    ComponentsLine,
    ComponentsOutcome,
    ComponentsResultLine,
    ComponentsReviewLine,
    ComponentsRow,
    ComponentsStartedLine,
    answer_line,
    decode_components_line,
)
from .role_image import components_role_image

__all__ = [
    "ComponentsCancellation",
    "ComponentsEventSink",
    "ComponentsLaunch",
    "ComponentsLauncher",
    "ComponentsRequest",
    "ComponentsReviewer",
    "launch_components_role",
    "not_in_this_build_result",
    "run_components_role",
]

ROLE_ARGUMENTS: Final = ("--role", "components")
"""The leading arguments that start the Cadrumo binary as the components role."""

INVALID_REQUEST_STATUS: Final = 64
"""The exit status of a command line the role cannot read."""

_EXIT_GRACE_S: Final = 30.0
"""How long a role that wrote its result, or lost its input, is given to exit before it is ended."""

_POLL_S: Final = 0.2

_BROWSER_ONLY_COMMANDS: Final = frozenset({ComponentsCommand.PLAN, ComponentsCommand.SETUP, ComponentsCommand.REMOVE})
"""The commands that change what is installed or plan to; the local AI is outside them."""

type ComponentsEventSink = Callable[[ComponentsEvent], None]
"""Receives each event the role writes while it works."""

type ComponentsReviewer = Callable[[ComponentsReviewLine], ComponentsAnswer]
"""Answers a setup's review: approve exactly the reviewed digest, or decline."""


@dataclass(frozen=True, slots=True)
class ComponentsRequest:
    """One command of the role: the items it is for, a full status, and a setup's approved digest.

    A plan, setup or removal never names the local AI: only the desktop sets it up.
    """

    command: ComponentsCommand
    items: tuple[DependencyItemKind, ...] = ()
    full: bool = False
    approve: str | None = None

    def __post_init__(self) -> None:
        """Refuse a combination the role's command line does not have."""
        if self.full and self.command is not ComponentsCommand.STATUS:
            raise ValueError("only a status is asked for in full")
        if self.approve is not None and self.command is not ComponentsCommand.SETUP:
            raise ValueError("only a setup carries an approved digest")
        if self.command is ComponentsCommand.CANCEL and self.items:
            raise ValueError("a cancel names no item")
        if self.command is ComponentsCommand.REMOVE and not self.items:
            raise ValueError("a removal names its items")
        if len(set(self.items)) != len(self.items):
            raise ValueError("each item is named once")
        if self.command in _BROWSER_ONLY_COMMANDS and DependencyItemKind.LOCAL_AI in self.items:
            raise ValueError("only the desktop plans, sets up or removes the local AI")

    def arguments(self) -> tuple[str, ...]:
        """Return the role's command line after its role arguments."""
        arguments: list[str] = [self.command.value]
        for item in self.items:
            arguments.extend(("--item", item.value))
        if self.full:
            arguments.append("--full")
        if self.approve is not None:
            arguments.extend(("--approve", self.approve))
        return tuple(arguments)


class ComponentsCancellation:
    """Asks a running command to stop; safe to call from any thread, before or during the call."""

    def __init__(self) -> None:
        """Start with no stop asked for and no running role to tell."""
        self._lock = threading.Lock()
        self._requested = False
        self._send: Callable[[], None] | None = None

    @property
    def requested(self) -> bool:
        """Whether a stop was asked for."""
        with self._lock:
            return self._requested

    def cancel(self) -> None:
        """Ask the role to stop at its next transfer chunk, or a following setup to stop following."""
        with self._lock:
            self._requested = True
            send = self._send
        if send is not None:
            send()

    def attach_sender(self, send: Callable[[], None]) -> None:
        """Bind the call that delivers a stop to the running role; a stop already asked for is sent at once."""
        with self._lock:
            self._send = send
            requested = self._requested
        if requested:
            send()


class ComponentsLaunch(Protocol):
    """A started role: its input, its output, and how to wait for and end it."""

    @property
    def standard_input(self) -> IO[bytes]:
        """Where the client writes its answers."""
        ...

    @property
    def standard_output(self) -> IO[bytes]:
        """Where the role writes its lines."""
        ...

    def wait(self, timeout: float) -> int | None:
        """Return the exit status, or ``None`` when the role is still running after ``timeout``."""
        ...

    def end(self) -> None:
        """End the role and everything it started, and release the launch."""
        ...


type ComponentsLauncher = Callable[[Path, Sequence[str], Mapping[str, str], Path], ComponentsLaunch]
"""Starts ``image`` with arguments, environment and working directory."""


class _WindowsLaunch:
    """The role in a kill-on-close job of its own, joined at creation, with private pipes and no console."""

    def __init__(self, image: Path, arguments: Sequence[str], environment: Mapping[str, str], directory: Path) -> None:
        """Start ``image`` in a new job; standard error is drained and discarded."""
        from cadrumo_client.transport.windows_process import WindowsProcessScope

        scope = WindowsProcessScope()
        try:
            process, standard_input, standard_output, standard_error = scope.launch_with_standard_pipes(
                executable=image, arguments=arguments, directory=directory, environment=environment
            )
        except BaseException:
            scope.terminate()
            raise
        self._scope = scope
        self._process = process
        self.standard_input: IO[bytes] = standard_input
        self.standard_output: IO[bytes] = standard_output
        self._errors = standard_error
        threading.Thread(target=_drain, args=(standard_error,), name="components-role-errors", daemon=True).start()

    def wait(self, timeout: float) -> int | None:
        try:
            return self._process.wait(timeout=timeout)
        except RefusalError as error:
            if error.reason is RefusalCode.DEADLINE_EXCEEDED:
                return None
            raise

    def end(self) -> None:
        try:
            self._scope.terminate()
        finally:
            self._process.close()
            for stream in (self.standard_input, self.standard_output):
                with contextlib.suppress(OSError):
                    stream.close()


class _PosixLaunch:
    """The role in a session and process group of its own, ended as a group, with no terminal."""

    def __init__(self, image: Path, arguments: Sequence[str], environment: Mapping[str, str], directory: Path) -> None:
        """Start ``image`` with ``arguments`` in a new session; its output and input are piped, errors discarded."""
        command = [str(image), *arguments]
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=dict(environment),
            cwd=directory,
            close_fds=True,
            start_new_session=True,
        )
        standard_input, standard_output = self._process.stdin, self._process.stdout
        if standard_input is None or standard_output is None:
            raise RefusalError(RefusalCode.UNAVAILABLE)
        self.standard_input: IO[bytes] = standard_input
        self.standard_output: IO[bytes] = standard_output

    def wait(self, timeout: float) -> int | None:
        try:
            return self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def end(self) -> None:
        if sys.platform != "win32" and self._process.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self._process.pid, 9)
            self._process.wait()
        for stream in (self.standard_input, self.standard_output):
            with contextlib.suppress(OSError):
                stream.close()


def _drain(stream: IO[bytes]) -> None:
    with contextlib.suppress(OSError, ValueError):
        while stream.read(65536):
            pass
    with contextlib.suppress(OSError):
        stream.close()


def launch_components_role(
    image: Path, arguments: Sequence[str], environment: Mapping[str, str], directory: Path
) -> ComponentsLaunch:
    """Start ``image`` contained and without a console window: the launcher every call uses by default."""
    if sys.platform == "win32":
        return _WindowsLaunch(image, arguments, environment, directory)
    return _PosixLaunch(image, arguments, environment, directory)


def _blocked_rows(items: Sequence[DependencyItemKind], mode: DependencyCheckMode) -> tuple[ComponentsRow, ...]:
    return tuple(
        ComponentsRow(
            item_id=item.value,
            mode=mode,
            state=DependencyState.BLOCKED,
            blocked_reason=DependencyBlockedReason.NOT_IN_THIS_BUILD,
        )
        for item in items
    )


def not_in_this_build_result(request: ComponentsRequest) -> ComponentsResultLine:
    """Return the role's answer for a build without it: every item blocked as not in this build.

    A status or check reports the rows of the items it names, every item by
    default; a setup or plan of every item has nothing it can do, and one that
    names an item, or a removal, is refused for the first item it names, which
    can only be the browser.
    """
    command = request.command
    every = tuple(DependencyItemKind)
    checked = command in {ComponentsCommand.STATUS, ComponentsCommand.VERIFY}
    full = request.full or command is ComponentsCommand.VERIFY
    refused: DependencyItemKind | None = None
    if checked:
        outcome = ComponentsOutcome.OK
    elif command is ComponentsCommand.CANCEL:
        outcome = ComponentsOutcome.NOTHING_RUNNING
    elif request.items:
        outcome, refused = ComponentsOutcome.REFUSED, request.items[0]
    else:
        outcome = ComponentsOutcome.NOTHING_TO_DO
    mode = DependencyCheckMode.FULL if full else DependencyCheckMode.QUICK
    return ComponentsResultLine(
        type="result",
        command=command,
        outcome=outcome,
        mode=mode,
        rows=_blocked_rows((request.items or every) if checked else every, mode),
        setup_complete=False,
        item_id=None if refused is None else refused.value,
        failure_category=None if refused is None else DependencyFailureCategory.NOT_IN_THIS_BUILD,
        items=() if command in {ComponentsCommand.CANCEL, ComponentsCommand.REMOVE} else None,
    )


def _environment() -> tuple[dict[str, str], Path]:
    root = configured_storage_root()
    return child_environment(ChildEnvironmentProfile.OPERATOR, root), root


@dataclass(slots=True)
class _Reader:
    """Reads the role's lines on a thread of its own, so waiting stays interruptible."""

    stream: IO[bytes]
    lines: queue.Queue[bytes | BaseException | None] = field(default_factory=queue.Queue)

    def start(self) -> None:
        threading.Thread(target=self._read, name="components-role-output", daemon=True).start()

    def _read(self) -> None:
        try:
            while True:
                line = self.stream.readline(MAX_LINE_BYTES + 1)
                if not line:
                    self.lines.put(None)
                    return
                self.lines.put(line)
                if len(line) > MAX_LINE_BYTES or not line.endswith(b"\n"):
                    self.lines.put(None)
                    return
        except BaseException as error:  # the stream's failure is the caller's to judge
            self.lines.put(error)

    def next(self, deadline: float | None) -> bytes | None:
        """Return the next line, or ``None`` at the end of output."""
        while True:
            wait = _POLL_S if deadline is None else min(_POLL_S, deadline - time.monotonic())
            if wait <= 0:
                raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)
            try:
                item = self.lines.get(timeout=wait)
            except queue.Empty:
                continue
            if isinstance(item, BaseException):
                raise RefusalError(RefusalCode.UNAVAILABLE) from item
            return item


class _Input:
    """The role's standard input, written by the call and by a cancellation from another thread."""

    def __init__(self, stream: IO[bytes]) -> None:
        self._stream = stream
        self._lock = threading.Lock()

    def send(self, line: bytes) -> None:
        with self._lock:
            if self._stream.closed:
                return
            try:
                self._stream.write(line)
                self._stream.flush()
            except (OSError, ValueError):
                # The role is gone; its result, or the end of its output, says how it ended.
                pass

    def close(self) -> None:
        with self._lock, contextlib.suppress(OSError):
            self._stream.close()


def _exit_matches(outcome: ComponentsOutcome, status: int) -> bool:
    if outcome is ComponentsOutcome.INVALID_REQUEST:
        return status == INVALID_REQUEST_STATUS
    return status == (0 if outcome.succeeded else 1)


def _settle(launch: ComponentsLaunch, result: ComponentsResultLine, reader: _Reader) -> ComponentsResultLine:
    status = launch.wait(_EXIT_GRACE_S)
    if status is None or not _exit_matches(result.outcome, status):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    if reader.next(time.monotonic() + _EXIT_GRACE_S) is not None:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    return result


def _converse(
    request: ComponentsRequest,
    launch: ComponentsLaunch,
    *,
    on_event: ComponentsEventSink | None,
    review: ComponentsReviewer | None,
    cancellation: ComponentsCancellation | None,
    deadline: float | None,
) -> ComponentsResultLine:
    reader = _Reader(launch.standard_output)
    reader.start()
    answers = _Input(launch.standard_input)
    if cancellation is not None:
        cancellation.attach_sender(lambda: answers.send(CANCEL_LINE))
    started = False
    reviewed = False
    while True:
        raw = reader.next(deadline)
        if raw is None:
            # The output ended without a result: the role failed or was ended.
            raise RefusalError(RefusalCode.UNAVAILABLE)
        line: ComponentsLine = decode_components_line(raw)
        if isinstance(line, ComponentsResultLine):
            answers.close()
            if line.command is not (request.command if started else None):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            return _settle(launch, line, reader)
        if isinstance(line, ComponentsStartedLine):
            if started or line.command is not request.command:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            started = True
            continue
        if not started:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        if isinstance(line, ComponentsReviewLine):
            if reviewed or request.command is not ComponentsCommand.SETUP or request.approve is not None:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            reviewed = True
            answer = ComponentsDecline() if review is None else review(line)
            answers.send(answer_line(answer))
            continue
        if on_event is not None:
            on_event(line)


def run_components_role(
    request: ComponentsRequest,
    *,
    on_event: ComponentsEventSink | None = None,
    review: ComponentsReviewer | None = None,
    cancellation: ComponentsCancellation | None = None,
    timeout: float | None = None,
    image: Path | None = None,
    launcher: ComponentsLauncher | None = None,
) -> ComponentsResultLine:
    """Run ``request`` through the components role and return its result.

    ``image`` is the Cadrumo binary to run, the one this build has by default;
    without one the answer is :func:`not_in_this_build_result`. ``timeout``
    bounds the whole call, for a read that must answer promptly; a setup runs
    unbounded and stops on ``cancellation`` or when the call is left.

    Raises:
        RefusalError: ``UNAVAILABLE`` when the role cannot start or ends without
            a result, ``INVALID_FRAME`` when it breaks the protocol, and
            ``DEADLINE_EXCEEDED`` when ``timeout`` passes first. The role is
            ended in every case.
    """
    located = image if image is not None else components_role_image()
    if located is None:
        return not_in_this_build_result(request)
    environment, root = _environment()
    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        start = launch_components_role if launcher is None else launcher
        launch = start(located, (*ROLE_ARGUMENTS, *request.arguments()), environment, root)
    except RefusalError:
        raise
    except OSError as error:
        raise RefusalError(RefusalCode.UNAVAILABLE) from error
    try:
        return _converse(
            request, launch, on_event=on_event, review=review, cancellation=cancellation, deadline=deadline
        )
    except ComponentsContractMismatchError:
        # A role of another build: its plans cannot be read here, so none is approved.
        return not_in_this_build_result(request)
    finally:
        try:
            with contextlib.suppress(OSError, ValueError):
                launch.standard_input.close()
            # Closing the input cancels a running setup, which then writes its result and exits.
            launch.wait(_EXIT_GRACE_S)
        finally:
            launch.end()
