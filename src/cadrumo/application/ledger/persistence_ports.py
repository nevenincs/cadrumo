"""Application-owned persistence error vocabulary for ledger actions.

Persistence adapters translate their substrate-specific contention failures to
this error at the ledger boundary.  Ledger services consequently need no
knowledge of the secure-object implementation to preserve guarded retries.
"""

from __future__ import annotations


class LedgerPersistenceConflictError(RuntimeError):
    """A revision-guarded ledger persistence operation lost a race."""


__all__ = ["LedgerPersistenceConflictError"]
