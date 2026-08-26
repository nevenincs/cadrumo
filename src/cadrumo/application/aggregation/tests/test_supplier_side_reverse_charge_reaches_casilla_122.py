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

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.invoices import Invoice, IvaRate
from ....domain.iva import InvoiceKind, IvaCategory, is_deducible_flow
from .._iva_ledger import resolve_iva_ledger_binding_values
from .._modelo_bindings import _DECLARED_CATEGORY_BASE_ONLY_FLOWS, _invoice_line_iva_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BASE = Decimal("1000.00")
_DEVENGO = date(2024, 3, 15)

_CASILLA_122 = "modelo-303-casilla-122-inversion-sujeto-pasivo-base"
_CASILLA_59 = "modelo-303-casilla-59-entregas-intracomunitarias-base"
_CASILLA_60 = "modelo-303-casilla-60-exportaciones-base"


def test_every_declared_category_base_only_flow_stays_outside_deduction_authority() -> None:
    """The complete production table must remain output-side under the canonical predicate.

    These cuota-less issued rows are constructed without deduction provenance.
    If a future table member points at a deducible flow, the observation model
    will refuse it before the intended base reaches its casilla. Iterating the
    production table keeps the assertion total without restating its members or
    duplicating the deduction-side flow set.
    """
    wrongly_deducible = {
        category.value: flow.value
        for category, flow in _DECLARED_CATEGORY_BASE_ONLY_FLOWS.items()
        if is_deducible_flow(flow)
    }

    assert not wrongly_deducible


def _revision():
    return bundled_authority().snapshot("303", filing_year=2024, period="1T").revision


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
    line = invoice.lines[0]
    base_amount_eur = invoice.line_amount_eur(line.subtotal)
    iva_amount_eur = invoice.line_amount_eur(line.iva_amount)
    assert base_amount_eur is not None
    assert iva_amount_eur is not None
    observation = _invoice_line_iva_observation(
        invoice=invoice,
        line=line,
        line_index=0,
        devengo_date=_DEVENGO,
        recargo_amount=Decimal("0"),
        base_amount_eur=base_amount_eur,
        iva_amount_eur=iva_amount_eur,
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


_CASILLA_120 = "modelo-303-casilla-120-no-sujetas-localizacion-base"


def test_an_eu_b2b_service_base_reaches_casilla_120() -> None:
    """A service located where the EU recipient is established is volumen, not silence.

    LIVA art. 69.Uno.1 puts the operation outside the Spanish hecho imponible,
    so it is NO SUJETA rather than exempt and carries no cuota. It is still
    turnover, and M303 names a box for it. Before this it reached nothing: the
    line has no cuota, so rate-slot classification replaced the declared
    category before any binding could select it -- the same upstream loss that
    kept casilla 122 blank.
    """
    resolved = _resolved_for(_invoice(category=IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY, kind=InvoiceKind.ISSUED))

    assert resolved.get(_CASILLA_120) == _BASE, (
        f"the not-subject service base never reached casilla 120: {resolved.get(_CASILLA_120)!r}"
    )


def test_the_two_informacion_adicional_boxes_do_not_collect_each_other() -> None:
    """Casillas 120 and 122 declare different operations and must not cross.

    Run as a pair rather than as two separate positives: a selector keyed on
    "issued and no cuota" would fill BOTH boxes from either invoice and satisfy
    each single-box test on its own. Only the cross-check catches that, and
    crossing them doubles the declared volumen across the two lines.
    """
    service = _resolved_for(_invoice(category=IvaCategory.INTRA_COMMUNITY_SERVICE_SUPPLY, kind=InvoiceKind.ISSUED))
    reverse_charge = _resolved_for(_invoice(category=IvaCategory.DOMESTIC_REVERSE_CHARGE, kind=InvoiceKind.ISSUED))

    assert service.get(_CASILLA_120) == _BASE
    assert not service.get(_CASILLA_122), "a not-subject service is not a reverse charge"
    assert reverse_charge.get(_CASILLA_122) == _BASE
    assert not reverse_charge.get(_CASILLA_120), "a reverse charge IS subject; it is not a localizacion case"


def test_an_article_7_not_subject_operation_does_not_reach_casilla_120() -> None:
    """Discrimination control: not-subject BY NATURE is not not-subject BY LOCATION.

    LIVA art. 7 excludes operations such as the transmision of a going concern.
    They carry no cuota and are issued, exactly like the art. 69 case, but the
    box says "por reglas de localizacion" and art. 7 is not one of those rules.
    Routing them here would report as located abroad an operation that was never
    located anywhere else.
    """
    resolved = _resolved_for(_invoice(category=IvaCategory.OPERACION_NO_SUJETA, kind=InvoiceKind.ISSUED))

    assert not resolved.get(_CASILLA_120)
