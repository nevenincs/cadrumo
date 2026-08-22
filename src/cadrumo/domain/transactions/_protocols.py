"""Domain-level repository Protocol for the transaction catalogue.

Application-layer code that persists or loads the :class:`TransactionCatalogue`
depends on :class:`TransactionCatalogueRepositoryProtocol`, not on the concrete
adapter-backed :class:`TransactionCatalogueRepository`. This keeps the domain
layer free of adapter imports while still providing a typed port surface.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Protocol, runtime_checkable

from ._models import LedgerDatePartition, TransactionCatalogue


@runtime_checkable
class TransactionCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for the transaction catalogue.

    Any object that provides ``exists``, ``load``, ``load_by_ids``, ``load_for_date_range``,
    ``partition_by_date_range``, and ``save`` over a per-bucket
    :class:`TransactionCatalogue` satisfies this protocol. The concrete
    secure-object-backed implementation is :class:`TransactionCatalogueRepository`.
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

    def load_for_date_range(self, start: date, end: date) -> TransactionCatalogue:
        """Return the persisted catalogue filtered to ``[start, end]`` inclusive.

        Implementations MAY use a non-sensitive routing index to select
        candidate rows before decrypting, but MUST always return the same
        result :meth:`load` filtered by filing date would return.

        Args:
            start: Inclusive lower bound of the filing-date window.
            end: Inclusive upper bound of the filing-date window.
        """
        ...

    def load_by_ids(self, transaction_ids: Iterable[str]) -> TransactionCatalogue:
        """Return only the encrypted rows addressed by ``transaction_ids``.

        Missing identifiers are omitted, matching a full catalogue lookup,
        while every returned row still passes schema and addressed-row identity
        validation.
        """
        ...

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        """Split the persisted catalogue into an in-window half and an out-of-window remainder.

        Implementations MAY use a non-sensitive routing index to decide the
        split without decrypting the out-of-window half, but MUST always
        return the same in-window transaction set :meth:`load` filtered by
        filing date would return. They MUST also represent every remaining
        catalogue transaction (regardless of any other field) either as
        row-level out-of-window index entries during migration or as the compact
        count/date-span summary -- never silently omit one from either half.
        Summary payloads must carry only
        plaintext date-index facts, never decrypted transaction fields.

        Args:
            start: Inclusive lower bound of the filing-date window.
            end: Inclusive upper bound of the filing-date window.
        """
        ...

    def save(self, catalogue: TransactionCatalogue) -> None:
        """Persist ``catalogue`` in the encrypted database object store.

        Args:
            catalogue: The :class:`TransactionCatalogue` to persist.
        """
        ...


__all__ = ["TransactionCatalogueRepositoryProtocol"]
