"""An exempt line carries a base the declaration needs, and no cuota.

The invoice IVA screen builds one observation per invoice line. It skipped every
line whose cuota was zero or less, which reads as a sensible "nothing to
declare" filter and is not one: a line's cuota being zero says nothing about
whether its BASE is declarable.

Exempt operations (LIVA art. 20), intra-community supplies (art. 25) and
issued-side reverse charge all carry a real base with a cuota that is zero BY
LAW. The component table says so outright -- `domestic_exempt` and
`intra_community_supply` are both ``base=required, cuota=zero_by_law`` -- and
Modelo 303 declares those bases in its own base-only casillas.

So the filter dropped exactly the lines whose base is the only thing they were
ever going to contribute.

CORRECTION, recorded because the first version of this module claimed more than
it delivered: keeping the line does NOT by itself put an exempt base on Modelo
303. The screen classifies from the RATE SLOT, so an exempt line becomes
``domestic_exempt``/``exempt`` while casilla 59 selects
``intra_community_supply``/``zero`` and casilla 60 the export categories -- a
miss on both axes. No M303 binding selects ``domestic_exempt``, so the
observation routes nowhere rather than into a wrong casilla: inert, not harmful.

These tests therefore assert exactly what the predicate does -- that a
declarable line is retained -- and deliberately do NOT assert that a casilla is
populated, because it is not. The routing fix is to construct the observation
from the invoice's own category the way the bank-transaction path already does.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....domain.invoices.enums import IvaRate
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.components import category_components
from ....domain.iva.invoice_classification import invoice_line_to_iva_observation
from ....domain.iva.schema import IvaCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("category", "rate"),
    [
        (IvaCategory.DOMESTIC_EXEMPT, IvaRate.EXEMPT),
        (IvaCategory.INTRA_COMMUNITY_SUPPLY, IvaRate.EXEMPT),
    ],
)
def test_a_zero_cuota_category_still_requires_its_base(category: IvaCategory, rate: IvaRate) -> None:
    """The component table is the authority, and it says the base is required.

    Asserted against the table rather than against a hand-written expectation,
    so this stays true if the taxonomy changes: whatever the table declares
    ``base=required, cuota=zero_by_law`` for is a category whose line MUST reach
    the declaration despite carrying no cuota.
    """
    components = category_components(category, InvoiceKind.ISSUED)

    assert components.base.value == "required", f"{category.value} should require a base"
    assert components.cuota.value == "zero_by_law", f"{category.value} should carry no cuota by law"


def test_an_exempt_line_builds_a_declarable_observation() -> None:
    """The observation the screen declined to build is perfectly valid.

    This is what makes the omission a loss rather than a refusal. Nothing about
    the line is malformed -- it classifies, it carries its base, and the
    classifier hands back exactly the record Modelo 303 wants for an exempt
    operation. The screen simply never asked for it.
    """
    observation = invoice_line_to_iva_observation(
        invoice_id="invoice:exempt-line-proof:0",
        issued_at=date(2026, 2, 10),
        invoice_kind=InvoiceKind.ISSUED,
        iva_rate=IvaRate.EXEMPT,
        base_amount=Decimal("1000.00"),
        iva_amount=Decimal("0"),
        deduction_fact_kind=None,
        deduction_provenance=None,
        recargo_amount=Decimal("0"),
    )

    assert observation.category is IvaCategory.DOMESTIC_EXEMPT
    assert observation.base_amount == Decimal("1000.00")
    assert observation.iva_amount == Decimal("0")


def test_the_screen_keeps_a_line_whose_only_contribution_is_its_base() -> None:
    """The regression guard: a cuota-less line must not be filtered out.

    The predicate under test is the screen's own skip condition. A line
    contributes when it carries a base OR a cuota; screening on the cuota alone
    drops every exempt and intra-community line in the catalogue, and the
    resulting declaration understates the exempt base by the whole amount
    without any surface reporting it.

    Written against the boundary values rather than one example: a line with
    neither a base nor a cuota is the ONLY shape that genuinely contributes
    nothing, and it is the only one this filter may drop.
    """
    exempt_base_only = (Decimal("1000.00"), Decimal("0"))
    ordinary_rated = (Decimal("1000.00"), Decimal("210.00"))
    contributes_nothing = (Decimal("0"), Decimal("0"))

    def contributes(base: Decimal, cuota: Decimal) -> bool:
        """Mirror of the screen's retention rule, asserted below against it."""
        return base > Decimal("0") or cuota > Decimal("0")

    assert contributes(*exempt_base_only), "an exempt line's base is declarable and must be kept"
    assert contributes(*ordinary_rated)
    assert not contributes(*contributes_nothing), "an empty line is the only one safe to drop"

    from .._modelo_bindings_invoice_iva import line_contributes_to_the_iva_screen

    assert line_contributes_to_the_iva_screen(*exempt_base_only) is True
    assert line_contributes_to_the_iva_screen(*ordinary_rated) is True
    assert line_contributes_to_the_iva_screen(*contributes_nothing) is False
