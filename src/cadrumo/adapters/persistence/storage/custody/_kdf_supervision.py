"""Supervised Argon2id work for current-format profile custody."""

from __future__ import annotations

import base64
import ctypes
import json
import os
import queue
import secrets
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Generator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import TYPE_CHECKING, Any, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError, field_validator, model_validator

from .....core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core import StorageCategory, storage_path
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ..crypto import EncryptedBlob, decrypt_record
from ._errors import (
    ProfileCustodyPasswordError,
    ProfileCustodyRecordError,
    ProfileCustodyRefusal,
    ProfileCustodyRefusedError,
)
from ._records import (
    PROFILE_CUSTODY_KDF_ITERATIONS,
    PROFILE_CUSTODY_KDF_MEMORY_MIB,
    PROFILE_CUSTODY_KDF_PARALLELISM,
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    validate_profile_password,
)

if TYPE_CHECKING:
    from .....core.config import Settings

PROFILE_CUSTODY_KDF_CALIBRATION_VERSION: Final = 1
PROFILE_CUSTODY_KDF_SAMPLE_COUNT: Final = 5
PROFILE_CUSTODY_KDF_WARMUP_COUNT: Final = 1
PROFILE_CUSTODY_KDF_SAMPLE_DEADLINE_SECONDS: Final = 2.0
PROFILE_CUSTODY_KDF_TOTAL_DEADLINE_SECONDS: Final = 15.0
PROFILE_CUSTODY_KDF_TARGET_MIN_SECONDS: Final = 0.250
PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS: Final = 0.500
PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES: Final = 1024 * 1024 * 1024
PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS: Final = 15
PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES: Final = 2

KDF_FRAME_MAGIC: Final = b"CKDF"
KDF_FRAME_VERSION: Final = 1
KDF_FRAME_CONTROL: Final = 1
KDF_FRAME_DEK: Final = 2
KDF_FRAME_HEADER: Final = struct.Struct("!4sBBHI")
_FRAME_MAX_BYTES: Final = 8 * 1024
KDF_CALIBRATED_FRAME: Final = b"cadrumo-profile-kdf-calibrated-v1"
KDF_FAILED_FRAME: Final = b"cadrumo-profile-kdf-failed-v1"
_MEBIBYTE: Final = 1024 * 1024
_KDF_LEASE_FILENAME: Final = "profile-kdf.v1.lock"
_KDF_THREAD_LEASE: Final = threading.BoundedSemaphore(value=1)
_PROFILE_CUSTODY_DATA_FORMAT_VERSION: Final = 1
_PROFILE_CUSTODY_SENTINEL_PURPOSE: Final = "profile-dek-sentinel/v1"
_PROFILE_CUSTODY_SENTINEL_PROOF: Final = "profile-dek-sentinel-proof/v1"
_AEAD_NONCE_BYTES: Final = 12
_AEAD_TAG_BYTES: Final = 16
_WIN32_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: Final = 9
_WIN32_JOB_OBJECT_BASIC_PROCESS_ID_LIST: Final = 3
_WIN32_JOB_OBJECT_LIMIT_PROCESS_TIME: Final = 0x00000002
_WIN32_JOB_OBJECT_LIMIT_ACTIVE_PROCESS: Final = 0x00000008
_WIN32_JOB_OBJECT_LIMIT_PROCESS_MEMORY: Final = 0x00000100
_WIN32_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: Final = 0x00002000
_WIN32_PROCESS_SET_QUOTA: Final = 0x0100
_WIN32_PROCESS_TERMINATE: Final = 0x0001
_WIN32_PROCESS_QUERY_LIMITED_INFORMATION: Final = 0x1000


@dataclass(frozen=True, slots=True)
class ProfileCustodyKdfResources:
    """Explicit local resources used to decide whether one grid point is safe."""

    available_memory_bytes: int
    cpu_count: int

    def __post_init__(self) -> None:
        if self.available_memory_bytes < 1 or self.cpu_count < 1:
            raise ValueError("profile KDF resources must be positive")


@dataclass(frozen=True, slots=True)
class ProfileCustodyKdfCalibration:
    """Versioned result of deterministic finite-grid enrollment calibration."""

    version: Literal[1]
    parameters: ProfileCustodyKdfParameters
    source: Literal["measured", "fallback"]
    median_seconds: float | None


@dataclass(frozen=True, slots=True)
class ProfileCustodyUnlock:
    """A DEK accepted only after a parent-owned sentinel proof."""

    profile_id: UUID
    envelope_digest: str
    kdf: ProfileCustodyKdfParameters
    dek: bytes


@dataclass(frozen=True, slots=True)
class ProfileCustodyKdfRatchetProposal:
    """A post-success proposal for the custody transaction owner to publish."""

    profile_id: UUID
    expected_envelope_digest: str
    current: ProfileCustodyKdfParameters
    proposed: ProfileCustodyKdfParameters


def profile_custody_sentinel_aad(envelope: ProfileCustodyEnvelope) -> bytes:
    """Derive the only AAD accepted for a current-format DEK sentinel."""
    return profile_custody_sentinel_aad_for(
        profile_id=envelope.profile_id,
        dek_epoch=envelope.dek_epoch,
    )


