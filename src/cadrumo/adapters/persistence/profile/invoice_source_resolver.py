"""Outward adapter for the invoice source-mesh read capability.

Core types:
:class:`~cadrumo.domain.invoices.models.InvoiceCatalogue`.
"""

from __future__ import annotations

from typing import override

from ....application.invoices.source_resolver_ports import (
    InvoiceSourceCatalogueReader,
    InvoiceSourcePersistenceError,
)
from ....domain.invoices.models import InvoiceCatalogue
from ..storage.errors import STORAGE_DEGRADATION_ERRORS
from .invoices import InvoiceCatalogueRepository


class InvoiceCatalogueSourceResolverAdapter(InvoiceSourceCatalogueReader):
    """Translate the encrypted invoice repository to the application read port."""

    def __init__(self, *, repository: InvoiceCatalogueRepository) -> None:
        """Bind an already-composed invoice repository."""
        self._repository = repository

    @override
    def load(self) -> InvoiceCatalogue:
        """Load the catalogue while translating degradation failures."""
        try:
            return self._repository.load()
        except STORAGE_DEGRADATION_ERRORS as exc:
            raise InvoiceSourcePersistenceError("invoice_catalogue_load") from exc


__all__ = ["InvoiceCatalogueSourceResolverAdapter"]
