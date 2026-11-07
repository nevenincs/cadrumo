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
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ....domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ....domain.calculations.registry.ledger_iva_screen_bindings import (
    IvaLedgerScreenBinding,
    invoice_ledger_screen_bindings,
)
from ....domain.invoices.enums import IvaRate
from ....domain.invoices.models import Invoice
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.flow import IvaFlowDirection
from ....domain.iva.schema import InvoiceKind, IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ..errors import AggregationValidationError
from ..iva_ledger_apportionment import resolve_iva_ledger_binding_values
from ..modelo_bindings_invoice_iva import (
    invoice_line_iva_observation,
    reverse_charge_cuota_not_derivable,
    screened_invoice_iva_result,
)
from ..modelo_bindings_invoice_iva_refusal import uncovered_withheld_invoice_cuota

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]


def _pinned_operation() -> PinnedAuthorityOperation:
    """The session lease this module scopes every test to."""
    scoped = governed_facts_in_scope()
    assert isinstance(scoped, PinnedAuthorityOperation)
    return scoped


_BASE = Decimal("2000.00")
_DAY = date(2026, 3, 15)
_DEFAULT_INVOICE_RATE = IvaRate.from_registry("EXEMPT")


def _received_reverse_charge(*, slot: IvaRate = _DEFAULT_INVOICE_RATE, cuota: str = "0.00") -> Invoice:
    """A construction supply the recipient must self-assess.

    The supplier charges nothing, which is what an art. 84.Uno.2 invoice looks
    like: a base, a declared treatment, and no cuota.
    """
    total = _BASE + Decimal(cuota)
    return Invoice.model_validate(
        {
            "bucket_id": "29292929-2929-4929-8929-292929292929",
            "kind": InvoiceKind.RECEIVED.value,
            "invoice_number": "F-2026-0077",
            "issued_at": _DAY.isoformat(),
            "counterparty_name": "Constructora Ejemplo SL",
            "counterparty_tax_id": "ESB00015016",
            "counterparty_country": "ES",
            "base_total": format(_BASE, "f"),
            "iva_total": cuota,
            "grand_total": format(total, "f"),
            "currency": "EUR",
            "payment_status": "PENDING",
            "iva_category": IvaCategory("domestic_reverse_charge").value,
            "lines": [
                {
                    "description": "Ejecucion de obra",
                    "quantity": "1",
                    "unit_price": format(_BASE, "f"),
                    "subtotal": format(_BASE, "f"),
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
    revision = published_snapshot("303", filing_year=2026, period="2T").revision

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


def test_a_cuota_bearing_received_invoice_is_withheld_when_no_ledger_authority_is_linked(
    operation: PinnedAuthorityOperation,
) -> None:
    """An invoice never manufactures the deduction authority an input row needs.

    An invoice carries an amount and a direction. It does not carry the exact
    statutory deduction family, nor the immutable evidence provenance that
    separates a domestic current expense from an investment, an import, an
    acquisition or a rectification. That authority lives on the frozen
    transaction-ledger observation the invoice is linked to.

    So the screen withholds the invoice rather than defaulting it to
    domestic-current, and says so on ``deduction_authority_missing`` -- which the
    silence guard turns into a refusal naming the transaction ledger as the
    producer that must supply the missing facts. Defaulting instead would invent
    a statutory fact, and the invented value would be indistinguishable from a
    recorded one everywhere downstream.
    """
    rated = _received_reverse_charge(slot=IvaRate.from_registry("RATE_21"), cuota="420.00")

    screened = screened_invoice_iva_result(rated, ledger_observations=(), operation=operation)

    assert screened.deduction_authority_missing is True
    assert screened.observations == ()


def test_a_linked_ledger_authority_is_copied_onto_the_projection_not_reinvented(
    operation: PinnedAuthorityOperation,
) -> None:
    """The complement: with the authority linked, the row projects and carries it.

    The point of withholding is not that received invoices are unroutable -- it
    is that their deduction identity must come from the ledger. Once the link
    exists, the exact family and provenance are copied across UNCHANGED. Asserted
    against the authority object itself rather than against literals, because a
    literal would still pass if the projection substituted its own default.
    """
    authority = _received_reverse_charge_deduction_authority()
    linked = _received_reverse_charge(slot=IvaRate.from_registry("RATE_21"), cuota="420.00").model_copy(
        update={"linked_transaction_ids": (authority.ledger_id,)},
    )

    screened = screened_invoice_iva_result(linked, ledger_observations=(authority,), operation=operation)

    assert screened.deduction_authority_missing is False
    (observation,) = screened.observations
    assert observation.deduction_fact_kind is authority.deduction_fact_kind
    assert observation.deduction_provenance == authority.deduction_provenance


_INPUT_CUOTA = "modelo-303-iva-soportado-interiores-cuota"
_OUTPUT_GENERAL_CUOTA = "modelo-303-iva-repercutido-general-cuota"


def _screen_bindings() -> tuple[IvaLedgerScreenBinding, ...]:
    """The M303 screen's typed bindings, selected from the pinned revision."""
    revision = published_snapshot("303", filing_year=2025, period="1T").revision
    return invoice_ledger_screen_bindings(revision, modelo="303")


def _unlinked_purchase(*, currency: str = "EUR", fx_rate: str | None = None) -> Invoice:
    """A received invoice: base 2000.00 plus 420.00 cuota, in ``currency``."""
    payload: dict[str, object] = {
        "bucket_id": "29292929-2929-4929-8929-292929292929",
        "kind": InvoiceKind.RECEIVED.value,
        "invoice_number": "F-2026-0078",
        "issued_at": _DAY.isoformat(),
        "counterparty_name": "Proveedor Ejemplo SL",
        "counterparty_tax_id": "ESB00015016",
        "counterparty_country": "ES",
        "base_total": "2000.00",
        "iva_total": "420.00",
        "grand_total": "2420.00",
        "currency": currency,
        "payment_status": "PENDING",
        "lines": [
            {
                "description": "Servicio",
                "quantity": "1",
                "unit_price": "2000.00",
                "subtotal": "2000.00",
                "iva_rate": IvaRate.from_registry("RATE_21").value,
                "iva_amount": "420.00",
            },
        ],
    }
    if fx_rate is not None:
        payload.update(fx_rate=fx_rate, fx_rate_date=_DAY.isoformat(), fx_rate_source="synthetic-fixture")
    return Invoice.model_validate(payload)


def test_a_withheld_invoice_the_ledger_already_carries_is_not_counted_as_uncovered() -> None:
    """Withholding the row is unconditional; refusing the whole filing is not.

    An unlinked purchase invoice whose cuota the transaction ledger ALREADY
    carries is corroborating evidence of an operation that is declared. The
    totals are right, so there is nothing silent to refuse over -- the operator
    is told through the diagnostic channel instead. Refusing here would block a
    correct filing purely because an invoice-to-transaction link is absent.
    """
    rated = _received_reverse_charge(slot=IvaRate.from_registry("RATE_21"), cuota="420.00")

    uncovered = uncovered_withheld_invoice_cuota(
        (rated,),
        screen_bindings=_screen_bindings(),
        transaction_binding_values={_INPUT_CUOTA: Decimal("420.00")},
    )

    assert uncovered == Decimal("0")


def test_a_withheld_invoice_absent_from_the_ledger_is_counted_as_uncovered() -> None:
    """The other half, and the reason the refusal still exists.

    With no matching ledger cuota the invoice's input IVA reaches no casilla at
    all. That is the genuine gap this guard was built for, so it is reported as
    an excess and the caller refuses rather than quietly filing short. Asserted
    on the exact shortfall, not merely on being positive, because a guard that
    fires with the wrong magnitude tells the operator to look in the wrong place.
    """
    rated = _received_reverse_charge(slot=IvaRate.from_registry("RATE_21"), cuota="420.00")

    uncovered = uncovered_withheld_invoice_cuota(
        (rated,),
        screen_bindings=_screen_bindings(),
        transaction_binding_values={_INPUT_CUOTA: Decimal("100.00")},
    )

    assert uncovered == Decimal("320.00")


def test_output_iva_cannot_cover_a_missing_purchase_cuota() -> None:
    """A received invoice is weighed against the input slots only.

    Sales IVA of 1000.00 sits in the output slot and the input slot is empty:
    the 420.00 purchase cuota is entirely uncovered. Summing every slot would
    have judged it covered (1000.00 >= 420.00).
    """
    uncovered = uncovered_withheld_invoice_cuota(
        (_unlinked_purchase(),),
        screen_bindings=_screen_bindings(),
        transaction_binding_values={_OUTPUT_GENERAL_CUOTA: Decimal("1000.00")},
    )

    assert uncovered == Decimal("420.00")


def test_an_unconverted_foreign_invoice_refuses_instead_of_being_compared() -> None:
    """USD 420.00 without a rate has no EUR value; comparing it would be a currency mix."""
    with pytest.raises(AggregationValidationError) as exc_info:
        uncovered_withheld_invoice_cuota(
            (_unlinked_purchase(currency="USD"),),
            screen_bindings=_screen_bindings(),
            transaction_binding_values={_INPUT_CUOTA: Decimal("420.00")},
        )

    assert exc_info.value.translated_message == "aggregation.modelo_bindings.errors.invoice_line_currency_unconverted"
    context = exc_info.value.context
    assert context is not None
    assert context["currency"] == "USD"
    assert context["line_index"] == "0"


def test_a_converted_foreign_invoice_is_compared_in_euro() -> None:
    """USD 420.00 at 0.80 EUR/USD is 336.00 EUR (420 * 0.8), not 420.

    Ledger input 400.00 EUR covers 336.00; the raw native comparison would have
    reported 20.00 uncovered. Ledger input 300.00 leaves 36.00 uncovered.
    """
    invoice = _unlinked_purchase(currency="USD", fx_rate="0.80")
    bindings = _screen_bindings()

    covered = uncovered_withheld_invoice_cuota(
        (invoice,),
        screen_bindings=bindings,
        transaction_binding_values={_INPUT_CUOTA: Decimal("400.00")},
    )
    short = uncovered_withheld_invoice_cuota(
        (invoice,),
        screen_bindings=bindings,
        transaction_binding_values={_INPUT_CUOTA: Decimal("300.00")},
    )

    assert covered == Decimal("0")
    assert short == Decimal("36.00")


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
    invoice = _received_intra_eu_service(linked_to=authority.ledger_id)

    screened = screened_invoice_iva_result(invoice, ledger_observations=(authority,), operation=_pinned_operation())

    assert screened.deduction_authority_missing is False
    (observation,) = screened.observations
    assert observation.category == _INTRA_EU_SERVICE
    assert observation.flow_direction == IvaFlowDirection.from_registry("inversion_sujeto_pasivo")
    assert observation.deduction_provenance == authority.deduction_provenance
    revision = published_snapshot("303", filing_year=2025, period="1T").revision
    from_invoice = resolve_iva_ledger_binding_values(revision, (observation,), operation=authority_operation)
    from_ledger = resolve_iva_ledger_binding_values(revision, (authority,), operation=authority_operation)
    assert any(from_ledger.values())
    assert from_invoice == from_ledger


def test_an_unlinked_intra_eu_invoice_is_withheld() -> None:
    """Without the ledger row's deduction authority the self-assessed input is not invented."""
    screened = screened_invoice_iva_result(
        _received_intra_eu_service(), ledger_observations=(), operation=_pinned_operation()
    )

    assert screened.deduction_authority_missing is True
    assert screened.observations == ()
