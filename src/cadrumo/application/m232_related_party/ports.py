"""Capabilities the Modelo 232 related-party operations run through.

The composition root binds them inside the admitted profile worker: the
encrypted statement store of the profile and the pinned authority's write
answers.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..aggregation.m232_related_party_repository import Modelo232RelatedPartyWritePorts

__all__ = ["Modelo232RelatedPartyPortsFactory"]


class Modelo232RelatedPartyPortsFactory(Protocol):
    """Compose the read and write capabilities for one admitted profile and pinned authority operation."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> Modelo232RelatedPartyWritePorts:
        """Return the capabilities for ``profile_id`` under ``operation``."""
        ...
