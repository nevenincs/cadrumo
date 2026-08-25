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
from pathlib import Path

import pytest

from ....adapters.outbound.fx import ECB_RATE_SOURCE_ID
from ....core import BindingSourceKind, Modelo, Period
from ....core.resources import resources
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.bindings import resolve_retenciones_aggregation_binding_values
from ....domain.invoices import Invoice, InvoiceLine, IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.iva import InvoiceKind, IvaCategory, IvaRetencionRole, category_components
from ....tests.secure_sql import isolated_runtime_profile
from ..errors import AggregationValidationError
from .._invoice_retencion import (
    INVOICE_RETENCION_DEFECT_GUIDANCE,
    InvoiceRetencionProjectionDefect,
    merge_manual_and_routed_retencion_observations,
    project_received_invoice_retencion,
    route_invoice_retenciones,
)
from .._retencion_observations_repository import (
    RetencionObservationRepository,
    persist_retencion_observations,
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
    category: IvaCategory = IvaCategory.DOMESTIC_GENERAL,
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
            "iva_category": category,
            "retention_rate": None if retention_rate is None else Decimal(retention_rate),
            "retention_amount": None if retention_amount is None else Decimal(retention_amount),
            "fx_rate": None if fx_rate is None else Decimal(fx_rate),
            "fx_rate_date": None if fx_rate is None else date(2026, 3, 15),
            # The three fx fields are set together or not at all: a rate with no
            # named authority is an unattributable conversion.
            "fx_rate_source": None if fx_rate is None else ECB_RATE_SOURCE_ID,
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
    assert projection.defects == (InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY,)


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
        InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY,
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


def test_merge_unions_manual_and_routed_observations() -> None:
    """The merge is a plain union when the two sides name disjoint invoices."""
    manual = (
        RetencionObservation(
            source_kind=BindingSourceKind.LEDGER_TRANSACTION,
            source_object_id="ledger-txn-1",
            perceptor_nif="12345678Z",
            perceptor_name="Ledger Perceptor",
            scheme=_PROFESIONAL,
            taxable_base=Decimal("500.00"),
            retencion_amount=Decimal("75.00"),
            accrued_on="2026-02-01",
        ),
    )
    routing = route_invoice_retenciones(((_invoice(), _PROFESIONAL),))

    merged = merge_manual_and_routed_retencion_observations(manual, routing.observations)

    assert merged == (*manual, *routing.observations)


def test_merge_refuses_when_a_manual_row_collides_with_a_routed_invoice() -> None:
    """A hand-typed observation for the SAME invoice the routing already covers is refused.

    ``persist_retencion_observations`` set-replaces the whole per-perceptor window, so
    silently picking a winner between the two would either double-count the invoice's
    retención in the rollup or silently drop whichever side lost. Refusing loudly is the
    only sound choice when a bound value would otherwise gain two writers.
    """
    invoice = _invoice()
    routing = route_invoice_retenciones(((invoice, _PROFESIONAL),))
    assert routing.observations, "the fixture invoice must route for this collision to be meaningful"
    duplicate_manual = (
        RetencionObservation(
            source_kind=BindingSourceKind.PAYABLE_INVOICE,
            source_object_id=invoice.invoice_id,
            perceptor_nif="12345678Z",
            perceptor_name="Hand-typed duplicate",
            scheme=_PROFESIONAL,
            taxable_base=Decimal("1000.00"),
            retencion_amount=Decimal("150.00"),
            accrued_on="2026-03-15",
        ),
    )

    with pytest.raises(AggregationValidationError) as exc_info:
        merge_manual_and_routed_retencion_observations(duplicate_manual, routing.observations)
    assert exc_info.value.context is not None
    assert exc_info.value.context["source_object_ids"] == invoice.invoice_id
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


def test_routed_retencion_lands_in_the_existing_encrypted_store(tmp_path: Path) -> None:
    """The liability reaches the real store, read back through the real read path.

    Asserting that the projection returned an observation proves only that this
    module ran. What the step actually claims is that a received invoice becomes
    a row in the ONE per-perceptor store the committed Modelo 111 bindings read,
    so the assertion is on the store's contents after the shared write helper
    persisted them -- no second store, no second write path.
    """
    period = Period.from_year_and_code(2026, "1T")
    routing = route_invoice_retenciones(((_invoice(), _PROFESIONAL),))

    with isolated_runtime_profile(tmp_path=tmp_path):
        persist_retencion_observations(
            modelo="111",
            filing_year=period.filing_year,
            period=period,
            observations=routing.observations,
        )
        stored = RetencionObservationRepository().load_observations("111", period)

    assert len(stored) == 1
    assert stored[0].retencion_amount == Decimal("150.00")
    assert stored[0].taxable_base == Decimal("1000.00")
    assert stored[0].source_kind is BindingSourceKind.PAYABLE_INVOICE
    assert stored[0].scheme is _PROFESIONAL


def test_an_excluded_invoice_leaves_the_store_empty(tmp_path: Path) -> None:
    """The negative control: an issued invoice contributes no stored liability.

    Without this the store test above would pass just as happily if the
    projection routed everything it was handed.
    """
    period = Period.from_year_and_code(2026, "1T")
    routing = route_invoice_retenciones(((_invoice(kind=InvoiceKind.ISSUED), _PROFESIONAL),))

    with isolated_runtime_profile(tmp_path=tmp_path):
        persist_retencion_observations(
            modelo="111",
            filing_year=period.filing_year,
            period=period,
            observations=routing.observations,
        )
        stored = RetencionObservationRepository().load_observations("111", period)

    assert routing.observations == ()
    assert stored == ()
    assert routing.excluded[0].defects == (InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY,)


def test_the_role_is_read_from_the_axis_a_table_not_from_the_invoice_kind() -> None:
    """A received invoice whose declared pair yields no liability still does not route.

    An invoice the taxpayer RECEIVED under a category whose Axis-A row gives no
    retenedor liability must be excluded even though its kind is RECEIVED. A
    ``kind is RECEIVED`` shortcut would route it, which is precisely the
    re-derivation the module refuses; this case is what separates the two
    implementations.
    """
    received_no_liability = _invoice(category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE)
    role = category_components(
        IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        InvoiceKind.RECEIVED,
    ).retencion_role

    projection = project_received_invoice_retencion(received_no_liability, scheme=_PROFESIONAL)

    assert role is not IvaRetencionRole.TAXPAYER_LIABILITY
    assert received_no_liability.kind is InvoiceKind.RECEIVED
    assert projection.defects == (InvoiceRetencionProjectionDefect.NOT_A_RETENEDOR_LIABILITY,)


# --------------------------------------------------------------------------- #
# The received side, carried to its filed casillas
# --------------------------------------------------------------------------- #
#
# Everything above proves the projection and the aggregation agree. Neither
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
    return (
        resources()
        .modelos.authority.snapshot(
            Modelo.M111.value,
            filing_year=2026,
            period="1T",
        )
        .revision
    )


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

    routing = route_invoice_retenciones(((invoice, _PROFESIONAL),))
    aggregation = aggregate_retenciones_111(
        routing.observations,
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

    routing = route_invoice_retenciones(((invoice, _PROFESIONAL),))
    aggregation = aggregate_retenciones_111(
        routing.observations,
        period=Period.from_year_and_code(2026, "1T"),
    )

    resolved = resolve_retenciones_aggregation_binding_values(_modelo_111_revision(), aggregation)

    assert resolved[_M111_ACTIVIDADES_BASE_BINDING] != invoice.grand_total
    assert resolved[_M111_ACTIVIDADES_BASE_BINDING] == invoice.base_total
