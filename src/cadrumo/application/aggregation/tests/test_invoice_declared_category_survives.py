"""A declared IVA treatment must reach the record, and its loss must be reported.

The invoice projection derived an observation's category from the line's RATE
SLOT even when the invoice DECLARED one. For a received domestic reverse charge
(LIVA art. 84.Uno.2) that is doubly wrong: the supplier charges no cuota, so the
line carries an exempt slot, and the projection turned a declared
``domestic_reverse_charge`` into ``domestic_exempt`` at flow ``soportado``. The
same operation recorded as a bank row is classified correctly, because that path
reads the declared category first and derives the flow from it.

Two things are asserted here and they must not be confused with each other.

The record now STATES what the document stated. That is worth having on its own:
a record that silently relabels a reverse charge as an exemption is wrong on its
face, and every later reader inherits the wrong label.

It does NOT make the operation declare. The recipient-side binding selector is a
triple -- category, rate kind, flow -- and an exempt-slot line still carries the
wrong rate kind, so it selects nothing even with the category and the flow both
correct. That is asserted explicitly, so nobody reads this change as closing the
self-assessment gap. What closes that is a decision about whether an invoice line
may carry a rated slot with a zero cuota, which is open.

Because the loss remains, it is reported rather than left silent: the operator is
told the cuota could not be derived, through the same advisory channel that
already reports an invoice withheld for a category its counterparty contradicts.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ....domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.invoices.enums import IvaRate
from ....domain.invoices.models import Invoice
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.flow import IvaFlowDirection
from ....domain.iva.schema import InvoiceKind, IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ...ledger.preflight import HeldTransactionCatalogue
from ..errors import AggregationValidationError
from ..invoice_iva_source import (
    InvoiceIvaFinding,
    InvoiceIvaFindingReason,
    PeriodInvoiceIvaSide,
    period_invoice_iva_side,
)
from ..iva_ledger_apportionment import resolve_iva_ledger_binding_values
from ..iva_ledger_classification import bien_inversion_threshold
from ..modelo_bindings_invoice_iva import (
    invoice_line_iva_observation,
    reverse_charge_cuota_not_derivable,
    screened_invoice_iva_result,
)
from .ledger_source_mesh_support import machine_acquisition_transaction

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _pinned_operation() -> PinnedAuthorityOperation:
    """The session lease this module scopes every test to."""
    scoped = governed_facts_in_scope()
    assert isinstance(scoped, PinnedAuthorityOperation)
    return scoped


_BASE = Decimal("2000.00")
_DAY = date(_YEAR, 3, 15)
_DEFAULT_INVOICE_RATE = IvaRate.from_registry("EXEMPT")


def _received_reverse_charge(
    *, slot: IvaRate = _DEFAULT_INVOICE_RATE, cuota: str = "0.00", base: Decimal = _BASE
) -> Invoice:
    """A construction supply the recipient must self-assess.

    The supplier charges nothing, which is what an art. 84.Uno.2 invoice looks
    like: a base, a declared treatment, and no cuota.
    """
    total = base + Decimal(cuota)
    return Invoice.model_validate(
        {
            "bucket_id": "29292929-2929-4929-8929-292929292929",
            "kind": InvoiceKind.RECEIVED.value,
            "invoice_number": "F-2026-0077",
            "issued_at": _DAY.isoformat(),
            "counterparty_name": "Constructora Ejemplo SL",
            "counterparty_tax_id": "ESB00015016",
            "counterparty_country": "ES",
            "base_total": format(base, "f"),
            "iva_total": cuota,
            "grand_total": format(total, "f"),
            "currency": "EUR",
            "payment_status": "PENDING",
            "iva_category": IvaCategory("domestic_reverse_charge").value,
            "lines": [
                {
                    "description": "Ejecucion de obra",
                    "quantity": "1",
                    "unit_price": format(base, "f"),
                    "subtotal": format(base, "f"),
                    "iva_rate": slot.value,
                    "iva_amount": cuota,
                },
            ],
        },
    )


def _observation_for(invoice: Invoice):
    line = invoice.lines[0]
    base_amount_eur = invoice.line_amount_eur(line.subtotal)
    iva_amount_eur = invoice.line_amount_eur(line.iva_amount)
    assert base_amount_eur is not None
    assert iva_amount_eur is not None
    return invoice_line_iva_observation(
        invoice=invoice,
        line=line,
        line_index=0,
        devengo_date=_DAY,
        recargo_amount=Decimal("0"),
        base_amount_eur=base_amount_eur,
        iva_amount_eur=iva_amount_eur,
        deduction_authority=_received_reverse_charge_deduction_authority(),
        operation=_pinned_operation(),
    )


def _received_reverse_charge_deduction_authority() -> IvaLedgerObservation:
    """The exact frozen ledger authority required for received input IVA."""
    return IvaLedgerObservation(
        ledger_id="transaction:received-reverse-charge",
        transaction_date=_DAY,
        category=IvaCategory("domestic_reverse_charge"),
        rate_kind=IvaRateKind("exempt"),
        flow_direction=IvaFlowDirection.from_registry("inversion_sujeto_pasivo"),
        base_amount=_BASE,
        iva_amount=Decimal("0"),
        deduction_fact_kind=IvaDeductionFactKind.from_registry("domestic_current"),
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
            source_locator="invoice:received-reverse-charge",
            evidence_digest="a" * 64,
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def test_the_declared_reverse_charge_survives_the_projection() -> None:
    """The observation states the treatment the invoice declared.

    Asserted on the flow as well as the category, because the two are separate
    losses. A preserved category at flow ``soportado`` would still describe the
    recipient as merely bearing input tax rather than self-assessing output tax,
    which is the substance of what a reverse charge is.
    """
    observation = _observation_for(_received_reverse_charge())

    assert observation is not None
    assert observation.category == IvaCategory("domestic_reverse_charge"), (
        f"the declared treatment was overwritten from the rate slot: {observation.category.value}"
    )
    assert observation.flow_direction == IvaFlowDirection.from_registry("inversion_sujeto_pasivo"), (
        f"the recipient is not recorded as self-assessing: {observation.flow_direction.value}"
    )
    assert observation.base_amount == _BASE


def test_the_preserved_category_does_not_by_itself_declare_the_cuota(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The honest half: the record is right and the return is still short.

    Pinned deliberately. The recipient-side selector is a triple and only two of
    its three conditions are now satisfied -- the rate kind is still ``exempt``
    because the line carries no rated slot. Asserting this stops the change being
    read, later and by someone else, as having closed the self-assessment gap.
    """
    observation = _observation_for(_received_reverse_charge())
    assert observation is not None
    revision = published_snapshot("303", filing_year=_YEAR, period="2T").revision

    resolved = {
        str(k): v
        for k, v in resolve_iva_ledger_binding_values(
            revision,
            (observation,),
            operation=authority_operation,
        ).items()
    }

    assert not any(resolved.values()), (
        f"this change is not supposed to route anything yet, but it did: "
        f"{ {k: str(v) for k, v in resolved.items() if v} }"
    )


