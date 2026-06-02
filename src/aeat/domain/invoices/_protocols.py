"""Domain-level repository Protocol for the invoice catalogue.

Application-layer code that persists or loads the :class:`InvoiceCatalogue`
depends on this Protocol, not on the concrete adapter-backed
``InvoiceCatalogueRepository``. This keeps the domain layer free of
adapter imports while still providing a typed port surface.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ._models import InvoiceCatalogue


@runtime_checkable
class InvoiceCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for the invoice catalogue.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket invoice catalogue satisfies this protocol. The concrete
    secure-object-backed implementation lives in the adapter layer.
    """

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        ...

    def exists(self) -> bool:
        """Return whether an invoice catalogue has been persisted."""
        ...

    def load(self) -> InvoiceCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Returns:
            The :class:`InvoiceCatalogue` loaded from storage.
        """
        ...

    def save(self, catalogue: InvoiceCatalogue) -> None:
        """Persist ``catalogue`` atomically under the file lock.

        Args:
            catalogue: The :class:`InvoiceCatalogue` to persist.
        """
        ...


__all__ = ["InvoiceCatalogueRepositoryProtocol"]
