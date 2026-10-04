"""Application-owned persistence capability for the prorrata register.

The prorrata register service needs the register's complete mutation surface,
while calculation paths only need its read and secure-write capabilities.  This
protocol extends the domain read/write contract with the three atomic mutation
verbs used by the application service, keeping both application consumers
independent from the encrypted-storage adapter.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol, override

from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
from ...domain.prorrata_register.register import (
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)
from ..calculations.observations_repository import ObservationEnvelopePayload


class ProrrataRegisterServiceRepositoryProtocol(ProrrataRegisterRepositoryProtocol, Protocol):
    """Complete bucket-bound register capability required by application services."""

    def upsert_entry(self, entry: ProrrataRegisterEntry) -> ProrrataRegister:
        """Atomically add or replace one exercise/sector entry."""
        ...

    def upsert_sector_definition(self, definition: SectorDefinition) -> ProrrataRegister:
        """Atomically add or replace one differentiated-sector definition."""
        ...

    def seed_sector_carried(
        self,
        ejercicio: int,
        sector_id: str,
        *,
        validate_entry: Callable[[ProrrataRegisterEntry], None],
    ) -> tuple[ProrrataRegister, ProrrataRegisterEntry]:
        """Derive the sector carry from each current CAS candidate and commit it."""
        ...

    def settle_sector(
        self,
        ejercicio: int,
        sector_id: str,
        *,
        con_derecho_volume: Decimal,
        sin_derecho_volume: Decimal,
        producing_snapshot_ref: RegistrySnapshotRef,
        validate_entry: Callable[[ProrrataRegisterEntry], None],
    ) -> tuple[ProrrataRegister, ProrrataRegisterEntry]:
        """Derive definitive sector values from each current CAS candidate."""
        ...

    @override
    def load_revisioned(self) -> tuple[ProrrataRegister, str]:
        """Read the register and the exact revision used for a source-fenced seed."""
        ...

    def commit_whole_carried_seed(
        self,
        register: ProrrataRegister,
        *,
        ejercicio: int,
        expected_revision_id: str,
        source_snapshot: ProrrataPriorSettlementSourceSnapshot,
    ) -> None:
        """Atomically assert source and register revisions while writing the seed."""
        ...


@dataclass(frozen=True, slots=True)
class ProrrataSourceRevision:
    """One source row's revision, including an absent row's absence marker."""

    namespace: str
    object_key: str
    expected_revision_id: str


@dataclass(frozen=True, slots=True)
class ProrrataPriorSettlementSourceSnapshot:
    """Effective prior-year 303 rows and their finite guarded source coordinates."""

    observations: tuple[ObservationEnvelopePayload, ...]
    revisions: tuple[ProrrataSourceRevision, ...]
    backend_identity: object = field(repr=False, compare=False)


class ProrrataPriorSettlementSnapshotRepositoryProtocol(Protocol):
    """Load finite whole-entity 303 settlement sources with their row revisions."""

    def load_prior_m303_settlement_snapshot(self, prior_year: int) -> ProrrataPriorSettlementSourceSnapshot:
        """Read unmembered prior-year terminal quarter/month rows and revisions."""
        ...


class ProrrataRegisterRepositoryFactory(Protocol):
    """Construct the bucket-bound register capability for one profile."""

    def __call__(self, *, bucket_id: str) -> ProrrataRegisterServiceRepositoryProtocol:
        """Return the required repository for ``bucket_id``."""
        ...


__all__ = [
    "ProrrataPriorSettlementSnapshotRepositoryProtocol",
    "ProrrataPriorSettlementSourceSnapshot",
    "ProrrataRegisterRepositoryFactory",
    "ProrrataRegisterServiceRepositoryProtocol",
    "ProrrataSourceRevision",
]