def profile_custody_sentinel_aad_for(*, profile_id: UUID, dek_epoch: str) -> bytes:
    """Derive sentinel AAD from the immutable custody identity alone."""
    return _canonical_json_bytes(
        {
            "data_format_version": _PROFILE_CUSTODY_DATA_FORMAT_VERSION,
            "dek_epoch": dek_epoch,
            "product": "cadrumo",
            "profile_id": str(profile_id),
            "purpose": _PROFILE_CUSTODY_SENTINEL_PURPOSE,
            "schema_version": 1,
        },
    )


def profile_custody_sentinel_plaintext(
    *,
    profile_id: UUID,
    dek_epoch: str,
    data_format_version: Literal[1] = 1,
) -> bytes:
    """Derive the non-caller-selectable sentinel plaintext for one DEK epoch."""
    return _canonical_json_bytes(
        {
            "data_format_version": data_format_version,
            "dek_epoch": dek_epoch,
            "product": "cadrumo",
            "profile_id": str(profile_id),
            "proof": _PROFILE_CUSTODY_SENTINEL_PROOF,
            "purpose": _PROFILE_CUSTODY_SENTINEL_PURPOSE,
            "schema_version": 1,
        },
    )


class ProfileCustodySentinelRecord(BaseModel):
    """Strict proof input consumed before a custody transaction can publish it."""

    model_config = _STRICT_FROZEN

    schema_version: Literal[1]
    product: Literal["cadrumo"]
    profile_id: UUID
    dek_epoch: str
    data_format_version: Literal[1]
    purpose: Literal["profile-dek-sentinel/v1"]
    nonce_b64: str
    ciphertext_b64: str
    tag_b64: str

    @field_validator("dek_epoch")
    @classmethod
    def _validate_epoch(cls, value: str) -> str:
        _decode_canonical_b64(value, field_name="dek_epoch", expected_bytes=16)
        return value

    @field_validator("nonce_b64")
    @classmethod
    def _validate_nonce(cls, value: str) -> str:
        _decode_canonical_b64(value, field_name="nonce_b64", expected_bytes=_AEAD_NONCE_BYTES)
        return value

    @field_validator("tag_b64")
    @classmethod
    def _validate_tag(cls, value: str) -> str:
        _decode_canonical_b64(value, field_name="tag_b64", expected_bytes=_AEAD_TAG_BYTES)
        return value

    @field_validator("ciphertext_b64")
    @classmethod
    def _validate_ciphertext(cls, value: str) -> str:
        _decode_canonical_b64(value, field_name="ciphertext_b64", expected_bytes=None)
        return value

    @model_validator(mode="after")
    def _verify_exact_proof_shape(self) -> ProfileCustodySentinelRecord:
        ciphertext = _decode_canonical_b64(
            self.ciphertext_b64,
            field_name="ciphertext_b64",
            expected_bytes=None,
        )
        expected = profile_custody_sentinel_plaintext(
            profile_id=self.profile_id,
            dek_epoch=self.dek_epoch,
            data_format_version=self.data_format_version,
        )
        if len(ciphertext) != len(expected):
            raise ValueError("sentinel ciphertext must have the canonical proof length")
        return self

    def encrypted_blob(self) -> EncryptedBlob:
        """Return the format-neutral AEAD representation after strict validation."""
        return EncryptedBlob(
            nonce=_decode_canonical_b64(self.nonce_b64, field_name="nonce_b64", expected_bytes=_AEAD_NONCE_BYTES),
            ciphertext=(
                _decode_canonical_b64(self.ciphertext_b64, field_name="ciphertext_b64", expected_bytes=None)
                + _decode_canonical_b64(self.tag_b64, field_name="tag_b64", expected_bytes=_AEAD_TAG_BYTES)
            ),
        )

    def canonical_json_bytes(self) -> bytes:
        """Return the unique strict transport representation for a custody transaction."""
        return _canonical_json_bytes(cast(dict[str, object], self.model_dump(mode="json")))


def parse_profile_custody_sentinel_record(value: bytes) -> ProfileCustodySentinelRecord:
    """Parse one canonical sentinel record without creating or publishing it."""
    try:
        decoded = value.decode(_UTF_8_ENCODING, errors="strict")
        parsed = json.loads(decoded, object_pairs_hook=_reject_duplicate_members, parse_constant=_reject_json_constant)
        if not isinstance(parsed, dict):
            raise ValueError("profile custody sentinel must be an object")
        payload = cast("dict[str, object]", parsed)
        record = ProfileCustodySentinelRecord.model_validate_json(_canonical_json_bytes(payload))
        if record.canonical_json_bytes() != value:
            raise ValueError("profile custody sentinel is not canonical")
        return record
    except (UnicodeDecodeError, ValidationError, ValueError, TypeError) as exc:
        raise ProfileCustodyRecordError("profile custody sentinel is not a valid current-format record") from exc


def kdf_worker_ready_attestation() -> bytes:
    """Build a child attestation of the limits it can observe before any secret arrives."""
    platform = "win32" if sys.platform == "win32" else "posix"
    limits: dict[str, int] = {
        "cpu_seconds": PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,
        "memory_bytes": PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,
        "max_processes": PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES,
    }
    if platform == "posix":
        import resource

        resource_module = cast(Any, resource)
        expected = {
            "cpu_seconds": resource_module.getrlimit(resource_module.RLIMIT_CPU)[0],
            "memory_bytes": resource_module.getrlimit(resource_module.RLIMIT_AS)[0],
            "max_open_files": resource_module.getrlimit(resource_module.RLIMIT_NOFILE)[0],
        }
        if expected != {
            "cpu_seconds": PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,
            "memory_bytes": PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,
            "max_open_files": 16,
        }:
            raise ValueError("profile KDF worker limits are not active")
        limits["max_open_files"] = 16
    payload: dict[str, object] = {
        "cwd": os.getcwd(),
        "environment_keys": sorted(os.environ),
        "limits": limits,
        "platform": platform,
        "protocol": "profile-kdf-ready/v1",
        "transport": "framed-anonymous-pipe/v1",
    }
    if platform == "posix":
        payload["open_file_descriptors"] = _open_posix_file_descriptors()
    return _canonical_json_bytes(payload)


