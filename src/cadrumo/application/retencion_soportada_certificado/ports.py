"""Capabilities the suffered-withholding certificate operations run through.

The composition root binds them inside the admitted profile worker: the
encrypted repository (which alone holds the profile key ``payer_ref`` is
digested under), the pinned authority's write answers and the profile's own
tax identifier.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.renta.retencion_soportada import RetencionSoportadaIdentity, RetencionSoportadaRecord
from ..aggregation.retencion_soportada_repository import (
    RetencionSoportadaRecordRepository,
    RetencionSoportadaWriteAuthority,
)


class RetencionSoportadaCertificadoRepository(RetencionSoportadaRecordRepository, Protocol):
    """The guarded read, write and removal capability over the per-payer store."""

    def list_revisioned(self, ejercicio: int) -> tuple[tuple[RetencionSoportadaRecord, str], ...]:
        """Return every payer record of ``ejercicio`` beside the revision it was read at."""
        ...

    def delete_revisioned(self, identity: RetencionSoportadaIdentity, *, expected_revision_id: str) -> None:
        """Remove the row at ``identity`` only if it is still at ``expected_revision_id``.

        Raises:
            RetencionSoportadaRevisionConflictError: The row moved or is gone.
        """
        ...


@dataclass(frozen=True, slots=True)
class RetencionSoportadaCertificadoPorts:
    """The capabilities one operation uses, bound to one profile and authority generation."""

    repository: RetencionSoportadaCertificadoRepository
    authority: RetencionSoportadaWriteAuthority
    taxpayer_tax_id: Callable[[], str | None]
    """The profile's own tax identifier, or ``None`` when the profile declares none."""


class RetencionSoportadaCertificadoPortsFactory(Protocol):
    """Compose the capabilities for one admitted profile and pinned authority operation."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> RetencionSoportadaCertificadoPorts:
        """Return the capabilities for ``profile_id`` under ``operation``."""
        ...


__all__ = [
    "RetencionSoportadaCertificadoPorts",
    "RetencionSoportadaCertificadoPortsFactory",
    "RetencionSoportadaCertificadoRepository",
]
