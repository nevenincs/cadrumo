"""Domain-level repository Protocol for the invoice catalogue.

Application-layer code that persists or loads the :class:`InvoiceCatalogue`
depends on :class:`~cadrumo.domain.invoices.InvoiceCatalogueRepositoryProtocol`,
not on the concrete secure-object-backed :class:`InvoiceCatalogueRepository`.
This keeps callers typed against the narrow port while the concrete repository
owns the adapter integration.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import InvoiceCatalogue


@runtime_checkable
class InvoiceCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for the invoice catalogue.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket :class:`InvoiceCatalogue` satisfies this protocol. The production
    implementation is :class:`InvoiceCatalogueRepository`.
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
