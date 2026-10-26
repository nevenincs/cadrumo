"""Inward invoice-catalogue store shared by verify-path tests.

The verification gates require the complete invoice-catalogue capability even
where a case's modelo or source family keeps it untouched, so the fake holds
real :class:`~cadrumo.domain.invoices.models.Invoice` records rather than
standing in for the catalogue's own behaviour.
"""

from __future__ import annotations

from ....domain.invoices.models import Invoice, InvoiceCatalogue

__all__ = ["InvoiceCatalogueFake"]


class InvoiceCatalogueFake:
    """Protocol-conforming invoice store over real invoice records."""

    def __init__(self, *invoices: Invoice, bucket_id: str | None = None) -> None:
        """Hold ``invoices`` as the persisted catalogue for ``bucket_id``."""
        self._catalogue = InvoiceCatalogue.model_validate(invoices)
        self._bucket_id = bucket_id

    @property
    def bucket_id(self) -> str | None:
        """Return the bucket this store answers for."""
        return self._bucket_id

    def exists(self) -> bool:
        """Report whether a catalogue has been persisted."""
        return bool(self._catalogue.invoices)

    def load(self) -> InvoiceCatalogue:
        """Return the held catalogue."""
        return self._catalogue

    def save(self, catalogue: InvoiceCatalogue) -> None:
        """Replace the held catalogue."""
        self._catalogue = catalogue
