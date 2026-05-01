"""Secret-store substrate: keyed secret repository on top of blob_store.

Bucket boundary established by audit-4 in the aeat-restructure ADR.
"""

from __future__ import annotations

from ._secret_store import SecretRecord, SecretStore

__all__ = [
    "SecretRecord",
    "SecretStore",
]
