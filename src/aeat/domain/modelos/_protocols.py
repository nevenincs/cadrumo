"""Domain-level repository Protocols for the modelos aggregate.

Application-layer code that persists or loads modelo work-unit catalogues,
filing records, calculation results, or verification reports depends on these
Protocols, not on the concrete adapter-backed repository classes. This keeps
the domain layer free of adapter imports while still providing typed port surfaces.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ._work_unit import WorkUnit, WorkUnitCatalogue


@runtime_checkable
class WorkUnitCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for the work-unit catalogue.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket work-unit catalogue satisfies this protocol. The concrete
    secure-object-backed implementation lives in ``_repository.py``.
    """

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        ...

    def exists(self) -> bool:
        """Return whether a work-unit catalogue object has been persisted."""
        ...

    def load(self) -> WorkUnitCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent."""
        ...

    def save(self, catalogue: WorkUnitCatalogue) -> None:
        """Persist ``catalogue`` as the encrypted singleton object."""
        ...


__all__ = ["WorkUnitCatalogueRepositoryProtocol"]