def _open_posix_file_descriptors() -> list[int]:
    return [descriptor for descriptor in range(16) if _is_open_file_descriptor(descriptor)]


def _is_open_file_descriptor(descriptor: int) -> bool:
    try:
        os.fstat(descriptor)
    except OSError:
        return False
    return True


def profile_password_wrap_aad(
    *,
    profile_id: UUID,
    password_generation: int,
    dek_epoch: str,
    kdf: ProfileCustodyKdfParameters,
) -> bytes:
    """Build the canonical password-wrap AAD for one current custody envelope."""
    payload = {
        "dek_epoch": dek_epoch,
        "kdf_digest": _canonical_digest(kdf.model_dump(mode="json")),
        "key_schedule": "profile-password-dek-wrap/v1",
        "password_encoding": _UTF_8_ENCODING,
        "password_generation": password_generation,
        "product": "cadrumo",
        "profile_id": str(profile_id),
        "purpose": "profile-password-dek-wrap/v1",
        "schema_version": 1,
    }
    return _canonical_json_bytes(payload)


def profile_kdf_grid(*, salt: bytes) -> tuple[ProfileCustodyKdfParameters, ...]:
    """Return the complete deterministic Argon2id v1 grid, strongest first."""
    if len(salt) != 16:
        raise ValueError("profile KDF calibration salt must contain exactly 16 bytes")
    encoded_salt = base64.b64encode(salt).decode("ascii")
    return tuple(
        ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=cast("Literal[19, 32, 64, 128, 256]", memory_mib),
            iterations=cast("Literal[2, 3, 4, 6, 8, 10]", iterations),
            parallelism=cast("Literal[1, 2, 4]", parallelism),
            salt_b64=encoded_salt,
            output_bytes=32,
        )
        for memory_mib in sorted(PROFILE_CUSTODY_KDF_MEMORY_MIB, reverse=True)
        for iterations in sorted(PROFILE_CUSTODY_KDF_ITERATIONS, reverse=True)
        for parallelism in sorted(PROFILE_CUSTODY_KDF_PARALLELISM, reverse=True)
    )


def fixed_profile_kdf_fallback(*, salt: bytes) -> ProfileCustodyKdfParameters:
    """Return the sole eligible fallback point without weakening its parameters."""
    return ProfileCustodyKdfParameters(
        algorithm="argon2id",
        version=19,
        memory_mib=64,
        iterations=3,
        parallelism=1,
        salt_b64=base64.b64encode(salt).decode("ascii"),
        output_bytes=32,
    )


def profile_kdf_resources() -> ProfileCustodyKdfResources:
    """Read the portable resources that bound a local KDF worker."""
    cpu_count = os.cpu_count()
    if cpu_count is None or cpu_count < 1:
        raise _resource_refusal()
    try:
        if sys.platform == "win32":
            available_memory = _windows_available_memory_bytes()
        else:
            page_size = os.sysconf("SC_PAGE_SIZE")
            available_pages = os.sysconf("SC_AVPHYS_PAGES")
            available_memory = page_size * available_pages
    except (AttributeError, OSError, ValueError):
        raise _resource_refusal() from None
    if available_memory < 1:
        raise _resource_refusal()
    return ProfileCustodyKdfResources(available_memory_bytes=available_memory, cpu_count=cpu_count)


def profile_kdf_is_eligible(
    parameters: ProfileCustodyKdfParameters,
    *,
    resources: ProfileCustodyKdfResources,
) -> bool:
    """Return whether one finite-grid point fits the explicit local envelope."""
    required_memory = parameters.memory_mib * _MEBIBYTE
    return (
        parameters.parallelism <= resources.cpu_count
        and required_memory <= PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES
        and required_memory + _MEBIBYTE * 64 <= resources.available_memory_bytes
    )


def calibrate_profile_kdf(*, salt: bytes, settings: Settings | None = None) -> ProfileCustodyKdfCalibration:
    """Calibrate a fresh profile KDF with bounded real child-process samples."""
    resources = profile_kdf_resources()
    fallback = fixed_profile_kdf_fallback(salt=salt)
    if not profile_kdf_is_eligible(fallback, resources=resources):
        raise _resource_refusal()

    deadline = time.monotonic() + PROFILE_CUSTODY_KDF_TOTAL_DEADLINE_SECONDS
    completed_measurements: list[tuple[ProfileCustodyKdfParameters, tuple[float, ...] | None]] = []
    for parameters in profile_kdf_grid(salt=salt):
        if not profile_kdf_is_eligible(parameters, resources=resources):
            continue
        try:
            _measure_profile_kdf(parameters, deadline=deadline, settings=settings)
            samples: list[float] = []
            for _ in range(PROFILE_CUSTODY_KDF_SAMPLE_COUNT):
                samples.append(_measure_profile_kdf(parameters, deadline=deadline, settings=settings))
        except TimeoutError:
            if time.monotonic() >= deadline:
                break
            completed_measurements.append((parameters, None))
            continue
        except ProfileCustodyRefusedError as exc:
            if exc.refusal is ProfileCustodyRefusal.KDF_RESOURCE_LIMIT:
                continue
            raise
        completed_measurements.append((parameters, tuple(samples)))
        selected = _select_profile_kdf_calibration(completed_measurements)
        if selected is not None:
            return selected
    return ProfileCustodyKdfCalibration(
        version=PROFILE_CUSTODY_KDF_CALIBRATION_VERSION,
        parameters=fallback,
        source="fallback",
        median_seconds=None,
    )


