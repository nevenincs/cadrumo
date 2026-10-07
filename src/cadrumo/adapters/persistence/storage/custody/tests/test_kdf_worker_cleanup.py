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
from .. import _kdf_process as process_boundary
from .. import _kdf_worker_supervision as supervision
from .._kdf_codec import KDF_FRAME_CONTROL, close_fd
from .._kdf_operations import KdfOperation
from .._kdf_windows_job import _WindowsJob
from .._kdf_worker_supervision import _SupervisedKdfWorker
from ..errors import ProfileCustodyRefusal, ProfileCustodyRefusedError
from ..records import ProfileCustodyKdfParameters

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@pytest.fixture
def running_worker(
    tmp_path: Path,
) -> Generator[tuple[_SupervisedKdfWorker, subprocess.Popen[bytes], _WindowsJob | None]]:
    """Keep independent exact-child ownership even if the regression clears its fields."""
    worker = _SupervisedKdfWorker(
        deadline=time.monotonic() + 30, settings=Settings(cadrumo_local_storage_root=tmp_path)
    )
    terminate = supervision._terminate_process_tree
    cleanup = worker._cleanup_neutral_directory
    process: subprocess.Popen[bytes] | None = None
    job: _WindowsJob | None = None
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
def partial_worker(tmp_path: Path) -> Generator[_SupervisedKdfWorker]:
    worker = _SupervisedKdfWorker(
        deadline=time.monotonic() + 30, settings=Settings(cadrumo_local_storage_root=tmp_path)
    )
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
    partial_worker: _SupervisedKdfWorker, monkeypatch: pytest.MonkeyPatch
) -> None:
    closes: Counter[int] = Counter()

    def observe_close(descriptor: int | None) -> None:
        if descriptor is not None:
            closes[descriptor] += 1
        close_fd(descriptor)

    monkeypatch.setattr(supervision, "_close_fd", observe_close)
    descriptors = (partial_worker._request_fd, partial_worker._result_fd)
    partial_worker._close(failed=True)
    partial_worker._close(failed=True)
    assert all(descriptor is not None and closes[descriptor] == 1 for descriptor in descriptors)
    assert partial_worker._request_fd is None and partial_worker._result_fd is None


def test_partial_no_process_cleanup_retains_failed_job_but_closes_safe_pipes(
    partial_worker: _SupervisedKdfWorker,
) -> None:
    primary = OSError("synthetic job close failure")

    class Job:
        attempts = 0

        def close(self) -> None:
            self.attempts += 1
            if self.attempts == 1:
                raise primary

    job = Job()
    partial_worker._job = cast("_WindowsJob", job)
    with pytest.raises(OSError) as escaped:
        partial_worker._close(failed=True)
    assert escaped.value is primary and partial_worker._job is job
    assert partial_worker._request_fd is None and partial_worker._result_fd is None
    partial_worker._close(failed=True)
    assert partial_worker._job is None and job.attempts == 2


