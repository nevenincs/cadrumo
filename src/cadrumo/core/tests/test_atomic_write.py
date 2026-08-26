"""Unit tests for the three-tier atomic-write helper in
:mod:`cadrumo.core.atomic_write`.

Every failure test induces a REAL error (a directory occupying the target
path so :func:`os.replace` genuinely refuses it, or a wrongly-typed payload
so the underlying ``write``/``os.write`` call genuinely raises) rather than
patching or mocking any part of the write sequence, per the project's
real-behaviour testing discipline.

The directory-occupies-the-target obstructions below are written inline
DELIBERATELY, and are not an oversight left behind by the sweep that routed
every other such obstruction in this codebase through the shared owner in
``cadrumo.tests.path_obstruction``. That helper's own tests assert that the
functions under test here refuse an obstructed path, so using it here would
make the atomic writer's unit tests depend on a helper that depends on the
atomic writer: a bug in the helper could then mask a bug in the thing under
test. A primitive's own tests do not import a helper built on that primitive.
"""

from __future__ import annotations

import ast
import functools
import multiprocessing
import os
import stat
import tempfile
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

from ...tests.attribute_scope import scoped_attribute
from .. import atomic_write
from ..atomic_write import (
    _write_all,
    atomic_write_best_effort_bytes,
    atomic_write_best_effort_text,
    atomic_write_bytes,
    atomic_write_hardened_bytes,
    atomic_write_hardened_text,
    atomic_write_publish_once_bytes,
    atomic_write_stream,
    atomic_write_text,
    durable_write_batch,
    hardened_staged_publication,
)
from ..directory_scan import DirectoryEntryKind, scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PERMISSION_PROBE_WRITES = 20

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
    return list(scan_directory(directory, pattern="*.tmp"))


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

    def test_stream_failure_cleans_tmp_and_preserves_existing_target(self, tmp_path: Path) -> None:
        """A real malformed stream chunk cannot replace a known-good target."""
        target = tmp_path / "manual.pdf"
        atomic_write_bytes(target, b"KNOWN-GOOD-PDF")

        invalid_chunks: Any = (b"partial replacement", "not-bytes")
        with pytest.raises(TypeError):
            atomic_write_stream(target, invalid_chunks)

        assert target.read_bytes() == b"KNOWN-GOOD-PDF"
        assert _tmp_leftovers(tmp_path) == []


