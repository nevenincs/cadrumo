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

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.aggregation import BindingSourceKind, RetencionScheme
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.retenciones_bindings import resolve_retenciones_aggregation_binding_values
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.components import IvaRetencionRole, category_components
from ....domain.iva.schema import IvaCategory
from ..invoice_retencion import InvoiceRetencionProjectionDefect, invoice_retencion_liability_defects
from ..retenciones import RetencionObservation, aggregate_retenciones_111

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PROFESIONAL = RetencionScheme("actividades_profesionales")
_FX_RATE_SOURCE = "test_reference"
_DEFAULT_IVA_CATEGORY = IvaCategory("domestic_general")


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
    category: IvaCategory = _DEFAULT_IVA_CATEGORY,
) -> Invoice:
    subtotal = Decimal(base)
    rate = iva_rate_percentage(IvaRate.from_registry("RATE_21"), date(2026, 1, 1))
    assert rate is not None
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=subtotal,
        subtotal=subtotal,
        iva_rate=IvaRate.from_registry("RATE_21"),
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
            "iva_category": category,
            "retention_rate": None if retention_rate is None else Decimal(retention_rate),
            "retention_amount": None if retention_amount is None else Decimal(retention_amount),
            "fx_rate": None if fx_rate is None else Decimal(fx_rate),
            "fx_rate_date": None if fx_rate is None else date(2026, 3, 15),
            # The three fx fields are set together or not at all: a rate with no
            # named authority is an unattributable conversion.
            "fx_rate_source": None if fx_rate is None else _FX_RATE_SOURCE,
        },
    )


def _routed_observations(*invoices: Invoice) -> tuple[RetencionObservation, ...]:
    """Return the store observation each routable invoice contributes, refusing a defective fixture."""
    observations: list[RetencionObservation] = []
    for invoice in invoices:
        assert invoice_retencion_liability_defects(invoice) == (), (
            f"the fixture invoice {invoice.invoice_number!r} must route"
        )
        assert invoice.base_total_eur is not None
        assert invoice.retention_amount_eur is not None
        assert invoice.counterparty_tax_id is not None
        observations.append(
            RetencionObservation(
                source_kind=BindingSourceKind.PAYABLE_INVOICE,
                source_object_id=invoice.invoice_id,
                perceptor_nif=invoice.counterparty_tax_id,
                perceptor_name=invoice.counterparty_name,
                scheme=_PROFESIONAL,
                taxable_base=invoice.base_total_eur,
                retencion_amount=invoice.retention_amount_eur,
                accrued_on=invoice.issued_at.isoformat(),
            )
        )
    return tuple(observations)


def test_a_received_invoice_with_a_declared_retencion_is_a_retenedor_liability() -> None:
    assert invoice_retencion_liability_defects(_invoice()) == ()


def test_an_issued_invoice_never_enters_the_retenedor_store() -> None:
    """Its retención is a credit owed TO the taxpayer, not a liability owed BY them.

    This is the role inversion the whole surface exists to prevent: the same
    150 euros means opposite things on the two kinds, and only the received
    side is a Modelo 111 liability.
    """
    defects = invoice_retencion_liability_defects(_invoice(kind=InvoiceKind.ISSUED))

    assert defects == (InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY,)


def test_an_invoice_declaring_no_retencion_routes_nothing() -> None:
    """Most received invoices withhold nothing; that is not a defect in the data."""
    defects = invoice_retencion_liability_defects(_invoice(retention_amount=None, retention_rate=None))

    assert defects == (InvoiceRetencionProjectionDefect.NO_RETENCION_DECLARED,)


def test_a_zero_retencion_routes_nothing_rather_than_an_empty_row() -> None:
    """A declared zero is still nothing to remit; the store stays free of noise."""
    defects = invoice_retencion_liability_defects(_invoice(retention_amount="0.00", retention_rate="0.00"))

    assert defects == (InvoiceRetencionProjectionDefect.NO_RETENCION_DECLARED,)


def test_a_non_resident_supplier_is_excluded_rather_than_filed_under_modelo_111() -> None:
    """The IRPF per-perceptor family does not govern payments to non-residents.

    Excluding surfaces the invoice for the operator; routing it would file a
    figure under a modelo that does not cover it.
    """
    defects = invoice_retencion_liability_defects(_invoice(country="PT", tax_id="PT123456789"))

    assert defects == (InvoiceRetencionProjectionDefect.NON_RESIDENT_SUPPLIER,)


def test_an_unconverted_foreign_invoice_is_excluded_rather_than_approximated() -> None:
    """The store holds euro figures, and this invoice has none."""
    defects = invoice_retencion_liability_defects(_invoice(country="US", tax_id="US-TAX-1", currency="USD"))

    assert InvoiceRetencionProjectionDefect.FX_UNRESOLVED in defects


def test_a_converted_foreign_resident_invoice_routes_in_euro() -> None:
    """With a resolved rate the invoice routes and its euro figures are the converted ones."""
    invoice = _invoice(currency="USD", fx_rate="0.90")

    assert invoice_retencion_liability_defects(invoice) == ()
    assert invoice.base_total_eur == Decimal("900.00")
    assert invoice.retention_amount_eur == Decimal("135.00")


def test_defects_accumulate_so_one_pass_shows_everything_wrong() -> None:
    """An issued, retención-less, non-resident invoice reports all three."""
    defects = invoice_retencion_liability_defects(
        _invoice(
            kind=InvoiceKind.ISSUED, retention_amount=None, retention_rate=None, country="FR", tax_id="FR12345678901"
        )
    )

    assert defects == (
        InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY,
        InvoiceRetencionProjectionDefect.NO_RETENCION_DECLARED,
        InvoiceRetencionProjectionDefect.NON_RESIDENT_SUPPLIER,
    )


