"""Supervised Argon2id work for current-format profile custody."""

from __future__ import annotations

import base64
import os
import sys
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from statistics import median
from typing import TYPE_CHECKING, Final, Literal, cast
from uuid import UUID

from .....core.config import load_settings
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_path
from ..crypto.aead import KEY_SIZE
from ._kdf_codec import (
    KDF_FRAME_CONTROL,
    KDF_FRAME_DEK,
    KDF_FRAME_HEADER,
    KDF_FRAME_MAGIC,
    KDF_FRAME_VERSION,
    read_kdf_frame,
    write_kdf_frame,
)
from ._kdf_codec import (
    canonical_frame_bytes as _canonical_frame_bytes,
)
from ._kdf_codec import (
    canonical_frame_digest as _canonical_frame_digest,
)
from ._kdf_codec import (
    close_fd as _close_fd,
)
from ._kdf_codec import (
    kdf_strength as _kdf_strength,
)
from ._kdf_codec import (
    resource_refusal as _resource_refusal,
)
from ._kdf_codec import (
    supervision_refusal as _supervision_refusal,
)
from ._kdf_codec import (
    windows_available_memory_bytes as _windows_available_memory_bytes,
)
from ._kdf_windows_job import PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES
from ._kdf_worker_supervision import _SupervisedKdfWorker
from ._recovery_secret_codec import encode_recovery_secret
from .errors import (
    ProfileCustodyPasswordError,
    ProfileCustodyRecordError,
    ProfileCustodyRecoverySecretError,
    ProfileCustodyRefusal,
    ProfileCustodyRefusedError,
)
from .records import (
    PROFILE_CUSTODY_KDF_ITERATIONS,
    PROFILE_CUSTODY_KDF_MEMORY_MIB,
    PROFILE_CUSTODY_KDF_PARALLELISM,
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    encode_profile_password,
)
from .sentinel_contract import ProfileCustodySentinelRecord, verify_profile_custody_sentinel

if TYPE_CHECKING:
    from .....core.config import Settings

PROFILE_CUSTODY_KDF_CALIBRATION_VERSION: Final = 1
PROFILE_CUSTODY_KDF_SAMPLE_COUNT: Final = 5
PROFILE_CUSTODY_KDF_WARMUP_COUNT: Final = 1
PROFILE_CUSTODY_KDF_SAMPLE_DEADLINE_SECONDS: Final = 2.0
PROFILE_CUSTODY_KDF_TOTAL_DEADLINE_SECONDS: Final = 15.0
PROFILE_CUSTODY_KDF_TARGET_MIN_SECONDS: Final = 0.250
PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS: Final = 0.500
_MEBIBYTE: Final = 1024 * 1024
_KDF_LEASE_FILENAME: Final = "profile-kdf.v1.lock"
_KDF_THREAD_LEASE: Final = threading.BoundedSemaphore(value=1)


