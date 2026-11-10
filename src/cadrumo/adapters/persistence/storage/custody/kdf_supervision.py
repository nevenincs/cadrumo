"""Supervised Argon2id work for current-format profile custody."""

from __future__ import annotations

import atexit
import base64
import contextvars
import logging
import math
import os
import sys
import threading
import time
from collections.abc import Callable, Generator, Mapping
from contextlib import ExitStack, closing, contextmanager, nullcontext
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal, NoReturn, cast
from uuid import UUID

from .....application.user_profile.proof_cancellation import ProfileProofCancellation, ProfileProofCancelledError
from .....core.config import load_settings
from .....core.diagnostic_log import diagnostic_event
from .....core.errors.hierarchy import CadrumoError
from .....core.external_constants import UTF_8_ENCODING
from .....core.logging import get_logger
from .....core.storage_taxonomy import StorageCategory
from .....core.storage_taxonomy_locations import storage_path
from ..crypto.aes_gcm import KEY_SIZE
from .errors import (
    ProfileCustodyPasswordError,
    ProfileCustodyRecordError,
    ProfileCustodyRecoverySecretError,
    ProfileCustodyRefusal,
    ProfileCustodyRefusedError,
)
from .kdf_calibration_search import search_profile_kdf_grid
from .kdf_codec import (
    canonical_frame_bytes,
    canonical_frame_digest,
    close_fd,
    windows_available_memory_bytes,
)
from .kdf_file_lease import acquire_kdf_file_lease, open_kdf_file_lease, release_kdf_file_lease
from .kdf_records import (
    PROFILE_CUSTODY_KDF_ITERATIONS,
    PROFILE_CUSTODY_KDF_MEMORY_MIB,
    PROFILE_CUSTODY_KDF_PARALLELISM,
)
from .kdf_refusals import resource_refusal, supervision_refusal
from .kdf_worker_limits import PROFILE_CUSTODY_KDF_WORKER_MEMORY_BYTES
from .kdf_worker_supervision import SupervisedKdfWorker, kdf_worker_never_attested
from .profile_password_codec import encode_profile_password
from .records import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
)
from .recovery_secret_codec import encode_recovery_secret
from .sentinel_contract import ProfileCustodySentinelRecord, verify_profile_custody_sentinel

if TYPE_CHECKING:
    from .....core.config import Settings

PROFILE_CUSTODY_KDF_CALIBRATION_VERSION: Final = 1
PROFILE_CUSTODY_KDF_SAMPLE_COUNT: Final = 5
PROFILE_CUSTODY_KDF_SAMPLE_DEADLINE_SECONDS: Final = 2.0
PROFILE_CUSTODY_KDF_TOTAL_DEADLINE_SECONDS: Final = 15.0
#: Seconds of child launch and attestation a whole calibration may wait for,
#: beyond its total deadline. Launching a contained child is uncancellable
#: operating-system work that takes seconds on a loaded Windows host; charging
#: it to the total deadline ended calibration before it could confirm a point,
#: and that fallback is the weakest eligible point. Launch time therefore
#: extends the total deadline instead, but only from this separate budget, so
#: enrolment still ends when launches are unusable.
PROFILE_CUSTODY_KDF_LAUNCH_BUDGET_SECONDS: Final = 20.0
#: Default wall-clock bound on direct wrap or unwrap. Runtime first login supplies its
#: retained absolute timeout deadline instead; no normal phase timeout applies there.
#: Includes waiting for the installation's single
#: KDF permit, attesting a fresh child, then the derivation; the operating system's
#: uncancellable process-creation call is not charged, because no child exists to
#: stall while it blocks. The derivation's own cost is bounded by the child's
#: operating-system CPU-time and memory ceilings; this bound only guarantees a
#: stalled child is abandoned. The child starts the base interpreter without
#: ``site`` and imports only its allow-listed leaves, so its start-up is a fraction
#: of this even on a saturated host; a slow start is fixed there, never by widening
#: this bound.
PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS: Final = 15.0
PROFILE_CUSTODY_KDF_TARGET_MIN_SECONDS: Final = 0.250
PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS: Final = 0.500
_MEBIBYTE: Final = 1024 * 1024
_KDF_LEASE_FILENAME: Final = "profile-kdf.v1.lock"
KDF_THREAD_LEASE: Final = threading.BoundedSemaphore(value=1)
KDF_THREAD_CAPACITY: Final = threading.Condition()
_log = get_logger(__name__)
_KDF_PREWARM: Final = contextvars.ContextVar["ProfileKdfPrewarm | None"]("cadrumo_profile_kdf_prewarm", default=None)


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


