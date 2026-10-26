"""Transaction persistence failure translation that retains integrity and CAS refusals."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING

from ....domain.transactions.errors import LedgerStorageError
from ..storage.errors import (
    BlobIntegrityError,
    ClassificationError,
    EnvelopeVersionError,
    SecureObjectRowIdentityError,
    StorageError,
)

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    pass


_INTEGRITY_REFUSALS = (
    BlobIntegrityError,
    ClassificationError,
    EnvelopeVersionError,
    SecureObjectRowIdentityError,
)


def translating_transaction_storage_failures[**P, R](method: Callable[P, R]) -> Callable[P, R]:
    """Report an unreadable store as a ledger storage failure at the port boundary.

    Callers above the adapter degrade on the domain persistence error; a raw
    storage error would escape that and fail the whole calculation instead.
    """

    @functools.wraps(method)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        from ....application.ledger.persistence_ports import LedgerPersistenceConflictError

        try:
            return method(*args, **kwargs)
        except _INTEGRITY_REFUSALS:
            # Tampered or foreign stored bytes are an integrity refusal, never a
            # degradable read failure.
            raise
        except LedgerPersistenceConflictError:
            # Secure-object revision conflicts inherit both storage and ledger
            # conflict errors. Preserve the ledger conflict at this boundary so
            # application guarded-write retry loops can recognize it.
            raise
        except StorageError as exc:
            raise LedgerStorageError(
                "transaction catalogue storage could not be read",
                context={"operation": getattr(method, "__name__", repr(method))},
            ) from exc

    return wrapper
