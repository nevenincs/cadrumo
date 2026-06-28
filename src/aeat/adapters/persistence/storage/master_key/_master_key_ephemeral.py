"""Ephemeral in-memory master-key provider."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from .....core.time import now
from ..crypto._crypto import KEY_SIZE
from ..errors import SecretStoreError

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from types import TracebackType

    from ._bucket_session import BucketSession

__all__ = ["EphemeralMasterKeyProvider"]


class EphemeralMasterKeyProvider:
    """In-memory master-key provider used exclusively by tests."""

    def __init__(self, *, key: bytes | None = None) -> None:
        """Construct a provider with an optional fixed key."""
        if key is None:
            key = secrets.token_bytes(KEY_SIZE)
        if len(key) != KEY_SIZE:
            raise SecretStoreError(
                f"ephemeral master key must be {KEY_SIZE} bytes; got {len(key)}",
            )
        self._key = key
        self._session: BucketSession | None = None
        self._activation_cm: AbstractContextManager[None] | None = None

    def get_master_key(self) -> bytes:
        """Return the in-memory master key minted for this provider instance."""
        return self._key

    def provision_master_key(self) -> bytes:
        """Return the in-memory key without minting fresh material."""
        return self._key

    def __enter__(self) -> object:
        if self._session is not None:
            from ._errors import MasterKeyReentrantError

            raise MasterKeyReentrantError(type(self).__name__)

        from ._active_session import activate_session
        from ._bucket_session import BucketSession

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
        self._session = session
        self._activation_cm = activation
        return session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        activation = self._activation_cm
        session = self._session
        self._activation_cm = None
        self._session = None
        if activation is not None:
            activation.__exit__(exc_type, exc, tb)
        if session is not None:
            session.close()