def unlock_profile_custody(
    envelope: ProfileCustodyEnvelope,
    password: str,
    *,
    sentinel: ProfileCustodySentinelRecord,
    settings: Settings | None = None,
    timeout_seconds: float = PROFILE_CUSTODY_KDF_TOTAL_DEADLINE_SECONDS,
) -> ProfileCustodyUnlock:
    """Return a DEK only after supervised unwrap and parent sentinel proof."""
    dek = unlock_profile_custody_material(
        profile_id=envelope.profile_id,
        dek_epoch=envelope.dek_epoch,
        kdf=envelope.kdf,
        wrapped_dek=envelope.wrapped_dek,
        secret=password,
        associated_data=profile_password_wrap_aad(
            profile_id=envelope.profile_id,
            password_generation=envelope.password_generation,
            dek_epoch=envelope.dek_epoch,
            kdf=envelope.kdf,
        ),
        sentinel=sentinel,
        settings=settings,
        timeout_seconds=timeout_seconds,
    )
    return ProfileCustodyUnlock(
        profile_id=envelope.profile_id,
        envelope_digest=envelope.self_digest,
        kdf=envelope.kdf,
        dek=dek,
    )


def unlock_profile_custody_material(
    *,
    profile_id: UUID,
    dek_epoch: str,
    kdf: ProfileCustodyKdfParameters,
    wrapped_dek: ProfileCustodyWrappedDek,
    secret: str,
    associated_data: bytes,
    sentinel: ProfileCustodySentinelRecord,
    settings: Settings | None = None,
    timeout_seconds: float = PROFILE_CUSTODY_KDF_TOTAL_DEADLINE_SECONDS,
) -> bytes:
    """Supervise one current-format wrapper unwrap and prove its immutable DEK.

    The caller owns one closed wrapper AAD domain.  This adapter owns password
    representation, process supervision, and the non-optional capsule proof.
    It never returns an unproved key.
    """
    if timeout_seconds <= 0:
        raise ValueError("profile KDF timeout must be positive")
    password_bytes = validate_profile_password(secret).encode(_UTF_8_ENCODING, errors="strict")
    deadline = time.monotonic() + timeout_seconds
    try:
        with (
            profile_kdf_lease(settings=settings, deadline=deadline),
            _SupervisedKdfWorker(deadline=deadline) as worker,
        ):
            dek = worker.unwrap(
                password=password_bytes,
                kdf=kdf,
                wrapped_dek=wrapped_dek,
                associated_data=associated_data,
            )
    except TimeoutError:
        raise _resource_refusal() from None
    if dek is None:
        raise ProfileCustodyPasswordError("profile password did not authenticate the custody envelope")
    verify_profile_custody_sentinel(
        dek=dek,
        profile_id=profile_id,
        dek_epoch=dek_epoch,
        sentinel=sentinel,
    )
    return dek


def wrap_profile_custody_material(
    *,
    secret: str,
    dek: bytes,
    kdf: ProfileCustodyKdfParameters,
    associated_data: bytes,
    settings: Settings | None = None,
    timeout_seconds: float = PROFILE_CUSTODY_KDF_TOTAL_DEADLINE_SECONDS,
) -> ProfileCustodyWrappedDek:
    """Build one wrapper only inside the existing supervised KDF boundary."""
    if timeout_seconds <= 0:
        raise ValueError("profile KDF timeout must be positive")
    if len(dek) != 32:
        raise ProfileCustodyRecordError("profile custody DEK must contain exactly 32 bytes")
    secret_bytes = validate_profile_password(secret).encode(_UTF_8_ENCODING, errors="strict")
    deadline = time.monotonic() + timeout_seconds
    try:
        with (
            profile_kdf_lease(settings=settings, deadline=deadline),
            _SupervisedKdfWorker(deadline=deadline) as worker,
        ):
            wrapped_dek = worker.wrap(
                secret=secret_bytes,
                dek=dek,
                kdf=kdf,
                associated_data=associated_data,
            )
    except TimeoutError:
        raise _resource_refusal() from None
    if wrapped_dek is None:
        raise ProfileCustodyRecordError("supervised profile custody wrapper creation failed")
    return wrapped_dek


def propose_profile_kdf_ratchet(
    unlock: ProfileCustodyUnlock,
    calibration: ProfileCustodyKdfCalibration,
) -> ProfileCustodyKdfRatchetProposal | None:
    """Propose, but never publish, a strictly stronger post-proof KDF record."""
    if _kdf_strength(calibration.parameters) <= _kdf_strength(unlock.kdf):
        return None
    return ProfileCustodyKdfRatchetProposal(
        profile_id=unlock.profile_id,
        expected_envelope_digest=unlock.envelope_digest,
        current=unlock.kdf,
        proposed=calibration.parameters,
    )


