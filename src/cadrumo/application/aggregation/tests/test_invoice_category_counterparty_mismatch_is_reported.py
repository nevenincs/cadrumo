"""Pure classification coverage for counterparty/category routing.

The persistence-backed mismatch and diagnostic scenarios live with the profile
persistence adapter.  This inward test keeps the structural rule that a
category with no reachable declaration casilla cannot be reported as a
counterparty mismatch.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.aggregation import IntracomOperationType
from ....domain.calculations.registry.ledger_iva_bindings import structurally_unroutable_iva_base_categories
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ....tests.recorded_ecb_rates import recorded_ecb_rate_provider
from ...invoices.catalogue_creation import build_catalogue_invoice

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "e5cd70fc-3d46-4768-a775-f9443282596d"
_YEAR = 2024
_PERIOD = "1T"
_BASE = Decimal("4500.00")


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
        iva_category=IvaCategory("intra_community_supply"),
        # Clave E: an ordinary entrega intracomunitaria. Stated because the
        # category alone cannot separate E from the exempt-importation claves.
        operation_type=IntracomOperationType.E,
        rate_provider=recorded_ecb_rate_provider(),
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
        iva_category=IvaCategory("domestic_exempt"),
        rate_provider=recorded_ecb_rate_provider(),
    )

    revision = published_snapshot("303", filing_year=_YEAR, period=_PERIOD).revision
    unroutable = frozenset(structurally_unroutable_iva_base_categories(revision))
    assert contradicted.iva_category not in unroutable
    assert domestic.iva_category in unroutable
