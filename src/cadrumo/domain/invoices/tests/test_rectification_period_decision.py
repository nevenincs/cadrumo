"""One rectificativa's modification is placed in exactly one period, and never guessed.

LIVA art. 89.Cinco and art. 114.Dos put different periods on the same document
depending on the side, the cause, the direction and the election the taxpayer
made. This exercises the real decision against the published vocabulary, and
the real write boundary against the published window facts.

The expected periods are read independently off the articles, not off the
implementation:

* an issued aumento on an art. 80 ground, elected into the period, belongs to
  the period the rectification was effected in -- "la declaración-liquidación
  del periodo en que se deba efectuar la rectificación";
* the same aumento electing a declaración-liquidación rectificativa, and the
  art. 120.3 LGT minoración route, belong to declarations these returns do not
  produce, so they name a route and no period;
* a received minoración on an art. 80 ground belongs to the reception period
  -- "el periodo impositivo en que el sujeto pasivo reciba el documento
  justificativo";
* a received minoración under art. 80.Tres belongs to "el periodo en que se
  ejerció el derecho a la deducción", against the RIVA art. 24 attestation;
* and every unrecorded election names the field the person opens.

Real-behaviour: the real decision and the real invoice write boundary over the
published authority. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from ....core.period import Period, PeriodKind
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.invoice_legal_classification import (
    resolve_invoice_legal_classification_catalogue,
)
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...iva.schema import InvoiceKind
from ..enums import InvoiceClass, IvaRate, PaymentStatus, RectificationFact
from ..errors import InvoiceValidationError
from ..models import INVOICE_WRITE_ADMISSION, Invoice, InvoiceLine
from ..rectification_period import (
    RectificationPeriodRefusal,
    RectificationPeriodRoute,
    decide_rectification_period,
)
from ..rule_findings import InvoiceRuleFindingCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUCKET_ID = "7d7d7d7d-7d7d-4d7d-8d7d-7d7d7d7d7d7d"
_YEAR = filing_year_envelope().horizon
#: The rectificativa is issued inside the second quarter, and received in it.
_ISSUED_AT = date(_YEAR, 5, 12)
_RATE_21 = IvaRate.from_registry("RATE_21")
_Q2 = Period.from_year_and_code(_YEAR, "2T")
_Q3 = Period.from_year_and_code(_YEAR, "3T")


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Read the vocabularies and the windows from the generation production pins."""
    with bundled_indexed_authority().operation():
        yield


def _catalogue() -> Any:
    return resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)


def _decide(**overrides: Any) -> Any:
    catalogue = _catalogue()
    facts: dict[str, Any] = {
        "kind": InvoiceKind.RECEIVED,
        "cause": catalogue.require_rectification_cause("art_80_dos"),
        "direction": catalogue.minoracion_token,
        "issued_at": _ISSUED_AT,
        "document_received_on": _ISSUED_AT,
        "issuer_increase_election": None,
        "issuer_minoracion_election": None,
        "issuer_minoracion_regularisation_period": None,
        "recipient_increase_period": None,
        "art_80_tres_obligations_attested": None,
        "exercised_deduction_period": None,
        "cadence": PeriodKind.QUARTERLY,
        "catalogue": catalogue,
    }
    facts.update(overrides)
    return decide_rectification_period(**facts)


def test_a_received_minoracion_on_an_art_80_ground_belongs_to_the_reception_period() -> None:
    """LIVA art. 114.Dos.2.º's last paragraph: the period the justificante was received in."""
    decided = _decide()

    assert decided.route is RectificationPeriodRoute.RECIPIENT_MINORACION_RECEPTION
    assert decided.period == _Q2
    assert decided.need is None


def test_a_received_minoracion_on_any_other_ground_goes_to_a_declaracion_liquidacion_rectificativa() -> None:
    """Art. 114.Dos.2.º's first paragraph is the rule; only art. 80 and the error fundado escape it."""
    decided = _decide(cause=_catalogue().otra_modificacion_cause_token)

    assert decided.route is RectificationPeriodRoute.RECIPIENT_MINORACION_AUTOLIQUIDACION_RECTIFICATIVA
    assert decided.period is None
    assert decided.need is None


