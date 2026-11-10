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
from .....core.async_cleanup import AsyncResourceCleanupError, attach_async_cleanup_error
from .....core.config import Settings, load_settings
from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_path
from ..crypto.aes_gcm import KEY_SIZE
from .kdf_attestation import (
    parse_ready_attestation,
)
from .kdf_codec import (
    KDF_FAILED_FRAME,
    KDF_FRAME_CONTROL,
    KDF_FRAME_DEK,
    KDF_TRANSPORT_ENCODING,
    canonical_frame_bytes,
    close_fd,
    parse_calibration_frame,
    read_kdf_frame_to_queue,
    write_kdf_frame,
)
from .kdf_file_lease import wait_for_kdf_process_exit
from .kdf_operations import KdfOperation
from .kdf_process import (
    launch_worker,
)
from .kdf_refusals import resource_refusal, supervision_refusal
from .kdf_windows_job import WindowsJob
from .kdf_worker_cleanup import KdfWorkerCleanup
from .kdf_worker_identity import verify_ready_worker
from .kdf_worker_observation import KDF_WORKER_PHASE_FIELDS, KdfCleanupPart, KdfWorkerCleanupStatus, KdfWorkerStage
from .records import ProfileCustodyKdfParameters, ProfileCustodyWrappedDek

_NEVER_ATTESTED = "_kdf_worker_never_attested"


def kdf_worker_never_attested(error: BaseException) -> bool:
    """Whether ``error`` is a deadline that elapsed before the child attested, so no derivation began."""
    return error.__dict__.get(_NEVER_ATTESTED) is True


