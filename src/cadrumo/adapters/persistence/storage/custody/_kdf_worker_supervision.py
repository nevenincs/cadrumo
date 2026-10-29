"""Process supervision boundary for profile-custody KDF work."""

from __future__ import annotations

import base64
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import ExitStack, nullcontext, suppress
from pathlib import Path
from typing import Literal, cast

from pydantic import ValidationError

from .....application.user_profile.proof_cancellation import ProfileProofCancellation, ProfileProofCancelledError
from .....core.config import Settings, load_settings
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
from ._kdf_file_lease import wait_for_kdf_process_exit
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
from ._kdf_worker_observation import KDF_WORKER_PHASE_FIELDS, KdfCleanupPart, KdfWorkerObservation, KdfWorkerStage
from .records import ProfileCustodyKdfParameters, ProfileCustodyWrappedDek

_NEVER_ATTESTED = "_kdf_worker_never_attested"


def kdf_worker_never_attested(error: BaseException) -> bool:
    """Whether ``error`` is a deadline that elapsed before the child attested, so no derivation began."""
    return error.__dict__.get(_NEVER_ATTESTED) is True


class _SupervisedKdfWorker(KdfWorkerObservation):
    """One process with a complete no-fallback lifecycle and bounded pipes."""

    def __init__(
        self,
        *,
        deadline: float,
        settings: Settings | None = None,
        absolute_deadline: bool = False,
        cancellation: ProfileProofCancellation | None = None,
    ) -> None:
        self._deadline = deadline
        self._absolute_deadline = absolute_deadline
        self._cancellation = cancellation
        self._readers: list[threading.Thread] = []
        self._temporary_root = (settings or load_settings()).cadrumo_temp_dir
        self._process: subprocess.Popen[bytes] | None = None
        self._request_fd: int | None = None
        self._result_fd: int | None = None
        self._job: _WindowsJob | None = None
        self._neutral_directory: tempfile.TemporaryDirectory[str] | None = None
        self._ready_payload: dict[str, object] | None = None
        self._environment_keys: frozenset[str] | None = None
        self._expected_posix_file_descriptors: tuple[int, int] | None = None
        self._started_ns = 0
        self._adopted_ns: int | None = None
        self._phase_elapsed_ms: dict[KdfWorkerStage, float | None] = dict.fromkeys(KDF_WORKER_PHASE_FIELDS)
        self._cleanup_elapsed_ms: dict[KdfCleanupPart, float | None] = dict.fromkeys(("process", "pipes", "directory"))
        self._failure_stage: KdfWorkerStage | Literal["caller"] | None = None
        self._failure_type: str | None = None
        self._launch_attempted = False
        self._result_refused = False
        self._diagnostic_emitted = False
        self._operation: KdfOperation | None = None

    def __enter__(self) -> _SupervisedKdfWorker:
        self._started_ns = time.monotonic_ns()
        self._adopted_ns = None
        self._phase_elapsed_ms = dict.fromkeys(KDF_WORKER_PHASE_FIELDS)
        self._cleanup_elapsed_ms = dict.fromkeys(("process", "pipes", "directory"))
        self._failure_stage = None
        self._failure_type = None
        self._launch_attempted = False
        self._result_refused = False
        self._diagnostic_emitted = False
        try:
            if self._cancellation is not None:
                self._cancellation.raise_if_cancelled()
            launch_started = time.monotonic()
            with self._phase("start"):
                self._start()
            if self._cancellation is not None:
                self._cancellation.raise_if_cancelled()
            # Process creation is one uncancellable OS call that can block for
            # tens of seconds on a saturated host, before any child exists to
            # stall. The deadline abandons a stalled child, so it starts once
            # the child does instead of refusing one that has not run yet.
            if not self._absolute_deadline:
                self._deadline += time.monotonic() - launch_started
            with self._phase("ready_wait"):
                try:
                    ready = self._read_response_frame()
                    # A late wake-up can return a frame that arrived after the budget
                    # ended; the budget ended before the child attested, whatever the
                    # scheduler did, and no request has been sent yet.
                    if time.monotonic() >= self._deadline:
                        raise TimeoutError("profile KDF worker attested after its deadline")
                except TimeoutError as error:
                    error.__dict__[_NEVER_ATTESTED] = True
                    raise
            with self._phase("ready_attestation"):
                self._verify_ready_attestation(ready)
                if self._absolute_deadline and time.monotonic() >= self._deadline:
                    raise TimeoutError("profile KDF worker timeout elapsed during attestation")
            return self
        except BaseException as error:
            self._close_with_diagnostic(failed=True, primary_error=error)
            raise

    def adopt(self, *, deadline: float, cancellation: ProfileProofCancellation | None = None) -> bool:
        """Hand this attested, still idle child to one operation under that operation's deadline.

        A child launched ahead of need has proved its limits but received no
        request. It is handed over only while its process is still running
        inside its containment; otherwise the caller discards it and launches
        a fresh one.
        """
        process = self._process
        if self._ready_payload is None or process is None or process.poll() is not None:
            return False
        if sys.platform == "win32" and (self._job is None or not self._job.contains(process)):
            return False
        self._deadline = deadline
        self._cancellation = cancellation
        self._adopted_ns = time.monotonic_ns()
        return True

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

    def _exchange(self, payload: dict[str, object]) -> tuple[int, bytes]:
        operation = payload.get("operation")
        self._operation = operation if isinstance(operation, KdfOperation) else None
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
                self._process, self._job, self._environment_keys = _launch_worker(
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
        if self._cancellation is not None:
            self._cancellation.raise_if_cancelled()
        if time.monotonic() >= self._deadline:
            raise TimeoutError("profile KDF worker timeout elapsed before request")
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
        # One producer frame and one cancellation cue can race; neither may
        # strand the retained pipe reader on a full queue during containment.
        result_queue: queue.Queue[tuple[int, bytes] | BaseException] = queue.Queue(maxsize=2)
        reader = threading.Thread(
            target=_read_kdf_frame_to_queue,
            args=(self._result_fd, result_queue),
            daemon=True,
        )
        self._readers.append(reader)
        reader.start()

        def cancelled() -> None:
            with suppress(queue.Full):
                result_queue.put_nowait(ProfileProofCancelledError("profile proof attempt cancelled"))

        with self._cancellation.watch(cancelled) if self._cancellation is not None else nullcontext():
            if self._cancellation is not None:
                self._cancellation.raise_if_cancelled()
            try:
                item = result_queue.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError("profile KDF worker did not respond before its deadline") from None
            if self._cancellation is not None:
                self._cancellation.raise_if_cancelled()
        if isinstance(item, ProfileProofCancelledError):
            raise item
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
            environment_keys=self._environment_keys,
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
        if self._cancellation is not None:
            exit_code = wait_for_kdf_process_exit(process, deadline=self._deadline, cancellation=self._cancellation)
        else:
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


__all__ = ["_SupervisedKdfWorker"]