class CalibrationDeadlineElapsedError(CadrumoError):
    """Signal that a calibration grid cannot continue within its total deadline."""


type _CalibrationStop = Literal["total_deadline_exhausted", "launch_budget_exhausted", "launch_retry_failed"]


@dataclass(slots=True)
class _CalibrationClock:
    """The total deadline of one calibration, extended only by launch time paid from its launch budget."""

    deadline: float
    launch_budget_seconds: float
    stop: _CalibrationStop | None = None

    def excuse_launch(self, seconds: float) -> None:
        """Move the deadline past ``seconds`` of launch, or stop once the budget cannot pay for it."""
        paid = min(max(seconds, 0.0), self.launch_budget_seconds)
        self.launch_budget_seconds -= paid
        self.deadline += paid
        if seconds > paid:
            self.abandon("launch_budget_exhausted")

    def abandon(self, stop: _CalibrationStop) -> NoReturn:
        """Abandon the whole search for the fixed fallback, naming why."""
        self.stop = stop
        raise CalibrationDeadlineElapsedError


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
        "kdf_digest": canonical_frame_digest(kdf.model_dump(mode="json")),
        "key_schedule": "profile-password-dek-wrap/v1",
        "password_encoding": UTF_8_ENCODING,
        "password_generation": password_generation,
        "product": "cadrumo",
        "profile_id": str(profile_id),
        "purpose": "profile-password-dek-wrap/v1",
        "schema_version": 1,
    }
    return canonical_frame_bytes(payload)


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


def posix_memory_bytes() -> int:
    """Return a POSIX memory bound for the eligibility gate, or 0 if unknowable.

    ``SC_AVPHYS_PAGES`` is the currently-free page count and is the figure to
    prefer, but it is NOT portable: macOS omits it from ``os.sysconf_names``
    entirely, so asking for it by name raises ``ValueError`` rather than
    answering, and the lookup guards on membership for that reason.

    Reading it unguarded here made every macOS host refuse profile custody
    outright: the ``ValueError`` was caught beside genuine probe failures and
    turned into ``KDF_RESOURCE_LIMIT``, so `config profile create` could not
    succeed on any Mac at any memory pressure -- while the refusal told the
    operator to retry when the machine was less loaded, a state that could
    never arrive. Measured on macOS 26.5.1: ``SC_AVPHYS_PAGES`` absent,
    ``SC_PHYS_PAGES`` present and reporting 8 GiB, ~1.6 GiB genuinely
    reclaimable.

    Where the free count is unavailable, total physical memory is used
    instead. That is deliberately a weaker bound -- it cannot see load -- and
    it is the honest one, because the alternative on such a platform is to
    refuse work the host can plainly do. The allocation is not left unguarded:
    the derivation runs in a supervised child under ``RLIMIT_AS`` with a
    deadline, so a host that genuinely cannot supply the memory still fails
    there, loudly, instead of being predicted here.
    """
    # Reached through ``getattr`` rather than named directly: neither attribute
    # is declared on Windows, where this branch never runs, so naming them
    # outright is an unresolved attribute to a type checker reading the
    # Windows surface. The names are also the only portable way to ask what
    # this host actually answers.
    names = getattr(os, "sysconf_names", None)
    sysconf = getattr(os, "sysconf", None)
    # Narrowed by test rather than by annotation. Annotating the ``getattr``
    # results would assert their shape instead of establishing it, and these
    # are exactly the attributes whose presence and type this function exists
    # to be unsure about.
    if not isinstance(names, Mapping) or not callable(sysconf):
        return 0
    if "SC_PAGE_SIZE" not in names:
        return 0
    sysconf_reader = cast("Callable[[str], int]", sysconf)
    page_size = int(sysconf_reader("SC_PAGE_SIZE"))
    for pages_name in ("SC_AVPHYS_PAGES", "SC_PHYS_PAGES"):
        if pages_name in names:
            return page_size * int(sysconf_reader(pages_name))
    return 0


