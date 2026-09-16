"""Real bucket-session support for storage-adapter tests."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import TYPE_CHECKING

from .....core.time.clock import now
from ..crypto.aead import KEY_SIZE
from ..errors import SecretStoreError
from ..master_key.active_session import activate_session
from ..master_key.bucket_session import BucketSession
from ..master_key.errors import MasterKeyReentrantError

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from types import TracebackType

_IDLE_MINUTES = 60


class EphemeralBucketSession:
    """In-memory session that exercises the real bucket-session lifecycle."""

    def __init__(self, *, key: bytes | None = None) -> None:
        """Construct a session binder with an optional fixed AES-256 data key."""
        if key is None:
            key = secrets.token_bytes(KEY_SIZE)
        if len(key) != KEY_SIZE:
            raise SecretStoreError(
                f"ephemeral data key must be {KEY_SIZE} bytes; got {len(key)}",
            )
        self._key = key
        self.session: BucketSession | None = None
        self.activation_cm: AbstractContextManager[None] | None = None

    @property
    def key(self) -> bytes:
        """Return the in-memory data key this binder activates."""
        return self._key

    def __enter__(self) -> BucketSession:
        if self.session is not None:
            raise MasterKeyReentrantError(type(self).__name__)

        opened_at = now()
        window = timedelta(minutes=_IDLE_MINUTES)
        session = BucketSession.open_resumed(
            bucket_id="ephemeral",
            dek=self._key,
            idle_minutes=_IDLE_MINUTES,
            opened_at=opened_at,
            idle_deadline=opened_at + window,
            absolute_deadline=opened_at + window,
        )
        activation = activate_session(session)
        activation.__enter__()
        self.session = session
        self.activation_cm = activation
        return session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Unbind this activation, then close its session.

        The order matters and is why this is not two independent statements:
        the activation is a scoped binding onto the session, so unwinding it
        first means no binding ever names a closed session. Both handles are
        cleared before either is touched, so a raising teardown cannot leave
        this binder holding a half-torn-down session it would try to reuse.
        """
        activation, self.activation_cm = self.activation_cm, None
        session, self.session = self.session, None
        try:
            if activation is not None:
                activation.__exit__(exc_type, exc, tb)
        finally:
            if session is not None:
                session.close()


__all__ = ["EphemeralBucketSession"]
