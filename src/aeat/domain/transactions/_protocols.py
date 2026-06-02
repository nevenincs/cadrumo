"""Domain-level repository Protocol for the transaction catalogue.

Application-layer code that persists or loads the :class:`TransactionCatalogue`
depends on this Protocol, not on the concrete adapter-backed
``TransactionCatalogueRepository``. This keeps the domain layer free of
adapter imports while still providing a typed port surface.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ._models import TransactionCatalogue


@runtime_checkable
class TransactionCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for the transaction catalogue.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket transaction catalogue satisfies this protocol. The concrete
    secure-object-backed implementation lives in the adapter layer.
    """

    @property
    def bucket_id(self) -> str:
        """Return the profile bucket id this repository is bound to."""
        ...

    def exists(self) -> bool:
        """Return whether this bucket's transaction catalogue has been persisted."""
        ...

    def load(self) -> TransactionCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Returns:
            The :class:`TransactionCatalogue` loaded from storage.
        """
        ...

    def save(self, catalogue: TransactionCatalogue) -> None:
        """Persist ``catalogue`` in the encrypted database object store.

        Args:
            catalogue: The :class:`TransactionCatalogue` to persist.
        """
        ...


__all__ = ["TransactionCatalogueRepositoryProtocol"]