def profile_kdf_resources() -> ProfileCustodyKdfResources:
    """Read the portable resources that bound a local KDF worker."""
    cpu_count = os.cpu_count()
    if cpu_count is None or cpu_count < 1:
        raise resource_refusal()
    try:
        if sys.platform == "win32":
            available_memory = windows_available_memory_bytes()
        else:
            available_memory = posix_memory_bytes()
    except (AttributeError, OSError, ValueError):
        raise resource_refusal() from None
    if available_memory < 1:
        raise resource_refusal()
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


def _fallback_profile_kdf_calibration(
    parameters: ProfileCustodyKdfParameters,
) -> ProfileCustodyKdfCalibration:
    return ProfileCustodyKdfCalibration(
        version=PROFILE_CUSTODY_KDF_CALIBRATION_VERSION,
        parameters=parameters,
        source="fallback",
        median_seconds=None,
    )


def profile_kdf_at_fallback(parameters: ProfileCustodyKdfParameters) -> bool:
    """Return whether stored parameters are exactly the fixed fallback point.

    Calibration adopts that point whenever it cannot confirm a stronger one in
    time, so a profile holding it may gain strength from a fresh calibration.
    The salt is the profile's own and plays no part in the comparison.
    """
    fallback = fixed_profile_kdf_fallback(salt=bytes(16))
    return (
        parameters.algorithm,
        parameters.version,
        parameters.memory_mib,
        parameters.iterations,
        parameters.parallelism,
    ) == (fallback.algorithm, fallback.version, fallback.memory_mib, fallback.iterations, fallback.parallelism)


def profile_kdf_meets_fallback_floor(parameters: ProfileCustodyKdfParameters) -> bool:
    """Return whether a grid point is at least as strong as the fixed fallback.

    Calibration never selects below this floor, so measuring a host can only
    ever strengthen an enrollment relative to not measuring it.
    """
    floor = fixed_profile_kdf_fallback(salt=bytes(16))
    return (
        parameters.memory_mib >= floor.memory_mib
        and parameters.memory_mib * parameters.iterations >= floor.memory_mib * floor.iterations
    )


def calibrate_profile_kdf(*, salt: bytes, settings: Settings | None = None) -> ProfileCustodyKdfCalibration:
    """Calibrate a fresh profile KDF with bounded real child-process samples."""
    resources = profile_kdf_resources()
    fallback = fixed_profile_kdf_fallback(salt=salt)
    if not profile_kdf_is_eligible(fallback, resources=resources):
        raise resource_refusal()

    # Measuring the grid costs one supervised child per probe and per sample,
    # which is the right price for an operator's one-off enrolment and the
    # wrong one for a host that enrols constantly. Declining to measure adopts
    # the SAME fixed point this function already returns when no point can be
    # confirmed before its deadline, so nothing about the wrap weakens; only
    # the host measurement is skipped.
    if not (settings or load_settings()).cadrumo_profile_kdf_measure_calibration:
        return _fallback_profile_kdf_calibration(fallback)

    candidates = tuple(
        parameters
        for parameters in profile_kdf_grid(salt=salt)
        if profile_kdf_is_eligible(parameters, resources=resources) and profile_kdf_meets_fallback_floor(parameters)
    )
    return _measured_calibration(candidates, fallback=fallback, settings=settings)


