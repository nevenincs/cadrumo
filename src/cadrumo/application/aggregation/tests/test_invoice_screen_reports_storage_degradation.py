"""An unreadable invoice catalogue must not look like an empty one.

The invoice catalogue is the IVA source: every invoice accruing in the period
contributes its lines to the declaration. Its load can fail for reasons that are
not the operator's doing: an envelope that will not decrypt, a version the
reader does not know, a storage validation error.

Read as empty, such a failure would file a declaration with every invoiced
operation missing and nothing saying so. The IVA resolver therefore binds the
read error and returns a resolution carrying a ``storage_degraded`` diagnostic
and no values, as its sibling resolvers do. Degrading is still the right
behaviour -- a temporarily unreadable catalogue should not hard-fail every
calculation -- but it must be said.

The fault is injected at the storage boundary because that is the only place a
degraded read can be produced: the failure being exercised is the catch itself,
so the reader must actually raise. Everything downstream of the boundary is the
real production path.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.period import Period
from ....domain.bienes_inversion.register import BienesInversionIvaRegister
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.invoices.catalogue import InvoiceCatalogue
from ...invoices.catalogue_reads_ports import (
    InvoiceCatalogueReader,
    InvoiceCatalogueReadPersistenceError,
    InvoiceCatalogueReadPorts,
)
from ..modelo_bindings_iva import LedgerIvaAggregationSourceResolver
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .ledger_source_mesh_support import (
    BUCKET_ID,
    InMemoryTransactionCatalogueRepository,
    empty_prorrata_repository,
)

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = _YEAR
_PERIOD_CODE = "2T"


class _UnreadableInvoiceCatalogue:
    """A catalogue that exists and cannot be read.

    Fault injection at the I/O boundary, not a stand-in for the code under test:
    the behaviour being exercised IS the resolver's handling of a failed load,
    so the load has to fail. It raises a real production error from the set the
    resolver catches.
    """

    bucket_id: str = BUCKET_ID

    def load(self) -> InvoiceCatalogue:
        raise InvoiceCatalogueReadPersistenceError("invoice_catalogue_load")


class _EmptyInvoiceCatalogue:
    """A bucket that genuinely holds no invoices."""

    bucket_id: str = BUCKET_ID

    def load(self) -> InvoiceCatalogue:
        return InvoiceCatalogue.model_validate({})


def _resolve(invoice_reader: InvoiceCatalogueReader) -> CalculationSourceResolution:
    transactions = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    resolver = LedgerIvaAggregationSourceResolver(
        transaction_repository=transactions,
        invoice_catalogue_read_ports=InvoiceCatalogueReadPorts(
            invoice_reader=invoice_reader,
            transaction_reader=transactions,
        ),
        prorrata_register_repository=empty_prorrata_repository(),
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=BUCKET_ID,
    )
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="303",
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, _PERIOD_CODE),
            revision=published_snapshot("303", filing_year=_YEAR, period=_PERIOD_CODE).revision,
        )
    )


def test_an_unreadable_catalogue_degrades_the_iva_source_instead_of_reading_as_empty() -> None:
    """The resolver says it could not look, and declares nothing from a partial read."""
    resolution = _resolve(_UnreadableInvoiceCatalogue())

    degraded = [diagnostic for diagnostic in resolution.diagnostics if diagnostic.reason == "storage_degraded"]
    assert [diagnostic.source_kind for diagnostic in degraded] == ["ledger_iva_aggregation"], (
        "an unreadable invoice catalogue was reported as an empty one"
    )
    assert not any(resolution.binding_values.values())
    assert resolution.provenance == ()


def test_a_readable_empty_catalogue_is_not_reported_as_degraded() -> None:
    """The negative case, so the diagnostic means what it says.

    A bucket that genuinely holds no invoices must not raise a degradation
    signal. Without this, the signal would fire on every empty bucket and the
    operator would learn to ignore it.
    """
    resolution = _resolve(_EmptyInvoiceCatalogue())

    assert all(diagnostic.reason != "storage_degraded" for diagnostic in resolution.diagnostics)
