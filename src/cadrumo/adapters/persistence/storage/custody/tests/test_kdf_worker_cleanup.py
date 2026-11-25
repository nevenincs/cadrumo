"""KDF cleanup settles its child before touching pipes held by blocked readers."""

from __future__ import annotations

import base64
import json
import os
import queue
import subprocess
import threading
import time
from collections import Counter
from collections.abc import Generator
from pathlib import Path
from typing import cast

import pytest

from ......core.config import Settings
from .. import kdf_process, kdf_worker_cleanup, kdf_worker_supervision
from ..errors import ProfileCustodyRefusal, ProfileCustodyRefusedError
from ..kdf_codec import KDF_FRAME_CONTROL, close_fd
from ..kdf_operations import KdfOperation
from ..kdf_windows_job import WindowsJob
from ..kdf_worker_supervision import SupervisedKdfWorker
from ..records import ProfileCustodyKdfParameters

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@pytest.fixture
def running_worker(
    tmp_path: Path,
) -> Generator[tuple[SupervisedKdfWorker, subprocess.Popen[bytes], WindowsJob | None]]:
    """Keep independent exact-child ownership even if the regression clears its fields."""
    worker = SupervisedKdfWorker(deadline=time.monotonic() + 30, settings=Settings(cadrumo_storage_root=tmp_path))
    terminate = kdf_worker_cleanup.terminate_process_tree
    cleanup = worker._cleanup_neutral_directory
    process: subprocess.Popen[bytes] | None = None
    job: WindowsJob | None = None
    try:
        worker.__enter__()
        process = worker._process
        job = worker._job
        assert process is not None
        yield worker, process, job
    finally:
        process = process or worker._process
        job = job or worker._job
        if process is not None:
            terminate(process, job)
            process.wait(timeout=5)
        elif job is not None:
            job.close()
        close_fd(worker._request_fd)
        close_fd(worker._result_fd)
        worker._request_fd = None
        worker._result_fd = None
        worker._process = None
        worker._job = None
        cleanup()


@pytest.fixture
def partial_worker(tmp_path: Path) -> Generator[SupervisedKdfWorker]:
    worker = SupervisedKdfWorker(deadline=time.monotonic() + 30, settings=Settings(cadrumo_storage_root=tmp_path))
    request_read, worker._request_fd = os.pipe()
    close_fd(request_read)
    worker._result_fd, result_write = os.pipe()
    close_fd(result_write)
    try:
        yield worker
    finally:
        close_fd(worker._request_fd)
        close_fd(worker._result_fd)


def test_partial_no_process_cleanup_closes_descriptors_once_and_can_repeat(
    partial_worker: SupervisedKdfWorker, monkeypatch: pytest.MonkeyPatch
) -> None:
    closes: Counter[int] = Counter()

    def observe_close(descriptor: int | None) -> None:
        if descriptor is not None:
            closes[descriptor] += 1
        close_fd(descriptor)

    monkeypatch.setattr(kdf_worker_cleanup, "close_fd", observe_close)
    descriptors = (partial_worker._request_fd, partial_worker._result_fd)
    partial_worker._close(failed=True)
    partial_worker._close(failed=True)
    assert all(descriptor is not None and closes[descriptor] == 1 for descriptor in descriptors)
    assert partial_worker._request_fd is None and partial_worker._result_fd is None


def test_partial_no_process_cleanup_retains_failed_job_but_closes_safe_pipes(
    partial_worker: SupervisedKdfWorker,
) -> None:
    primary = OSError("synthetic job close failure")

    class Job:
        attempts = 0

        def close(self) -> None:
            self.attempts += 1
            if self.attempts == 1:
                raise primary

    job = Job()
    partial_worker._job = cast("WindowsJob", job)
    with pytest.raises(OSError) as escaped:
        partial_worker._close(failed=True)
    assert escaped.value is primary and partial_worker._job is job
    assert partial_worker._request_fd is None and partial_worker._result_fd is None
    partial_worker._close(failed=True)
    assert partial_worker._job is None and job.attempts == 2