def test_a_received_aumento_without_its_elected_period_names_that_field() -> None:
    """Art. 114.Dos.1.º hands the recipient the choice, and nothing here makes it for them."""
    decided = _decide(direction=_catalogue().aumento_token)

    assert decided.period is None
    assert decided.need is RectificationFact.RECIPIENT_INCREASE_PERIOD


def test_a_received_aumento_takes_the_period_the_recipient_elected() -> None:
    """The election is recorded, so the modification is declared where it says."""
    decided = _decide(direction=_catalogue().aumento_token, recipient_increase_period=_Q3)

    assert decided.route is RectificationPeriodRoute.RECIPIENT_INCREASE_ELECTED
    assert decided.period == _Q3


def test_an_issued_minoracion_without_its_election_names_that_field() -> None:
    """Art. 89.Cinco gives the issuer two routes for a minoración and no default between them."""
    decided = _decide(kind=InvoiceKind.ISSUED, document_received_on=None)

    assert decided.period is None
    assert decided.need is RectificationFact.ISSUER_MINORACION_ELECTION


def test_the_art_120_3_lgt_route_declares_outside_these_autoliquidaciones() -> None:
    """Letter a) is a procedure before the administration, so no period of these returns holds it."""
    decided = _decide(
        kind=InvoiceKind.ISSUED,
        document_received_on=None,
        issuer_minoracion_election=_catalogue().procedimiento_120_3_lgt_token,
    )

    assert decided.route is RectificationPeriodRoute.ISSUER_MINORACION_PROCEDIMIENTO_120_3_LGT
    assert decided.period is None
    assert decided.need is None


def test_the_regularisation_route_needs_the_period_it_regularises_in() -> None:
    """Letter b) regularises in a period the taxpayer picks inside its one-year window."""
    catalogue = _catalogue()
    needed = _decide(
        kind=InvoiceKind.ISSUED,
        document_received_on=None,
        issuer_minoracion_election=catalogue.regularizacion_en_autoliquidacion_token,
    )
    chosen = _decide(
        kind=InvoiceKind.ISSUED,
        document_received_on=None,
        issuer_minoracion_election=catalogue.regularizacion_en_autoliquidacion_token,
        issuer_minoracion_regularisation_period=_Q3,
    )

    assert needed.need is RectificationFact.ISSUER_MINORACION_REGULARISATION_PERIOD
    assert chosen.route is RectificationPeriodRoute.ISSUER_MINORACION_REGULARISATION
    assert chosen.period == _Q3


def test_an_issued_aumento_on_an_art_80_ground_offers_the_election_and_then_takes_it() -> None:
    """Art. 89.Cinco's second paragraph: the difference MAY go in the period of the rectification."""
    catalogue = _catalogue()
    needed = _decide(kind=InvoiceKind.ISSUED, document_received_on=None, direction=catalogue.aumento_token)
    included = _decide(
        kind=InvoiceKind.ISSUED,
        document_received_on=None,
        direction=catalogue.aumento_token,
        issuer_increase_election=catalogue.incluir_en_el_periodo_token,
    )

    assert needed.need is RectificationFact.ISSUER_INCREASE_ELECTION
    assert included.route is RectificationPeriodRoute.ISSUER_INCREASE_IN_PERIOD
    # The rectificativa was issued on 12 May, so the rectification is effected
    # in the second quarter and the difference is included there.
    assert included.period == _Q2


def test_an_issued_aumento_on_any_other_ground_has_no_election_at_all() -> None:
    """Art. 89.Cinco's first paragraph is the rule: a rectificativa autoliquidación, with no choice."""
    catalogue = _catalogue()
    decided = _decide(
        kind=InvoiceKind.ISSUED,
        document_received_on=None,
        direction=catalogue.aumento_token,
        cause=catalogue.otra_modificacion_cause_token,
    )

    assert decided.route is RectificationPeriodRoute.ISSUER_INCREASE_AUTOLIQUIDACION_RECTIFICATIVA
    assert decided.need is None


def test_art_80_tres_is_held_without_the_riva_art_24_attestation() -> None:
    """The application cannot observe a communication or a remittance, so it asks for the attestation."""
    decided = _decide(cause=_catalogue().art_80_tres_cause_token)

    assert decided.period is None
    assert decided.need is RectificationFact.ART_80_TRES_OBLIGATIONS_ATTESTED


