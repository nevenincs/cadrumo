"""Per-bucket failed-login throttle sidecar.

A plaintext, best-effort rate-limit cache that records only the count of
consecutive failed authentication attempts and the timestamp of the most
recent one — never a secret, a passphrase, or any key material. It lives
beside the wrapped bucket DEK in the separated keystore directory and is
written through the same hardened atomic writer.

The throttle enforces this backoff: the caller evaluates the
remaining wait BEFORE running any Argon2id derivation, so the KDF can never
become a passphrase-testing timing oracle. The required wait after ``n``
consecutive failures is ``min(2 ** n, 60)`` seconds, measured from
``last_failure_at`` — so a caller that simply waited the backoff out is
cleared to retry.

There is deliberately NO permanent lockout: a local-CLI self-DoS is worse
than throttled retry (NIST SP 800-63B §5.2.2 requires throttling, not
lockout). For the same reason the sidecar is a *revocable cache*, not an
authoritative record — a missing, unreadable, or version-mismatched file is
treated as "no active throttle" and rewritten on the next failure, never a
hard refusal that could strand the legitimate operator. The counter resets
to clear on a successful login and on logout.

Every read-modify-write of the sidecar is serialized under
:func:`~cadrumo.core.exclusive_file_lock`, because the counter is the whole
substance of the control: overlapping attempts that each read ``n`` and each
write ``n + 1`` advance it once, so a burst of wrong passwords faces the
backoff owed to a single failure. That tolerance is not one of the ones above
-- treating an unusable file as cleared protects the legitimate operator,
while a lost increment only helps whoever is guessing.

See Also:
    :class:`~adapters.persistence.storage.master_key.BucketSession`
        The unlock session whose authentication attempts this throttle guards.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field, NonNegativeInt

from .....core.atomic_write import atomic_write_hardened_bytes
from .....core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from .....core.locks import exclusive_file_lock
from .....core.locks_errors import LockAcquisitionError
from .....core.logging import get_logger
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.time.utc import UtcInstant
from ..storage_path_definitions import LOGIN_THROTTLE_FILENAME

_log = get_logger(__name__)

LOGIN_THROTTLE_SCHEMA_VERSION = 1
"""Version stamped on the persisted throttle state."""

THROTTLE_BACKOFF_CAP_SECONDS = 60
"""Maximum required wait between consecutive failed attempts."""

# 2 ** 6 == 64 already exceeds the 60 s cap; clamping the exponent keeps the
# shift bounded no matter how many failures accumulate.
_MAX_BACKOFF_EXPONENT = 6


class LoginThrottleState(BaseModel):
    """Strict, plaintext throttle state persisted per bucket.

    Carries only a non-negative failure count and the timestamp of the most
    recent failure. It never holds a passphrase, key, or any other secret.

    ``last_failure_at`` is a canonical :data:`~core.time.UtcInstant` because
    the whole backoff is a comparison against it. A bare ``datetime`` admitted
    two shapes the sidecar must never carry: a naive stamp, which made
    :func:`_evaluate_state` raise a raw ``TypeError`` out of the security gate
    rather than clearing, and an offset stamp, which silently shifted the
    deadline by that offset -- a ``+01:00`` value read an hour into the past
    and reported the operator clear to retry while the same instant in UTC was
    still throttled. Refusing both at the model boundary routes such a sidecar
    through the documented unreadable-means-cleared path instead.
    """

    model_config = _STRICT_FROZEN

    schema_version: int = LOGIN_THROTTLE_SCHEMA_VERSION
    consecutive_failures: int = Field(default=0, ge=0)
    last_failure_at: UtcInstant | None = None


class ThrottleEvaluation(BaseModel):
    """Typed outcome of a throttle evaluation at a given instant."""

    model_config = _STRICT_FROZEN

    throttled: bool
    remaining_seconds: NonNegativeInt
    consecutive_failures: NonNegativeInt


def _required_wait_seconds(consecutive_failures: int) -> int:
    """Return the exponential-backoff window (seconds) for a failure count.

    Zero failures impose no wait; otherwise the window is
    ``min(2 ** n, 60)`` with ``n`` the consecutive-failure count.
    """
    if consecutive_failures <= 0:
        return 0
    exponent = min(consecutive_failures, _MAX_BACKOFF_EXPONENT)
    return min(1 << exponent, THROTTLE_BACKOFF_CAP_SECONDS)


def login_throttle_path(*, storage_root: Path, bucket_id: str) -> Path:
    """Return the throttle sidecar path inside the bucket keystore directory."""
    from ..bucket._keystore_paths import keystore_sidecar_path

    return keystore_sidecar_path(storage_root=storage_root, bucket_id=bucket_id, filename=LOGIN_THROTTLE_FILENAME)


def _read_state(path: Path) -> LoginThrottleState:
    """Read the throttle state, treating any unusable file as cleared.

    A missing, unreadable, malformed, or version-mismatched sidecar yields
    a cleared state so the throttle can never permanently lock the operator
    out; the next :func:`record_login_failure` rewrites a canonical file.

    A stamp that is naive or carries a non-UTC offset is malformed in exactly
    this sense: the model refuses it, pydantic reports that as a
    ``ValidationError`` (a ``ValueError``), and it is caught below like any
    other unusable file. The clearing is deliberate rather than incidental --
    a throttle record whose instant cannot be compared is no record at all,
    and the alternative of crashing the security gate is the failure mode
    this module's revocable-cache contract exists to avoid.
    """
    if not path.is_file():
        return LoginThrottleState()
    try:
        state = LoginThrottleState.model_validate_json(path.read_text(encoding=_UTF_8_ENCODING))
    except (OSError, ValueError):
        _log.debug("login throttle sidecar unreadable; treating as cleared path=%s", path)
        return LoginThrottleState()
    if state.schema_version != LOGIN_THROTTLE_SCHEMA_VERSION:
        _log.debug(
            "login throttle sidecar schema mismatch; treating as cleared version=%s",
            state.schema_version,
        )
        return LoginThrottleState()
    return state


def _write_state(path: Path, state: LoginThrottleState) -> None:
    """Persist ``state`` atomically with restrictive permissions."""
    payload = json.dumps(
        state.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
    ).encode(_UTF_8_ENCODING)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_hardened_bytes(path, payload + b"\n")


def _evaluate_state(state: LoginThrottleState, now: datetime) -> ThrottleEvaluation:
    """Evaluate ``state`` at ``now`` without touching disk."""
    failures = state.consecutive_failures
    required = _required_wait_seconds(failures)
    if required == 0 or state.last_failure_at is None:
        return ThrottleEvaluation(throttled=False, remaining_seconds=0, consecutive_failures=failures)
    deadline = state.last_failure_at + timedelta(seconds=required)
    if now >= deadline:
        return ThrottleEvaluation(throttled=False, remaining_seconds=0, consecutive_failures=failures)
    remaining = math.ceil((deadline - now).total_seconds())
    return ThrottleEvaluation(
        throttled=True,
        remaining_seconds=max(0, remaining),
        consecutive_failures=failures,
    )


def evaluate_login_throttle(*, storage_root: Path, bucket_id: str, now: datetime) -> ThrottleEvaluation:
    """Return the remaining backoff wait for a bucket at ``now``.

    Call this BEFORE any Argon2id derivation. ``remaining_seconds`` is zero
    (and ``throttled`` is ``False``) whenever the operator is clear to retry.

    Args:
        storage_root: The Cadrumo storage root owning the bucket keystore.
        bucket_id: Identifier of the bucket whose throttle to evaluate.
        now: UTC timestamp at which the evaluation runs.

    Returns:
        A :class:`ThrottleEvaluation` carrying ``throttled``,
        ``remaining_seconds``, and the current ``consecutive_failures``.
    """
    state = _read_state(login_throttle_path(storage_root=storage_root, bucket_id=bucket_id))
    return _evaluate_state(state, now)


def record_login_failure(*, storage_root: Path, bucket_id: str, now: datetime) -> LoginThrottleState:
    """Increment the consecutive-failure count and stamp ``now``.

    Args:
        storage_root: The Cadrumo storage root owning the bucket keystore.
        bucket_id: Identifier of the bucket whose failure to record.
        now: UTC timestamp of the failed attempt.

    Returns:
        The persisted :class:`LoginThrottleState` after the increment.
    """
    path = login_throttle_path(storage_root=storage_root, bucket_id=bucket_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with exclusive_file_lock(path):
            current = _read_state(path)
            updated = LoginThrottleState(
                schema_version=LOGIN_THROTTLE_SCHEMA_VERSION,
                consecutive_failures=current.consecutive_failures + 1,
                last_failure_at=now,
            )
            _write_state(path, updated)
            return updated
    except (LockAcquisitionError, OSError):
        # Never propagate out of the throttle. This runs inside the caller's
        # authentication-failure handler, so an exception raised here REPLACES
        # the wrong-password error the operator needs to see with a lock or
        # filesystem error about a sidecar they did not ask about. The sibling
        # reset already logs rather than raises for exactly this reason; the
        # increment path simply never adopted it, and on Windows overlapping
        # attempts made that visible by colliding in the atomic rename.
        _log.warning(
            "login throttle increment could not be persisted; the attempt is uncounted path=%s",
            path,
        )
        return _read_state(path)


def reset_login_throttle(*, storage_root: Path, bucket_id: str) -> None:
    """Clear the throttle by removing the sidecar (idempotent).

    Called on a successful login and on logout. A missing sidecar is a clean
    no-op; a removal failure is logged rather than raised so it never breaks
    the success path — the stale window expires by clock regardless.
    """
    path = login_throttle_path(storage_root=storage_root, bucket_id=bucket_id)
    if not path.parent.is_dir():
        return
    try:
        with exclusive_file_lock(path):
            path.unlink(missing_ok=True)
    except (LockAcquisitionError, OSError):
        _log.debug("login throttle sidecar removal failed; window expires by clock path=%s", path)


__all__ = [
    "LOGIN_THROTTLE_FILENAME",
    "LOGIN_THROTTLE_SCHEMA_VERSION",
    "THROTTLE_BACKOFF_CAP_SECONDS",
    "LoginThrottleState",
    "ThrottleEvaluation",
    "evaluate_login_throttle",
    "login_throttle_path",
    "record_login_failure",
    "reset_login_throttle",
]