@pytest.mark.parametrize("interrupted", [False, True])
def test_termination_failure_retains_real_ownership_until_a_later_close(
    running_worker: tuple[SupervisedKdfWorker, subprocess.Popen[bytes], WindowsJob | None],
    interrupted: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker, process, job = running_worker
    descriptors = (worker._request_fd, worker._result_fd)
    neutral_directory = worker._neutral_directory
    primary = (
        KeyboardInterrupt("synthetic termination interruption")
        if interrupted
        else OSError("synthetic termination failure")
    )

    def refuse_termination(_process: subprocess.Popen[bytes], _job: WindowsJob | None) -> None:
        raise primary

    with monkeypatch.context() as patch:
        patch.setattr(kdf_worker_cleanup, "terminate_process_tree", refuse_termination)
        with pytest.raises(type(primary)) as escaped:
            worker._close(failed=True)
        assert escaped.value is primary
        assert worker._process is process and worker._job is job and worker._neutral_directory is neutral_directory
        assert (worker._request_fd, worker._result_fd) == descriptors
        for descriptor in descriptors:
            assert descriptor is not None
            os.fstat(descriptor)
        assert process.poll() is None
    worker._close(failed=True)
    assert process.returncode is not None
    assert worker._process is None and worker._job is None and worker._neutral_directory is None
    assert worker._request_fd is None and worker._result_fd is None
    worker._close(failed=True)


def test_unconfirmed_existing_termination_attempts_refuse_without_closing_pipes(
    running_worker: tuple[SupervisedKdfWorker, subprocess.Popen[bytes], WindowsJob | None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker, process, job = running_worker
    descriptors = (worker._request_fd, worker._result_fd)
    attempts = 0
    waits: list[float | None] = []

    def unconfirmed_termination(_process: subprocess.Popen[bytes], _job: WindowsJob | None) -> None:
        nonlocal attempts
        attempts += 1

    def wait(*, timeout: float | None = None) -> int:
        waits.append(timeout)
        assert timeout is not None
        raise subprocess.TimeoutExpired("synthetic child", timeout)

    with monkeypatch.context() as patch:
        patch.setattr(kdf_worker_cleanup, "terminate_process_tree", unconfirmed_termination)
        patch.setattr(process, "wait", wait)
        with pytest.raises(ProfileCustodyRefusedError) as refused:
            worker._close(failed=True)
        assert refused.value.refusal == ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE
        assert attempts == 2 and waits == [1.0]
        assert worker._process is process and worker._job is job and process.returncode is None
        assert (worker._request_fd, worker._result_fd) == descriptors
        for descriptor in descriptors:
            assert descriptor is not None
            os.fstat(descriptor)
    worker._close(failed=True)
    assert process.returncode is not None and worker._process is None
    assert worker._request_fd is None and worker._result_fd is None


_PAUSED_WRITER_CHILD_SOURCE = (
    "from cadrumo.adapters.persistence.storage.custody import kdf_worker as worker\n"
    "import threading\n"
    "original_write = worker.write_kdf_frame\n"
    "result_fd = None\n"
    "def write(fd, value, *, kind):\n"
    "    global result_fd\n"
    "    result_fd = fd\n"
    "    original_write(fd, value, kind=kind)\n"
    "def hold_writer(payload):\n"
    "    original_write(result_fd, b'fixture-paused', kind=worker.KDF_FRAME_CONTROL)\n"
    "    threading.Event().wait()\n"
    "worker.write_kdf_frame = write\n"
    "worker.derive_calibration = hold_writer\n"
    "raise SystemExit(worker.main())\n"
)


def _launch_paused_writer_child(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the worker launch a child that answers one frame and then blocks forever."""
    launch_process = kdf_process.launch_worker_process

    def launch(command: list[str], launch_kwargs: dict[str, object]) -> subprocess.Popen[bytes]:
        entry = command.index("-m")
        return launch_process(
            [*command[:entry], "-c", _PAUSED_WRITER_CHILD_SOURCE, *command[entry + 2 :]], launch_kwargs
        )

    monkeypatch.setattr(kdf_process, "launch_worker_process", launch)


class _BlockedReaderCleanup:
    """Drive a real worker whose reader is blocked while cleanup must settle the child first."""

    def __init__(self, worker: SupervisedKdfWorker) -> None:
        self.worker = worker
        self.process: subprocess.Popen[bytes] | None = None
        self.job: WindowsJob | None = None
        self.result_fd: int | None = None
        self.reader_threads: list[threading.Thread] = []
        self.cleanup_thread: threading.Thread | None = None
        self.rescue_thread: threading.Thread | None = None
        self.entered_read = threading.Event()
        self.entered_close = threading.Event()
        self.closed = threading.Event()
        self.cleanup_done = threading.Event()
        self.rescued = threading.Event()
        self.close_exit_codes: list[int | None] = []
        self.cleanup_errors: list[BaseException] = []
        self.original_reader = kdf_worker_supervision.read_kdf_frame_to_queue
        self.original_close = kdf_worker_cleanup.close_fd
        self.terminate = kdf_worker_cleanup.terminate_process_tree
        self.cleanup_started = 0.0
        self.cleanup_elapsed = 0.0

    def start_and_pause_child(self) -> None:
        self.worker.__enter__()
        self.process = self.worker._process
        self.job = self.worker._job
        assert self.process is not None and self.worker._result_fd is not None
        self.result_fd = self.worker._result_fd
        kdf = ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=base64.b64encode(b"k" * 16).decode("ascii"),
            output_bytes=32,
        )
        self.worker.write_request(
            {"version": 1, "operation": KdfOperation.CALIBRATE, "kdf": kdf.model_dump(mode="json")}
        )
        assert self.worker.read_response_frame() == (KDF_FRAME_CONTROL, b"fixture-paused")

    def observe_reader(self, descriptor: int, result_queue: queue.Queue[tuple[int, bytes] | BaseException]) -> None:
        self.reader_threads.append(threading.current_thread())
        self.entered_read.set()
        self.original_reader(descriptor, result_queue)

    def observe_close(self, descriptor: int | None) -> None:
        if descriptor != self.result_fd:
            self.original_close(descriptor)
            return
        assert self.process is not None
        self.close_exit_codes.append(self.process.returncode)
        self.entered_close.set()
        try:
            self.original_close(descriptor)
        finally:
            self.closed.set()

    def cleanup(self) -> None:
        try:
            self.worker._close(failed=True)
        except BaseException as error:
            self.cleanup_errors.append(error)
        finally:
            self.cleanup_elapsed = time.monotonic() - self.cleanup_started
            self.cleanup_done.set()

    def rescue(self) -> None:
        if self.entered_close.wait(timeout=5) and self.close_exit_codes == [None] and not self.closed.wait(timeout=0.2):
            assert self.process is not None
            self.rescued.set()
            self.process.kill()
            self.process.wait(timeout=5)

    def block_reader_past_the_deadline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(kdf_worker_supervision, "read_kdf_frame_to_queue", self.observe_reader)
        monkeypatch.setattr(kdf_worker_cleanup, "close_fd", self.observe_close)
        self.worker._deadline = time.monotonic() + 0.05
        with pytest.raises(TimeoutError):
            self.worker.read_response_frame()
        assert self.entered_read.is_set() and self.reader_threads and self.reader_threads[0].is_alive()

    def run_cleanup_beside_rescue(self) -> None:
        self.cleanup_started = time.monotonic()
        self.rescue_thread = threading.Thread(target=self.rescue)
        self.cleanup_thread = threading.Thread(target=self.cleanup)
        self.rescue_thread.start()
        self.cleanup_thread.start()
        assert self.cleanup_done.wait(timeout=10), "Owned rescue must release blocked cleanup"

    def assert_child_settled_before_descriptor_close(self) -> None:
        assert not self.cleanup_errors
        assert self.close_exit_codes and all(code is not None for code in self.close_exit_codes)
        assert not self.rescued.is_set()
        assert self.process is not None and self.process.returncode is not None and self.worker._process is None
        assert self.worker._request_fd is None and self.worker._result_fd is None

    def _stop_child(self, teardown_errors: list[str]) -> None:
        process = self.process
        if process is None:
            return
        try:
            self.terminate(process, self.job)
            process.wait(timeout=5)
        except BaseException as error:
            teardown_errors.append(type(error).__name__)
            # The fixture retains exact-child ownership independently of
            # the supervisor, including when its cleanup assertion fails.
            try:
                process.kill()
                process.wait(timeout=5)
            except BaseException as rescue_error:
                teardown_errors.append(type(rescue_error).__name__)

    def _join_threads(self) -> None:
        if self.cleanup_thread is not None and self.cleanup_thread.ident is not None:
            self.cleanup_thread.join(timeout=10)
        if self.rescue_thread is not None:
            self.entered_close.set()
            if self.rescue_thread.ident is not None:
                self.rescue_thread.join(timeout=10)
        for reader in self.reader_threads:
            reader.join(timeout=10)

    def _close_descriptors(self, teardown_errors: list[str]) -> None:
        try:
            close_fd(self.worker._request_fd)
            close_fd(self.worker._result_fd)
            self.worker._request_fd = None
            self.worker._result_fd = None
            self.worker._cleanup_neutral_directory()
        except BaseException as error:
            teardown_errors.append(type(error).__name__)

    def teardown(self, tmp_path: Path) -> None:
        teardown_errors: list[str] = []
        process = self.process
        self._stop_child(teardown_errors)
        self._join_threads()
        readers_settled = all(not reader.is_alive() for reader in self.reader_threads)
        cleanup_settled = self.cleanup_thread is None or not self.cleanup_thread.is_alive()
        rescue_settled = self.rescue_thread is None or not self.rescue_thread.is_alive()
        child_settled = process is None or process.returncode is not None
        if child_settled and readers_settled and cleanup_settled and rescue_settled:
            self._close_descriptors(teardown_errors)
        facts = {
            "pid": process.pid if process is not None else None,
            "exit_code": process.returncode if process is not None else None,
            "close_exit_codes": self.close_exit_codes,
            "rescued": self.rescued.is_set(),
            "cleanup_elapsed_seconds": self.cleanup_elapsed,
            "reader_threads_settled": readers_settled,
            "cleanup_thread_settled": cleanup_settled,
            "rescue_thread_settled": rescue_settled,
            "child_settled": child_settled,
            "teardown_error_types": teardown_errors,
        }
        # Kept in the test's own pytest-managed directory for inspection after a failure.
        evidence = tmp_path / "blocked-cleanup.json"
        evidence.write_text(json.dumps(facts, indent=2), encoding="utf-8")
        assert child_settled and cleanup_settled and rescue_settled and readers_settled, facts
        assert not teardown_errors, facts


def test_real_blocked_reader_cleanup_settles_child_before_descriptor_close(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _launch_paused_writer_child(monkeypatch)
    worker = SupervisedKdfWorker(deadline=time.monotonic() + 30, settings=Settings(cadrumo_storage_root=tmp_path))
    blocked = _BlockedReaderCleanup(worker)
    try:
        blocked.start_and_pause_child()
        blocked.block_reader_past_the_deadline(monkeypatch)
        blocked.run_cleanup_beside_rescue()
        blocked.assert_child_settled_before_descriptor_close()
    finally:
        blocked.teardown(tmp_path)