def test_a_denied_art_80_tres_attestation_refuses_rather_than_asks_again() -> None:
    """An explicit "the obligations were not met" is an answer, and the answer refuses."""
    decided = _decide(cause=_catalogue().art_80_tres_cause_token, art_80_tres_obligations_attested=False)

    assert decided.refusal is RectificationPeriodRefusal.ART_80_TRES_OBLIGATIONS_NOT_ATTESTED
    assert decided.need is None
    assert decided.period is None


def test_an_attested_art_80_tres_minoracion_goes_to_the_exercised_deduction_period() -> None:
    """Art. 114.Dos.2.º: "el periodo en que se ejerció el derecho a la deducción", once attested."""
    catalogue = _catalogue()
    needed = _decide(cause=catalogue.art_80_tres_cause_token, art_80_tres_obligations_attested=True)
    placed = _decide(
        cause=catalogue.art_80_tres_cause_token,
        art_80_tres_obligations_attested=True,
        exercised_deduction_period=Period.from_year_and_code(_YEAR - 1, "4T"),
    )

    assert needed.need is RectificationFact.EXERCISED_DEDUCTION_PERIOD
    assert placed.route is RectificationPeriodRoute.RECIPIENT_MINORACION_EXERCISED_DEDUCTION
    assert placed.period == Period.from_year_and_code(_YEAR - 1, "4T")


def _line(base: Decimal, cuota: Decimal) -> InvoiceLine:
    return InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=_RATE_21,
        iva_amount=cuota,
    )


def _rectificativa(**overrides: Any) -> Invoice:
    catalogue = _catalogue()
    base, cuota = Decimal("100.00"), Decimal("21.00")
    payload: dict[str, Any] = {
        "bucket_id": _BUCKET_ID,
        "kind": InvoiceKind.RECEIVED,
        "invoice_class": InvoiceClass.from_registry("RECTIFICATIVA"),
        "series": "R",
        "invoice_number": "2026/R-0001",
        "issued_at": _ISSUED_AT,
        "counterparty_name": "Proveedor SL",
        "counterparty_tax_id": "B00015016",
        "counterparty_country": "ES",
        "base_total": base,
        "iva_total": cuota,
        "grand_total": base + cuota,
        "currency": "EUR",
        "lines": (_line(base, cuota),),
        "payment_status": PaymentStatus.PENDING,
        "rectifies_invoice_number": "2026/F-0001",
        "rectification_method": str(catalogue.diferencia_token),
        "rectification_cause": "art_80_dos",
        "rectification_direction": str(catalogue.minoracion_token),
        "document_received_on": _ISSUED_AT,
    }
    payload.update(overrides)
    return Invoice.model_validate(payload, context=INVOICE_WRITE_ADMISSION)


def _refused_rule_code(**overrides: Any) -> tuple[str, tuple[str, ...]]:
    """The stable rule code and the fields the write boundary's refusal names."""
    refusal = _write_refusal(**overrides)
    context = refusal.context
    assert context is not None
    code = context["rule_finding_code"]
    fields = context["fields"]
    assert isinstance(code, str)
    assert isinstance(fields, tuple)
    return code, tuple(str(field) for field in fields)


def _write_refusal(**overrides: Any) -> InvoiceValidationError:
    """The registered invoice refusal the write boundary raised, with its stable rule code.

    Pydantic wraps a validator's exception, so the refusal travels as the cause
    inside the validation failure. The lifecycle write verb unwraps it the same
    way before a person ever reads it, which is why the code and not the
    sentence is what this asserts on.
    """
    with pytest.raises(ValidationError) as raised:
        _rectificativa(**overrides)
    for detail in raised.value.errors(include_url=False):
        candidate = (detail.get("ctx") or {}).get("error")
        for error in (candidate, getattr(candidate, "__cause__", None)):
            if isinstance(error, InvoiceValidationError):
                return error
    message = f"the write boundary raised no registered invoice refusal: {raised.value}"
    raise AssertionError(message)


