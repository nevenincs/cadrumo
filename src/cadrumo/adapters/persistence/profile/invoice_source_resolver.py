"""Outward adapter for the invoice source-mesh read capability.

Core types:
:class:`~cadrumo.domain.invoices.catalogue.InvoiceCatalogue`;
:class:`CalculationRevision`, the saved calculation revision.
"""

from __future__ import annotations

from typing import Protocol, override

from ....application.invoices.source_resolver_ports import (
    CounterpartyProvinciaReader,
    InvoiceSourceCatalogueReader,
    InvoiceSourcePersistenceError,
    M349FiledDeclaration,
    M349FiledDeclarationReader,
)
from ....application.ledger.counterparty_establishment import stated_counterparty_provincia
from ....application.ledger.counterparty_establishment_ports import (
    CounterpartyEstablishmentPersistenceError,
    CounterpartyEstablishmentRepositoryProtocol,
)
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.form_codes import form_for_role
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.modelos.calculation_repository import CalculationRevisionPersistenceError
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionCatalogue,
    CalculationRevisionState,
)
from ....domain.modelos.row_models import Modelo349OperadorRow, Modelo349RectificacionRow
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


class CounterpartyProvinciaAdapter(CounterpartyProvinciaReader):
    """Read the provincia stated for a counterparty from the encrypted counterparty facts."""

    def __init__(self, *, repository: CounterpartyEstablishmentRepositoryProtocol) -> None:
        """Bind an already-composed counterparty-facts repository."""
        self._repository = repository

    @override
    def provincia_of(self, tax_identifier: str) -> str | None:
        """Return the stated provincia while translating storage failures."""
        try:
            return stated_counterparty_provincia(tax_identifier, repository=self._repository)
        except CounterpartyEstablishmentPersistenceError as exc:
            raise InvoiceSourcePersistenceError("counterparty_provincia_load") from exc


class _CalculationCatalogueLoader(Protocol):
    def load(self, *, operation: PinnedAuthorityOperation | None = None) -> CalculationRevisionCatalogue: ...


class M349FiledDeclarationAdapter(M349FiledDeclarationReader):
    """Read what each period's current filed Modelo 349 revision declared.

    A superseded revision no longer states what stands declared, and a filed
    revision is local evidence: its AEAT status may still be pending.
    """

    def __init__(
        self,
        *,
        repository: _CalculationCatalogueLoader,
        operation: PinnedAuthorityOperation | None,
    ) -> None:
        """Bind the calculation repository and the operation's pinned authority."""
        self._repository = repository
        self._operation = operation

    @override
    def load(self) -> tuple[M349FiledDeclaration, ...]:
        """Return one declaration per filed period while translating degradation failures."""
        try:
            catalogue = self._repository.load(operation=self._operation)
        except (CalculationRevisionPersistenceError, *STORAGE_DEGRADATION_ERRORS) as exc:
            raise InvoiceSourcePersistenceError("m349_filed_declarations_load") from exc
        modelo = form_for_role("iva.intracommunity_summary")
        current: dict[Period, CalculationRevision] = {}
        for revision in catalogue.revisions.values():
            ref = revision.registry_snapshot_ref
            if ref.modelo != modelo or revision.state is not CalculationRevisionState.PRESENTADO:
                continue
            period = Period.from_year_and_code(ref.modelo_year, ref.period)
            held = current.get(period)
            if held is None or revision.updated_at > held.updated_at:
                current[period] = revision
        return tuple(
            M349FiledDeclaration(
                period=period,
                rows=tuple(
                    row
                    for row in revision.detail_rows
                    if isinstance(row, Modelo349OperadorRow | Modelo349RectificacionRow)
                ),
            )
            for period, revision in current.items()
        )


__all__ = ["InvoiceCatalogueSourceResolverAdapter", "M349FiledDeclarationAdapter"]
