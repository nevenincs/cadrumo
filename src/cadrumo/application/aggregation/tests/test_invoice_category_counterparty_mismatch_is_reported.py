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

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import IntracomOperationType, Period
from ....core.resources import resources
from ....domain.invoices import InvoiceCatalogue
from ....domain.iva import InvoiceKind, IvaCategory
from ...invoices import build_catalogue_invoice
from .._modelo_bindings import (
    _category_counterparty_mismatch_diagnostics,
    _claims_a_base_only_category,
    _screened_invoice_iva_observations,
    _ScreenedInvoiceIva,
)
from .._source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "e5cd70fc-3d46-4768-a775-f9443282596d"  # was 'bucket-category-counterparty-mismatch'
_YEAR = 2024
_PERIOD = "1T"
_BASE = Decimal("4500.00")


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
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        # Clave E: an ordinary entrega intracomunitaria. Stated because the
        # category alone cannot separate E from the exempt-importation claves.
        operation_type=IntracomOperationType.E,
    )
    catalogue = InvoiceCatalogue.from_invoices((invoice,))
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(catalogue)
    return invoice.invoice_id


def _screen(secure_objects: SecureObjectRepository) -> _ScreenedInvoiceIva:
    """Run the real screen, returning its channels as the types they are."""
    snapshot = resources().modelos.authority.snapshot("303", filing_year=_YEAR, period=_PERIOD)
    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        revision=snapshot.revision,
    )
    return _screened_invoice_iva_observations(
        context=context,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        invoice_repository=InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
    )


def test_the_withheld_invoice_is_collected_not_dropped(secure_objects: SecureObjectRepository) -> None:
    """The screen must hand the withheld operation back, not swallow it.

    This is the whole defect in one assertion. The base never reaches a
    casilla, correctly; the question this pins is whether ANYTHING downstream
    can find out that it did not.
    """
    invoice_id = _persist_contradicted_supply(secure_objects)

    screened = _screen(secure_objects)
    compared, mismatches = screened.compared, screened.category_counterparty_mismatches

    assert [invoice.invoice_id for invoice in mismatches] == [invoice_id], (
        "the contradicted supply must be reported as withheld; dropping it silently is the "
        "under-declaration this gate exists to prevent"
    )
    assert [invoice.invoice_id for invoice in compared] != [invoice_id], (
        "it must NOT be reported as compared -- it reached no casilla, so describing its "
        "period placement would assert a declaration that did not happen"
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
    mismatches = _screen(secure_objects).category_counterparty_mismatches

    diagnostics = _category_counterparty_mismatch_diagnostics(mismatches, resolver_id="probe")

    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
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
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        # Clave E: an ordinary entrega intracomunitaria. Stated because the
        # category alone cannot separate E from the exempt-importation claves.
        operation_type=IntracomOperationType.E,
    )
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(
        InvoiceCatalogue.from_invoices((invoice,)),
    )

    mismatches = _screen(secure_objects).category_counterparty_mismatches

    assert mismatches == (), "a Portuguese counterparty supports an intra-community supply"


def test_the_predicate_narrows_to_categories_that_had_a_casilla_to_reach() -> None:
    """A domestic exemption is withheld too, and reporting it would be wrong.

    ``domestic_exempt`` routes nowhere on Modelo 303 whatever its counterparty
    is, so it was never going to reach a casilla and nothing was taken from the
    operator by the counterparty check. Only a category with a base-only
    casilla behind it represents a real loss worth telling them about.
    """
    contradicted = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Zuerich Handel AG",
        counterparty_tax_id="CHE116281838",
        counterparty_country="CH",
        invoice_number="FAC-PREDICATE-IC",
        issued_at=date(_YEAR, 2, 14),
        taxable_base=_BASE,
        iva_rate=Decimal("0"),
        currency="EUR",
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        # Clave E: an ordinary entrega intracomunitaria. Stated because the
        # category alone cannot separate E from the exempt-importation claves.
        operation_type=IntracomOperationType.E,
    )
    domestic = build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Clinica Madrid SL",
        counterparty_tax_id="B58818501",
        counterparty_country="ES",
        invoice_number="FAC-PREDICATE-EXEMPT",
        issued_at=date(_YEAR, 2, 14),
        taxable_base=_BASE,
        iva_rate=Decimal("0"),
        currency="EUR",
        iva_category=IvaCategory.DOMESTIC_EXEMPT,
    )

    assert _claims_a_base_only_category(contradicted) is True
    assert _claims_a_base_only_category(domestic) is False
