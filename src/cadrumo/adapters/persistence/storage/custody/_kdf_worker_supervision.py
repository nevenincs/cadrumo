"""Process supervision boundary for profile-custody KDF work."""

from __future__ import annotations

import base64
import json
import logging
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Literal, cast

from pydantic import ValidationError

from .....core.config import Settings, load_settings
from .....core.diagnostic_log import DiagnosticValue, diagnostic_event
from .....core.logging import get_logger
from ..crypto.aes_gcm import KEY_SIZE
from ._kdf_attestation import (
    parse_ready_attestation as _parse_ready_attestation,
)
from ._kdf_codec import (
    KDF_FAILED_FRAME,
    KDF_FRAME_CONTROL,
    KDF_FRAME_DEK,
    KDF_TRANSPORT_ENCODING,
    write_kdf_frame,
)
from ._kdf_codec import (
    canonical_frame_bytes as _canonical_frame_bytes,
)
from ._kdf_codec import (
    close_fd as _close_fd,
)
from ._kdf_codec import (
    parse_calibration_frame as _parse_calibration_frame,
)
from ._kdf_codec import (
    read_kdf_frame_to_queue as _read_kdf_frame_to_queue,
)
from ._kdf_operations import KdfOperation
from ._kdf_process import (
    launch_worker as _launch_worker,
)
from ._kdf_process import (
    terminate_process_tree as _terminate_process_tree,
)
from ._kdf_refusals import resource_refusal as _resource_refusal
from ._kdf_refusals import supervision_refusal as _supervision_refusal
from ._kdf_windows_job import _WindowsJob
from ._kdf_worker_identity import verify_ready_worker as _verify_ready_worker
from .records import ProfileCustodyKdfParameters, ProfileCustodyWrappedDek

logger = get_logger(__name__)

type _KdfStage = Literal[
    "start",
    "ready_wait",
    "ready_attestation",
    "request_write",
    "result_wait",
    "clean_exit",
    "result_validation",
    "cleanup",
]
type _KdfCleanupStatus = Literal["completed", "unconfirmed", "failed"]

_PHASE_FIELDS: dict[_KdfStage, str] = {
    "start": "kdf_start_elapsed_ms",
    "ready_wait": "kdf_ready_wait_elapsed_ms",
    "ready_attestation": "kdf_ready_attestation_elapsed_ms",
    "request_write": "kdf_request_write_elapsed_ms",
    "result_wait": "kdf_result_wait_elapsed_ms",
    "clean_exit": "kdf_clean_exit_elapsed_ms",
    "cleanup": "kdf_cleanup_elapsed_ms",
}