def _measured_calibration(
    candidates: tuple[ProfileCustodyKdfParameters, ...],
    *,
    fallback: ProfileCustodyKdfParameters,
    settings: Settings | None,
) -> ProfileCustodyKdfCalibration:
    """Search the eligible grid under the total deadline and launch budget, else adopt the fallback."""
    started = time.monotonic()
    clock = _CalibrationClock(
        deadline=started + PROFILE_CUSTODY_KDF_TOTAL_DEADLINE_SECONDS,
        launch_budget_seconds=PROFILE_CUSTODY_KDF_LAUNCH_BUDGET_SECONDS,
    )
    with ExitStack() as owned:
        # Every sample runs in a spare attested before its clock starts: the
        # creation's bound prewarm, or one owned by this calibration alone.
        prewarm = _KDF_PREWARM.get() or owned.enter_context(closing(ProfileKdfPrewarm(settings=settings)))
        try:
            choice = search_profile_kdf_grid(
                candidates,
                probe=_calibration_probe(prewarm=prewarm, clock=clock, settings=settings),
                target_min_seconds=PROFILE_CUSTODY_KDF_TARGET_MIN_SECONDS,
                target_max_seconds=PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS,
                confirmation_samples=PROFILE_CUSTODY_KDF_SAMPLE_COUNT,
            )
        except CalibrationDeadlineElapsedError:
            choice = None
    if choice is None:
        _log_calibration_fallback(clock.stop or "no_in_band_point", started=started)
        return _fallback_profile_kdf_calibration(fallback)
    return ProfileCustodyKdfCalibration(
        version=PROFILE_CUSTODY_KDF_CALIBRATION_VERSION,
        parameters=choice.parameters,
        source="measured",
        median_seconds=choice.median_seconds,
    )


def _calibration_probe(
    *, prewarm: ProfileKdfPrewarm, clock: _CalibrationClock, settings: Settings | None
) -> Callable[[ProfileCustodyKdfParameters], float]:
    """Score one grid point by a supervised sample; only a timed derivation's overrun reads as over the band."""

    def probe(parameters: ProfileCustodyKdfParameters) -> float:
        try:
            return _measure_profile_kdf(parameters, prewarm=prewarm, clock=clock, settings=settings)
        except TimeoutError:
            if time.monotonic() >= clock.deadline:
                clock.abandon("total_deadline_exhausted")
            # Only a timed derivation overruns a sample, so this point is over the band.
            return math.inf
        except ProfileCustodyRefusedError as exc:
            if exc.refusal is ProfileCustodyRefusal.KDF_RESOURCE_LIMIT:
                return math.inf
            raise

    return probe


def _log_calibration_fallback(reason: str, *, started: float) -> None:
    """Name, at WARNING, why calibration adopted the fixed fallback instead of a measured point."""
    diagnostic_event(
        _log,
        "profile_kdf_calibration_fallback",
        fields={"reason": reason, "elapsed_seconds": round(time.monotonic() - started, 3), "outcome": "fallback"},
        level=logging.WARNING,
    )


def unlock_profile_custody(
    envelope: ProfileCustodyEnvelope,
    password: str,
    *,
    sentinel: ProfileCustodySentinelRecord,
    settings: Settings | None = None,
    timeout_seconds: float = PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS,
    timeout_deadline: float | None = None,
    cancellation: ProfileProofCancellation | None = None,
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
        timeout_deadline=timeout_deadline,
        cancellation=cancellation,
    )
    return ProfileCustodyUnlock(
        profile_id=envelope.profile_id,
        envelope_digest=envelope.self_digest,
        kdf=envelope.kdf,
        dek=dek,
    )