def _measure_profile_kdf(
    parameters: ProfileCustodyKdfParameters,
    *,
    deadline: float,
    settings: Settings | None,
) -> float:
    remaining = min(PROFILE_CUSTODY_KDF_SAMPLE_DEADLINE_SECONDS, deadline - time.monotonic())
    if remaining <= 0:
        raise TimeoutError("profile KDF calibration total deadline elapsed")
    started = time.monotonic()
    with (
        profile_kdf_lease(settings=settings, deadline=deadline),
        _SupervisedKdfWorker(
            deadline=time.monotonic() + remaining,
        ) as worker,
    ):
        worker.calibrate(parameters)
    elapsed = time.monotonic() - started
    if elapsed > PROFILE_CUSTODY_KDF_SAMPLE_DEADLINE_SECONDS:
        raise TimeoutError("profile KDF calibration sample deadline elapsed")
    return elapsed


@contextmanager
def profile_kdf_lease(*, deadline: float, settings: Settings | None = None) -> Generator[None]:
    """Acquire the one OS-released KDF permit for a canonical installation root.

    The descriptor stays open for the operation, so an abnormal owner death
    releases its permit at the operating-system boundary instead of leaving a
    process-local or persistent ownership record behind.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0 or not _KDF_THREAD_LEASE.acquire(timeout=remaining):
        raise _resource_refusal()
    try:
        try:
            root = storage_path(StorageCategory.BUCKETS, settings=settings).parent.resolve(strict=True)
            if not root.is_dir():
                raise NotADirectoryError(root)
            lock_path = root / _KDF_LEASE_FILENAME
            descriptor = os.open(
                lock_path,
                os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0),
                0o600,
            )
        except OSError:
            raise _supervision_refusal() from None
        try:
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"\x00")
            _acquire_kdf_file_lease(descriptor, deadline=deadline)
            try:
                yield
            finally:
                _release_kdf_file_lease(descriptor)
        finally:
            _close_fd(descriptor)
    finally:
        _KDF_THREAD_LEASE.release()


def _select_profile_kdf_calibration(
    measurements: list[tuple[ProfileCustodyKdfParameters, tuple[float, ...] | None]],
) -> ProfileCustodyKdfCalibration | None:
    """Choose the first complete target-range median in deterministic grid order."""
    for parameters, samples in measurements:
        if samples is None:
            continue
        if len(samples) != PROFILE_CUSTODY_KDF_SAMPLE_COUNT or any(sample < 0 for sample in samples):
            raise ValueError("profile KDF measurements must contain five non-negative samples")
        observed_median = median(samples)
        if PROFILE_CUSTODY_KDF_TARGET_MIN_SECONDS <= observed_median <= PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS:
            return ProfileCustodyKdfCalibration(
                version=PROFILE_CUSTODY_KDF_CALIBRATION_VERSION,
                parameters=parameters,
                source="measured",
                median_seconds=observed_median,
            )
    return None


def _acquire_kdf_file_lease(descriptor: int, *, deadline: float) -> None:
    while True:
        try:
            if sys.platform == "win32":
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _resource_refusal() from None
            time.sleep(min(0.02, remaining))


def _release_kdf_file_lease(descriptor: int) -> None:
    try:
        if sys.platform == "win32":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_UN)
    except OSError:
        raise _supervision_refusal() from None


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

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
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
    ) -> bytes | None:
        self._write_request(
            {
                "associated_data_b64": base64.b64encode(associated_data).decode("ascii"),
                "kdf": kdf.model_dump(mode="json"),
                "operation": "unwrap-v1",
                "password_b64": base64.b64encode(password).decode("ascii"),
                "version": 1,
                "wrapped_dek": wrapped_dek.model_dump(mode="json"),
            },
        )
        kind, result = self._read_response_frame()
        self._require_clean_worker_exit()
        if (kind, result) == (KDF_FRAME_CONTROL, KDF_FAILED_FRAME):
            return None
        if kind != KDF_FRAME_DEK or len(result) != 32:
            raise _supervision_refusal()
        return result

    def wrap(
        self,
        *,
        secret: bytes,
        dek: bytes,
        kdf: ProfileCustodyKdfParameters,
        associated_data: bytes,
    ) -> ProfileCustodyWrappedDek | None:
        self._write_request(
            {
                "associated_data_b64": base64.b64encode(associated_data).decode("ascii"),
                "dek_b64": base64.b64encode(dek).decode("ascii"),
                "kdf": kdf.model_dump(mode="json"),
                "operation": "wrap-v1",
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
        encoded = _canonical_json_bytes(payload)
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
            parsed = json.loads(value.decode(_UTF_8_ENCODING, errors="strict"))
            if not isinstance(parsed, dict):
                raise ValueError("profile KDF ready payload is invalid")
            payload = cast("dict[str, object]", parsed)
            expected_platform = "win32" if sys.platform == "win32" else "posix"
            expected_fields = {"cwd", "environment_keys", "limits", "platform", "protocol", "transport"}
            if expected_platform == "posix":
                expected_fields.add("open_file_descriptors")
            if set(payload) != expected_fields:
                raise ValueError("profile KDF ready fields are invalid")
            expected_limits: dict[str, int] = {
                "cpu_seconds": PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,
                "memory_bytes": PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,
                "max_processes": PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES,
            }
            if expected_platform == "posix":
                expected_limits["max_open_files"] = 16
            if (
                payload["platform"] != expected_platform
                or payload["protocol"] != "profile-kdf-ready/v1"
                or payload["transport"] != "framed-anonymous-pipe/v1"
                or payload["limits"] != expected_limits
            ):
                raise ValueError("profile KDF ready attestation is invalid")
            if self._neutral_directory is None:
                raise ValueError("profile KDF neutral directory is unavailable")
            neutral_root = Path(self._neutral_directory.name).resolve()
            if payload["cwd"] != str(neutral_root):
                raise ValueError("profile KDF worker cwd is not neutral")
            if payload["environment_keys"] != sorted(_worker_environment(neutral_root=neutral_root)):
                raise ValueError("profile KDF worker environment is not allowlisted")
            if expected_platform == "posix":
                expected_descriptors = self._expected_posix_file_descriptors
                if expected_descriptors is None:
                    raise ValueError("profile KDF child descriptors are unavailable")
                if payload["open_file_descriptors"] != sorted({0, 1, 2, *expected_descriptors}):
                    raise ValueError("profile KDF worker inherited an unallowlisted descriptor")
        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            raise _supervision_refusal() from None
        process = self._process
        if process is None:
            raise _supervision_refusal()
        if sys.platform == "win32":
            if (
                self._job is None
                or not self._job.contains(process)
                or self._job.limits()
                != {
                    "cpu_seconds": PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,
                    "memory_bytes": PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,
                    "max_processes": PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES,
                }
            ):
                raise _supervision_refusal()
        elif os.getpgid(process.pid) != process.pid:
            raise _supervision_refusal()
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


def _launch_worker(
    *,
    neutral_root: Path,
    request_read: int,
    result_write: int,
) -> tuple[subprocess.Popen[bytes], _WindowsJob | None]:
    command, launch_kwargs = _worker_command(
        neutral_root=neutral_root,
        request_read=request_read,
        result_write=result_write,
    )
    if sys.platform == "win32":
        job = _WindowsJob.create()
        process: subprocess.Popen[bytes] | None = None
        try:
            process = cast(
                "subprocess.Popen[bytes]",
                subprocess.Popen(command, **cast(Any, launch_kwargs)),  # noqa: S603 - fixed interpreter and module argv
            )
            job.assign(process)
            if not job.contains(process):
                raise _supervision_refusal()
        except BaseException:
            if process is None:
                job.close()
            else:
                _terminate_process_tree(process, job)
            raise
        finally:
            _clear_worker_handle_inheritance(
                request_read=request_read,
                result_write=result_write,
            )
        return process, job
    process = cast(
        "subprocess.Popen[bytes]",
        subprocess.Popen(command, **cast(Any, launch_kwargs)),  # noqa: S603 - fixed interpreter and module argv
    )
    return process, None


def _clear_worker_handle_inheritance(*, request_read: int, result_write: int) -> None:
    """Close the Windows inheritance window immediately after the one launch."""
    if sys.platform != "win32":
        return
    import msvcrt

    for descriptor in (request_read, result_write):
        with suppress(OSError):
            os.set_handle_inheritable(msvcrt.get_osfhandle(descriptor), False)


def _worker_command(
    *,
    neutral_root: Path,
    request_read: int,
    result_write: int,
) -> tuple[list[str], dict[str, object]]:
    neutral_cwd = str(neutral_root.resolve())
    command = [sys.executable, "-m", "cadrumo.adapters.persistence.storage.custody._kdf_worker"]
    environment = _worker_environment(neutral_root=neutral_root)
    common: dict[str, object] = {
        "close_fds": True,
        "cwd": neutral_cwd,
        "env": environment,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        import msvcrt

        request_handle = msvcrt.get_osfhandle(request_read)
        result_handle = msvcrt.get_osfhandle(result_write)
        os.set_handle_inheritable(request_handle, True)
        os.set_handle_inheritable(result_handle, True)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.lpAttributeList = {"handle_list": [request_handle, result_handle]}
        common["startupinfo"] = startupinfo
        command.extend(("--request-handle", str(request_handle), "--result-handle", str(result_handle)))
    else:
        common["pass_fds"] = (request_read, result_write)
        common["start_new_session"] = True
        common["preexec_fn"] = _apply_posix_worker_limits
        command.extend(("--request-fd", str(request_read), "--result-fd", str(result_write)))
    return command, common


def _worker_environment(*, neutral_root: Path) -> dict[str, str]:
    environment = {
        "CADRUMO_LOG_DIR": str(neutral_root / "logs"),
        "CADRUMO_LOCAL_STORAGE_ROOT": str(neutral_root / "state"),
        "HOME": str(neutral_root),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
    }
    if sys.platform == "win32":
        system_root = os.environ.get("SYSTEMROOT")
        if system_root is None:
            raise _supervision_refusal()
        environment["SYSTEMROOT"] = system_root
        environment["USERPROFILE"] = str(neutral_root)
    else:
        environment["LC_ALL"] = "C"
    return environment


def _apply_posix_worker_limits() -> None:
    import resource

    resource_module = cast(Any, resource)
    resource_module.setrlimit(resource_module.RLIMIT_AS, (PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES,) * 2)
    resource_module.setrlimit(resource_module.RLIMIT_CPU, (PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS,) * 2)
    resource_module.setrlimit(resource_module.RLIMIT_CORE, (0, 0))
    resource_module.setrlimit(resource_module.RLIMIT_FSIZE, (0, 0))
    resource_module.setrlimit(resource_module.RLIMIT_NOFILE, (16, 16))


class _WindowsJob:
    """A required kill-on-close Windows process-tree and resource boundary."""

    def __init__(self, handle: int, kernel32: Any) -> None:
        self._handle = handle
        self._kernel32 = kernel32

    @classmethod
    def create(cls) -> _WindowsJob:
        from ctypes import wintypes

        class _BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_uint64)
                for name in (
                    "ReadOperationCount",
                    "WriteOperationCount",
                    "OtherOperationCount",
                    "ReadTransferCount",
                    "WriteTransferCount",
                    "OtherTransferCount",
                )
            ]

        class _ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BasicLimitInformation),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise _supervision_refusal()
        information = _ExtendedLimitInformation()
        information.BasicLimitInformation.PerProcessUserTimeLimit = PROFILE_CUSTODY_KDF_WORKER_CPU_SECONDS * 10_000_000
        information.BasicLimitInformation.ActiveProcessLimit = PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES
        information.BasicLimitInformation.LimitFlags = (
            _WIN32_JOB_OBJECT_LIMIT_PROCESS_TIME
            | _WIN32_JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | _WIN32_JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | _WIN32_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        information.ProcessMemoryLimit = PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES
        if not kernel32.SetInformationJobObject(
            wintypes.HANDLE(handle),
            _WIN32_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(information),
            ctypes.sizeof(information),
        ):
            kernel32.CloseHandle(wintypes.HANDLE(handle))
            raise _supervision_refusal()
        return cls(int(handle), kernel32)

    def assign(self, process: subprocess.Popen[bytes]) -> None:
        from ctypes import wintypes

        process_handle = int(cast(Any, process)._handle)
        if not self._kernel32.AssignProcessToJobObject(
            wintypes.HANDLE(self._handle),
            wintypes.HANDLE(process_handle),
        ):
            raise _supervision_refusal()

    def contains(self, process: subprocess.Popen[bytes]) -> bool:
        """Prove the launched worker PID is present in this exact job object."""
        from ctypes import wintypes

        class _BasicProcessIdList(ctypes.Structure):
            _fields_ = [
                ("NumberOfAssignedProcesses", wintypes.DWORD),
                ("NumberOfProcessIdsInList", wintypes.DWORD),
                ("ProcessIdList", ctypes.c_size_t * PROFILE_CUSTODY_KDF_WORKER_MAX_PROCESSES),
            ]

        if not self._handle:
            return False
        members = _BasicProcessIdList()
        if not self._kernel32.QueryInformationJobObject(
            wintypes.HANDLE(self._handle),
            _WIN32_JOB_OBJECT_BASIC_PROCESS_ID_LIST,
            ctypes.byref(members),
            ctypes.sizeof(members),
            None,
        ):
            return False
        process_ids = members.ProcessIdList[: int(members.NumberOfProcessIdsInList)]
        return process.pid in process_ids

    def limits(self) -> dict[str, int]:
        """Read back the required Job Object limits before releasing a secret."""
        from ctypes import wintypes

        class _BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_uint64)
                for name in (
                    "ReadOperationCount",
                    "WriteOperationCount",
                    "OtherOperationCount",
                    "ReadTransferCount",
                    "WriteTransferCount",
                    "OtherTransferCount",
                )
            ]

        class _ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BasicLimitInformation),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        if not self._handle:
            raise _supervision_refusal()
        information = _ExtendedLimitInformation()
        if not self._kernel32.QueryInformationJobObject(
            wintypes.HANDLE(self._handle),
            _WIN32_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(information),
            ctypes.sizeof(information),
            None,
        ):
            raise _supervision_refusal()
        expected_flags = (
            _WIN32_JOB_OBJECT_LIMIT_PROCESS_TIME
            | _WIN32_JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | _WIN32_JOB_OBJECT_LIMIT_PROCESS_MEMORY
            | _WIN32_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        if information.BasicLimitInformation.LimitFlags & expected_flags != expected_flags:
            raise _supervision_refusal()
        return {
            "cpu_seconds": int(information.BasicLimitInformation.PerProcessUserTimeLimit // 10_000_000),
            "memory_bytes": int(information.ProcessMemoryLimit),
            "max_processes": int(information.BasicLimitInformation.ActiveProcessLimit),
        }

    def close(self) -> None:
        from ctypes import wintypes

        if self._handle:
            self._kernel32.CloseHandle(wintypes.HANDLE(self._handle))
            self._handle = 0


def _terminate_process_tree(process: subprocess.Popen[bytes], job: _WindowsJob | None) -> None:
    if job is not None:
        job.close()
    elif sys.platform != "win32":
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
    if process.poll() is None:
        process.kill()
    with suppress(subprocess.TimeoutExpired):
        process.wait(timeout=1.0)


def verify_profile_custody_sentinel(
    *,
    dek: bytes,
    profile_id: UUID,
    dek_epoch: str,
    sentinel: ProfileCustodySentinelRecord,
) -> None:
    if sentinel.profile_id != profile_id or sentinel.dek_epoch != dek_epoch:
        raise ProfileCustodyRecordError("profile custody sentinel identity does not match its envelope")
    try:
        actual_sentinel = decrypt_record(
            sentinel.encrypted_blob(),
            key=dek,
            associated_data=profile_custody_sentinel_aad_for(profile_id=profile_id, dek_epoch=dek_epoch),
        )
    except Exception as exc:
        raise ProfileCustodyRecordError("profile custody sentinel did not authenticate") from exc
    expected_sentinel = profile_custody_sentinel_plaintext(
        profile_id=profile_id,
        dek_epoch=dek_epoch,
    )
    if not secrets.compare_digest(actual_sentinel, expected_sentinel):
        raise ProfileCustodyRecordError("profile custody sentinel contents did not match")


def _canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode(_UTF_8_ENCODING)
    if len(encoded) > _FRAME_MAX_BYTES:
        raise ValueError("profile KDF frame exceeds its bounded transport")
    return encoded


def _canonical_digest(payload: Mapping[str, object]) -> str:
    import hashlib

    return f"sha256:{hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()}"


def _decode_canonical_b64(value: str, *, field_name: str, expected_bytes: int | None) -> bytes:
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be canonical base64") from exc
    if expected_bytes is not None and len(decoded) != expected_bytes:
        raise ValueError(f"{field_name} has an invalid byte length")
    if expected_bytes is None and not decoded:
        raise ValueError(f"{field_name} must not be empty")
    if base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError(f"{field_name} must be canonical base64")
    return decoded


def _reject_duplicate_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, member in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON member {key!r}")
        result[key] = member
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r} is forbidden")


def _kdf_strength(parameters: ProfileCustodyKdfParameters) -> tuple[int, int, int]:
    return (parameters.memory_mib, parameters.iterations, parameters.parallelism)


def _read_kdf_frame_to_queue(fd: int, result_queue: queue.Queue[tuple[int, bytes] | BaseException]) -> None:
    try:
        result_queue.put(read_kdf_frame(fd))
    except BaseException as exc:
        result_queue.put(exc)


def read_kdf_frame(fd: int) -> tuple[int, bytes]:
    header = _read_exact(fd, KDF_FRAME_HEADER.size)
    magic, version, kind, flags, length = KDF_FRAME_HEADER.unpack(header)
    if magic != KDF_FRAME_MAGIC or version != KDF_FRAME_VERSION or flags != 0:
        raise ValueError("profile KDF frame header is invalid")
    if kind not in {KDF_FRAME_CONTROL, KDF_FRAME_DEK}:
        raise ValueError("profile KDF frame kind is invalid")
    if length > _FRAME_MAX_BYTES:
        raise ValueError("profile KDF frame exceeds its bounded transport")
    return cast(int, kind), _read_exact(fd, length)


def write_kdf_frame(fd: int, value: bytes, *, kind: int) -> None:
    if len(value) > _FRAME_MAX_BYTES:
        raise ValueError("profile KDF frame exceeds its bounded transport")
    if kind not in {KDF_FRAME_CONTROL, KDF_FRAME_DEK}:
        raise ValueError("profile KDF frame kind is invalid")
    _write_all(fd, KDF_FRAME_HEADER.pack(KDF_FRAME_MAGIC, KDF_FRAME_VERSION, kind, 0, len(value)) + value)


def _read_exact(fd: int, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = os.read(fd, remaining)
        if not chunk:
            raise EOFError("profile KDF worker closed its pipe")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _write_all(fd: int, value: bytes) -> None:
    offset = 0
    while offset < len(value):
        offset += os.write(fd, value[offset:])


def _close_fd(fd: int | None) -> None:
    if fd is None:
        return
    with suppress(OSError):
        os.close(fd)


def _resource_refusal() -> ProfileCustodyRefusedError:
    return ProfileCustodyRefusedError(ProfileCustodyRefusal.KDF_RESOURCE_LIMIT)


def _supervision_refusal() -> ProfileCustodyRefusedError:
    return ProfileCustodyRefusedError(ProfileCustodyRefusal.KDF_SUPERVISION_UNAVAILABLE)


def _windows_available_memory_bytes() -> int:
    class _MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError(ctypes.get_last_error(), "GlobalMemoryStatusEx failed")
    return int(status.ullAvailPhys)


__all__ = [
    "PROFILE_CUSTODY_KDF_CALIBRATION_VERSION",
    "PROFILE_CUSTODY_KDF_SAMPLE_COUNT",
    "PROFILE_CUSTODY_KDF_SAMPLE_DEADLINE_SECONDS",
    "PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS",
    "PROFILE_CUSTODY_KDF_TARGET_MIN_SECONDS",
    "PROFILE_CUSTODY_KDF_TOTAL_DEADLINE_SECONDS",
    "PROFILE_CUSTODY_KDF_WARMUP_COUNT",
    "ProfileCustodyKdfCalibration",
    "ProfileCustodyKdfRatchetProposal",
    "ProfileCustodyKdfResources",
    "ProfileCustodySentinelRecord",
    "ProfileCustodyUnlock",
    "calibrate_profile_kdf",
    "fixed_profile_kdf_fallback",
    "parse_profile_custody_sentinel_record",
    "profile_custody_sentinel_aad",
    "profile_custody_sentinel_aad_for",
    "profile_custody_sentinel_plaintext",
    "profile_kdf_grid",
    "profile_kdf_is_eligible",
    "profile_kdf_lease",
    "profile_kdf_resources",
    "profile_password_wrap_aad",
    "propose_profile_kdf_ratchet",
    "unlock_profile_custody",
    "unlock_profile_custody_material",
    "verify_profile_custody_sentinel",
    "wrap_profile_custody_material",
]