class _SupervisedKdfWorker:
    """One process with a complete no-fallback lifecycle and bounded pipes."""

    def __init__(self, *, deadline: float, settings: Settings | None = None) -> None:
        self._deadline = deadline
        self._temporary_root = (settings or load_settings()).cadrumo_temp_dir
        self._process: subprocess.Popen[bytes] | None = None
        self._request_fd: int | None = None
        self._result_fd: int | None = None
        self._job: _WindowsJob | None = None
        self._neutral_directory: tempfile.TemporaryDirectory[str] | None = None
        self._ready_payload: dict[str, object] | None = None
        self._expected_posix_file_descriptors: tuple[int, int] | None = None
        self._started_ns = 0
        self._phase_elapsed_ms: dict[_KdfStage, float | None] = dict.fromkeys(_PHASE_FIELDS)
        self._failure_stage: _KdfStage | Literal["caller"] | None = None
        self._failure_type: str | None = None
        self._launch_attempted = False
        self._result_refused = False
        self._diagnostic_emitted = False

    def __enter__(self) -> _SupervisedKdfWorker:
        self._started_ns = time.monotonic_ns()
        self._phase_elapsed_ms = dict.fromkeys(_PHASE_FIELDS)
        self._failure_stage = None
        self._failure_type = None
        self._launch_attempted = False
        self._result_refused = False
        self._diagnostic_emitted = False
        try:
            with self._phase("start"):
                self._start()
            with self._phase("ready_wait"):
                ready = self._read_response_frame()
            with self._phase("ready_attestation"):
                self._verify_ready_attestation(ready)
            return self
        except BaseException as error:
            self._close_with_diagnostic(failed=True, primary_error=error)
            raise

    def __exit__(self, exc_type: object, exc_value: object, _traceback: object) -> None:
        primary = exc_value if isinstance(exc_value, BaseException) else None
        if primary is not None and self._failure_type is None:
            self._failure_stage = "caller"
            self._failure_type = type(primary).__name__
        self._close_with_diagnostic(failed=exc_type is not None, primary_error=primary)

    def calibrate(self, parameters: ProfileCustodyKdfParameters) -> float:
        """Return the seconds the worker itself timed around the one derivation."""
        kind, result = self._exchange(
            {
                "kdf": parameters.model_dump(mode="json"),
                "operation": KdfOperation.CALIBRATE,
                "version": 1,
            },
        )
        with self._phase("result_validation"):
            if (kind, result) == (KDF_FRAME_CONTROL, KDF_FAILED_FRAME):
                self._result_refused = True
                raise _resource_refusal()
            if kind != KDF_FRAME_CONTROL:
                raise _supervision_refusal()
            try:
                derivation_ns = _parse_calibration_frame(result)
            except (UnicodeDecodeError, ValueError):
                raise _supervision_refusal() from None
            return derivation_ns / 1_000_000_000

    def unwrap(
        self,
        *,
        password: bytes,
        kdf: ProfileCustodyKdfParameters,
        wrapped_dek: ProfileCustodyWrappedDek,
        associated_data: bytes,
        recovery: bool = False,
    ) -> bytes | None:
        kind, result = self._exchange(
            {
                "associated_data_b64": base64.b64encode(associated_data).decode("ascii"),
                "kdf": kdf.model_dump(mode="json"),
                "operation": KdfOperation.RECOVERY_UNWRAP if recovery else KdfOperation.PASSWORD_UNWRAP,
                "password_b64": base64.b64encode(password).decode("ascii"),
                "version": 1,
                "wrapped_dek": wrapped_dek.model_dump(mode="json"),
            },
        )
        with self._phase("result_validation"):
            if (kind, result) == (KDF_FRAME_CONTROL, KDF_FAILED_FRAME):
                self._result_refused = True
                return None
            if kind != KDF_FRAME_DEK or len(result) != KEY_SIZE:
                raise _supervision_refusal()
            return result

    def wrap(
        self,
        *,
        secret: bytes,
        dek: bytes,
        kdf: ProfileCustodyKdfParameters,
        associated_data: bytes,
        recovery: bool = False,
    ) -> ProfileCustodyWrappedDek | None:
        kind, result = self._exchange(
            {
                "associated_data_b64": base64.b64encode(associated_data).decode("ascii"),
                "dek_b64": base64.b64encode(dek).decode("ascii"),
                "kdf": kdf.model_dump(mode="json"),
                "operation": KdfOperation.RECOVERY_WRAP if recovery else KdfOperation.PASSWORD_WRAP,
                "secret_b64": base64.b64encode(secret).decode("ascii"),
                "version": 1,
            },
        )
        with self._phase("result_validation"):
            if (kind, result) == (KDF_FRAME_CONTROL, KDF_FAILED_FRAME):
                self._result_refused = True
                return None
            if kind != KDF_FRAME_CONTROL:
                raise _supervision_refusal()
            try:
                payload = json.loads(result.decode(KDF_TRANSPORT_ENCODING, errors="strict"))
                if not isinstance(payload, dict):
                    raise ValueError("profile KDF wrapper response is invalid")
                record = cast("dict[str, object]", payload)
                if set(record) != {"wrapped_dek"}:
                    raise ValueError("profile KDF wrapper response is invalid")
                return ProfileCustodyWrappedDek.model_validate(record["wrapped_dek"])
            except (UnicodeDecodeError, ValidationError, ValueError, TypeError, json.JSONDecodeError):
                raise _supervision_refusal() from None

    @contextmanager
    def _phase(self, stage: _KdfStage) -> Generator[None]:
        """Collect fixed monotonic spans in memory; never emit during a phase."""
        started = time.monotonic_ns()
        try:
            yield
        except BaseException as error:
            if self._failure_type is None:
                self._failure_stage = stage
                self._failure_type = type(error).__name__
            raise
        finally:
            if stage in _PHASE_FIELDS:
                elapsed_ms = max(0, time.monotonic_ns() - started) / 1_000_000
                self._phase_elapsed_ms[stage] = (self._phase_elapsed_ms[stage] or 0.0) + elapsed_ms

    def _exchange(self, payload: dict[str, object]) -> tuple[int, bytes]:
        with self._phase("request_write"):
            self._write_request(payload)
        with self._phase("result_wait"):
            response = self._read_response_frame()
        with self._phase("clean_exit"):
            self._require_clean_worker_exit()
        return response

    def _close_with_diagnostic(self, *, failed: bool, primary_error: BaseException | None) -> None:
        process = self._process
        try:
            with self._phase("cleanup"):
                self._close(failed=failed)
        except BaseException as cleanup_error:
            self._emit_diagnostic(
                cleanup_status="failed",
                cleanup_error=cleanup_error,
                primary_error=cleanup_error,
                exit_code=process.returncode if process is not None else None,
            )
            raise
        if process is None:
            cleanup_status = "unconfirmed" if self._launch_attempted or self._failure_stage == "start" else "completed"
        else:
            cleanup_status = "unconfirmed" if process.returncode is None else "completed"
        self._emit_diagnostic(
            cleanup_status=cleanup_status,
            cleanup_error=None,
            primary_error=primary_error,
            exit_code=process.returncode if process is not None else None,
        )

    def _emit_diagnostic(
        self,
        *,
        cleanup_status: _KdfCleanupStatus,
        cleanup_error: BaseException | None,
        primary_error: BaseException | None,
        exit_code: int | None = None,
    ) -> None:
        """Attempt one summary after cleanup; elapsed time excludes this emission."""
        if self._diagnostic_emitted:
            return
        self._diagnostic_emitted = True
        fields: dict[str, DiagnosticValue] = {
            name: self._phase_elapsed_ms[stage] for stage, name in _PHASE_FIELDS.items()
        }
        outcome = "completed"
        if self._failure_type is not None or cleanup_error is not None:
            outcome = "failed"
        elif cleanup_status != "completed":
            outcome = "unconfirmed"
        elif self._result_refused:
            outcome = "refused"
        fields.update(
            stage=self._failure_stage,
            error_type=self._failure_type,
            outcome=outcome,
            elapsed_seconds=max(0, time.monotonic_ns() - self._started_ns) / 1_000_000_000,
            cleanup_status=cleanup_status,
            cleanup_incomplete=cleanup_status != "completed",
            cleanup_error_type=type(cleanup_error).__name__ if cleanup_error is not None else None,
            exit_code=exit_code,
        )
        diagnostic_event(
            logger,
            "kdf_worker_lifecycle",
            fields=fields,
            level=logging.INFO if outcome == "completed" else logging.WARNING,
            primary_error=primary_error,
        )

    def _start(self) -> None:
        with ExitStack() as child_descriptors:
            request_read, request_write = os.pipe()
            child_descriptors.callback(_close_fd, request_read)
            self._request_fd = request_write
            result_read, result_write = os.pipe()
            child_descriptors.callback(_close_fd, result_write)
            self._result_fd = result_read
            if sys.platform != "win32":
                self._expected_posix_file_descriptors = (request_read, result_write)
            self._temporary_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._neutral_directory = tempfile.TemporaryDirectory(
                prefix="cadrumo-profile-kdf-",
                dir=self._temporary_root,
            )
            try:
                self._launch_attempted = True
                self._process, self._job = _launch_worker(
                    neutral_root=Path(self._neutral_directory.name),
                    request_read=request_read,
                    result_write=result_write,
                )
            except (OSError, subprocess.SubprocessError, ValueError):
                raise _supervision_refusal() from None

    def _write_request(self, payload: dict[str, object]) -> None:
        if self._request_fd is None:
            raise _supervision_refusal()
        encoded = _canonical_frame_bytes(payload)
        try:
            write_kdf_frame(self._request_fd, encoded, kind=KDF_FRAME_CONTROL)
        except OSError:
            raise _supervision_refusal() from None

    def _read_response_frame(self) -> tuple[int, bytes]:
        if self._result_fd is None:
            raise _supervision_refusal()
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("profile KDF worker deadline elapsed")
        result_queue: queue.Queue[tuple[int, bytes] | BaseException] = queue.Queue(maxsize=1)
        reader = threading.Thread(
            target=_read_kdf_frame_to_queue,
            args=(self._result_fd, result_queue),
            daemon=True,
        )
        reader.start()
        try:
            item = result_queue.get(timeout=remaining)
        except queue.Empty:
            raise TimeoutError("profile KDF worker did not respond before its deadline") from None
        if isinstance(item, BaseException):
            raise _supervision_refusal() from item
        return item

    def _verify_ready_attestation(self, frame: tuple[int, bytes]) -> None:
        kind, value = frame
        if kind != KDF_FRAME_CONTROL:
            raise _supervision_refusal()
        try:
            payload = _parse_ready_attestation(value)
        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            raise _supervision_refusal() from None
        process = self._process
        if process is None:
            raise _supervision_refusal()
        _verify_ready_worker(
            payload,
            neutral_directory=self._neutral_directory,
            expected_posix_file_descriptors=self._expected_posix_file_descriptors,
            process=process,
            job=self._job,
        )
        self._ready_payload = payload

    def _require_clean_worker_exit(self) -> None:
        process = self._process
        result_fd = self._result_fd
        if process is None or result_fd is None:
            raise _supervision_refusal()
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("profile KDF worker deadline elapsed")
        try:
            exit_code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise TimeoutError("profile KDF worker did not exit after its response") from None
        if exit_code != 0:
            raise _supervision_refusal()
        try:
            if os.read(result_fd, 1) != b"":
                raise _supervision_refusal()
        except OSError:
            raise _supervision_refusal() from None

    def _close(self, *, failed: bool) -> None:
        process = self._process
        job = self._job
        if process is not None:
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
        _close_fd(self._request_fd)
        _close_fd(self._result_fd)
        self._request_fd = None
        self._result_fd = None
        if process is None and job is not None:
            job.close()
            self._job = None
        self._cleanup_neutral_directory()

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


__all__ = ["_SupervisedKdfWorker"]