def test_an_underivable_self_assessment_is_reported_not_silent() -> None:
    """The loss is surfaced, because a short return with no signal is the defect.

    The cuota cannot be derived from this record: the line carries an exempt
    slot, so the rate the self-assessment would apply is simply not there. That
    is a legitimate refusal to invent a figure -- and it stops being acceptable
    the moment nobody is told.
    """
    assert reverse_charge_cuota_not_derivable(_received_reverse_charge()) is True


def test_a_rated_reverse_charge_line_is_not_reported() -> None:
    """A record that CAN support the self-assessment raises no advisory.

    The negative case matters as much as the positive one: an advisory that
    fires on every reverse charge, including the ones carrying a rate, trains the
    operator to ignore the channel. Only the underivable shape is reported.
    """
    rated = _received_reverse_charge(slot=IvaRate.from_registry("RATE_21"), cuota="420.00")

    assert reverse_charge_cuota_not_derivable(rated) is False


def _movement_carrying(authority: IvaLedgerObservation) -> Transaction:
    """A paying bank movement whose recorded deduction classification is ``authority``'s."""
    return machine_acquisition_transaction("material_oficina", provider_id=authority.ledger_id[:16]).model_copy(
        update={
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "deduction_fact_kind": authority.deduction_fact_kind,
            "deduction_provenance": authority.deduction_provenance,
        }
    )


def _escaso_valor() -> Decimal:
    """Fact 0032 (LIVA art. 108.Dos.5.º) on the invoice's date, read from the pinned registry."""
    return bien_inversion_threshold(operation_date=_DAY, operation=_pinned_operation())