def _require_unlock_timeout(
    timeout_seconds: float, timeout_deadline: float | None, cancellation: ProfileProofCancellation | None
) -> None:
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("profile KDF timeout must be positive")
    if timeout_deadline is not None and not math.isfinite(timeout_deadline):
        raise ValueError("profile KDF timeout deadline must be finite")
    if cancellation is not None:
        cancellation.raise_if_cancelled()


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
    timeout_seconds: float = PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS,
    timeout_deadline: float | None = None,
    cancellation: ProfileProofCancellation | None = None,
) -> bytes:
    """Supervise one current-format wrapper unwrap and prove its immutable DEK.

    The caller owns one closed wrapper AAD domain.  This adapter owns password
    representation, process supervision, and the non-optional capsule proof.
    It never returns an unproved key.
    """
    _require_unlock_timeout(timeout_seconds, timeout_deadline, cancellation)
    password_bytes = encode_profile_password(secret)
    deadline = time.monotonic() + timeout_seconds if timeout_deadline is None else timeout_deadline
    try:
        _require_timeout_budget(timeout_deadline, cancellation=cancellation)
        with (
            profile_kdf_lease(settings=settings, deadline=deadline, cancellation=cancellation),
            supervised_kdf_worker(
                deadline=deadline,
                settings=settings,
                absolute_deadline=timeout_deadline is not None,
                cancellation=cancellation,
            ) as worker,
        ):
            _require_timeout_budget(timeout_deadline, cancellation=cancellation)
            dek = worker.unwrap(
                password=password_bytes,
                kdf=kdf,
                wrapped_dek=wrapped_dek,
                associated_data=associated_data,
            )
    except TimeoutError as error:
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        if timeout_deadline is not None:
            raise _owner_timeout_refusal() from None
        raise _timeout_refusal(error) from None
    except ProfileCustodyRefusedError:
        _require_timeout_budget(timeout_deadline, cancellation=cancellation)
        raise
    _require_timeout_budget(timeout_deadline, cancellation=cancellation)
    if dek is None:
        raise ProfileCustodyPasswordError("profile password did not authenticate the custody envelope")
    verify_profile_custody_sentinel(
        dek=dek,
        profile_id=profile_id,
        dek_epoch=dek_epoch,
        sentinel=sentinel,
    )
    _require_timeout_budget(timeout_deadline, cancellation=cancellation)
    return dek


def wrap_profile_custody_password_material(
    *,
    secret: str,
    dek: bytes,
    kdf: ProfileCustodyKdfParameters,
    associated_data: bytes,
    settings: Settings | None = None,
    timeout_seconds: float = PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS,
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
            supervised_kdf_worker(deadline=deadline, settings=settings) as worker,
        ):
            wrapped_dek = worker.wrap(
                secret=secret_bytes,
                dek=dek,
                kdf=kdf,
                associated_data=associated_data,
            )
    except TimeoutError as error:
        raise _timeout_refusal(error) from None
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
    timeout_seconds: float = PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS,
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
        with (
            profile_kdf_lease(settings=settings, deadline=deadline),
            supervised_kdf_worker(deadline=deadline, settings=settings) as worker,
        ):
            dek = worker.unwrap(
                password=secret_bytes,
                kdf=kdf,
                wrapped_dek=wrapped_dek,
                associated_data=associated_data,
                recovery=True,
            )
    except TimeoutError as error:
        raise _timeout_refusal(error) from None
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
    timeout_seconds: float = PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS,
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
        with (
            profile_kdf_lease(settings=settings, deadline=deadline),
            supervised_kdf_worker(deadline=deadline, settings=settings) as worker,
        ):
            wrapped = worker.wrap(secret=secret_bytes, dek=dek, kdf=kdf, associated_data=associated_data, recovery=True)
    except TimeoutError as error:
        raise _timeout_refusal(error) from None
    if wrapped is None:
        raise ProfileCustodyRecordError("supervised profile recovery wrapper creation failed")
    return wrapped