@dataclass(frozen=True, slots=True)
class ProfileCustodyKdfResources:
    """Explicit local resources used to decide whether one grid point is safe."""

    available_memory_bytes: int
    cpu_count: int

    def __post_init__(self) -> None:
        """Refuse a resource reading of zero or negative memory or CPUs.

        A zero or negative reading here would silently make every grid point
        look unsafe (or, worse, divide-by-zero somewhere downstream) instead
        of surfacing that the resource probe itself failed — this is the
        boundary that turns a bad probe into a loud refusal.
        """
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
        "kdf_digest": _canonical_frame_digest(kdf.model_dump(mode="json")),
        "key_schedule": "profile-password-dek-wrap/v1",
        "password_encoding": _UTF_8_ENCODING,
        "password_generation": password_generation,
        "product": "cadrumo",
        "profile_id": str(profile_id),
        "purpose": "profile-password-dek-wrap/v1",
        "schema_version": 1,
    }
    return _canonical_frame_bytes(payload)


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

    # Measuring the grid costs one supervised child per warmup and per sample,
    # which is the right price for an operator's one-off enrolment and the
    # wrong one for a host that enrols constantly. Declining to measure adopts
    # the SAME fixed point this function already returns when the grid cannot
    # be measured before its deadline -- a stronger point than the measured
    # band's floor -- so nothing about the wrap weakens; only the host
    # measurement is skipped.
    if not (settings or load_settings()).cadrumo_profile_kdf_measure_calibration:
        return ProfileCustodyKdfCalibration(
            version=PROFILE_CUSTODY_KDF_CALIBRATION_VERSION,
            parameters=fallback,
            source="fallback",
            median_seconds=None,
        )

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
    dek = unlock_profile_custody_password_material(
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


def unlock_profile_custody_password_material(
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
    password_bytes = encode_profile_password(secret)
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


def wrap_profile_custody_password_material(
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
    if len(dek) != KEY_SIZE:
        raise ProfileCustodyRecordError("profile custody DEK must contain exactly 32 bytes")
    secret_bytes = encode_profile_password(secret)
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


def unlock_profile_custody_recovery_material(
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
    """Unlock the DEK using the recovery secret, inside the same supervised KDF boundary.

    The recovery-path sibling of the password unlock above it: same
    supervised worker and lease, but authenticated against the recovery
    secret rather than the login password, so a wrong recovery secret raises
    :class:`ProfileCustodyRecoverySecretError` rather than the password
    error a caller further up must distinguish.
    """
    if timeout_seconds <= 0:
        raise ValueError("profile KDF timeout must be positive")
    secret_bytes = encode_recovery_secret(secret)
    deadline = time.monotonic() + timeout_seconds
    try:
        with profile_kdf_lease(settings=settings, deadline=deadline), _SupervisedKdfWorker(deadline=deadline) as worker:
            dek = worker.unwrap(
                password=secret_bytes,
                kdf=kdf,
                wrapped_dek=wrapped_dek,
                associated_data=associated_data,
                recovery=True,
            )
    except TimeoutError:
        raise _resource_refusal() from None
    if dek is None:
        raise ProfileCustodyRecoverySecretError("profile recovery secret did not authenticate the custody envelope")
    verify_profile_custody_sentinel(dek=dek, profile_id=profile_id, dek_epoch=dek_epoch, sentinel=sentinel)
    return dek


def wrap_profile_custody_recovery_material(
    *,
    secret: str,
    dek: bytes,
    kdf: ProfileCustodyKdfParameters,
    associated_data: bytes,
    settings: Settings | None = None,
    timeout_seconds: float = PROFILE_CUSTODY_KDF_TOTAL_DEADLINE_SECONDS,
) -> ProfileCustodyWrappedDek:
    """Wrap the DEK under the recovery secret, inside the same supervised KDF boundary.

    The recovery-path sibling of the password wrap above it — same
    supervised worker and lease, but the resulting wrapper is unlocked later
    by :func:`unlock_profile_custody_recovery_material` with the recovery
    secret, never the login password.
    """
    if timeout_seconds <= 0:
        raise ValueError("profile KDF timeout must be positive")
    if len(dek) != KEY_SIZE:
        raise ProfileCustodyRecordError("profile custody DEK must contain exactly 32 bytes")
    secret_bytes = encode_recovery_secret(secret)
    deadline = time.monotonic() + timeout_seconds
    try:
        with profile_kdf_lease(settings=settings, deadline=deadline), _SupervisedKdfWorker(deadline=deadline) as worker:
            wrapped = worker.wrap(secret=secret_bytes, dek=dek, kdf=kdf, associated_data=associated_data, recovery=True)
    except TimeoutError:
        raise _resource_refusal() from None
    if wrapped is None:
        raise ProfileCustodyRecordError("supervised profile recovery wrapper creation failed")
    return wrapped


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
            root = storage_path(StorageCategory.BUCKETS, settings=settings).parent
            # The first credential enrollment occurs before a capsule exists,
            # so the storage root has no prior lifecycle owner to materialise
            # it.  The KDF lease owns this one non-capsule coordination file;
            # create only its configured parent before resolving it.
            root.mkdir(parents=True, exist_ok=True)
            root = root.resolve(strict=True)
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


__all__ = [
    "KDF_FRAME_CONTROL",
    "KDF_FRAME_DEK",
    "KDF_FRAME_HEADER",
    "KDF_FRAME_MAGIC",
    "KDF_FRAME_VERSION",
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
    "ProfileCustodyUnlock",
    "calibrate_profile_kdf",
    "fixed_profile_kdf_fallback",
    "profile_kdf_grid",
    "profile_kdf_is_eligible",
    "profile_kdf_lease",
    "profile_kdf_resources",
    "profile_password_wrap_aad",
    "propose_profile_kdf_ratchet",
    "read_kdf_frame",
    "unlock_profile_custody",
    "unlock_profile_custody_password_material",
    "unlock_profile_custody_recovery_material",
    "wrap_profile_custody_password_material",
    "wrap_profile_custody_recovery_material",
    "write_kdf_frame",
]
