"""An invoice withheld for a contradictory counterparty must say so.

The invoice IVA screen routes a cuota-less line to a base-only casilla from the
invoice's own ``iva_category``. Before doing so it checks the counterparty
country can bear that category: an intra-community supply (LIVA art. 25) needs
a counterparty in another member state, and an export (art. 21) needs one
outside the Union.

That check is right, and withholding is the right outcome. An operation tagged
``intra_community_supply`` whose counterparty sits in a third country is not an
intra-community supply whatever it claims, and declaring its base in casilla 59
on the tag alone would put volume on the return the taxpayer never supplied
that way.

What was wrong is that it happened SILENTLY. ``_counterparty_supports_the_declared_category``
returned ``False`` and the line was dropped with nothing on any surface saying
a real, catalogued operation had left the declaration. The bank-transaction
feed returns a typed gate issue for the same shape; this projector returns
observations and simply had no issue channel, so the two feeds into one binding
source disagreed about whether a refusal is reportable.

The advisory is non-blocking on purpose. Calculating still succeeds, because
the withholding is correct and the return is right for the data as recorded --
the operator just now learns that a record they entered was excluded, and which
of its two fields to look at. Blocking would refuse a filing that is otherwise
sound.

Real-behaviour: the real encrypted-SQLite object store, the real
:class:`InvoiceCatalogueRepository`, the real registry authority, and the real
screen. No mocks, stubs, skips, or xfail.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from .....application.aggregation.modelo_bindings import LedgerIvaAggregationSourceResolver
from .....application.aggregation.source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceResolution,
)
from .....application.invoices.catalogue_creation import build_catalogue_invoice
from .....application.invoices.catalogue_reads_ports import InvoiceCatalogueReadPorts
from .....core.aggregation import IntracomOperationType
from .....core.period import Period
from .....domain.bienes_inversion.register import BienesInversionIvaRegister
from .....domain.iva.classification import InvoiceKind
from .....domain.iva.schema import IvaCategory
from .....domain.transactions.models import LedgerDatePartition, TransactionCatalogue
from ....outbound.fx.tests.recorded_ecb_rates import recorded_ecb_rate_provider
from ...storage.sql.secure_objects import SecureObjectRepository
from ..catalogue_reads import InvoiceCatalogueReadAdapter
from ..invoices import InvoiceCatalogueRepository
from ..prorrata_register import ProrrataRegisterRepository
from ..transactions import TransactionCatalogueRepository
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "e5cd70fc-3d46-4768-a775-f9443282596d"  # was 'bucket-category-counterparty-mismatch'
_YEAR = 2024
_PERIOD = "1T"
_BASE = Decimal("4500.00")


class _EmptyTransactionCatalogueReader:
    def load(self) -> TransactionCatalogue:
        return TransactionCatalogue()

    def partition_by_date_range(self, start: date, end: date) -> LedgerDatePartition:
        return LedgerDatePartition(in_window=TransactionCatalogue(), index_complete=True)


def _persist_contradicted_supply(secure_objects: SecureObjectRepository) -> str:
    """Persist one issued invoice whose category its counterparty cannot bear.

    An intra-community supply billed to a Swiss counterparty. Switzerland is
    not an EU member state, so ``intra_community_supply`` is unsupportable for
    this operation -- but the base is a real 4,500 euro of turnover that the
    operator entered and expects to see somewhere.
    """
    invoice = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Zuerich Handel AG",
        counterparty_tax_id="CHE116281838",
        counterparty_country="CH",
        invoice_number=f"FAC-{_YEAR}-CONTRADICTED",
        issued_at=date(_YEAR, 2, 14),
        taxable_base=_BASE,
        iva_rate=Decimal("0"),
        currency="EUR",
        iva_category=IvaCategory("intra_community_supply"),
        # Clave E: an ordinary entrega intracomunitaria. Stated because the
        # category alone cannot separate E from the exempt-importation claves.
        operation_type=IntracomOperationType.E,
        rate_provider=recorded_ecb_rate_provider(),
    )
    catalogue = build_invoice_catalogue((invoice,))
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(catalogue)
    return invoice.invoice_id


def _screen(secure_objects: SecureObjectRepository) -> CalculationSourceResolution:
    """Run the public IVA resolver and return its diagnostic-bearing resolution."""
    snapshot = published_authority_operation().snapshot("303", filing_year=_YEAR, period=_PERIOD)
    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        revision=snapshot.revision,
    )
    return LedgerIvaAggregationSourceResolver(
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        invoice_catalogue_read_ports=InvoiceCatalogueReadPorts(
            invoice_reader=InvoiceCatalogueReadAdapter(
                repository=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
            ),
            transaction_reader=_EmptyTransactionCatalogueReader(),
        ),
        prorrata_register_repository=ProrrataRegisterRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id=_BUCKET_ID,
    ).resolve(context)


def _mismatch_diagnostics(resolution: CalculationSourceResolution) -> tuple[CalculationSourceDiagnostic, ...]:
    """Select the public resolver diagnostics for a contradictory invoice."""
    return tuple(
        diagnostic
        for diagnostic in resolution.diagnostics
        if diagnostic.reason == "invoice_category_counterparty_mismatch"
    )


def test_the_withheld_invoice_is_collected_not_dropped(secure_objects: SecureObjectRepository) -> None:
    """The screen must hand the withheld operation back, not swallow it.

    This is the whole defect in one assertion. The base never reaches a
    casilla, correctly; the question this pins is whether ANYTHING downstream
    can find out that it did not.
    """
    invoice_id = _persist_contradicted_supply(secure_objects)

    mismatches = _mismatch_diagnostics(_screen(secure_objects))

    assert [diagnostic.source_ref for diagnostic in mismatches] == [f"invoice:{invoice_id}"], (
        "the contradicted supply must be reported as withheld; dropping it silently is the "
        "under-declaration this gate exists to prevent"
    )


def test_the_advisory_names_the_invoice_and_both_candidate_fields(
    secure_objects: SecureObjectRepository,
) -> None:
    """The operator must be able to act on it without re-deriving the cause.

    Either field could be the wrong one -- the category may be mis-tagged, or
    the country may be. The record cannot tell which, so the remedy names both
    rather than guessing and sending the operator to the wrong correction.
    """
    _persist_contradicted_supply(secure_objects)
    mismatches = _mismatch_diagnostics(_screen(secure_objects))

    assert len(mismatches) == 1
    diagnostic = mismatches[0]
    assert diagnostic.reason == "invoice_category_counterparty_mismatch"
    assert f"FAC-{_YEAR}-CONTRADICTED" in diagnostic.message, "the operator must know WHICH invoice"
    assert "CH" in diagnostic.message
    remedy = diagnostic.remedy
    assert remedy is not None, "an advisory the operator must act on carries no remedy"
    assert "category" in remedy.lower()
    assert "country" in remedy.lower()


def test_a_supportable_supply_produces_no_advisory(secure_objects: SecureObjectRepository) -> None:
    """The other direction: a correct invoice must not be flagged.

    Without this the gate above is satisfiable by reporting every invoice, and
    an advisory that fires on sound data is noise the operator learns to skip
    -- which is how the report stops being read before it is ever needed.
    """
    invoice = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Lisboa Comercio Lda",
        counterparty_tax_id="PT501442600",
        counterparty_country="PT",
        invoice_number=f"FAC-{_YEAR}-SOUND",
        issued_at=date(_YEAR, 2, 14),
        taxable_base=_BASE,
        iva_rate=Decimal("0"),
        currency="EUR",
        iva_category=IvaCategory("intra_community_supply"),
        # Clave E: an ordinary entrega intracomunitaria. Stated because the
        # category alone cannot separate E from the exempt-importation claves.
        operation_type=IntracomOperationType.E,
        rate_provider=recorded_ecb_rate_provider(),
    )
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(
        build_invoice_catalogue((invoice,)),
    )

    mismatches = _mismatch_diagnostics(_screen(secure_objects))

    assert mismatches == (), "a Portuguese counterparty supports an intra-community supply"