class SupervisedKdfWorker(KdfWorkerCleanup):
    """One process with a complete no-fallback lifecycle and bounded pipes."""

    def __init__(
        self,
        *,
        deadline: float,
        settings: Settings | None = None,
        absolute_deadline: bool = False,
        cancellation: ProfileProofCancellation | None = None,
    ) -> None:
        """Store the worker's deadline, deadline mode and cancellation and initialize its lifecycle state."""
        self._deadline = deadline
        self._absolute_deadline = absolute_deadline
        self._cancellation = cancellation
        self._readers: list[threading.Thread] = []
        self._cleanup_lock = threading.Lock()
        self._temporary_root = storage_path(StorageCategory.TEMPORARY_FILES, settings=settings or load_settings())
        self._process: subprocess.Popen[bytes] | None = None
        self._request_fd: int | None = None
        self._result_fd: int | None = None
        self._job: WindowsJob | None = None
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

    def __enter__(self) -> SupervisedKdfWorker:
        """Launch the worker and wait for its verified ready attestation, closing it again on any failure."""
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
                    ready = self.read_response_frame()
                    # A late wake-up can return a frame that arrived after the budget
                    # ended; the budget ended before the child attested, whatever the
                    # scheduler did, and no request has been sent yet.
                    if time.monotonic() >= self._deadline:
                        raise TimeoutError("profile KDF worker attested after its deadline")
                except TimeoutError as error:
                    error.__dict__[_NEVER_ATTESTED] = True
                    raise
            with self._phase("ready_attestation"):
                self.verify_ready_attestation(ready)
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
        """Close the worker, recording the caller's failure for the diagnostic."""
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
                raise resource_refusal()
            if kind != KDF_FRAME_CONTROL:
                raise supervision_refusal()
            try:
                derivation_ns = parse_calibration_frame(result)
            except (UnicodeDecodeError, ValueError):
                raise supervision_refusal() from None
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
        """Unwrap a wrapped profile DEK in the supervised worker, returning None on failure."""
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
                raise supervision_refusal()
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
        """Wrap a profile DEK under a secret in the supervised worker, returning None on failure."""
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
                raise supervision_refusal()
            try:
                payload = json.loads(result.decode(KDF_TRANSPORT_ENCODING, errors="strict"))
                if not isinstance(payload, dict):
                    raise ValueError("profile KDF wrapper response is invalid")
                record = cast("dict[str, object]", payload)
                if set(record) != {"wrapped_dek"}:
                    raise ValueError("profile KDF wrapper response is invalid")
                return ProfileCustodyWrappedDek.model_validate(record["wrapped_dek"])
            except (UnicodeDecodeError, ValidationError, ValueError, TypeError, json.JSONDecodeError):
                raise supervision_refusal() from None

    def _exchange(self, payload: dict[str, object]) -> tuple[int, bytes]:
        operation = payload.get("operation")
        self._operation = operation if isinstance(operation, KdfOperation) else None
        with self._phase("request_write"):
            self.write_request(payload)
        with self._phase("result_wait"):
            response = self.read_response_frame()
        with self._phase("clean_exit"):
            self.require_clean_worker_exit()
        return response

    def _close_with_diagnostic(self, *, failed: bool, primary_error: BaseException | None) -> None:
        process = self._process
        # Cleanup kills a running child, which on Windows also reports 0, so
        # whether a child that answered had exited by itself is read first.
        exited_before_cleanup = self._failure_stage == "clean_exit" and process is not None and process.poll() == 0
        try:
            with self._phase("cleanup"):
                self._close(failed=failed)
        except BaseException as cleanup_error:
            self._retain_pending_cleanup(cleanup_error)
            self._emit_diagnostic(
                cleanup_status="failed",
                cleanup_error=cleanup_error,
                primary_error=cleanup_error,
                exit_code=process.returncode if process is not None else None,
            )
            raise
        self._emit_diagnostic(
            cleanup_status=self._settled_cleanup_status(process),
            cleanup_error=None,
            primary_error=primary_error,
            exit_code=process.returncode if process is not None else None,
            exited_before_cleanup=exited_before_cleanup,
        )

    def _retain_pending_cleanup(self, cleanup_error: BaseException) -> None:
        """Attach this supervisor as the retry owner when a failed cleanup left work pending."""
        if self._cleanup_pending():
            retained = AsyncResourceCleanupError(
                (self,), (cleanup_error,), retry_task_name="profile-kdf-cleanup", close_attempts=1
            )
            attach_async_cleanup_error(cleanup_error, retained)

    def _settled_cleanup_status(self, process: subprocess.Popen[bytes] | None) -> KdfWorkerCleanupStatus:
        """Report whether a cleanup that raised nothing can confirm the worker is gone."""
        if process is None:
            return "unconfirmed" if self._launch_attempted or self._failure_stage == "start" else "completed"
        return "unconfirmed" if process.returncode is None else "completed"

    def _start(self) -> None:
        with ExitStack() as child_descriptors:
            request_read, request_write = os.pipe()
            child_descriptors.callback(close_fd, request_read)
            self._request_fd = request_write
            result_read, result_write = os.pipe()
            child_descriptors.callback(close_fd, result_write)
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
                self._process, self._job, self._environment_keys = launch_worker(
                    neutral_root=Path(self._neutral_directory.name),
                    request_read=request_read,
                    result_write=result_write,
                )
            except (OSError, subprocess.SubprocessError, ValueError):
                raise supervision_refusal() from None

    def write_request(self, payload: dict[str, object]) -> None:
        """Write the canonical request frame to the worker before its deadline unless cancelled."""
        if self._request_fd is None:
            raise supervision_refusal()
        encoded = canonical_frame_bytes(payload)
        if self._cancellation is not None:
            self._cancellation.raise_if_cancelled()
        if time.monotonic() >= self._deadline:
            raise TimeoutError("profile KDF worker timeout elapsed before request")
        try:
            write_kdf_frame(self._request_fd, encoded, kind=KDF_FRAME_CONTROL)
        except OSError:
            raise supervision_refusal() from None

    def read_response_frame(self) -> tuple[int, bytes]:
        """Read one worker frame before the deadline, raising on cancellation, timeout or a failed read."""
        if self._result_fd is None:
            raise supervision_refusal()
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("profile KDF worker deadline elapsed")
        # One producer frame and one cancellation cue can race; neither may
        # strand the retained pipe reader on a full queue during containment.
        result_queue: queue.Queue[tuple[int, bytes] | BaseException] = queue.Queue(maxsize=2)
        reader = threading.Thread(
            target=read_kdf_frame_to_queue,
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
            raise supervision_refusal() from item
        return item

    def verify_ready_attestation(self, frame: tuple[int, bytes]) -> None:
        """Verify the worker's ready attestation against the expected process environment and retain it."""
        kind, value = frame
        if kind != KDF_FRAME_CONTROL:
            raise supervision_refusal()
        try:
            payload = parse_ready_attestation(value)
        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            raise supervision_refusal() from None
        process = self._process
        if process is None:
            raise supervision_refusal()
        verify_ready_worker(
            payload,
            neutral_directory=self._neutral_directory,
            environment_keys=self._environment_keys,
            expected_posix_file_descriptors=self._expected_posix_file_descriptors,
            process=process,
            job=self._job,
        )
        self._ready_payload = payload

    def require_clean_worker_exit(self) -> None:
        """Wait for the worker to exit before the deadline and refuse anything but a clean exit."""
        process = self._process
        result_fd = self._result_fd
        if process is None or result_fd is None:
            raise supervision_refusal()
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
            raise supervision_refusal()
        try:
            if os.read(result_fd, 1) != b"":
                raise supervision_refusal()
        except OSError:
            raise supervision_refusal() from None


__all__ = ["SupervisedKdfWorker"]
