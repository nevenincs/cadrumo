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
from pathlib import Path
from typing import Final, cast

from pydantic import ValidationError

from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ..crypto import KEY_SIZE
from ._kdf_attestation import (
    parse_ready_attestation as _parse_ready_attestation,
)
from ._kdf_codec import (
    KDF_FRAME_CONTROL,
    KDF_FRAME_DEK,
    write_kdf_frame,
)
from ._kdf_codec import (
    canonical_frame_bytes as _canonical_frame_bytes,
)
from ._kdf_codec import (
    close_fd as _close_fd,
)
from ._kdf_codec import (
    read_kdf_frame_to_queue as _read_kdf_frame_to_queue,
)
from ._kdf_codec import (
    resource_refusal as _resource_refusal,
)
from ._kdf_codec import (
    supervision_refusal as _supervision_refusal,
)
from ._kdf_process import (
    launch_worker as _launch_worker,
)
from ._kdf_process import (
    terminate_process_tree as _terminate_process_tree,
)
from ._kdf_windows_job import _WindowsJob
from ._kdf_worker_identity import verify_ready_worker as _verify_ready_worker
from ._records import ProfileCustodyKdfParameters, ProfileCustodyWrappedDek

KDF_CALIBRATED_FRAME: Final = b"cadrumo-profile-kdf-calibrated-v1"
KDF_FAILED_FRAME: Final = b"cadrumo-profile-kdf-failed-v1"


class _SupervisedKdfWorker:
    """One process with a complete no-fallback lifecycle and bounded pipes."""

    def __init__(self, *, deadline: float) -> None:
        self._deadline = deadline
        self._process: subprocess.Popen[bytes] | None = None
        self._request_fd: int | None = None
        self._result_fd: int | None = None
        self._job: _WindowsJob | None = None
        self._neutral_directory: tempfile.TemporaryDirectory[str] | None = None
        self._ready_payload: dict[str, object] | None = None
        self._expected_posix_file_descriptors: tuple[int, int] | None = None

    def __enter__(self) -> _SupervisedKdfWorker:
        try:
            self._start()
            self._verify_ready_attestation(self._read_response_frame())
            return self
        except BaseException:
            self._close(failed=True)
            raise

    def __exit__(self, exc_type: object, _exc_value: object, _traceback: object) -> None:
        self._close(failed=exc_type is not None)

    def calibrate(self, parameters: ProfileCustodyKdfParameters) -> None:
        self._write_request(
            {
                "kdf": parameters.model_dump(mode="json"),
                "operation": "calibrate-v1",
                "version": 1,
            },
        )
        kind, result = self._read_response_frame()
        self._require_clean_worker_exit()
        if (kind, result) == (KDF_FRAME_CONTROL, KDF_CALIBRATED_FRAME):
            return
        if (kind, result) == (KDF_FRAME_CONTROL, KDF_FAILED_FRAME):
            raise _resource_refusal()
        raise _supervision_refusal()

    def unwrap(
        self,
        *,
        password: bytes,
        kdf: ProfileCustodyKdfParameters,
        wrapped_dek: ProfileCustodyWrappedDek,
        associated_data: bytes,
        recovery: bool = False,
    ) -> bytes | None:
        self._write_request(
            {
                "associated_data_b64": base64.b64encode(associated_data).decode("ascii"),
                "kdf": kdf.model_dump(mode="json"),
                "operation": "recovery-unwrap-v1" if recovery else "password-unwrap-v1",
                "password_b64": base64.b64encode(password).decode("ascii"),
                "version": 1,
                "wrapped_dek": wrapped_dek.model_dump(mode="json"),
            },
        )
        kind, result = self._read_response_frame()
        self._require_clean_worker_exit()
        if (kind, result) == (KDF_FRAME_CONTROL, KDF_FAILED_FRAME):
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
        self._write_request(
            {
                "associated_data_b64": base64.b64encode(associated_data).decode("ascii"),
                "dek_b64": base64.b64encode(dek).decode("ascii"),
                "kdf": kdf.model_dump(mode="json"),
                "operation": "recovery-wrap-v1" if recovery else "password-wrap-v1",
                "secret_b64": base64.b64encode(secret).decode("ascii"),
                "version": 1,
            },
        )
        kind, result = self._read_response_frame()
        self._require_clean_worker_exit()
        if (kind, result) == (KDF_FRAME_CONTROL, KDF_FAILED_FRAME):
            return None
        if kind != KDF_FRAME_CONTROL:
            raise _supervision_refusal()
        try:
            payload = json.loads(result.decode(_UTF_8_ENCODING, errors="strict"))
            if not isinstance(payload, dict):
                raise ValueError("profile KDF wrapper response is invalid")
            record = cast("dict[str, object]", payload)
            if set(record) != {"wrapped_dek"}:
                raise ValueError("profile KDF wrapper response is invalid")
            return ProfileCustodyWrappedDek.model_validate(record["wrapped_dek"])
        except (UnicodeDecodeError, ValidationError, ValueError, TypeError, json.JSONDecodeError):
            raise _supervision_refusal() from None

    def _start(self) -> None:
        request_read, request_write = os.pipe()
        result_read, result_write = os.pipe()
        if sys.platform != "win32":
            self._expected_posix_file_descriptors = (request_read, result_write)
        self._request_fd = request_write
        self._result_fd = result_read
        self._neutral_directory = tempfile.TemporaryDirectory(prefix="cadrumo-profile-kdf-")
        try:
            self._process, self._job = _launch_worker(
                neutral_root=Path(self._neutral_directory.name),
                request_read=request_read,
                result_write=result_write,
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            os.close(request_write)
            os.close(result_read)
            raise _supervision_refusal() from None
        finally:
            _close_fd(request_read)
            _close_fd(result_write)

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
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise TimeoutError("profile KDF worker did not exit after its response") from None
        try:
            if os.read(result_fd, 1) != b"":
                raise _supervision_refusal()
        except OSError:
            raise _supervision_refusal() from None

    def _close(self, *, failed: bool) -> None:
        process = self._process
        job = self._job
        self._process = None
        self._job = None
        _close_fd(self._request_fd)
        _close_fd(self._result_fd)
        self._request_fd = None
        self._result_fd = None
        if process is None:
            if job is not None:
                job.close()
            self._cleanup_neutral_directory()
            return
        if failed or process.poll() is None:
            _terminate_process_tree(process, job)
        elif job is not None:
            job.close()
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            _terminate_process_tree(process, job)
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


__all__ = [
    "KDF_CALIBRATED_FRAME",
    "KDF_FAILED_FRAME",
    "_SupervisedKdfWorker",
]