class TestBestEffortTier:
    """Behaviour of :func:`atomic_write_best_effort_bytes` / :func:`atomic_write_best_effort_text`."""

    def test_bytes_roundtrip(self, tmp_path: Path) -> None:
        target = tmp_path / "payload.bin"
        atomic_write_best_effort_bytes(target, b"\x00\x01hello\xff")
        assert target.read_bytes() == b"\x00\x01hello\xff"

    def test_text_roundtrip(self, tmp_path: Path) -> None:
        target = tmp_path / "payload.txt"
        atomic_write_best_effort_text(target, "hola\nmundo\n", encoding="utf-8")
        assert target.read_text(encoding="utf-8") == "hola\nmundo\n"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c" / "payload.bin"
        atomic_write_best_effort_bytes(target, b"nested")
        assert target.read_bytes() == b"nested"

    def test_leaves_no_tmp_file_after_success(self, tmp_path: Path) -> None:
        target = tmp_path / "payload.bin"
        atomic_write_best_effort_bytes(target, b"clean")
        assert _tmp_leftovers(tmp_path) == []

    def test_overwrites_existing_target(self, tmp_path: Path) -> None:
        target = tmp_path / "payload.bin"
        atomic_write_best_effort_bytes(target, b"first")
        atomic_write_best_effort_bytes(target, b"second")
        assert target.read_bytes() == b"second"

    def test_replace_failure_cleans_tmp_and_never_clobbers_target(self, tmp_path: Path) -> None:
        """A real ``os.replace`` failure (target occupied by a directory)."""
        target = tmp_path / "payload.bin"
        target.mkdir()
        (target / "marker.txt").write_text("still a directory", encoding="utf-8")

        with pytest.raises(OSError):
            atomic_write_best_effort_bytes(target, b"would-be payload")

        assert target.is_dir()
        assert (target / "marker.txt").read_text(encoding="utf-8") == "still a directory"
        assert _tmp_leftovers(tmp_path) == []

    def test_write_failure_cleans_tmp_and_preserves_existing_target(self, tmp_path: Path) -> None:
        """A real ``handle.write`` failure (wrongly-typed payload mid-write)."""
        target = tmp_path / "payload.bin"
        atomic_write_best_effort_bytes(target, b"OLD-CONTENT")

        invalid_payload: Any = "not-bytes"
        with pytest.raises(TypeError):
            atomic_write_best_effort_bytes(target, invalid_payload)

        assert target.read_bytes() == b"OLD-CONTENT"
        assert _tmp_leftovers(tmp_path) == []

    def test_raises_unwrapped_and_does_not_log(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The best-effort tier never logs; the caller owns catch/log/swallow.

        Unlike the standard and hardened tiers (which log at ERROR before
        re-raising), this tier is used exclusively by callers that already wrap
        the call in their own catch with their own message and level. Internal
        logging here would double-log or contradict the caller's message, so
        this pins the "raises unwrapped, logs nothing" contract the module
        docstring documents.
        """
        target = tmp_path / "payload.bin"
        target.mkdir()
        (target / "marker.txt").write_text("still a directory", encoding="utf-8")

        with caplog.at_level("DEBUG"), pytest.raises(OSError):
            atomic_write_best_effort_bytes(target, b"would-be payload")

        assert caplog.records == []


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

    def test_hardened_tier_calls_no_per_file_permission_helper(self) -> None:
        """The durable write path must spawn no permission subprocess per file.

        Confidentiality for durable writes comes from the storage tree's
        directory ACL, applied ONCE at creation by
        :func:`~cadrumo.core.file_permissions.restrict_directory_permissions`.
        A per-file ``icacls.exe`` strip was measured at ~28 ms/write, and the
        blob writer runs this tier once per stored attachment, so reinstating
        one would be O(N) subprocess spawns across a bulk evidence ingest.

        Asserted against the module SOURCE rather than by timing a write.
        This gate was first written as an elapsed-time budget and was wrong:
        it passed alone and failed under parallel load, because wall-clock
        measures disk contention rather than the property in question. A
        reference to the per-file helper either exists in this module or it
        does not, and that answer does not vary with machine or load.
        """
        source = Path(atomic_write.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        called = {
            node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        } | {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }

        assert "restrict_file_permissions" not in called, (
            "the hardened tier calls the per-file permission helper again; "
            "harden the storage directory once instead of every write"
        )


class TestDurableWriteBatch:
    """Batched hardened writes stay atomic while deferring their durability sync."""

    def test_batched_writes_land_complete_and_leave_no_staging_files(self, tmp_path: Path) -> None:
        """Deferring fsync must not weaken ATOMICITY, only durability timing.

        The two properties are independent and the batch trades exactly one of
        them: ``O_EXCL`` staging plus :func:`os.replace` still means a reader
        never observes a partial file, while the fsync that guarantees the
        bytes survive a power cut moves to the commit.
        """
        payload = b"\x00evidence-bytes\xff"

        with durable_write_batch() as batch:
            for index in range(8):
                atomic_write_hardened_bytes(tmp_path / f"blob{index}.bin", payload, batch=batch)

        for index in range(8):
            assert (tmp_path / f"blob{index}.bin").read_bytes() == payload
        assert _tmp_leftovers(tmp_path) == []

    def test_commit_is_idempotent(self, tmp_path: Path) -> None:
        """An explicit commit inside the scope must not double-sync on exit."""
        with durable_write_batch() as batch:
            atomic_write_hardened_bytes(tmp_path / "one.bin", b"payload", batch=batch)
            batch.commit()
            batch.commit()

        assert (tmp_path / "one.bin").read_bytes() == b"payload"

    def test_an_exception_mid_batch_still_commits_what_landed(self, tmp_path: Path) -> None:
        """A failure must not leave completed writes LESS durable than unbatched.

        The commit runs from a ``finally``, so raising part-way through a bulk
        ingest still syncs the records that already landed. Without that, an
        interrupted import would be more exposed than the per-file path it
        replaced — a batch may defer durability, never abandon it.
        """
        sentinel = RuntimeError("ingest aborted part-way")

        with pytest.raises(RuntimeError) as caught, durable_write_batch() as batch:
            atomic_write_hardened_bytes(tmp_path / "landed.bin", b"kept", batch=batch)
            raise sentinel

        assert caught.value is sentinel
        assert (tmp_path / "landed.bin").read_bytes() == b"kept"
        assert _tmp_leftovers(tmp_path) == []

    def test_batching_defers_the_per_write_sync(self) -> None:
        """Batched writes must issue no per-file sync; unbatched must issue one each.

        This is the reason the class exists, so it is asserted rather than
        assumed — but asserted as a SYSCALL COUNT, not as elapsed time.

        Two earlier versions of this gate measured duration: an absolute
        budget, then a same-run ratio. Both passed alone and failed under
        parallel load, because a stopwatch measures whatever else is hitting
        the disk. The property is "how many syncs are issued", which is an
        integer that does not move with machine or contention.

        The counter DELEGATES to the real :func:`os.fsync`, so the writes
        under test perform genuine syncs and this observes them rather than
        replacing them.
        """
        real_fsync = os.fsync
        calls = 0

        def counting_fsync(fd: int) -> None:
            nonlocal calls
            calls += 1
            real_fsync(fd)

        payload = b"y" * 512
        writes = 8

        with scoped_attribute(os, "fsync", counting_fsync):
            with tempfile.TemporaryDirectory() as raw_unbatched:
                unbatched_dir = Path(raw_unbatched)
                calls = 0
                for index in range(writes):
                    atomic_write_hardened_bytes(unbatched_dir / f"plain{index}.bin", payload)
                unbatched_syncs = calls

            with tempfile.TemporaryDirectory() as raw_batched:
                batched_dir = Path(raw_batched)
                calls = 0
                with durable_write_batch() as batch:
                    for index in range(writes):
                        atomic_write_hardened_bytes(batched_dir / f"blob{index}.bin", payload, batch=batch)
                    during_batch = calls

        # Positive control: the counter genuinely observes the unbatched path,
        # so a zero on the batched side means deferral rather than a blind
        # instrument.
        assert unbatched_syncs >= writes, (
            f"expected at least one sync per unbatched write, saw {unbatched_syncs} for {writes} writes"
        )
        assert during_batch == 0, (
            f"batched writes issued {during_batch} per-file syncs; the batch is no longer deferring them"
        )


def test_publish_once_refuses_an_existing_target_and_leaves_it_untouched(tmp_path: Path) -> None:
    """The publish-once tier's whole reason to exist is the tier above it clobbering.

    The hardened tier's ``O_EXCL`` guards its staging sibling, not the
    destination, and it publishes with ``os.replace``. So the assertion that
    matters is comparative: the same two-write sequence must overwrite under the
    hardened tier and raise under this one. Asserting the refusal alone would
    pass just as well if both tiers refused, which would mean the new tier was
    redundant rather than necessary.
    """
    hardened_target = tmp_path / "hardened.json"
    atomic_write_hardened_bytes(hardened_target, b"FIRST")
    atomic_write_hardened_bytes(hardened_target, b"SECOND")
    assert hardened_target.read_bytes() == b"SECOND", (
        "the hardened tier is expected to overwrite; if it now refuses, the publish-once tier is redundant"
    )

    target = tmp_path / "publish_once.json"
    atomic_write_publish_once_bytes(target, b"FIRST")
    assert target.read_bytes() == b"FIRST"

    with pytest.raises(FileExistsError):
        atomic_write_publish_once_bytes(target, b"SECOND")

    assert target.read_bytes() == b"FIRST", "the refused write must not have replaced the target"
    assert {child.name for child in scan_directory(tmp_path)} == {"hardened.json", "publish_once.json"}, (
        "a refused or successful publish must not leave its staging sibling behind"
    )


def test_publish_once_creates_parents_and_publishes_at_the_requested_mode(tmp_path: Path) -> None:
    """A first write must still be an ordinary successful write, parents included.

    Without this the refusal test above could pass against a tier that never
    wrote anything at all.
    """
    target = tmp_path / "nested" / "deeper" / "evidence.json"
    atomic_write_publish_once_bytes(target, b'{"attested": true}', mode=0o600)

    assert target.read_bytes() == b'{"attested": true}'
    assert target.parent.is_dir()
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_staged_publication_reserves_an_unguessable_sibling_rather_than_a_predictable_one(
    tmp_path: Path,
) -> None:
    """The staging name must not be derivable from the destination the caller chose.

    A destination is frequently operator-supplied, so ``{name}.tmp`` beside it
    is a name anything watching that directory can compute in advance. Assert
    the negative directly -- the predictable sibling is never created -- and
    assert two successive reservations for the SAME destination differ, which a
    hard-coded "unpredictable-looking" constant would fail.
    """
    target = tmp_path / "declaracion.txt"
    predictable = target.with_name(target.name + ".tmp")

    with hardened_staged_publication(target) as first:
        first_path = first.path
        assert first_path != predictable
        assert not predictable.exists(), "the predictable sibling name must never be reserved"
        assert first_path.parent == target.parent, "staging must stay on the destination's filesystem"
        assert first_path.exists(), "the staging name must be reserved before the caller writes"
        assert first_path.read_bytes() == b"", "the reservation must be an empty file the caller owns"

    with hardened_staged_publication(target) as second:
        assert second.path != first_path, "two reservations for one destination must not share a name"

    assert scan_directory(tmp_path) == (), "an unpublished reservation must leave nothing behind"


def test_staged_publication_reservation_refuses_a_pre_existing_staging_file(tmp_path: Path) -> None:
    """``O_EXCL`` must refuse to adopt a file the caller did not create.

    Reserving with ``O_CREAT`` alone would silently write the payload into
    whatever already occupied the staging name. The name is unguessable, so
    this is reached by planting the exact reserved name and re-reserving it.
    """
    target = tmp_path / "declaracion.txt"
    with hardened_staged_publication(target) as staged:
        reserved = staged.path
        staged.path.write_bytes(b"PAYLOAD")
        staged.publish()

    reserved.write_bytes(b"PLANTED")
    with (
        scoped_attribute(atomic_write, "_hardened_staging_path", lambda _path: reserved),
        pytest.raises(FileExistsError),
        hardened_staged_publication(target),
    ):
        pass

    assert reserved.read_bytes() == b"PLANTED", "a refused reservation must not truncate the occupant"
    assert target.read_bytes() == b"PAYLOAD", "a refused reservation must not touch the destination"


def test_staged_publication_publishes_the_caller_written_bytes_and_removes_the_staging_file(
    tmp_path: Path,
) -> None:
    """The whole point of the tier: the caller writes the file, the tier moves it."""
    target = tmp_path / "nested" / "declaracion.txt"

    with hardened_staged_publication(target) as staged:
        assert staged.target_path == target
        assert not staged.published
        with staged.path.open("ab") as handle:
            handle.write(b"<T3030")
            handle.write(b"1>PAYLOAD")
        assert not target.exists(), "the destination must stay untouched until publication"
        staged.publish()
        assert staged.published

    assert target.read_bytes() == b"<T30301>PAYLOAD"
    assert {child.name for child in scan_directory(target.parent)} == {"declaracion.txt"}
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_staged_publication_discards_cleartext_staging_on_an_interrupt(tmp_path: Path) -> None:
    """A ``BaseException`` mid-work must not strand the staged payload on disk.

    This is the case a caller-owned ``except OSError`` or ``except Exception``
    around a hand-rolled staging file misses entirely: the operator interrupts
    the export after the sensitive bytes are written but before they are
    published, the narrow handler never runs, and a complete cleartext artefact
    survives beside the destination under a name nothing will ever clean up.
    """
    target = tmp_path / "declaracion.txt"
    sensitive = b"<T30301>99999999R" + b"9" * 200

    with pytest.raises(KeyboardInterrupt), hardened_staged_publication(target) as staged:
        staged.path.write_bytes(sensitive)
        raise KeyboardInterrupt

    assert not target.exists(), "an interrupted export must publish nothing"
    residue = list(scan_directory(tmp_path, recursive=True, select=DirectoryEntryKind.FILES))
    assert residue == [], f"cleartext staging survived an interrupt: {residue}"


def test_staged_publication_discards_the_staging_file_when_the_caller_never_publishes(
    tmp_path: Path,
) -> None:
    """An early return that skips publication is as much a leak as a raised error."""
    target = tmp_path / "declaracion.txt"

    def _abandon() -> None:
        with hardened_staged_publication(target) as staged:
            staged.path.write_bytes(b"SENSITIVE")
            return

    _abandon()

    assert not target.exists()
    assert scan_directory(tmp_path) == (), "an abandoned staging file must not survive the context"


def test_staged_publication_refuses_a_second_publish(tmp_path: Path) -> None:
    """The staging path is consumed by the first publish; a second call has no source."""
    target = tmp_path / "declaracion.txt"

    with hardened_staged_publication(target) as staged:
        staged.path.write_bytes(b"PAYLOAD")
        staged.publish()
        with pytest.raises(RuntimeError):
            staged.publish()

    assert target.read_bytes() == b"PAYLOAD"


def test_staged_publication_leaves_the_staging_file_for_the_context_when_publication_fails(
    tmp_path: Path,
) -> None:
    """A real publication failure must surface unwrapped and still leave no residue.

    The obstruction is real -- a directory occupying the destination -- so
    ``os.replace`` genuinely refuses rather than being made to.
    """
    target = tmp_path / "declaracion.txt"
    target.mkdir()
    (target / "occupant").write_bytes(b"held")

    with pytest.raises(OSError), hardened_staged_publication(target) as staged:
        staged.path.write_bytes(b"SENSITIVE")
        staged.publish()

    assert target.is_dir(), "the refused publication must leave the obstruction untouched"
    residue = [
        child
        for child in scan_directory(tmp_path, recursive=True, select=DirectoryEntryKind.FILES)
        if child.name != "occupant"
    ]
    assert residue == [], f"a failed publication stranded cleartext staging: {residue}"