def test_routed_observations_aggregate_through_the_existing_modelo_111_path() -> None:
    """A routable invoice's observation is consumable by the aggregator that already exists.

    This is what "route into the store, never fork a path" has to mean in
    practice: the observations reach the committed Modelo 111 rollups without
    any new aggregator standing between them.
    """
    first = _invoice(number="F-PROV-301")
    second = _invoice(number="F-PROV-302", base="2000.00", retention_amount="300.00")

    aggregation = aggregate_retenciones_111(
        _routed_observations(first, second),
        period=Period.from_year_and_code(2026, "1T"),
    )

    assert aggregation.total_retencion == Decimal("450.00")
    assert aggregation.total_taxable_base == Decimal("3000.00")
    assert aggregation.total_perceptors == 1


def test_the_role_is_read_from_the_axis_a_table_not_from_the_invoice_kind() -> None:
    """A received invoice whose declared pair yields no liability still does not route.

    An invoice the taxpayer RECEIVED under a category whose Axis-A row gives no
    retenedor liability must be excluded even though its kind is RECEIVED. A
    ``kind is RECEIVED`` shortcut would route it, which is precisely the
    re-derivation the module refuses; this case is what separates the two
    implementations.
    """
    received_no_liability = _invoice(category=IvaCategory("intra_community_acquisition_reverse_charge"))
    role = category_components(
        IvaCategory("intra_community_acquisition_reverse_charge"),
        InvoiceKind.RECEIVED,
    ).retencion_role

    defects = invoice_retencion_liability_defects(received_no_liability)

    assert role != IvaRetencionRole.from_registry("taxpayer_liability")
    assert received_no_liability.kind is InvoiceKind.RECEIVED
    assert defects == (InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY,)


# --------------------------------------------------------------------------- #
# The received side, carried to its filed casillas
# --------------------------------------------------------------------------- #
#
# Everything above proves the liability predicate and the aggregation agree. Neither
# proves the registry then routes those figures to the casillas a taxpayer
# files: a correct aggregation consumed by the wrong binding, or by none, is
# still a wrong return, and only the binding layer reaches a declaration.
#
# The issued side gained that check in the cross-domain scenario. This is the
# received side, where the sign of the consequence inverts -- here the taxpayer
# is the RETENEDOR and the figure is a liability owed to AEAT, not a credit
# owed to them. An error understates what is OWED, which is the direction that
# draws a sanction, so the harsher half should not have the weaker check.

_M111_ACTIVIDADES_PERCEPTORES_BINDING = "modelo-111-actividades-dinerario-perceptores"
_M111_ACTIVIDADES_BASE_BINDING = "modelo-111-actividades-dinerario-base"
_M111_ACTIVIDADES_RETENCIONES_BINDING = "modelo-111-actividades-dinerario-retenciones"


def _modelo_111_revision() -> ModeloRevision:
    """The committed M111 revision, resolved the way production resolves it.

    Through the registry authority rather than a test-side snapshot builder, so
    the bindings asserted are the ones a real calculate would load. A hand-built
    snapshot could agree with this test and disagree with the filing.
    """
    return published_snapshot(
        Modelo("111").value,
        filing_year=2026,
        period="1T",
    ).revision


def test_the_committed_m111_bindings_receive_the_invoice_figures() -> None:
    """A received invoice reaches the casillas that declare the liability.

    The base casilla takes the base imponible, never the grand total: the
    retención is computed on what was earned, not on what was invoiced
    including IVA. The retenciones casilla takes the withheld amount the
    taxpayer must now hand to AEAT.

    Both are asserted against the INVOICE figures rather than against the
    aggregation totals, which is the whole point of the layer. Asserting the
    binding against the aggregation would only prove the two agree with each
    other, and they are computed from the same source -- they would agree while
    both diverged from the invoice.
    """
    invoice = _invoice(base="1000.00", retention_amount="150.00")

    aggregation = aggregate_retenciones_111(
        _routed_observations(invoice),
        period=Period.from_year_and_code(2026, "1T"),
    )

    resolved = resolve_retenciones_aggregation_binding_values(_modelo_111_revision(), aggregation)

    assert resolved[_M111_ACTIVIDADES_BASE_BINDING] == Decimal("1000.00")
    assert resolved[_M111_ACTIVIDADES_RETENCIONES_BINDING] == Decimal("150.00")
    assert resolved[_M111_ACTIVIDADES_PERCEPTORES_BINDING] == Decimal("1")


def test_the_filed_base_is_never_the_grand_total() -> None:
    """The declared base must exclude the IVA the invoice also carries.

    Stated as its own case because the two figures are both present on the
    invoice and only one is correct: a 1000 base at 21 % invoices at 1210, and
    a resolver reaching for the total would file a base 21 % too high and a
    liability computed against it. Pinning the base positively leaves that
    substitution passing; pinning it negatively as well does not.
    """
    invoice = _invoice(base="1000.00", retention_amount="150.00")

    aggregation = aggregate_retenciones_111(
        _routed_observations(invoice),
        period=Period.from_year_and_code(2026, "1T"),
    )

    resolved = resolve_retenciones_aggregation_binding_values(_modelo_111_revision(), aggregation)

    assert resolved[_M111_ACTIVIDADES_BASE_BINDING] != invoice.grand_total
    assert resolved[_M111_ACTIVIDADES_BASE_BINDING] == invoice.base_total
