"""Per-bucket instance-scoped unlock state.

`BucketSession` replaces the module-global `ClassVar` caches that
previously survived a bucket switch on `KeyringMasterKeyProvider` and
`FileFallbackMasterKeyProvider`. Each instance binds to exactly one
`bucket_id`; the unlocked KEK and DEK are held in `bytearray` buffers
so `close()` can overwrite the bytes in place before the references are
dropped. The session is the only object that holds cleartext key
material on the master-key surface; the substrate invariant
forbids any module-global mutable state that could survive a bucket
switch.

The `bytearray` zeroisation is best-effort. Python may have produced
short-lived `bytes` copies of the buffers when callers materialised the
`kek` / `dek` properties; the garbage collector owns the lifetime of
those copies. The contract is documented honestly so callers do not
assume Python guarantees a deeper wipe than the language can deliver.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from .....core.errors import CoreValidationError
from .....core.logging import get_logger
from ..bucket._errors import BucketLockedError
from ..errors import (
    storage_validation_error as _storage_validation_error,
)
from ._zeroise import zeroise as _zeroise

_KEK_BYTES = 32
_DEK_BYTES = 32
_log = get_logger(__name__)


class BucketSession:
    """One per-bucket unlock session.

    The class deliberately holds NO `ClassVar` mutable state. Two
    sessions for two distinct bucket ids own two independent
    `bytearray` buffers and never share key material.
    """

    __slots__ = (
        "_bucket_id",
        "_dek_buffer",
        "_idle_deadline",
        "_idle_window",
        "_kek_buffer",
        "_sealed",
        "_unsecured_backend",
    )

    def __init__(
        self,
        *,
        bucket_id: str,
        kek_buffer: bytearray,
        dek_buffer: bytearray,
        idle_window: timedelta,
        idle_deadline: datetime,
        unsecured_backend: bool,
    ) -> None:
        self._bucket_id = bucket_id
        self._kek_buffer = kek_buffer
        self._dek_buffer = dek_buffer
        self._idle_window = idle_window
        self._idle_deadline = idle_deadline
        self._unsecured_backend = unsecured_backend
        self._sealed = False

    @classmethod
    def open(
        cls,
        *,
        bucket_id: str,
        kek: bytes,
        dek: bytes,
        idle_minutes: int,
        opened_at: datetime,
        unsecured_backend: bool = False,
    ) -> BucketSession:
        """Open a session for one bucket.

        Args:
            bucket_id: Non-empty identifier of the bucket being unlocked.
            kek: 32-byte Argon2id-derived key-encryption key.
            dek: 32-byte data-encryption key recovered by unwrapping the
                bucket's wrapped DEK under the KEK.
            idle_minutes: Idle-timeout window in minutes; must be a
                strict positive integer.
            opened_at: UTC timestamp at which the session opened.
            unsecured_backend: When ``True``, the session was opened
                against an unsecured (non-OS-keychain) backend; callers
                use this flag to emit appropriate warnings.

        Returns:
            A new :class:`BucketSession` with the provided credentials and TTL.

        Raises:
            StorageValidationError: When ``bucket_id`` is empty, ``idle_minutes`` is not
                positive, ``kek`` is not 32 bytes, or ``dek`` is not 32 bytes.
        """
        if not bucket_id:
            raise _storage_validation_error("bucket_id must be non-empty")
        if idle_minutes <= 0:
            raise _storage_validation_error("idle_minutes must be a strict positive integer")
        if len(kek) != _KEK_BYTES:
            raise _storage_validation_error(f"kek must be exactly {_KEK_BYTES} bytes")
        if len(dek) != _DEK_BYTES:
            raise _storage_validation_error(f"dek must be exactly {_DEK_BYTES} bytes")

        idle_window = timedelta(minutes=idle_minutes)
        return cls(
            bucket_id=bucket_id,
            kek_buffer=bytearray(kek),
            dek_buffer=bytearray(dek),
            idle_window=idle_window,
            idle_deadline=opened_at + idle_window,
            unsecured_backend=unsecured_backend,
        )

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def unsecured_backend(self) -> bool:
        return self._unsecured_backend

    @property
    def idle_deadline(self) -> datetime:
        return self._idle_deadline

    @property
    def kek(self) -> bytes:
        """Return an immutable view of the live KEK bytes.

        Raises `BucketLockedError` after `close()` has sealed the
        session.
        """
        if self._sealed:
            raise BucketLockedError(bucket_id=self._bucket_id)
        return bytes(self._kek_buffer)

    @property
    def dek(self) -> bytes:
        """Return an immutable view of the live DEK bytes.

        Raises `BucketLockedError` after `close()` has sealed the
        session.
        """
        if self._sealed:
            raise BucketLockedError(bucket_id=self._bucket_id)
        return bytes(self._dek_buffer)

    def touch(self, now: datetime) -> None:
        """Reset the idle-timeout deadline to `now + idle_window`."""
        if self._sealed:
            raise BucketLockedError(bucket_id=self._bucket_id)
        self._idle_deadline = now + self._idle_window

    def is_expired(self, now: datetime) -> bool:
        """Return whether the idle window has elapsed at `now`."""
        if self._sealed:
            return True
        return now >= self._idle_deadline

    def close(self) -> None:
        """Zeroise key buffers, evict the bucket's engine, and seal the session.

        Idempotent: a second call after the first is a no-op.

        Engine eviction:

        The SQLAlchemy engine for this bucket's database
        (``sqlite:///<aeat_local_storage_root>/buckets/<bucket_id>/db/aeat.db``)
        is removed from the process-wide engine cache so the next
        consumer that opens a different bucket does not accidentally
        reuse this bucket's engine handle. The lookup is conservative:
        the targeted dispose runs through the central active-profile
        route helper; when an explicit database URL prevents deriving
        a bucket route, every cached engine is disposed instead.
        """
        if self._sealed:
            return
        _zeroise(self._kek_buffer)
        _zeroise(self._dek_buffer)
        self._sealed = True
        self._evict_engine()

    def _evict_engine(self) -> None:
        """Dispose the SQLAlchemy engine bound to this bucket's database."""
        from .....core.config import load_settings, settings_for_active_profile_bucket
        from ..sql.engine import dispose_engine

        try:
            settings = settings_for_active_profile_bucket(self._bucket_id, load_settings())
        except (CoreValidationError, ValidationError) as exc:
            _log.debug(
                "bucket session targeted engine eviction unavailable error_type=%s",
                type(exc).__name__,
            )
            _evict_all_engines()
            return
        try:
            dispose_engine(settings)
        except SQLAlchemyError as exc:
            _log.debug("bucket session targeted engine eviction failed error_type=%s", type(exc).__name__)


def _evict_all_engines() -> None:
    """Dispose every cached SQLAlchemy engine when a targeted route is unavailable."""
    from ..sql.engine import dispose_engine

    try:
        dispose_engine()
    except SQLAlchemyError as exc:
        _log.debug("bucket session fallback engine eviction failed error_type=%s", type(exc).__name__)


__all__ = ["BucketSession"]
