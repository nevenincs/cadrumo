"""Real master-key provider support shared by storage tests."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from ..adapters.persistence.storage import KEY_SIZE, SecretStoreError
from ..adapters.persistence.storage.master_key import (
    BucketSession,
    MasterKeyReentrantError,
    activate_session,
)
from ..core.time import now

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from types import TracebackType


class EphemeralMasterKeyProvider:
    """In-memory provider that exercises the real bucket-session lifecycle."""

    def __init__(self, *, key: bytes | None = None) -> None:
        """Construct a provider with an optional fixed AES-256 key."""
        if key is None:
            key = secrets.token_bytes(KEY_SIZE)
        if len(key) != KEY_SIZE:
            raise SecretStoreError(
                f"ephemeral master key must be {KEY_SIZE} bytes; got {len(key)}",
            )
        self._key = key
        self.session: BucketSession | None = None
        self._activation_cm: AbstractContextManager[None] | None = None

    def get_master_key(self) -> bytes:
        """Return the in-memory master key minted for this provider instance."""
        return self._key

    def provision_master_key(self) -> bytes:
        """Return the in-memory key without minting fresh material."""
        return self._key

    def __enter__(self) -> object:
        if self.session is not None:
            raise MasterKeyReentrantError(type(self).__name__)

        session = BucketSession.open(
            bucket_id="ephemeral",
            kek=self._key,
            dek=self._key,
            idle_minutes=60,
            opened_at=now(),
            unsecured_backend=False,
        )
        activation = activate_session(session)
        activation.__enter__()
        self.session = session
        self._activation_cm = activation
        return session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Unbind this provider's activation, then close its session.

        The order matters and is why this is not two independent statements:
        the activation is a scoped binding onto the session, so unwinding it
        first means no binding ever names a closed session. Both handles are
        cleared before either is touched, so a raising teardown cannot leave
        this provider holding a half-torn-down session it would try to reuse.
        """
        activation, self._activation_cm = self._activation_cm, None
        session, self.session = self.session, None
        try:
            if activation is not None:
                activation.__exit__(exc_type, exc, tb)
        finally:
            if session is not None:
                session.close()


__all__ = ["EphemeralMasterKeyProvider"]