@pytest.mark.parametrize("interrupted", [False, True])
def test_termination_failure_retains_real_ownership_until_a_later_close(
    running_worker: tuple[_SupervisedKdfWorker, subprocess.Popen[bytes], _WindowsJob | None],
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

    def refuse_termination(_process: subprocess.Popen[bytes], _job: _WindowsJob | None) -> None:
        raise primary

    with monkeypatch.context() as patch:
        patch.setattr(supervision, "_terminate_process_tree", refuse_termination)
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
    running_worker: tuple[_SupervisedKdfWorker, subprocess.Popen[bytes], _WindowsJob | None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker, process, job = running_worker
    descriptors = (worker._request_fd, worker._result_fd)
    attempts = 0
    waits: list[float | None] = []

    def unconfirmed_termination(_process: subprocess.Popen[bytes], _job: _WindowsJob | None) -> None:
        nonlocal attempts
        attempts += 1

    def wait(*, timeout: float | None = None) -> int:
        waits.append(timeout)
        assert timeout is not None
        raise subprocess.TimeoutExpired("synthetic child", timeout)

    with monkeypatch.context() as patch:
        patch.setattr(supervision, "_terminate_process_tree", unconfirmed_termination)
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


def test_real_blocked_reader_cleanup_settles_child_before_descriptor_close(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    launch_process = process_boundary._launch_worker_process
    source = (
        "from cadrumo.adapters.persistence.storage.custody import _kdf_worker as worker\n"
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
        "worker._derive_calibration = hold_writer\n"
        "raise SystemExit(worker.main())\n"
    )

    def launch(command: list[str], launch_kwargs: dict[str, object]) -> subprocess.Popen[bytes]:
        return launch_process([command[0], "-c", source, *command[3:]], launch_kwargs)

    monkeypatch.setattr(process_boundary, "_launch_worker_process", launch)
    worker = _SupervisedKdfWorker(
        deadline=time.monotonic() + 30, settings=Settings(cadrumo_local_storage_root=tmp_path)
    )
    process: subprocess.Popen[bytes] | None = None
    job: _WindowsJob | None = None
    reader_threads: list[threading.Thread] = []
    cleanup_thread: threading.Thread | None = None
    rescue_thread: threading.Thread | None = None
    entered_read = threading.Event()
    entered_close = threading.Event()
    closed = threading.Event()
    cleanup_done = threading.Event()
    rescued = threading.Event()
    close_exit_codes: list[int | None] = []
    cleanup_errors: list[BaseException] = []
    original_reader = supervision._read_kdf_frame_to_queue
    original_close = supervision._close_fd
    terminate = supervision._terminate_process_tree
    cleanup_started = 0.0
    cleanup_elapsed = 0.0
    try:
        worker.__enter__()
        process = worker._process
        job = worker._job
        assert process is not None and worker._result_fd is not None
        child = process
        result_fd = worker._result_fd
        kdf = ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=base64.b64encode(b"k" * 16).decode("ascii"),
            output_bytes=32,
        )
        worker._write_request({"version": 1, "operation": KdfOperation.CALIBRATE, "kdf": kdf.model_dump(mode="json")})
        assert worker._read_response_frame() == (KDF_FRAME_CONTROL, b"fixture-paused")

        def observe_reader(descriptor: int, result_queue: queue.Queue[tuple[int, bytes] | BaseException]) -> None:
            reader_threads.append(threading.current_thread())
            entered_read.set()
            original_reader(descriptor, result_queue)

        def observe_close(descriptor: int | None) -> None:
            if descriptor != result_fd:
                original_close(descriptor)
                return
            close_exit_codes.append(child.returncode)
            entered_close.set()
            try:
                original_close(descriptor)
            finally:
                closed.set()

        def cleanup() -> None:
            nonlocal cleanup_elapsed
            try:
                worker._close(failed=True)
            except BaseException as error:
                cleanup_errors.append(error)
            finally:
                cleanup_elapsed = time.monotonic() - cleanup_started
                cleanup_done.set()

        def rescue() -> None:
            if entered_close.wait(timeout=5) and close_exit_codes == [None] and not closed.wait(timeout=0.2):
                rescued.set()
                child.kill()
                child.wait(timeout=5)

        monkeypatch.setattr(supervision, "_read_kdf_frame_to_queue", observe_reader)
        monkeypatch.setattr(supervision, "_close_fd", observe_close)
        worker._deadline = time.monotonic() + 0.05
        with pytest.raises(TimeoutError):
            worker._read_response_frame()
        assert entered_read.is_set() and reader_threads and reader_threads[0].is_alive()
        cleanup_started = time.monotonic()
        rescue_thread = threading.Thread(target=rescue)
        cleanup_thread = threading.Thread(target=cleanup)
        rescue_thread.start()
        cleanup_thread.start()
        assert cleanup_done.wait(timeout=10), "Owned rescue must release blocked cleanup"
        assert not cleanup_errors
        assert close_exit_codes and all(code is not None for code in close_exit_codes)
        assert not rescued.is_set()
        assert process.returncode is not None and worker._process is None
        assert worker._request_fd is None and worker._result_fd is None
    finally:
        teardown_errors: list[str] = []
        if process is not None:
            try:
                terminate(process, job)
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
        if cleanup_thread is not None and cleanup_thread.ident is not None:
            cleanup_thread.join(timeout=10)
        if rescue_thread is not None:
            entered_close.set()
            if rescue_thread.ident is not None:
                rescue_thread.join(timeout=10)
        for reader in reader_threads:
            reader.join(timeout=10)
        readers_settled = all(not reader.is_alive() for reader in reader_threads)
        cleanup_settled = cleanup_thread is None or not cleanup_thread.is_alive()
        rescue_settled = rescue_thread is None or not rescue_thread.is_alive()
        child_settled = process is None or process.returncode is not None
        if child_settled and readers_settled and cleanup_settled and rescue_settled:
            try:
                close_fd(worker._request_fd)
                close_fd(worker._result_fd)
                worker._request_fd = None
                worker._result_fd = None
                worker._cleanup_neutral_directory()
            except BaseException as error:
                teardown_errors.append(type(error).__name__)
        facts = {
            "pid": process.pid if process is not None else None,
            "exit_code": process.returncode if process is not None else None,
            "close_exit_codes": close_exit_codes,
            "rescued": rescued.is_set(),
            "cleanup_elapsed_seconds": cleanup_elapsed,
            "reader_threads_settled": readers_settled,
            "cleanup_thread_settled": cleanup_settled,
            "rescue_thread_settled": rescue_settled,
            "child_settled": child_settled,
            "teardown_error_types": teardown_errors,
        }
        evidence = Path(os.environ["CADRUMO_TEST_RUN_ROOT"]) / "artifacts" / "s26-blocked-cleanup.json"
        evidence.write_text(json.dumps(facts, indent=2), encoding="utf-8")
        assert child_settled and cleanup_settled and rescue_settled and readers_settled
        assert not teardown_errors