def _rated_reverse_charge(base: Decimal) -> Invoice:
    """The reverse-charge invoice at 21 % on ``base``, its cuota rounded to the cent."""
    cuota = (base * Decimal("0.21")).quantize(Decimal("0.01"))
    return _received_reverse_charge(slot=IvaRate.from_registry("RATE_21"), cuota=format(cuota, "f"), base=base)


def test_a_domestic_invoice_below_the_escaso_valor_threshold_is_its_own_current_deduction(
    operation: PinnedAuthorityOperation,
) -> None:
    """A line that cannot be a bien de inversión is a current deduction the factura itself grounds.

    LIVA art. 108.Dos.5.º excludes from the bienes de inversión every
    acquisition whose value "sea inferior a" the threshold, and fact 0085 names
    ``invoice_evidence`` as the authority a domestic current deduction needs
    (art. 97, RIVA art. 99). So the invoice projects without a linked movement,
    and its provenance names the invoice rather than an invented ledger row.
    """
    invoice = _rated_reverse_charge(_escaso_valor() - Decimal("0.01"))

    screened = screened_invoice_iva_result(invoice, linked_movements=(), operation=operation)

    assert screened.deduction_authority_missing is False
    (observation,) = screened.observations
    assert observation.deduction_fact_kind == IvaDeductionFactKind.from_registry("domestic_current")
    assert observation.deduction_provenance == IvaDeductionClassificationProvenance(
        authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
        source_locator=f"invoice:{invoice.invoice_id}",
        evidence_digest=invoice.invoice_id,
    )


def test_a_domestic_invoice_at_the_threshold_is_withheld_when_nothing_classifies_it(
    operation: PinnedAuthorityOperation,
) -> None:
    """ "Sea inferior a" is strict: at the threshold the good may be a bien de inversión.

    The deduction family then differs (``domestic_investment`` and the art. 107
    regularisation), so the invoice is withheld rather than defaulted to a
    current expense, and the caller reports it as a blocking finding.
    """
    invoice = _rated_reverse_charge(_escaso_valor())

    screened = screened_invoice_iva_result(invoice, linked_movements=(), operation=operation)

    assert screened.deduction_authority_missing is True
    assert screened.observations == ()


def test_a_linked_movement_classification_is_copied_onto_the_projection_not_reinvented(
    operation: PinnedAuthorityOperation,
) -> None:
    """With a classified paying movement, its exact family and provenance are copied across UNCHANGED.

    Asserted against the authority object rather than literals, and with a
    provenance distinct from the one the invoice would ground on its own, so a
    projection that fell back to ``invoice_evidence`` would fail here.
    """
    authority = _received_reverse_charge_deduction_authority()
    movement = _movement_carrying(authority)
    linked = _received_reverse_charge(slot=IvaRate.from_registry("RATE_21"), cuota="420.00").model_copy(
        update={"linked_transaction_ids": (movement.transaction_id,)},
    )

    screened = screened_invoice_iva_result(linked, linked_movements=(movement,), operation=operation)

    assert screened.deduction_authority_missing is False
    (observation,) = screened.observations
    assert observation.deduction_fact_kind is authority.deduction_fact_kind
    assert observation.deduction_provenance == authority.deduction_provenance


def test_linked_movements_that_disagree_leave_the_invoice_withheld(
    operation: PinnedAuthorityOperation,
) -> None:
    """Two payments classifying the one invoice differently ground nothing; no choice is made between them."""
    authority = _received_reverse_charge_deduction_authority()
    agreeing = _movement_carrying(authority)
    disagreeing = _movement_carrying(_intra_eu_ledger_authority())
    linked = _received_reverse_charge(slot=IvaRate.from_registry("RATE_21"), cuota="420.00").model_copy(
        update={"linked_transaction_ids": (agreeing.transaction_id, disagreeing.transaction_id)},
    )

    screened = screened_invoice_iva_result(linked, linked_movements=(agreeing, disagreeing), operation=operation)

    assert screened.deduction_authority_missing is True
    assert screened.observations == ()


_INVOICE_BUCKET_ID = "29292929-2929-4929-8929-292929292929"
_INVOICE_QUARTER = Period.from_year_and_code(_DAY.year, f"{(_DAY.month - 1) // 3 + 1}T")


