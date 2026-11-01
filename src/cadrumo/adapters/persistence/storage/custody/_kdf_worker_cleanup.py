"""Retained, ordered release of one supervised KDF worker's resources."""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
import threading
import time

from ._kdf_codec import close_fd as _close_fd
from ._kdf_process import terminate_process_tree as _terminate_process_tree
from ._kdf_refusals import supervision_refusal as _supervision_refusal
from ._kdf_windows_job import _WindowsJob
from ._kdf_worker_observation import KdfWorkerObservation


class KdfWorkerCleanup(KdfWorkerObservation):
    """Own child settlement, pipe readers and the worker's neutral directory."""

    _cleanup_lock: threading.Lock
    _process: subprocess.Popen[bytes] | None
    _job: _WindowsJob | None
    _readers: list[threading.Thread]
    _request_fd: int | None
    _result_fd: int | None
    _neutral_directory: tempfile.TemporaryDirectory[str] | None

    def _cleanup_pending(self) -> bool:
        """Whether this worker still owns a child, pipe reader, descriptor or directory."""
        return bool(
            self._process is not None
            or self._job is not None
            or self._readers
            or self._request_fd is not None
            or self._result_fd is not None
            or self._neutral_directory is not None
        )

    async def close(self) -> None:
        """Retry retained cleanup without blocking an asynchronous owner."""
        await asyncio.to_thread(self._close, failed=True)

    def _close(self, *, failed: bool) -> None:
        """Serialize all release attempts on the exact owned descriptors."""
        with self._cleanup_lock:
            self._close_resources(failed=failed)

    def _close_resources(self, *, failed: bool) -> None:
        process = self._process
        job = self._job
        if process is not None:
            with self._cleanup_span("process"):
                if failed or process.poll() is None:
                    _terminate_process_tree(process, job)
                elif job is not None:
                    job.close()
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    _terminate_process_tree(process, job)
                if process.returncode is None:
                    raise _supervision_refusal()
                self._process = None
                self._job = None
        # A Windows reader may hold the CRT descriptor lock while blocked in
        # os.read. Settle its writer before closing the parent pipe ends.
        self._close_pipes()
        if process is None and job is not None:
            with self._cleanup_span("process"):
                job.close()
                self._job = None
        with self._cleanup_span("directory"):
            self._cleanup_neutral_directory()

    def _close_pipes(self) -> None:
        with self._cleanup_span("pipes"):
            for reader in self._readers:
                reader.join(timeout=1.0)
                if reader.is_alive():
                    raise _supervision_refusal()
            self._readers.clear()
            _close_fd(self._request_fd)
            _close_fd(self._result_fd)
            self._request_fd = None
            self._result_fd = None

    def _cleanup_neutral_directory(self) -> None:
        if self._neutral_directory is not None:
            try:
                for attempt in range(10):
                    try:
                        self._neutral_directory.cleanup()
                    except OSError:
                        if attempt == 9:
                            raise
                        time.sleep(0.05)
                    else:
                        self._neutral_directory = None
                        return
            except OSError:
                raise _supervision_refusal() from None