class ProfileKdfPrewarm:
    """Keep one attested, idle KDF child ready for its owner's next wrap or unwrap.

    Every Argon2 operation still runs in its own freshly launched, contained
    child that performs exactly one derivation and exits; no secret reaches a
    child before its ready attestation is verified. This only moves that
    launch and attestation, an interpreter start-up that costs far more than
    the derivation itself, off the caller's critical path. A spare is used
    only inside :meth:`bound`, so nothing outside the owner adopts it, and a
    spare that died while idle is discarded for a fresh launch. An operation
    that arrives while its spare is still attesting waits for that one child
    instead of starting a second; if the spare fails, the operation launches
    its own.
    """

    def __init__(self, *, settings: Settings | None = None) -> None:
        """Bind the owner's settings now: a spare launches on another thread, outside its context."""
        self._settings = settings or load_settings()
        self._lock = threading.Lock()
        self._settled = threading.Condition(self._lock)
        self._spare: SupervisedKdfWorker | None = None
        self._failed_launch: tuple[SupervisedKdfWorker, BaseException] | None = None
        self._launching = False
        self._closed = False
        # Lets close() abandon a launch that has not attested, so no spare outlives its owner.
        self._launch_cancellation = ProfileProofCancellation()
        atexit.register(self.close)

    def refill(self) -> None:
        """Start launching a spare unless one is ready, launching, or the owner closed."""
        with self._lock:
            if self._closed or self._spare is not None or self._launching or self._failed_launch is not None:
                return
            self._launching = True
        context = contextvars.copy_context()
        try:
            threading.Thread(target=context.run, args=(self._launch,), name="profile-kdf-prewarm", daemon=True).start()
        except BaseException:
            with self._settled:
                self._launching = False
                self._settled.notify_all()
            raise

    def _launch(self) -> None:
        spare: SupervisedKdfWorker | None = None
        candidate: SupervisedKdfWorker | None = None
        try:
            candidate = SupervisedKdfWorker(
                deadline=time.monotonic() + PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS,
                settings=self._settings,
                cancellation=self._launch_cancellation,
            )
            spare = candidate.__enter__()
        except BaseException as error:
            # An incompletely settled launch must remain owned and cannot fall back to a new child.
            if candidate is not None and candidate._cleanup_pending():
                with self._settled:
                    self._failed_launch = (candidate, error)
            if not isinstance(
                error, (ProfileCustodyRefusedError, ProfileProofCancelledError, TimeoutError, OSError, ValueError)
            ):
                raise
            spare = None
        finally:
            try:
                with self._settled:
                    if spare is not None and not self._closed and self._spare is None:
                        self._spare, spare = spare, None
                        self._settled.notify_all()
                if spare is not None:
                    spare.__exit__(None, None, None)
            finally:
                # Settled only once an unwanted spare is contained, so close() never returns ahead of it.
                with self._settled:
                    self._launching = False
                    self._settled.notify_all()

    def take(
        self, *, deadline: float, cancellation: ProfileProofCancellation | None = None
    ) -> SupervisedKdfWorker | None:
        """Hand the spare to one operation, or ``None`` when a fresh launch is needed.

        A spare still launching is awaited until the operation's deadline or
        cancellation; that child's own launch deadline bounds the wait as well.
        """
        with ExitStack() as watching:
            if cancellation is not None:
                watching.enter_context(cancellation.watch(self._wake))
            with self._settled:
                self._wait_for_launch(deadline=deadline, cancellation=cancellation)
                self._raise_unsettled_launch()
                spare, self._spare = self._spare, None
        if cancellation is not None and cancellation.cancelled:
            if spare is not None:
                spare.__exit__(None, None, None)
            cancellation.raise_if_cancelled()
        if spare is None:
            return None
        if not spare.adopt(deadline=deadline, cancellation=cancellation):
            spare.__exit__(None, None, None)
            return None
        return spare

    def _wait_for_launch(self, *, deadline: float, cancellation: ProfileProofCancellation | None) -> None:
        """Wait under ``_settled`` until the launch, deadline, cancellation or close settles the wait."""
        while self._launching and self._spare is None and not self._closed:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or (cancellation is not None and cancellation.cancelled):
                break
            self._settled.wait(remaining)

    @property
    def launching(self) -> bool:
        """Whether a spare is still launching and has neither attested nor failed."""
        with self._lock:
            return self._launching and self._spare is None

    def settle_launch(self, *, deadline: float) -> None:
        """Wait until a launching spare has attested or failed, or until ``deadline``.

        A timed calibration sample calls this before its clock starts, so no
        launch is in flight while its derivation is measured.
        """
        with self._settled:
            self._wait_for_launch(deadline=deadline, cancellation=None)

    @contextmanager
    def bound(self, *, refill: bool = True) -> Generator[None]:
        """Let supervised KDF work in this context use the spare, then prepare the next one.

        Without ``refill`` the scope launches no spare on exit, for an owner
        whose last derivation runs here and would only contain it unused.
        """
        token = _KDF_PREWARM.set(self)
        try:
            yield
        finally:
            _KDF_PREWARM.reset(token)
            if refill:
                self.refill()

    def _wake(self) -> None:
        with self._settled:
            self._settled.notify_all()

    def _raise_unsettled_launch(self) -> None:
        """Keep a failed launch until its retained owner has actually settled."""
        failed = self._failed_launch
        if failed is not None:
            worker, error = failed
            if worker._cleanup_pending():
                raise error
            self._failed_launch = None

    def close(self) -> None:
        """Stop launching spares and contain the idle one and any still launching."""
        with self._settled:
            self._closed = True
            spare, self._spare = self._spare, None
            self._settled.notify_all()
        self._launch_cancellation.cancel()
        with self._settled:
            self._settled.wait_for(lambda: not self._launching)
            self._raise_unsettled_launch()
        atexit.unregister(self.close)
        if spare is not None:
            spare.__exit__(None, None, None)


