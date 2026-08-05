"""Received-invoice retención routes into the one per-perceptor store.

The failure this surface exists to prevent is not an arithmetic one. Retención
on a received invoice is a LIABILITY the taxpayer owes AEAT as retenedor; on an
issued invoice the same arithmetic produces a CREDIT the taxpayer is owed. A
projection that ignored the direction would file one as the other, and a
projection that built its own store would fork the authority for a concept that
already has exactly one home.

So these gates assert three things: the issued side never enters this store,
what does enter is the same ``RetencionObservation`` the operator-declared path
builds (not a parallel type), and the scheme is never invented.

The euro figures are the invoice's own declared base and retención; no registry
formula is under test here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core import BindingSourceKind
from ....domain.invoices import Invoice, InvoiceLine, IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.iva import InvoiceKind, IvaCategory
from .._invoice_retencion import (
    INVOICE_RETENCION_DEFECT_GUIDANCE,
    InvoiceRetencionProjectionDefect,
    project_received_invoice_retencion,
    route_invoice_retenciones,
)
from .._retenciones import RetencionObservation, RetencionScheme, aggregate_retenciones_111

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFESIONAL = RetencionScheme.PROFESSIONAL


def _invoice(
    *,
    kind: InvoiceKind = InvoiceKind.RECEIVED,
    number: str = "F-PROV-001",
    base: str = "1000.00",
    retention_amount: str | None = "150.00",
    retention_rate: str | None = "0.15",
    country: str = "ES",
    tax_id: str = "B12345674",
    currency: str = "EUR",
    fx_rate: str | None = None,
) -> Invoice:
    subtotal = Decimal(base)
    rate = iva_rate_percentage(IvaRate.RATE_21)
    assert rate is not None
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=subtotal,
        subtotal=subtotal,
        iva_rate=IvaRate.RATE_21,
        iva_amount=subtotal * rate,
    )
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": number,
            "issued_at": date(2026, 3, 15),
            "counterparty_name": "Asesoría Profesional SL",
            "counterparty_tax_id": tax_id,
            "counterparty_country": country,
            "base_total": subtotal,
            "iva_total": line.iva_amount,
            "grand_total": subtotal + line.iva_amount,
            "currency": currency,
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory.DOMESTIC_GENERAL_21,
            "retention_rate": None if retention_rate is None else Decimal(retention_rate),
            "retention_amount": None if retention_amount is None else Decimal(retention_amount),
            "fx_rate": None if fx_rate is None else Decimal(fx_rate),
            "fx_rate_date": None if fx_rate is None else date(2026, 3, 15),
        },
    )


def test_received_invoice_routes_into_the_shared_observation_type() -> None:
    """The projection produces the store's own type, not a parallel one."""
    projection = project_received_invoice_retencion(_invoice(), scheme=_PROFESIONAL)

    assert projection.is_routed
    assert projection.defects == ()
    observation = projection.observation
    assert isinstance(observation, RetencionObservation)
    assert observation.source_kind is BindingSourceKind.PAYABLE_INVOICE
    assert observation.taxable_base == Decimal("1000.00")
    assert observation.retencion_amount == Decimal("150.00")
    assert observation.scheme is _PROFESIONAL
    assert observation.accrued_on == "2026-03-15"


def test_the_retencion_base_is_the_base_imponible_not_the_grand_total() -> None:
    """The store receives the base the withholding was computed on.

    A 1000 base invoice carries a 1210 grand total; routing the latter would
    overstate every per-perceptor rollup by the whole cuota.
    """
    projection = project_received_invoice_retencion(_invoice(), scheme=_PROFESIONAL)

    assert projection.observation is not None
    assert projection.observation.taxable_base == Decimal("1000.00")


def test_an_issued_invoice_never_enters_the_retenedor_store() -> None:
    """Its retención is a credit owed TO the taxpayer, not a liability owed BY them.

    This is the role inversion the whole surface exists to prevent: the same
    150 euros means opposite things on the two kinds, and only the received
    side is a Modelo 111 liability.
    """
    projection = project_received_invoice_retencion(
        _invoice(kind=InvoiceKind.ISSUED),
        scheme=_PROFESIONAL,
    )

    assert not projection.is_routed
    assert projection.defects == (InvoiceRetencionProjectionDefect.NOT_A_RECEIVED_INVOICE,)


def test_an_invoice_declaring_no_retencion_routes_nothing() -> None:
    """Most received invoices withhold nothing; that is not a defect in the data."""
    projection = project_received_invoice_retencion(
        _invoice(retention_amount=None, retention_rate=None),
        scheme=_PROFESIONAL,
    )

    assert projection.defects == (InvoiceRetencionProjectionDefect.NO_RETENCION_DECLARED,)


def test_a_zero_retencion_routes_nothing_rather_than_an_empty_row() -> None:
    """A declared zero is still nothing to remit; the store stays free of noise."""
    projection = project_received_invoice_retencion(
        _invoice(retention_amount="0.00", retention_rate="0.00"),
        scheme=_PROFESIONAL,
    )

    assert projection.defects == (InvoiceRetencionProjectionDefect.NO_RETENCION_DECLARED,)


