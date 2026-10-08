"""Encrypted SQL persistence for the taxpayer's own bank account register.

The :class:`domain.transactions.own_accounts.OwnAccountRegister` document is stored
as a ``FINANCIAL`` secure object through the profile secure-object kernel, in the
singleton namespace
:data:`adapters.persistence.storage.secure_object_namespaces.LEDGER_OWN_ACCOUNTS_NAMESPACE`.

The register is authoritative primary state: the operator enters each own account
and its role designations once, and no other store can answer them. It therefore
has a strict save/load roundtrip and revision-guarded mutation.

See Also:
    :mod:`domain.transactions.own_accounts`
        Typed register payload and its invariants.
    :mod:`adapters.persistence.profile.foreign_assets`
        Sibling register adapter on the same storage kernel.

Core types: :class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectRepository`.
"""

from __future__ import annotations

from collections.abc import Callable

from ....core.errors.hierarchy import CadrumoError
from ....core.logging import get_logger
from ....domain.transactions.own_accounts import OwnAccountRegister, OwnAccountRegisterError
from ..storage.secure_object_namespaces import LEDGER_OWN_ACCOUNTS_NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository
from ._secure_model_document import (
    ProfileBareModelSecurePersistence,
    resolve_profile_secure_object_repository,
)

_log = get_logger(__name__)


class OwnAccountRepository:
    """Governed repository for the encrypted own-account register singleton."""

    def __init__(
        self,
        *,
        bucket_id: str | None = None,
        objects: SecureObjectRepository | None = None,
    ) -> None:
        """Bind the repository to one bucket, or to an explicit secure-object store (tests)."""
        self._storage = ProfileBareModelSecurePersistence(
            objects=resolve_profile_secure_object_repository(objects=objects, bucket_id=bucket_id),
            definition=LEDGER_OWN_ACCOUNTS_NAMESPACE,
            model_type=OwnAccountRegister,
            empty_document=OwnAccountRegister,
        )

    def load(self) -> OwnAccountRegister:
        """Load the register, returning an empty document when none was ever written.

        Raises:
            OwnAccountRegisterError: When the stored envelope cannot be read or decrypted.
        """
        try:
            return self._storage.load()
        except (OSError, CadrumoError) as exc:
            _log.debug(
                "own account register load failed",
                extra={
                    "namespace": self._storage.namespace,
                    "object_key": self._storage.object_key,
                    "error_type": type(exc).__name__,
                },
            )
            raise OwnAccountRegisterError(
                f"unable to load own account register: {self._storage.object_key}",
                context={"namespace": self._storage.namespace, "object_key": self._storage.object_key},
                translated_message="adapters.persistence.profile.own_accounts.errors.load_register_failed",
            ) from exc

    def mutate(self, change: Callable[[OwnAccountRegister], OwnAccountRegister]) -> OwnAccountRegister:
        """Apply ``change`` to the current register and store the result atomically.

        The register is a singleton row: every change rewrites the document, so it
        runs through the revision-guarded unit of work and ``change`` is re-applied
        to the newly current document on a concurrent write. A refusal raised by
        ``change`` propagates without a write.
        """
        return self._storage.mutate(change)


__all__ = ["OwnAccountRepository"]