@contextmanager
def supervised_kdf_worker(
    *,
    deadline: float,
    settings: Settings | None,
    absolute_deadline: bool = False,
    cancellation: ProfileProofCancellation | None = None,
) -> Generator[SupervisedKdfWorker]:
    """Run one operation in the bound prewarmed child when one is ready, else in a fresh one."""
    prewarm = _KDF_PREWARM.get()
    waited_from = time.monotonic()
    spare = prewarm.take(deadline=deadline, cancellation=cancellation) if prewarm is not None else None
    if spare is None:
        if not absolute_deadline:
            # No child served the wait, so the fresh one keeps the whole relative budget.
            deadline += time.monotonic() - waited_from
        with SupervisedKdfWorker(
            deadline=deadline, settings=settings, absolute_deadline=absolute_deadline, cancellation=cancellation
        ) as worker:
            yield worker
        return
    with ExitStack() as owned:
        owned.push(spare)
        yield spare


def _owner_timeout_refusal() -> ProfileCustodyRefusedError:
    return ProfileCustodyRefusedError(ProfileCustodyRefusal.KDF_TIMEOUT)


def _require_timeout_budget(deadline: float | None, *, cancellation: ProfileProofCancellation | None = None) -> None:
    """An elapsed owner timeout may never release even a successfully proven key."""
    if cancellation is not None:
        cancellation.raise_if_cancelled()
    if deadline is not None and time.monotonic() >= deadline:
        raise _owner_timeout_refusal()


def _timeout_refusal(error: TimeoutError) -> ProfileCustodyRefusedError:
    """Name a child that never attested as supervision; a late permit or derivation as the busy host's limit."""
    return supervision_refusal() if kdf_worker_never_attested(error) else resource_refusal()


def _measure_profile_kdf(
    parameters: ProfileCustodyKdfParameters,
    *,
    prewarm: ProfileKdfPrewarm,
    clock: _CalibrationClock,
    settings: Settings | None,
) -> float:
    """Return the worker-timed derivation seconds of one supervised sample.

    The worker times only the Argon2 call, so the band measures derivation
    cost rather than interpreter start-up; the wall clock still bounds the
    sample, and a duration longer than the sample itself took is a lie the
    parent refuses.

    The sample's child is a spare whose launch and attestation settled before
    the sample's clock starts, so no launch competes with a measured
    derivation, which could read its cost high and select a weaker point, and
    the clock covers only the request, the derivation and the child's exit.
    That launch time moves the total deadline instead, paid from the launch
    budget. A spare that failed to launch or died idle is never scored; the
    sample is retried once in a fresh spare.
    """
    for _attempt in range(2):
        _settle_spare(prewarm, clock)
        with ExitStack() as sample:
            sample.enter_context(profile_kdf_lease(settings=settings, deadline=clock.deadline))
            remaining = min(PROFILE_CUSTODY_KDF_SAMPLE_DEADLINE_SECONDS, clock.deadline - time.monotonic())
            if remaining <= 0:
                raise TimeoutError("profile KDF calibration total deadline elapsed")
            started = time.monotonic()
            spare = prewarm.take(deadline=started + remaining)
            if spare is None:
                continue
            sample.push(spare)
            derivation_seconds = spare.calibrate(parameters)
            sample.close()
            elapsed = time.monotonic() - started
            if elapsed > PROFILE_CUSTODY_KDF_SAMPLE_DEADLINE_SECONDS:
                raise TimeoutError("profile KDF calibration sample deadline elapsed")
            if derivation_seconds > elapsed:
                raise supervision_refusal()
            return derivation_seconds
    clock.abandon("launch_retry_failed")