def test_the_write_boundary_refuses_an_elected_period_past_the_four_year_window() -> None:
    """Art. 114.Dos.1.º: no later declaración-liquidación once four years have run.

    The window fact declares four years, so the fifth year after the document
    was issued is outside it whatever the quarter.
    """
    code, fields = _refused_rule_code(
        rectification_direction=str(_catalogue().aumento_token),
        recipient_increase_period=Period.from_year_and_code(_YEAR + 5, "2T"),
    )

    assert code == InvoiceRuleFindingCode.RECTIFICATION_ELECTED_PERIOD_OUTSIDE_WINDOW.value
    assert fields == ("recipient_increase_period",)


def test_the_write_boundary_refuses_an_elected_period_before_the_reception() -> None:
    """Art. 114.Dos.1.º names the reception period first, so nothing earlier is admitted."""
    code, _fields = _refused_rule_code(
        rectification_direction=str(_catalogue().aumento_token),
        recipient_increase_period=Period.from_year_and_code(_YEAR, "1T"),
    )

    assert code == InvoiceRuleFindingCode.RECTIFICATION_ELECTED_PERIOD_OUTSIDE_WINDOW.value


def test_the_write_boundary_refuses_a_regularisation_period_past_the_one_year_window() -> None:
    """Art. 89.Cinco letter b) runs one year from the rectification, so the second year is out."""
    catalogue = _catalogue()
    code, _fields = _refused_rule_code(
        kind=InvoiceKind.ISSUED,
        document_received_on=None,
        issuer_minoracion_election=str(catalogue.regularizacion_en_autoliquidacion_token),
        issuer_minoracion_regularisation_period=Period.from_year_and_code(_YEAR + 2, "1T"),
    )

    assert code == InvoiceRuleFindingCode.RECTIFICATION_ELECTED_PERIOD_OUTSIDE_WINDOW.value


def test_the_write_boundary_admits_an_elected_period_inside_its_window() -> None:
    """The quarter after the reception is "las declaraciones-liquidaciones siguientes"."""
    invoice = _rectificativa(
        rectification_direction=str(_catalogue().aumento_token),
        recipient_increase_period=_Q3,
    )

    assert invoice.recipient_increase_period == _Q3


def test_the_write_boundary_refuses_an_issuer_election_on_a_received_invoice() -> None:
    """Art. 89.Cinco gives the ISSUER its election; a recipient never made it."""
    code, _fields = _refused_rule_code(
        issuer_minoracion_election=str(_catalogue().procedimiento_120_3_lgt_token),
    )

    assert code == InvoiceRuleFindingCode.RECTIFICATION_ELECTION_SIDE_MISMATCH.value


def test_the_write_boundary_refuses_a_recipient_period_on_an_issued_invoice() -> None:
    """Art. 114.Dos.1.º's election belongs to the recipient of the document."""
    code, _fields = _refused_rule_code(
        kind=InvoiceKind.ISSUED,
        document_received_on=None,
        rectification_direction=str(_catalogue().aumento_token),
        recipient_increase_period=_Q3,
    )

    assert code == InvoiceRuleFindingCode.RECTIFICATION_ELECTION_SIDE_MISMATCH.value


def test_the_write_boundary_refuses_an_increase_election_against_a_recorded_minoracion() -> None:
    """A minoración asks the art. 89.Cinco minoración question, not the increase one."""
    code, _fields = _refused_rule_code(
        kind=InvoiceKind.ISSUED,
        document_received_on=None,
        issuer_increase_election=str(_catalogue().incluir_en_el_periodo_token),
    )

    assert code == InvoiceRuleFindingCode.RECTIFICATION_ELECTION_DIRECTION_MISMATCH.value


def test_the_write_boundary_refuses_an_art_80_tres_attestation_on_another_cause() -> None:
    """The attestation attests the RIVA art. 24 obligations of an art. 80.Tres rectification."""
    code, _fields = _refused_rule_code(art_80_tres_obligations_attested=True)

    assert code == InvoiceRuleFindingCode.RECTIFICATION_ART_80_TRES_ATTESTATION_NOT_ALLOWED.value


def test_the_write_boundary_refuses_a_regularisation_period_without_its_election() -> None:
    """The period letter b) regularises in means nothing without letter b) recorded."""
    code, _fields = _refused_rule_code(
        kind=InvoiceKind.ISSUED,
        document_received_on=None,
        issuer_minoracion_regularisation_period=_Q2,
    )

    assert code == InvoiceRuleFindingCode.RECTIFICATION_REGULARISATION_PERIOD_WITHOUT_ELECTION.value