def _unlinked_purchase(*, base: str, cuota: str, currency: str = "EUR", fx_rate: str | None = None) -> Invoice:
    """A received domestic invoice with one line at 21 %, in ``currency``."""
    payload: dict[str, object] = {
        "bucket_id": _INVOICE_BUCKET_ID,
        "kind": InvoiceKind.RECEIVED.value,
        "invoice_number": "F-2026-0078",
        "issued_at": _DAY.isoformat(),
        "counterparty_name": "Proveedor Ejemplo SL",
        "counterparty_tax_id": "ESB00015016",
        "counterparty_country": "ES",
        "base_total": base,
        "iva_total": cuota,
        "grand_total": format(Decimal(base) + Decimal(cuota), "f"),
        "currency": currency,
        "payment_status": "PENDING",
        "lines": [
            {
                "description": "Servicio",
                "quantity": "1",
                "unit_price": base,
                "subtotal": base,
                "iva_rate": IvaRate.from_registry("RATE_21").value,
                "iva_amount": cuota,
            },
        ],
    }
    if fx_rate is not None:
        payload.update(fx_rate=fx_rate, fx_rate_date=_DAY.isoformat(), fx_rate_source="synthetic-fixture")
    return Invoice.model_validate(payload)


def _period_side(*invoices: Invoice) -> PeriodInvoiceIvaSide:
    """The invoice side of the invoices' quarter, as calculation and ledger readiness read it."""
    window = TransactionCatalogue()
    return period_invoice_iva_side(
        invoices,
        bucket_id=_INVOICE_BUCKET_ID,
        period=_INVOICE_QUARTER,
        window=window,
        repository=HeldTransactionCatalogue(window),
        operation=_pinned_operation(),
    )


def test_a_withheld_invoice_is_a_blocking_finding_not_a_ledger_comparison() -> None:
    """The invoice is the IVA source, so a withheld one is reported for the person to classify.

    The ledger no longer carries invoiced operations, so there is no ledger
    total to weigh a withheld cuota against: the invoice reaches no casilla and
    the period carries a ``DEDUCTION_FAMILY_UNRESOLVED`` finding naming it,
    which blocks filing grade until its deduction family is recorded.
    """
    withheld = _unlinked_purchase(base=format(_escaso_valor(), "f"), cuota="631.06")
    grounded = _unlinked_purchase(base="100.00", cuota="21.00").model_copy(update={"invoice_number": "F-2026-0079"})

    side = _period_side(withheld, grounded)

    assert side.source.findings == (
        InvoiceIvaFinding(reason=InvoiceIvaFindingReason.DEDUCTION_FAMILY_UNRESOLVED, invoice_id=withheld.invoice_id),
    )
    assert {observation.ledger_id for observation in side.source.observations} == {f"invoice:{grounded.invoice_id}:0"}


def test_an_unconverted_foreign_invoice_refuses_instead_of_being_measured() -> None:
    """USD 420.00 without a rate has no EUR value, so it cannot be held against a EUR threshold."""
    with pytest.raises(AggregationValidationError) as exc_info:
        _period_side(_unlinked_purchase(base="2000.00", cuota="420.00", currency="USD"))

    assert exc_info.value.translated_message == "aggregation.modelo_bindings.errors.invoice_line_currency_unconverted"
    context = exc_info.value.context
    assert context is not None
    assert context["currency"] == "USD"
    assert context["line_index"] == "0"


def test_a_converted_foreign_invoice_is_measured_against_the_threshold_in_euro() -> None:
    """USD 3,500.00 at 0.80 EUR/USD is 2,800.00 EUR: below the threshold, so a current deduction.

    The native figure is above the threshold, so measuring it unconverted would
    have withheld an invoice that cannot be a bien de inversión. The observation
    carries the EUR figures (735 * 0.8 = 588).
    """
    invoice = _unlinked_purchase(base="3500.00", cuota="735.00", currency="USD", fx_rate="0.80")
    assert Decimal("3500.00") >= _escaso_valor()

    side = _period_side(invoice)

    assert side.source.findings == ()
    (observation,) = side.source.observations
    assert observation.base_amount == Decimal("2800.00")
    assert observation.iva_amount == Decimal("588.00")
    assert observation.deduction_fact_kind == IvaDeductionFactKind.from_registry("domestic_current")


_INTRA_EU_SERVICE = IvaCategory("intra_community_service_acquisition_reverse_charge")
_INTRA_EU_CUOTA = Decimal("420.00")


