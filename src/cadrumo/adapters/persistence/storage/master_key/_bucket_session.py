"""Per-bucket instance-scoped unlock state.

`BucketSession` replaces the module-global `ClassVar` caches that once
survived a bucket switch on the shared-master providers, both since
deleted. Each instance binds to exactly one
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

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy.exc import SQLAlchemyError

from .....core.logging import get_logger
from .....core.time import validate_utc_aware
from ..bucket import BucketLockedError
from ..custody import zeroise as _zeroise
from ..errors import (
    storage_validation_error as _storage_validation_error,
)
from ._live_sessions import register_live_session

if TYPE_CHECKING:
    from sqlalchemy import Engine

    from .....core.config import Settings

_KEK_BYTES = 32
_DEK_BYTES = 32
DEFAULT_SESSION_ABSOLUTE_MINUTES = 240
#: Entries kept by the per-session routed-settings memo. Measured need is two
#: -- a profile write asks for the route once inside a settings override and
#: once outside it, alternating -- so the bound is that pair with headroom,
#: not a general-purpose cache size.
_ROUTED_SETTINGS_MEMO_SIZE = 4
_log = get_logger(__name__)


class BucketSession:
    """One per-bucket unlock session.

    The class deliberately holds NO `ClassVar` mutable state. Two
    sessions for two distinct bucket ids own two independent
    `bytearray` buffers and never share key material.
    """

    __slots__ = (
        # Required for the weak registration below: a __slots__ class is not
        # weak-referenceable unless it declares this, and the live-session
        # registry must hold sessions weakly so it never extends the lifetime of
        # the key buffers it exists to destroy.
        "__weakref__",
        "_absolute_deadline",
        "_bucket_id",
        "_dek_buffer",
        "_engine",
        "_hmac_subkeys",
        "_idle_deadline",
        "_idle_window",
        "_kek_available",
        "_kek_buffer",
        "_opened_at",
        "_routed_settings",
        "_sealed",
        "_storage_root",
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
        opened_at: datetime,
        absolute_deadline: datetime,
        unsecured_backend: bool,
        storage_root: Path | None,
        kek_available: bool = True,
    ) -> None:
        self._bucket_id = bucket_id
        self._storage_root = storage_root
        self._kek_available = kek_available
        self._kek_buffer = kek_buffer
        self._dek_buffer = dek_buffer
        self._idle_window = idle_window
        self._idle_deadline = idle_deadline
        self._opened_at = opened_at
        self._absolute_deadline = absolute_deadline
        self._unsecured_backend = unsecured_backend
        self._sealed = False
        self._engine: Engine | None = None
        # Small bounded memo behind :meth:`routed_settings`; see that method
        # for why the scope is the session and not the process, and why one
        # entry was not enough.
        self._routed_settings: dict[str, Settings] = {}
        # Per-context HKDF sub-key memo behind :meth:`hmac_subkey`. Session-
        # scoped for the same reason as the routed-settings memo: the values
        # are derived from this bucket's DEK, so a process-lifetime cache
        # would be bucket-scoped state outliving a bucket switch. Cleared on
        # :meth:`close`, with the same best-effort caveat as the ``dek``
        # property: the cached values are immutable ``bytes`` the language
        # cannot wipe in place.
        self._hmac_subkeys: dict[bytes, bytes] = {}
        # Registered at construction, not at binding: a session owns key buffers
        # from this point on, and the emergency-zeroisation path must cover it
        # whether or not it is ever bound to a context (and whichever thread
        # binds it). Weak, so this never keeps the buffers alive.
        register_live_session(self)

    @classmethod
    def open(
        cls,
        *,
        bucket_id: str,
        kek: bytes,
        dek: bytes,
        idle_minutes: int,
        opened_at: datetime,
        absolute_minutes: int | None = None,
        unsecured_backend: bool = False,
        storage_root: Path | None = None,
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
            absolute_minutes: Absolute session-lifetime cap in minutes,
                fixed at open time as ``opened_at + absolute_minutes``. The
                cap is immutable for the session's life: :meth:`touch`
                clamps the sliding idle deadline to it, so a
                continuously-touched session still seals once the cap is
                reached. Must be a strict positive integer. ``None`` falls
                back to :data:`DEFAULT_SESSION_ABSOLUTE_MINUTES`.
            unsecured_backend: When ``True``, the session was opened
                against an unsecured (non-OS-keychain) backend; callers
                use this flag to emit appropriate warnings.
            storage_root: Canonical local-storage root that supplied the
                bucket key material. ``None`` is reserved for synthetic or
                rootless sessions.

        Returns:
            A new :class:`BucketSession` with the provided credentials and TTL.

        Raises:
            StorageValidationError: When ``bucket_id`` is empty, ``idle_minutes`` or the
                resolved ``absolute_minutes`` is not positive, ``kek`` is not 32 bytes, or
                ``dek`` is not 32 bytes.
        """
        if not bucket_id:
            raise _storage_validation_error("bucket_id must be non-empty")
        if idle_minutes <= 0:
            raise _storage_validation_error("idle_minutes must be a strict positive integer")
        resolved_absolute_minutes = DEFAULT_SESSION_ABSOLUTE_MINUTES if absolute_minutes is None else absolute_minutes
        if resolved_absolute_minutes <= 0:
            raise _storage_validation_error("absolute_minutes must be a strict positive integer")
        if len(kek) != _KEK_BYTES:
            raise _storage_validation_error(f"kek must be exactly {_KEK_BYTES} bytes")
        if len(dek) != _DEK_BYTES:
            raise _storage_validation_error(f"dek must be exactly {_DEK_BYTES} bytes")

        opened_at = validate_utc_aware(opened_at)
        idle_window = timedelta(minutes=idle_minutes)
        absolute_deadline = opened_at + timedelta(minutes=resolved_absolute_minutes)
        # The idle deadline never outlives the absolute cap: clamp the initial
        # window so a session whose idle window would reach past the cap is born
        # already bounded by it.
        idle_deadline = min(opened_at + idle_window, absolute_deadline)
        return cls(
            bucket_id=bucket_id,
            kek_buffer=bytearray(kek),
            dek_buffer=bytearray(dek),
            idle_window=idle_window,
            idle_deadline=idle_deadline,
            opened_at=opened_at,
            absolute_deadline=absolute_deadline,
            unsecured_backend=unsecured_backend,
            storage_root=(storage_root.expanduser().resolve(strict=False) if storage_root is not None else None),
        )

    @classmethod
    def open_resumed(
        cls,
        *,
        bucket_id: str,
        dek: bytes,
        idle_minutes: int,
        opened_at: datetime,
        idle_deadline: datetime,
        absolute_deadline: datetime,
        storage_root: Path | None = None,
    ) -> BucketSession:
        """Re-open a session from a resumed persisted profile session.

        The persisted ``aeat config login`` record session-wraps the DEK
        only: the KEK stays login-scoped and is never placed in the OS
        keychain, so a resumed session legitimately has no KEK. Column
        crypto reads the DEK, so the resumed session is fully functional;
        :attr:`kek` refuses with
        :class:`~adapters.persistence.storage.errors.MasterKeyUnavailableError`
        rather than returning a placeholder.

        Both deadlines come from the resumed record instead of being
        re-derived, so the cross-process session inherits the ORIGINAL
        login's absolute cap and cannot be extended by re-opening.

        Args:
            bucket_id: Non-empty identifier of the resumed bucket.
            dek: 32-byte data-encryption key recovered by unwrapping the
                persisted session record under its keychain session key.
            idle_minutes: Sliding idle window applied by :meth:`touch`.
            opened_at: The ORIGINAL login instant from the record.
            idle_deadline: The record's current sliding idle deadline.
            absolute_deadline: The record's immutable absolute cap.
            storage_root: Canonical local-storage root that owns the bucket.

        Returns:
            A :class:`BucketSession` carrying the resumed DEK and deadlines.

        Raises:
            StorageValidationError: When ``bucket_id`` is empty,
                ``idle_minutes`` is not positive, ``dek`` is not 32 bytes,
                or the idle deadline outlives the absolute deadline.
        """
        if not bucket_id:
            raise _storage_validation_error("bucket_id must be non-empty")
        if idle_minutes <= 0:
            raise _storage_validation_error("idle_minutes must be a strict positive integer")
        if len(dek) != _DEK_BYTES:
            raise _storage_validation_error(f"dek must be exactly {_DEK_BYTES} bytes")
        opened_at = validate_utc_aware(opened_at)
        idle_deadline = validate_utc_aware(idle_deadline)
        absolute_deadline = validate_utc_aware(absolute_deadline)
        if idle_deadline > absolute_deadline:
            raise _storage_validation_error("idle_deadline must not exceed absolute_deadline")
        return cls(
            bucket_id=bucket_id,
            kek_buffer=bytearray(),
            dek_buffer=bytearray(dek),
            idle_window=timedelta(minutes=idle_minutes),
            idle_deadline=idle_deadline,
            opened_at=opened_at,
            absolute_deadline=absolute_deadline,
            unsecured_backend=False,
            storage_root=(storage_root.expanduser().resolve(strict=False) if storage_root is not None else None),
            kek_available=False,
        )

    @property
    def bucket_id(self) -> str:
        return self._bucket_id

    @property
    def storage_root(self) -> Path | None:
        """Return the local-storage root that owns this session's key material."""
        return self._storage_root

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
    def opened_at(self) -> datetime:
        """Return the UTC timestamp at which this session opened."""
        return self._opened_at

    @property
    def absolute_deadline(self) -> datetime:
        """Return the immutable absolute session-lifetime cap.

        Fixed at :meth:`open` as ``opened_at + absolute_minutes`` and never
        refreshed; :meth:`touch` clamps the sliding idle deadline to it.
        """
        return self._absolute_deadline

    @property
    def kek(self) -> bytes:
        """Return an immutable view of the live KEK bytes.

        Raises `BucketLockedError` after `close()` has sealed the
        session, and
        :class:`~adapters.persistence.storage.errors.MasterKeyUnavailableError`
        on a session opened through :meth:`open_resumed`, whose persisted
        record carries the DEK only (the KEK stays login-scoped).
        """
        if self._sealed:
            raise BucketLockedError(bucket_id=self._bucket_id)
        if not self._kek_available:
            from ..errors import MasterKeyUnavailableError

            raise MasterKeyUnavailableError(
                "this bucket session was resumed from a persisted profile session, which "
                "session-wraps the DEK only; the KEK is login-scoped. Run `aeat config login` "
                "to re-authenticate if key-encryption-key material is required.",
                translated_message="errors.auth.auth_storage_master_key_unavailable",
            )
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

    def hmac_subkey(self, context: bytes) -> bytes:
        """Return the HKDF-SHA256 sub-key of this session's DEK for ``context``, memoised.

        The keyed-lookup digest recipe (HKDF sub-key, then HMAC-SHA256 of the
        material) re-derived the sub-key on every call, yet the derivation
        depends only on ``(DEK, context)`` — both constant for the session's
        life. On the secure-object write path that derivation ran several
        times per row and dominated the crypto budget. Memoising it here
        follows the :meth:`routed_settings` precedent: the value is
        bucket-scoped, so its cache must live and die with the session that
        owns the bucket, never at module scope. Distinct ``context`` values
        yield cryptographically independent sub-keys, so entries cannot
        collide across consumers.

        Args:
            context: Stable per-consumer HKDF info bytes distinguishing this
                digest space from every other caller's.

        Returns:
            The 32-byte derived sub-key.

        Raises:
            BucketLockedError: When the session has already been sealed.
        """
        if self._sealed:
            raise BucketLockedError(bucket_id=self._bucket_id)
        cached = self._hmac_subkeys.get(context)
        if cached is None:
            from ..crypto import derive_key

            cached = derive_key(key_material=bytes(self._dek_buffer), salt=b"", context=context)
            self._hmac_subkeys[context] = cached
        return cached

    def touch(self, now: datetime) -> None:
        """Roll the idle deadline forward to `now + idle_window`, clamped to the cap.

        The sliding idle deadline is never advanced past the immutable
        absolute deadline, so continuous activity within the idle window
        cannot extend the session beyond its absolute lifetime cap.
        """
        if self._sealed:
            raise BucketLockedError(bucket_id=self._bucket_id)
        now = validate_utc_aware(now)
        self._idle_deadline = min(now + self._idle_window, self._absolute_deadline)

    def is_expired(self, now: datetime) -> bool:
        """Return whether the idle window or the absolute cap has elapsed at `now`."""
        if self._sealed:
            return True
        now = validate_utc_aware(now)
        return now >= self._idle_deadline or now >= self._absolute_deadline

    def routed_settings(self, source: Settings) -> Settings:
        """Return ``source`` re-routed to this bucket's database, memoised.

        Deriving the bucket route is not cheap: it re-validates the whole
        settings model, and the path validators resolve every configured
        directory against the filesystem -- on Windows, over a hundred
        path-canonicalisation syscalls per derivation. A single profile
        write resolves the route three times (the workflow store, the
        lifecycle store, the profile store each ask for a repository), so
        the same derivation was recomputed from scratch three times over.

        The memo is scoped to the SESSION, not the process, because its
        value is bucket-scoped: the substrate invariant is that no
        module-global mutable state may outlive a bucket switch, and a
        process-lifetime cache keyed on a bucket-scoped value is exactly
        what that forbids. Held here, the derivation dies with the session
        that owns the bucket -- the same lifetime, and the same reasoning,
        as the engine handle :meth:`acquire_engine` registers.

        Keyed on the serialised source rather than its identity: callers
        reach this through :func:`~core.config.load_settings`, which
        returns a fresh instance whenever no override is in scope, so
        identity would miss every time. Serialising costs about a
        thousandth of the derivation it avoids, and equal settings
        provably derive an equal route.

        A few entries are kept rather than one. The memo originally held a
        single slot on the premise that the access pattern is the same
        source asked repeatedly; measurement disproved it. A profile field
        edit asks for this route twice, once under a settings override and
        once outside it, and those two sources alternate strictly -- so a
        one-slot memo had each arm evict the other and served zero hits
        across an entire editing session, recomputing every derivation it
        existed to avoid. The bound stays small because the working set is
        that alternating pair, not an unbounded space of sources.

        Args:
            source: The live :class:`~core.config.Settings` whose non-route
                fields the derived settings preserve.

        Returns:
            A :class:`~core.config.Settings` routed to this session's bucket.

        Raises:
            BucketLockedError: When the session has already been sealed.
        """
        if self._sealed:
            raise BucketLockedError(bucket_id=self._bucket_id)
        from .....core.config import settings_for_active_profile_bucket

        key = source.model_dump_json()
        memoised = self._routed_settings.get(key)
        if memoised is not None:
            return memoised
        derived = settings_for_active_profile_bucket(self._bucket_id, source)
        if len(self._routed_settings) >= _ROUTED_SETTINGS_MEMO_SIZE:
            # Bounded, and evicting the oldest keeps an alternating pair
            # resident rather than letting one arm evict the other.
            self._routed_settings.pop(next(iter(self._routed_settings)))
        self._routed_settings[key] = derived
        return derived

    def acquire_engine(self, settings_factory: Callable[[], Settings]) -> Engine:
        """Lazily acquire and register this bucket's engine on first storage access.

        The session is the single owner of the SQLAlchemy engine
        lifecycle for its bucket: the first storage access within the
        session resolves (or creates) the bucket engine and registers the
        handle here, so :meth:`close` disposes exactly that engine on
        session close or profile switch. Subsequent accesses return the
        already-registered handle.

        The route arrives as a factory rather than a value because the
        handle is cached: every access after the first discards the
        settings it is handed. Building a :class:`~core.config.Settings`
        eagerly to satisfy a call that will not look at it costs a full
        model validation, and the caller has no way to know from the
        outside whether this session has an engine yet. Deferring the
        construction into this method puts that decision where the answer
        is known.

        Args:
            settings_factory: Returns the :class:`~core.config.Settings`
                routing to this bucket's database. Invoked at most once,
                and only when an engine must actually be resolved.

        Returns:
            The :class:`~sqlalchemy.engine.Engine` bound to this session.

        Raises:
            BucketLockedError: When the session has already been sealed.
        """
        if self._sealed:
            raise BucketLockedError(bucket_id=self._bucket_id)
        if self._engine is None:
            from ..sql.engine import get_engine

            self._engine = get_engine(settings_factory())
        return self._engine

    def invalidate_engine(self) -> None:
        """Drop this session's cached engine handle without sealing the session.

        :meth:`acquire_engine` caches its resolved handle for the life of
        the session, so a caller that destroys and later re-materialises
        this bucket's on-disk database out from under a still-open session
        (the profile-reset / bucket-removal path) must invalidate the
        session-level cache too, or the next :meth:`acquire_engine` call
        returns the stale handle bound to a directory that no longer
        exists. This is the session-scoped counterpart of
        :func:`~adapters.persistence.storage.sql.engine.dispose_engines_for_bucket`,
        which only evicts the process-wide engine cache; callers that
        remove a bucket directory while its session may still be active
        must call both. A no-op when no engine has been acquired yet or
        the session is already sealed.
        """
        # The memoised route resolves configured paths against the filesystem,
        # so a caller re-materialising this bucket's directory invalidates that
        # derivation for the same reason it invalidates the engine handle.
        self._routed_settings.clear()
        if self._sealed or self._engine is None:
            return
        from ..sql.engine import dispose_engine_handle

        engine = self._engine
        self._engine = None
        try:
            dispose_engine_handle(engine)
        except SQLAlchemyError as exc:
            _log.debug("bucket session engine invalidation failed error_type=%s", type(exc).__name__)

    def close(self) -> None:
        """Zeroise key buffers, dispose the bucket's engine, and seal the session.

        Idempotent: a second call after the first is a no-op.

        Engine disposal:

        The session owns the engine lifecycle for its bucket. Closing the
        session (on idle expiry, profile switch, or explicit close)
        disposes the engine handle registered at first storage access and
        evicts every cached engine bound to this bucket id, so the next
        consumer that opens a different bucket — or re-opens this one —
        never reuses a stale engine handle. Disposal keys on bucket
        identity, so it never depends on re-deriving a database route from
        live settings.
        """
        if self._sealed:
            return
        _zeroise(self._kek_buffer)
        _zeroise(self._dek_buffer)
        self._sealed = True
        self._routed_settings.clear()
        self._hmac_subkeys.clear()
        self._dispose_engine()

    def _dispose_engine(self) -> None:
        """Dispose the engine(s) bound to this bucket's database."""
        from ..sql.engine import dispose_engine_handle, dispose_engines_for_bucket

        engine = self._engine
        self._engine = None
        try:
            if engine is not None:
                dispose_engine_handle(engine)
            dispose_engines_for_bucket(self._bucket_id)
        except SQLAlchemyError as exc:
            _log.debug("bucket session engine disposal failed error_type=%s", type(exc).__name__)


__all__ = ["DEFAULT_SESSION_ABSOLUTE_MINUTES", "BucketSession"]
