"""Profile-bound canonical invoice intake and actual local commit capabilities."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ...core.errors.hierarchy import CadrumoError
from ...core.field_role import FieldRole
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .catalogue_creation_ports import CatalogueCreationPorts


class InvoiceIntakeCommitConflictError(CadrumoError):
    """An atomic CAS refusal proves that this prepared batch wrote nothing."""


InvoiceIntakeCommit = Callable[[Callable[[], None]], None]
InvoiceIntakeProviderAdmission = Callable[[], None]
InvoiceIntakeColumnMapper = Callable[[Sequence[str]], Sequence[FieldRole] | None]


@dataclass(frozen=True, slots=True)
class InvoiceIntakePorts:
    """Canonical capabilities with immutable owning profile and publication pin."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    creation: Callable[[], CatalogueCreationPorts]
    mapper: InvoiceIntakeColumnMapper
    mapping_reasons: Callable[[], tuple[str, ...]]


class InvoiceIntakePortsFactory(Protocol):
    """Compose lazy outbound capabilities and the exact prepared-write fence."""

    def __call__(
        self,
        *,
        profile_id: UUID,
        operation: PinnedAuthorityOperation,
        commit: InvoiceIntakeCommit,
        admit_provider: InvoiceIntakeProviderAdmission,
    ) -> InvoiceIntakePorts:
        """Bind the exact profile, authority pin and admitted prepared-write callback."""
        ...


__all__ = [
    "InvoiceIntakeColumnMapper",
    "InvoiceIntakeCommit",
    "InvoiceIntakeCommitConflictError",
    "InvoiceIntakePorts",
    "InvoiceIntakePortsFactory",
    "InvoiceIntakeProviderAdmission",
]