def _received_intra_eu_service(*, linked_to: str | None = None) -> Invoice:
    """A service bought from a supplier established in another Member State.

    The supplier invoices the base alone; the line carries the rate and cuota
    the recipient self-assesses under LIVA art. 84.Uno.2.º.
    """
    return Invoice.model_validate(
        {
            "bucket_id": "29292929-2929-4929-8929-292929292929",
            "kind": InvoiceKind.RECEIVED.value,
            "invoice_number": "CL-2026-0003",
            "issued_at": _DAY.isoformat(),
            "counterparty_name": "Cloud Example GmbH",
            "counterparty_tax_id": "DE123456789",
            "counterparty_country": "DE",
            "base_total": format(_BASE, "f"),
            "iva_total": format(_INTRA_EU_CUOTA, "f"),
            "grand_total": format(_BASE + _INTRA_EU_CUOTA, "f"),
            "currency": "EUR",
            "payment_status": "PENDING",
            "iva_category": _INTRA_EU_SERVICE.value,
            "linked_transaction_ids": () if linked_to is None else (linked_to,),
            "lines": [
                {
                    "description": "Alojamiento en la nube",
                    "quantity": "1",
                    "unit_price": format(_BASE, "f"),
                    "subtotal": format(_BASE, "f"),
                    "iva_rate": IvaRate.from_registry("RATE_21").value,
                    "iva_amount": format(_INTRA_EU_CUOTA, "f"),
                },
            ],
        },
    )


def _intra_eu_ledger_authority() -> IvaLedgerObservation:
    """The ledger row the supplier's invoice substantiates (LIVA art. 97.Uno.4.º)."""
    return IvaLedgerObservation(
        ledger_id="c" * 64,
        transaction_date=_DAY,
        category=_INTRA_EU_SERVICE,
        rate_kind=IvaRateKind("general"),
        flow_direction=IvaFlowDirection.from_registry("inversion_sujeto_pasivo"),
        base_amount=_BASE,
        iva_amount=_INTRA_EU_CUOTA,
        applied_rate=Decimal("0.21"),
        deduction_fact_kind=IvaDeductionFactKind.from_registry("intra_eu_current"),
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment"),
            source_locator="evidence:intra-eu-service",
            evidence_digest="b" * 64,
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def test_a_cuota_bearing_intra_eu_invoice_keeps_its_declared_self_assessment(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The self-assessed cuota is not read as domestic soportado from its rate slot.

    The rate slot alone would make the line a domestic purchase, a category the
    linked intra-EU deduction cannot pair with. The declared category governs, so
    the invoice describes what the ledger row describes and the two feeds reach
    the same casillas.
    """
    authority = _intra_eu_ledger_authority()
    invoice = _received_intra_eu_service(linked_to=_movement_carrying(authority).transaction_id)

    screened = screened_invoice_iva_result(
        invoice, linked_movements=(_movement_carrying(authority),), operation=_pinned_operation()
    )

    assert screened.deduction_authority_missing is False
    (observation,) = screened.observations
    assert observation.category == _INTRA_EU_SERVICE
    assert observation.flow_direction == IvaFlowDirection.from_registry("inversion_sujeto_pasivo")
    assert observation.deduction_provenance == authority.deduction_provenance
    revision = published_snapshot("303", filing_year=_YEAR, period="1T").revision
    from_invoice = resolve_iva_ledger_binding_values(revision, (observation,), operation=authority_operation)
    from_ledger = resolve_iva_ledger_binding_values(revision, (authority,), operation=authority_operation)
    assert any(from_ledger.values())
    assert from_invoice == from_ledger


def test_an_unlinked_intra_eu_invoice_is_withheld() -> None:
    """An intra-EU acquisition is never a domestic current deduction, so the invoice alone grounds nothing.

    It stays withheld whatever its base, and the period reports it as a
    finding instead of inventing an ``intra_eu_current`` family.
    """
    invoice = _received_intra_eu_service()
    screened = screened_invoice_iva_result(invoice, linked_movements=(), operation=_pinned_operation())

    assert screened.deduction_authority_missing is True
    assert screened.observations == ()
    assert _period_side(invoice).source.findings == (
        InvoiceIvaFinding(reason=InvoiceIvaFindingReason.DEDUCTION_FAMILY_UNRESOLVED, invoice_id=invoice.invoice_id),
    )
