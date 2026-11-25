"""Capabilities the suffered-withholding absence operations run through.

The composition root binds them inside the admitted profile worker: the
encrypted attestation and payer-record stores of the profile and the pinned
authority's write answers.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..aggregation.retencion_soportada_absence_repository import RetencionSoportadaAbsenceWritePorts

__all__ = ["RetencionSoportadaAbsencePortsFactory"]


class RetencionSoportadaAbsencePortsFactory(Protocol):
    """Compose the write capabilities for one admitted profile and pinned authority operation."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> RetencionSoportadaAbsenceWritePorts:
        """Return the capabilities for ``profile_id`` under ``operation``."""
        ...
