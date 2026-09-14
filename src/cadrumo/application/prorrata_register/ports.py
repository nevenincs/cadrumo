"""Application-owned persistence capability for the prorrata register.

The prorrata register service needs the register's complete mutation surface,
while calculation paths only need its read and secure-write capabilities.  This
protocol extends the domain read/write contract with the three atomic mutation
verbs used by the application service, keeping both application consumers
independent from the encrypted-storage adapter.
"""

from __future__ import annotations

from typing import Protocol

from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.prorrata_register.register import (
    ProrrataActivityRow,
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)


class ProrrataRegisterServiceRepositoryProtocol(ProrrataRegisterRepositoryProtocol, Protocol):
    """Complete bucket-bound register capability required by application services."""

    def upsert_entry(self, entry: ProrrataRegisterEntry) -> ProrrataRegister:
        """Atomically add or replace one exercise/sector entry."""
        ...

    def upsert_sector_definition(self, definition: SectorDefinition) -> ProrrataRegister:
        """Atomically add or replace one differentiated-sector definition."""
        ...

    def upsert_activity_row(self, row: ProrrataActivityRow) -> ProrrataRegister:
        """Atomically add or replace one activity row."""
        ...


class ProrrataRegisterRepositoryFactory(Protocol):
    """Construct the bucket-bound register capability for one profile."""

    def __call__(self, *, bucket_id: str) -> ProrrataRegisterServiceRepositoryProtocol:
        """Return the required repository for ``bucket_id``."""
        ...


__all__ = ["ProrrataRegisterRepositoryFactory", "ProrrataRegisterServiceRepositoryProtocol"]
