"""The SUPPLIER's side of a domestic reverse charge must reach casilla 122.

Under LIVA art. 84.Uno.2.º the RECIPIENT is the sujeto pasivo, so the supplier
makes a sujeta y no exenta supply and repercutes nothing. There is correctly no
cuota on this side. But the operation is turnover, and Modelo 303 asks for it by
name: casilla 122, "Operaciones sujetas con inversión del sujeto pasivo",
página 3 of the diseño at byte offset 63.

It reached nothing. The box existed, sat at its correct offset and was wired
into the export layout -- only the binding was missing, so a real reverse-charge
sale left volumen de operaciones understated by its full amount.

The binding alone would not have fixed it, which is the part worth keeping. The
line carries no cuota, so it fell past the standard branch, which classifies
from the RATE SLOT and therefore replaced ``domestic_reverse_charge`` with
whatever tier the slot printed. The identity the binding selects on was
destroyed upstream of the binding, and a binding-only change would have left the
box blank while looking like the registry was at fault.

Asserted at the resolved BINDING VALUES rather than at the observation, for the
reason the intra-community sibling file states: an observation that classifies
correctly and still matches no selector is exactly the failure worth catching.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.invoices import Invoice, IvaRate
from ....domain.iva import InvoiceKind, IvaCategory
from .._iva_ledger import resolve_iva_ledger_binding_values
from .._modelo_bindings import _invoice_line_iva_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BASE = Decimal("1000.00")
_DEVENGO = date(2024, 3, 15)

_CASILLA_122 = "modelo-303-casilla-122-inversion-sujeto-pasivo-base"
_CASILLA_59 = "modelo-303-casilla-59-entregas-intracomunitarias-base"
_CASILLA_60 = "modelo-303-casilla-60-exportaciones-base"


def _revision():
    return resources().modelos.authority.snapshot("303", filing_year=2024, period="1T").revision


def _invoice(*, category: IvaCategory, kind: InvoiceKind) -> Invoice:
    """One single-line invoice between two Spanish parties, carrying no cuota.

    Both counterparties are Spanish because a domestic reverse charge is a
    domestic operation -- which is also why the counterparty gate the
    intra-community and export arms apply must NOT be inherited here: it tests
    for EU identification or non-EU establishment, and would withhold every
    genuine domestic reverse charge.
    """
    return Invoice.model_validate(
        {
            "bucket_id": "29292929-2929-4929-8929-292929292929",
            "kind": kind.value,
            "invoice_number": "F-2024-0122",
            "issued_at": _DEVENGO.isoformat(),
            "counterparty_name": "Constructora Peninsular SL",
            "counterparty_tax_id": "ESB12345674",
            "counterparty_country": "ES",
            "counterparty_identification_state": "es",
            "base_total": format(_BASE, "f"),
            "iva_total": "0.00",
            "grand_total": format(_BASE, "f"),
            "currency": "EUR",
            "payment_status": "PENDING",
            "iva_category": category.value,
            "lines": [
                {
                    "description": "Ejecución de obra con inversión del sujeto pasivo",
                    "quantity": "1",
                    "unit_price": format(_BASE, "f"),
                    "subtotal": format(_BASE, "f"),
                    "iva_rate": IvaRate.EXEMPT.value,
                    "iva_amount": "0.00",
                },
            ],
        },
    )


def _resolved_for(invoice: Invoice) -> dict[str, Decimal]:
    """Project the invoice's single line the way the screen does, then resolve."""
    observation = _invoice_line_iva_observation(
        invoice=invoice,
        line=invoice.lines[0],
        line_index=0,
        devengo_date=_DEVENGO,
        recargo_amount=Decimal("0"),
    )
    if observation is None:
        return {}
    return {str(k): v for k, v in resolve_iva_ledger_binding_values(_revision(), (observation,)).items()}


def test_the_supplier_side_base_reaches_casilla_122() -> None:
    """The turnover arrives in the box AEAT names for it."""
    resolved = _resolved_for(_invoice(category=IvaCategory.DOMESTIC_REVERSE_CHARGE, kind=InvoiceKind.ISSUED))

    assert resolved.get(_CASILLA_122) == _BASE, (
        f"the supplier-side reverse-charge base never reached casilla 122: {resolved.get(_CASILLA_122)!r}"
    )


def test_the_supplier_side_declares_a_base_and_no_cuota_anywhere() -> None:
    """No cuota box may receive anything, because no cuota arises on this side.

    Run as a paired assertion rather than trusting the positive test alone: a
    fix that routed the base correctly while ALSO minting a cuota would satisfy
    the test above and over-declare. Under art. 84.Uno.2.º the supplier
    repercutes nothing, so every resolved value other than casilla 122 must be
    absent or zero.
    """
    resolved = _resolved_for(_invoice(category=IvaCategory.DOMESTIC_REVERSE_CHARGE, kind=InvoiceKind.ISSUED))

    leaked = {k: v for k, v in resolved.items() if k != _CASILLA_122 and v}
    assert not leaked, f"the supplier's side carries no cuota by law, but values reached {sorted(leaked)}"


def test_the_recipient_side_does_not_reach_casilla_122() -> None:
    """The SAME category on a received invoice is the other party's operation.

    Casilla 122 declares operations the taxpayer SUPPLIES under the reverse
    charge. The recipient's side of the identical operation is a self-assessment
    and belongs on its own line. Collapsing the two flows is the defect the
    fourth flow member exists to prevent, and without this control the arm could
    route both sides into 122 and double the declared volume across a pair of
    trading taxpayers.
    """
    resolved = _resolved_for(_invoice(category=IvaCategory.DOMESTIC_REVERSE_CHARGE, kind=InvoiceKind.RECEIVED))

    assert not resolved.get(_CASILLA_122), (
        f"a RECEIVED reverse charge is the recipient's self-assessment, not supplied turnover: "
        f"{resolved.get(_CASILLA_122)!r}"
    )


def test_a_domestic_exemption_does_not_reach_casilla_122() -> None:
    """Discrimination control: a cuota-less line is not automatically a reverse charge.

    A domestic exemption under LIVA art. 20 prints the same exempt slot and
    carries the same zero cuota. If the arm keyed on "issued and no cuota" rather
    than on the declared category, this base would be reported as reverse-charge
    turnover the taxpayer never supplied under that regime.
    """
    resolved = _resolved_for(_invoice(category=IvaCategory.DOMESTIC_EXEMPT, kind=InvoiceKind.ISSUED))

    assert not resolved.get(_CASILLA_122)


def test_the_new_arm_does_not_divert_the_intracom_and_export_bases() -> None:
    """Control on the neighbours: casillas 59 and 60 keep their own traffic.

    The new arm sits immediately before the base-only branch that serves 59 and
    60, so an over-broad condition would swallow their lines before they reach
    it. Asserted here rather than left to the sibling file, because a diversion
    would show up as those tests failing for a reason that names this change
    nowhere.
    """
    reverse_charge = _resolved_for(_invoice(category=IvaCategory.DOMESTIC_REVERSE_CHARGE, kind=InvoiceKind.ISSUED))

    assert not reverse_charge.get(_CASILLA_59), "a domestic reverse charge is not an intra-community supply"
    assert not reverse_charge.get(_CASILLA_60), "a domestic reverse charge is not an export"