def test_a_non_resident_supplier_is_excluded_rather_than_filed_under_modelo_111() -> None:
    """The IRPF per-perceptor family does not govern payments to non-residents.

    Excluding surfaces the invoice for the operator; routing it would file a
    figure under a modelo that does not cover it.
    """
    projection = project_received_invoice_retencion(
        _invoice(country="PT", tax_id="PT123456789"),
        scheme=_PROFESIONAL,
    )

    assert projection.defects == (InvoiceRetencionProjectionDefect.NON_RESIDENT_SUPPLIER,)


def test_an_unconverted_foreign_invoice_is_excluded_rather_than_approximated() -> None:
    """The store holds euro figures, and this invoice has none."""
    projection = project_received_invoice_retencion(
        _invoice(country="US", tax_id="US-TAX-1", currency="USD"),
        scheme=_PROFESIONAL,
    )

    assert InvoiceRetencionProjectionDefect.FX_UNRESOLVED in projection.defects


def test_a_converted_foreign_resident_invoice_routes_in_euro() -> None:
    """With a resolved rate the routed figures are the converted ones."""
    projection = project_received_invoice_retencion(
        _invoice(currency="USD", fx_rate="0.90"),
        scheme=_PROFESIONAL,
    )

    assert projection.observation is not None
    assert projection.observation.taxable_base == Decimal("900.00")
    assert projection.observation.retencion_amount == Decimal("135.00")


def test_defects_accumulate_so_one_pass_shows_everything_wrong() -> None:
    """An issued, retención-less, non-resident invoice reports all three."""
    projection = project_received_invoice_retencion(
        _invoice(
            kind=InvoiceKind.ISSUED, retention_amount=None, retention_rate=None, country="FR", tax_id="FR12345678901"
        ),
        scheme=_PROFESIONAL,
    )

    assert projection.defects == (
        InvoiceRetencionProjectionDefect.NOT_A_RECEIVED_INVOICE,
        InvoiceRetencionProjectionDefect.NO_RETENCION_DECLARED,
        InvoiceRetencionProjectionDefect.NON_RESIDENT_SUPPLIER,
    )


def test_routing_keeps_the_excluded_invoices_alongside_the_routed_ones() -> None:
    """An excluded liability is one the taxpayer may still owe; it is not dropped."""
    routed = _invoice(number="F-PROV-100")
    issued = _invoice(number="F-CLI-200", kind=InvoiceKind.ISSUED)

    routing = route_invoice_retenciones(((routed, _PROFESIONAL), (issued, _PROFESIONAL)))

    assert len(routing.observations) == 1
    assert routing.observations[0].source_object_id == routed.invoice_id
    assert len(routing.excluded) == 1
    assert routing.excluded[0].invoice_id == issued.invoice_id


def test_routed_observations_aggregate_through_the_existing_modelo_111_path() -> None:
    """The projection's output is consumable by the aggregator that already exists.

    This is what "route into the store, never fork a path" has to mean in
    practice: the observations reach the committed Modelo 111 rollups without
    any new aggregator standing between them.
    """
    from ....core import Period

    first = _invoice(number="F-PROV-301")
    second = _invoice(number="F-PROV-302", base="2000.00", retention_amount="300.00")

    routing = route_invoice_retenciones(((first, _PROFESIONAL), (second, _PROFESIONAL)))
    aggregation = aggregate_retenciones_111(
        routing.observations,
        period=Period.from_year_and_code(2026, "1T"),
    )

    assert aggregation.total_retencion == Decimal("450.00")
    assert aggregation.total_taxable_base == Decimal("3000.00")
    assert aggregation.total_perceptors == 1


def test_every_defect_carries_operator_guidance() -> None:
    """A new defect cannot ship without the sentence that tells an operator what to do."""
    assert set(INVOICE_RETENCION_DEFECT_GUIDANCE) == set(InvoiceRetencionProjectionDefect)
    assert all(text.strip() for text in INVOICE_RETENCION_DEFECT_GUIDANCE.values())


def test_the_scheme_is_supplied_never_inferred_from_the_invoice() -> None:
    """Two identical invoices route under whichever scheme the caller declares.

    Nothing on the record selects a clave, so the projection cannot and does
    not choose one. Were it ever to start inferring, this case would return the
    same scheme twice regardless of what was asked for.
    """
    invoice = _invoice()

    profesional = project_received_invoice_retencion(invoice, scheme=RetencionScheme.PROFESSIONAL)
    economica = project_received_invoice_retencion(invoice, scheme=RetencionScheme.ECONOMIC_ACTIVITY)

    assert profesional.observation is not None
    assert economica.observation is not None
    assert profesional.observation.scheme is RetencionScheme.PROFESSIONAL
    assert economica.observation.scheme is RetencionScheme.ECONOMIC_ACTIVITY