def _settle_spare(prewarm: ProfileKdfPrewarm, clock: _CalibrationClock) -> None:
    """Launch a spare if none is ready and wait for it, paying that wait from the launch budget."""
    prewarm.refill()
    waited_from = time.monotonic()
    prewarm.settle_launch(deadline=waited_from + clock.launch_budget_seconds)
    clock.excuse_launch(time.monotonic() - waited_from)
    if prewarm.launching:
        clock.abandon("launch_budget_exhausted")


@contextmanager
def profile_kdf_lease(
    *, deadline: float, settings: Settings | None = None, cancellation: ProfileProofCancellation | None = None
) -> Generator[None]:
    """Acquire the one OS-released KDF permit for a canonical installation root.

    The descriptor stays open for the operation, so an abnormal owner death
    releases its permit at the operating-system boundary instead of leaving a
    process-local or persistent ownership record behind.
    """

    def capacity_changed() -> None:
        with KDF_THREAD_CAPACITY:
            KDF_THREAD_CAPACITY.notify_all()

    with cancellation.watch(capacity_changed) if cancellation is not None else nullcontext(), KDF_THREAD_CAPACITY:
        while True:
            if cancellation is not None:
                cancellation.raise_if_cancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise resource_refusal()
            if KDF_THREAD_LEASE.acquire(blocking=False):
                break
            KDF_THREAD_CAPACITY.wait(timeout=remaining)
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
            descriptor = open_kdf_file_lease(lock_path)
        except OSError:
            raise supervision_refusal() from None
        try:
            acquire_kdf_file_lease(descriptor, deadline=deadline, settings=settings, cancellation=cancellation)
            try:
                yield
            finally:
                release_kdf_file_lease(descriptor)
        finally:
            close_fd(descriptor)
    finally:
        with KDF_THREAD_CAPACITY:
            KDF_THREAD_LEASE.release()
            KDF_THREAD_CAPACITY.notify_all()


__all__ = [
    "PROFILE_CUSTODY_KDF_CALIBRATION_VERSION",
    "PROFILE_CUSTODY_KDF_LAUNCH_BUDGET_SECONDS",
    "PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS",
    "PROFILE_CUSTODY_KDF_SAMPLE_COUNT",
    "PROFILE_CUSTODY_KDF_SAMPLE_DEADLINE_SECONDS",
    "PROFILE_CUSTODY_KDF_TARGET_MAX_SECONDS",
    "PROFILE_CUSTODY_KDF_TARGET_MIN_SECONDS",
    "PROFILE_CUSTODY_KDF_TOTAL_DEADLINE_SECONDS",
    "ProfileCustodyKdfCalibration",
    "ProfileCustodyKdfResources",
    "ProfileCustodyUnlock",
    "ProfileKdfPrewarm",
    "calibrate_profile_kdf",
    "fixed_profile_kdf_fallback",
    "profile_kdf_at_fallback",
    "profile_kdf_grid",
    "profile_kdf_is_eligible",
    "profile_kdf_lease",
    "profile_kdf_meets_fallback_floor",
    "profile_kdf_resources",
    "profile_password_wrap_aad",
    "unlock_profile_custody",
    "unlock_profile_custody_password_material",
    "unlock_profile_custody_recovery_material",
    "wrap_profile_custody_password_material",
    "wrap_profile_custody_recovery_material",
]
