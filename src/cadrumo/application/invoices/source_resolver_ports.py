"""Application-owned capabilities for invoice source resolution.

The invoice source-mesh resolver needs only a read projection of the invoice
catalogue.  The application owns that narrow capability and its translated
persistence failure; an outer composition root binds the encrypted repository
adapter for each bucket.

Core types:
:class:`~cadrumo.domain.invoices.catalogue.InvoiceCatalogue`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ...core.errors.hierarchy import CadrumoError
from ...core.period import Period
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.modelos.row_models import Modelo349OperadorRow, Modelo349RectificacionRow


class InvoiceSourcePersistenceError(CadrumoError):
    """Translated failure while reading the invoice source catalogue."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details."""
        self.operation = operation
        super().__init__(f"invoice source persistence operation failed: {operation}")


class InvoiceSourceCatalogueReader(Protocol):
    """Read the bucket-bound invoice catalogue used by source resolution."""

    def load(self) -> InvoiceCatalogue:
        """Return the validated invoice catalogue for the composed bucket."""
        ...


@dataclass(frozen=True, slots=True)
class M349FiledDeclaration:
    """The operator and rectification records of one Modelo 349 recorded as filed."""

    period: Period
    rows: tuple[Modelo349OperadorRow | Modelo349RectificacionRow, ...]


class M349FiledDeclarationReader(Protocol):
    """Read the Modelo 349 declarations recorded as filed for the composed bucket."""

    def load(self) -> tuple[M349FiledDeclaration, ...]:
        """Return each period's current filed records; raise the translated failure when unreadable."""
        ...


@dataclass(frozen=True, slots=True)
class InvoiceSourceResolverPorts:
    """Capabilities for one invoice source-mesh resolver.

    ``m349_filed_declarations`` is absent where a composition never calculates a
    declaration, such as the overview's applicability read. A correction of an
    earlier Modelo 349 period then has no known declared base, and is refused.
    """

    catalogue_reader: InvoiceSourceCatalogueReader
    m349_filed_declarations: M349FiledDeclarationReader | None = None


__all__ = [
    "InvoiceSourceCatalogueReader",
    "InvoiceSourcePersistenceError",
    "InvoiceSourceResolverPorts",
    "M349FiledDeclaration",
    "M349FiledDeclarationReader",
]
