"""Typed exception hierarchy for the master-key cluster.

Each class carries structured payload so callers can render typed
diagnostics without re-parsing the message string. Every class inherits
from an appropriate base in :mod:`adapters.persistence.storage`
and is bound to a declared :class:`core.errors.ErrorCode` row at
import time via the ``__init_subclass__`` hook.
"""

from __future__ import annotations

from ..errors import SecretStoreError


class MasterKeyReentrantError(SecretStoreError):
    """Raised when a master-key provider context manager is entered re-entrantly.

    The provider is single-entry: a second ``__enter__`` call while an active
    session is already held is a programming error, not a recoverable runtime
    state. The caller must close the outer session before re-entering.
    """

    def __init__(self, provider_name: str) -> None:
        """Initialize this public contract."""
        super().__init__(
            context={"provider_name": provider_name},
            translated_message="errors.internal.internal_master_key_reentrant",
        )
        self.provider_name = provider_name


__all__ = ["MasterKeyReentrantError"]
