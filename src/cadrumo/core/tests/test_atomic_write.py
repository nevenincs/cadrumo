"""Unit tests for the two-tier atomic-write helper in
:mod:`cadrumo.core.atomic_write`.

Every failure test induces a REAL error (a directory occupying the target
path so :func:`os.replace` genuinely refuses it, or a wrongly-typed payload
so the underlying ``write``/``os.write`` call genuinely raises) rather than
patching or mocking any part of the write sequence, per the project's
real-behaviour testing discipline.
"""

from __future__ import annotations

import functools
import multiprocessing
import os
import stat
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

from ..atomic_write import (
    _write_all,
    atomic_write_bytes,
    atomic_write_hardened_bytes,
    atomic_write_hardened_text,
    atomic_write_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PIPE_PAYLOAD = bytes(range(256)) * 4096
#: Hang guard for the reader thread's join, used INSIDE an already-booted child.
#: It deliberately stays a plain constant: the child must not call
#: :func:`_child_timeout_seconds`, which would spawn a grandchild process to
#: measure a baseline. Nothing here pays an interpreter boot -- the reader thread
#: is already running and only has to drain the pipe -- so a fixed, generous
#: ceiling is the honest shape for a guard against a wedged reader.
_READER_JOIN_TIMEOUT_SECONDS = 60.0

#: Multiple of the measured no-op ``spawn`` cost allowed for a real writer child.
#: The pipe children do the same interpreter boot and package re-import the
#: baseline measures, then a sub-second write of :data:`_PIPE_PAYLOAD` through a
#: real pipe; 8x that boot cost is far more than the write can need.
_SPAWN_BUDGET_FACTOR = 8.0
#: Absolute floor added to the derived budget, covering the children's own pipe
#: work and absorbing a load spike that lands after the baseline was measured.
_CHILD_WORK_MARGIN_SECONDS = 10.0


def _noop_child() -> None:
    """Do nothing: the baseline child measures interpreter boot and import only."""


@functools.cache
def _child_timeout_seconds() -> float:
    """Return this host's deadlock bound for a writer child, derived from measurement.

    A deadlock guard, not a performance budget: the assertions these children
    prove are their exit codes, never their wall-clock cost, so the bound only
    has to be short enough that a genuinely wedged writer fails in bounded time
    instead of hanging the run.

    The former fixed 5.0s bound was arbitrary and had no honest headroom: a
    Windows ``spawn`` child pays a full interpreter boot plus package re-import
    before it writes a byte, measured at 2.3-2.8s under merely moderate parallel
    load -- already over half the budget -- so a busy host failed on cost rather
    than on defect. Deriving the bound from a real no-op ``spawn`` on THIS host
    makes it self-scaling: when load inflates the writer children's boot, it
    inflates the baseline by the same factor, so a timeout can only mean a
    genuine wedge. ``timeout = 300`` in ``pyproject.toml`` remains the outer
    per-test ceiling.
    """
    started = time.perf_counter()
    process = multiprocessing.get_context("spawn").Process(target=_noop_child)
    process.start()
    process.join()
    process.close()
    baseline = time.perf_counter() - started
    return baseline * _SPAWN_BUDGET_FACTOR + _CHILD_WORK_MARGIN_SECONDS


_EXIT_NO_CONTINUATION = 21
_EXIT_INCOMPLETE = 22
_EXIT_READER_FAILURE = 23


def _tmp_leftovers(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.tmp"))


def _close_fd(fd: int) -> None:
    with suppress(OSError):
        os.close(fd)


def _fill_nonblocking_pipe(write_fd: int) -> None:
    block = b"x" * 65_536
    while True:
        try:
            written = os.write(write_fd, block)
        except BlockingIOError:
            return
        if written <= 0:
            raise OSError("real pipe fill made no progress")


def _no_reader_backpressure_child() -> None:
    read_fd, write_fd = os.pipe()
    try:
        os.set_blocking(write_fd, False)
        _fill_nonblocking_pipe(write_fd)
        try:
            _write_all(write_fd, b"blocked")
        except BlockingIOError:
            return
        raise AssertionError("full nonblocking pipe did not propagate backpressure")
    finally:
        _close_fd(write_fd)
        _close_fd(read_fd)


def _blocking_pipe_completion_child() -> None:
    read_fd, write_fd = os.pipe()
    received = bytearray()
    reader_errors: list[BaseException] = []

    def _drain_pipe() -> None:
        try:
            while chunk := os.read(read_fd, 65_536):
                received.extend(chunk)
        except BaseException as exc:
            reader_errors.append(exc)

    reader = threading.Thread(target=_drain_pipe, daemon=True)
    reader_started = False
    outcome = 0
    try:
        reader.start()
        reader_started = True
        try:
            _write_all(write_fd, _PIPE_PAYLOAD)
        finally:
            _close_fd(write_fd)
            write_fd = -1

        reader.join(timeout=_READER_JOIN_TIMEOUT_SECONDS)
        if reader.is_alive() or reader_errors:
            outcome = _EXIT_READER_FAILURE
        elif outcome == 0 and received != _PIPE_PAYLOAD:
            outcome = _EXIT_INCOMPLETE
    finally:
        _close_fd(write_fd)
        _close_fd(read_fd)
        if reader_started:
            reader.join(timeout=0.25)
    raise SystemExit(outcome)


def _positive_short_write_continuation_child() -> None:
    read_fd, write_fd = os.pipe()
    received = bytearray()
    outcome = 0
    try:
        # With no reader, the first internal os.write accepts a real positive
        # capacity-bounded prefix. _write_all must then make another call,
        # which encounters real nonblocking backpressure.
        os.set_blocking(write_fd, False)
        try:
            _write_all(write_fd, _PIPE_PAYLOAD)
        except BlockingIOError:
            pass
        else:
            raise SystemExit(_EXIT_NO_CONTINUATION)
        finally:
            _close_fd(write_fd)
            write_fd = -1

        while chunk := os.read(read_fd, 65_536):
            received.extend(chunk)
        if not 0 < len(received) < len(_PIPE_PAYLOAD) or received != _PIPE_PAYLOAD[: len(received)]:
            outcome = _EXIT_INCOMPLETE
    finally:
        _close_fd(write_fd)
        _close_fd(read_fd)
    raise SystemExit(outcome)


def _signal_interrupted_short_write_completion_child() -> None:
    import signal

    # These POSIX-only members are intentionally resolved at runtime because
    # the Windows stdlib typing surface omits them. Runtime dispatch calls this
    # helper only on POSIX; the shared production writer has no platform branch.
    posix_members = vars(signal)
    sigalrm = posix_members["SIGALRM"]
    itimer_real = posix_members["ITIMER_REAL"]
    siginterrupt = posix_members["siginterrupt"]
    setitimer = posix_members["setitimer"]

    read_fd, write_fd = os.pipe()
    received = bytearray()
    reader_errors: list[BaseException] = []
    reader_started = False

    def _drain_pipe() -> None:
        try:
            while chunk := os.read(read_fd, 65_536):
                received.extend(chunk)
        except BaseException as exc:
            reader_errors.append(exc)

    reader = threading.Thread(target=_drain_pipe, daemon=True)

    def _release_blocked_write(_signum: int, _frame: object) -> None:
        nonlocal reader_started
        if not reader_started:
            reader.start()
            reader_started = True

    prior_handler = signal.signal(sigalrm, _release_blocked_write)
    siginterrupt(sigalrm, True)
    outcome = 0
    try:
        # The first blocking os.write fills the real pipe and then blocks.
        # SIGALRM starts the reader and interrupts that call after a positive
        # prefix, forcing _write_all to resume from its recorded offset.
        setitimer(itimer_real, 0.01)
        _write_all(write_fd, _PIPE_PAYLOAD)
    finally:
        setitimer(itimer_real, 0.0)
        signal.signal(sigalrm, prior_handler)
        _close_fd(write_fd)
        write_fd = -1
        if not reader_started:
            reader.start()
            reader_started = True
        reader.join(timeout=_READER_JOIN_TIMEOUT_SECONDS)

        if reader.is_alive() or reader_errors:
            outcome = _EXIT_READER_FAILURE
        elif received != _PIPE_PAYLOAD:
            outcome = _EXIT_INCOMPLETE
        _close_fd(write_fd)
        _close_fd(read_fd)
    raise SystemExit(outcome)


def _bounded_child_exitcode(target: Callable[[], None]) -> int:
    # Measured on this host (once per session), so the guard scales with the
    # machine's real spawn cost instead of a magic constant.
    budget = _child_timeout_seconds()
    process = multiprocessing.get_context("spawn").Process(target=target)
    process.start()
    try:
        process.join(timeout=budget)
        if process.is_alive():
            process.terminate()
            process.join(timeout=budget)
            if process.is_alive():
                process.kill()
                process.join(timeout=budget)
            target_name = getattr(target, "__name__", type(target).__name__)
            pytest.fail(f"child writer {target_name} exceeded the bounded timeout")
        assert process.exitcode is not None
        return process.exitcode
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=budget)
            if process.is_alive():
                process.kill()
                process.join(timeout=budget)
        process.close()


class TestStandardTier:
    """Behaviour of :func:`atomic_write_bytes` / :func:`atomic_write_text`."""

    def test_bytes_roundtrip(self, tmp_path: Path) -> None:
        target = tmp_path / "payload.bin"
        atomic_write_bytes(target, b"\x00\x01hello\xff")
        assert target.read_bytes() == b"\x00\x01hello\xff"

    def test_text_roundtrip(self, tmp_path: Path) -> None:
        target = tmp_path / "payload.txt"
        atomic_write_text(target, "hola\nmundo\n", encoding="utf-8")
        assert target.read_text(encoding="utf-8") == "hola\nmundo\n"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c" / "payload.bin"
        atomic_write_bytes(target, b"nested")
        assert target.read_bytes() == b"nested"

    def test_leaves_no_tmp_file_after_success(self, tmp_path: Path) -> None:
        target = tmp_path / "payload.bin"
        atomic_write_bytes(target, b"clean")
        assert _tmp_leftovers(tmp_path) == []

    def test_overwrites_existing_target(self, tmp_path: Path) -> None:
        target = tmp_path / "payload.bin"
        atomic_write_bytes(target, b"first")
        atomic_write_bytes(target, b"second")
        assert target.read_bytes() == b"second"

    def test_replace_failure_cleans_tmp_and_never_clobbers_target(self, tmp_path: Path) -> None:
        """A real ``os.replace`` failure (target occupied by a directory)."""
        target = tmp_path / "payload.bin"
        target.mkdir()
        (target / "marker.txt").write_text("still a directory", encoding="utf-8")

        with pytest.raises(OSError):
            atomic_write_bytes(target, b"would-be payload")

        assert target.is_dir()
        assert (target / "marker.txt").read_text(encoding="utf-8") == "still a directory"
        assert _tmp_leftovers(tmp_path) == []

    def test_write_failure_cleans_tmp_and_preserves_existing_target(self, tmp_path: Path) -> None:
        """A real ``handle.write`` failure (wrongly-typed payload mid-write)."""
        target = tmp_path / "payload.bin"
        atomic_write_bytes(target, b"OLD-CONTENT")

        invalid_payload: Any = "not-bytes"
        with pytest.raises(TypeError):
            atomic_write_bytes(target, invalid_payload)

        assert target.read_bytes() == b"OLD-CONTENT"
        assert _tmp_leftovers(tmp_path) == []


class TestHardenedTier:
    """Behaviour of :func:`atomic_write_hardened_bytes` / :func:`atomic_write_hardened_text`."""

    def test_bytes_roundtrip(self, tmp_path: Path) -> None:
        target = tmp_path / "secret.bin"
        atomic_write_hardened_bytes(target, b"\x00\x01secret\xff")
        assert target.read_bytes() == b"\x00\x01secret\xff"

    def test_write_all_completes_capacity_limited_real_pipe(self) -> None:
        """A blocking capacity-limited OS pipe receives the complete payload."""
        assert _bounded_child_exitcode(_blocking_pipe_completion_child) == 0

    def test_write_all_continues_after_real_positive_short_write(self) -> None:
        """The production loop continues after a real positive short write.

        POSIX signals provide a deterministic byte-exact offset proof. Windows
        lacks that signal interruption contract, so its real nonblocking pipe
        pins the platform's positive-prefix then backpressure behavior; the
        separate blocking-pipe test pins complete delivery on both platforms.
        The production loop itself has no platform-specific branch.
        """
        child = (
            _positive_short_write_continuation_child
            if os.name == "nt"
            else _signal_interrupted_short_write_completion_child
        )
        assert _bounded_child_exitcode(child) == 0

    def test_write_all_propagates_permanent_nonblocking_backpressure(self) -> None:
        assert _bounded_child_exitcode(_no_reader_backpressure_child) == 0

    def test_bytes_roundtrip_preserves_newline_bytes(self, tmp_path: Path) -> None:
        """A 0x0A byte must survive verbatim (no Windows text-mode CRLF translation).

        Binary payloads written through the hardened tier (ciphertext, master
        keys, fichero-BOE / PDF bytes) routinely contain 0x0A bytes. If the
        underlying fd is opened in text mode on Windows, os.write translates
        every 0x0A to 0x0D0A and lengthens the file, silently corrupting the
        payload and breaking every content-hash / decrypt check downstream.
        This pins the byte-exact contract on every platform.
        """
        payload = b"line-one\nline-two\r\nbinary\x00\x0a\xff-tail\n"
        target = tmp_path / "newline.bin"
        atomic_write_hardened_bytes(target, payload)
        written = target.read_bytes()
        assert written == payload
        assert len(written) == len(payload)

    def test_text_roundtrip(self, tmp_path: Path) -> None:
        target = tmp_path / "secret.txt"
        atomic_write_hardened_text(target, "passphrase-material", encoding="utf-8")
        assert target.read_text(encoding="utf-8") == "passphrase-material"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "secret.bin"
        atomic_write_hardened_bytes(target, b"nested-secret")
        assert target.read_bytes() == b"nested-secret"

    def test_leaves_no_tmp_file_after_success(self, tmp_path: Path) -> None:
        target = tmp_path / "secret.bin"
        atomic_write_hardened_bytes(target, b"clean")
        assert _tmp_leftovers(tmp_path) == []

    def test_default_mode_is_0o600_on_posix(self, tmp_path: Path) -> None:
        target = tmp_path / "secret.bin"
        atomic_write_hardened_bytes(target, b"mode-check")
        if os.name != "nt":
            actual_mode = stat.S_IMODE(target.stat().st_mode)
            assert actual_mode == 0o600

    def test_explicit_mode_is_applied_on_posix(self, tmp_path: Path) -> None:
        target = tmp_path / "secret.bin"
        atomic_write_hardened_bytes(target, b"mode-check", mode=0o640)
        if os.name != "nt":
            actual_mode = stat.S_IMODE(target.stat().st_mode)
            assert actual_mode == 0o640

    def test_overwrites_existing_target(self, tmp_path: Path) -> None:
        target = tmp_path / "secret.bin"
        atomic_write_hardened_bytes(target, b"first")
        atomic_write_hardened_bytes(target, b"second")
        assert target.read_bytes() == b"second"

    def test_replace_failure_cleans_tmp_and_never_clobbers_target(self, tmp_path: Path) -> None:
        """A real ``os.replace`` failure (target occupied by a directory)."""
        target = tmp_path / "secret.bin"
        target.mkdir()
        (target / "marker.txt").write_text("still a directory", encoding="utf-8")

        with pytest.raises(OSError):
            atomic_write_hardened_bytes(target, b"would-be secret")

        assert target.is_dir()
        assert (target / "marker.txt").read_text(encoding="utf-8") == "still a directory"
        assert _tmp_leftovers(tmp_path) == []

    def test_write_failure_cleans_tmp_and_preserves_existing_target(self, tmp_path: Path) -> None:
        """A real ``os.write`` failure (wrongly-typed payload mid-write)."""
        target = tmp_path / "secret.bin"
        atomic_write_hardened_bytes(target, b"OLD-SECRET")

        invalid_payload: Any = "not-bytes"
        with pytest.raises(TypeError):
            atomic_write_hardened_bytes(target, invalid_payload)

        assert target.read_bytes() == b"OLD-SECRET"
        assert _tmp_leftovers(tmp_path) == []
