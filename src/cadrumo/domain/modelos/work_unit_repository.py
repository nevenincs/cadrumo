"""Public repository contract for the modelo work-unit catalogue."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ._work_unit import WorkUnitCatalogue

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...core import SecureObjectWrite


@runtime_checkable
class WorkUnitCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for the work-unit catalogue."""

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        ...

    def exists(self) -> bool:
        """Return whether a work-unit catalogue object has been persisted."""
        ...

    def load(self) -> WorkUnitCatalogue:
        """Return the persisted :class:`WorkUnitCatalogue` or an empty catalogue if absent."""
        ...

    def load_revisioned(self) -> tuple[WorkUnitCatalogue, str]:
        """Return the catalogue together with its current persistence revision."""
        ...

    def save(self, catalogue: WorkUnitCatalogue) -> None:
        """Persist ``catalogue`` as the encrypted singleton object."""
        ...

    def mutate(self, mutation: Callable[[WorkUnitCatalogue], WorkUnitCatalogue]) -> WorkUnitCatalogue:
        """Apply ``mutation`` to the stored catalogue as one revision-guarded unit of work."""
        ...

    def save_with_secure_object_writes(
        self,
        catalogue: WorkUnitCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
        *,
        expected_revision_id: str | None = None,
    ) -> None:
        """Persist ``catalogue`` plus co-emitted secure-object writes atomically."""
        ...

    def to_secure_object_write(
        self,
        catalogue: WorkUnitCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Return the secure-object upsert for ``catalogue`` without committing it."""
        ...


__all__ = ["WorkUnitCatalogueRepositoryProtocol"]
