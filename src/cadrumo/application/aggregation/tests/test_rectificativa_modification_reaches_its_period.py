"""A received rectificativa's modification reaches casillas 40 and 41 of the period that holds it.

Slice 2 derived the signed modification and declared none, because the period
it belongs to was not decided. With the period rule in place it is declared, on
the input side fact 0085 names for a rectification of the category, with the
negative sign the Modelo 303 instructions require: "Si el resultado de la
rectificación implica una minoración de las deducciones, se consignará con
signo negativo."

Five properties are proved here through the real invoice screen, the real
period side and the real Modelo 303 binding resolution:

* a received minoración on an art. 80 ground received inside the period reaches
  the rectificación-de-deducciones casillas with negative base and cuota;
* the same document received in the NEXT period contributes nothing to this one
  and is disclosed as an excluded contribution, and is declared in the next;
* an issued minoración whose art. 89.Cinco election is unrecorded blocks,
  naming that election;
* a received aumento whose art. 114.Dos.1.º period is unrecorded blocks, naming
  it;
* and an art. 80.Tres modification blocks until the RIVA art. 24 obligations
  are attested.

Expected figures are computed by hand from what the document states: a 100.00
base at 21 % is a 21.00 cuota, and a minoración declares both negative.

Real-behaviour: real invoices through the real invoice IVA screen, period side
and ledger binding resolver over the published authority. No mocks, stubs,
skips or xfail.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.invoice_legal_classification import (
    resolve_invoice_legal_classification_catalogue,
)
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.invoices.enums import InvoiceClass, IvaRate, PaymentStatus, RectificationFact
from ....domain.invoices.models import INVOICE_WRITE_ADMISSION, Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind, IvaLedgerObservationRole
from ....domain.transactions.models import TransactionCatalogue
from ...ledger.preflight import HeldTransactionCatalogue
from ..invoice_iva_source import (
    InvoiceIvaFinding,
    InvoiceIvaFindingReason,
    PeriodInvoiceIvaSide,
    period_invoice_iva_side,
)
from ..iva_ledger_apportionment import resolve_iva_ledger_binding_values
from ..modelo_bindings_invoice_iva import excluded_rectification_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "5e5e5e5e-5e5e-4e5e-8e5e-5e5e5e5e5e5e"
_YEAR = filing_year_envelope().horizon
#: The original accrued in the first quarter; the rectificativa is issued in the second.
_ORIGINAL_ISSUED_AT = date(_YEAR, 2, 10)
_ISSUED_AT = date(_YEAR, 5, 12)
#: A reception inside the second quarter, and one inside the third.
_RECEIVED_IN_Q2 = date(_YEAR, 5, 20)
_RECEIVED_IN_Q3 = date(_YEAR, 7, 3)
_RATE_21 = IvaRate.from_registry("RATE_21")
_BASE = Decimal("100.00")
_CUOTA = Decimal("21.00")
_Q2 = Period.from_year_and_code(_YEAR, "2T")
_Q3 = Period.from_year_and_code(_YEAR, "3T")
#: The semantic casillas the 2022 and later editions bind the interior
#: rectificación de deducciones to, which the Modelo 303 form prints as 40
#: and 41.
_CASILLA_BASE = "iva.rectificacion-deducciones.interiores.base"
_CASILLA_CUOTA = "iva.rectificacion-deducciones.interiores"
#: The semantic carriers of the invoice-sourced half of boxes 14 and 15.
_CASILLA_MODIFICACION_BASE = "iva.modificacion-bases-cuotas.base"
_CASILLA_MODIFICACION_CUOTA = "iva.modificacion-bases-cuotas"
_CASILLA_MODIFICACION_RECARGO = "iva.modificacion-recargo"


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Screen invoices under the generation-pinned authority production uses."""
    with bundled_indexed_authority().operation():
        yield


def _line(base: Decimal, cuota: Decimal) -> InvoiceLine:
    return InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=_RATE_21,
        iva_amount=cuota,
    )


def _invoice(*, issued_at: date = _ISSUED_AT, **overrides: Any) -> Invoice:
    payload: dict[str, Any] = {
        "bucket_id": _BUCKET_ID,
        "kind": InvoiceKind.RECEIVED,
        "invoice_class": InvoiceClass.from_registry("ORDINARIA"),
        "invoice_number": "2026/F-0001",
        "issued_at": issued_at,
        "counterparty_name": "Proveedor SL",
        "counterparty_tax_id": "B00015016",
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA,
        "currency": "EUR",
        "lines": (_line(_BASE, _CUOTA),),
        "payment_status": PaymentStatus.PENDING,
    }
    payload.update(overrides)
    return Invoice.model_validate(payload, context=INVOICE_WRITE_ADMISSION)


def _original() -> Invoice:
    """The ordinary received invoice the rectificativa corrects, accrued a quarter earlier."""
    return _invoice(issued_at=_ORIGINAL_ISSUED_AT)


def _rectificativa(**overrides: Any) -> Invoice:
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    payload: dict[str, Any] = {
        "invoice_class": InvoiceClass.from_registry("RECTIFICATIVA"),
        "series": "R",
        "invoice_number": "2026/R-0001",
        "rectifies_invoice_number": "2026/F-0001",
        "rectification_method": str(catalogue.diferencia_token),
        "rectification_cause": "art_80_dos",
        "rectification_direction": str(catalogue.minoracion_token),
        "document_received_on": _RECEIVED_IN_Q2,
    }
    payload.update(overrides)
    return _invoice(**payload)


def _side(invoices: Sequence[Invoice], *, period: Period) -> PeriodInvoiceIvaSide:
    window = TransactionCatalogue.from_transactions(())
    with bundled_indexed_authority().operation() as operation:
        return period_invoice_iva_side(
            invoices,
            bucket_id=_BUCKET_ID,
            period=period,
            window=window,
            repository=HeldTransactionCatalogue(window),
            operation=operation,
        )


def _casilla_values(side: PeriodInvoiceIvaSide, *, period: Period) -> dict[str, Decimal]:
    """Resolve the period's observations into the casillas the 303 revision binds them to."""
    revision = published_snapshot("303", filing_year=period.filing_year, period=period.registry_token).revision
    with bundled_indexed_authority().operation() as operation:
        values = resolve_iva_ledger_binding_values(revision, side.source.observations, operation=operation)
    by_binding = {str(binding): amount for binding, amount in values.items()}
    return {
        str(casilla.id): by_binding[str(casilla.binding)]
        for casilla in _bound_casillas(revision)
        if str(casilla.binding) in by_binding
    }


def _bound_casillas(revision: ModeloRevision) -> tuple[Any, ...]:
    return tuple(casilla for casilla in revision.casillas if casilla.binding is not None)


def _finding(side: PeriodInvoiceIvaSide) -> InvoiceIvaFinding:
    (finding,) = side.source.findings
    return finding


def test_a_received_minoracion_received_in_the_period_reaches_casillas_40_and_41_negative() -> None:
    """Art. 114.Dos.2.º places it in the reception period, and the instructions sign it negative."""
    original = _original()
    rectificativa = _rectificativa()

    side = _side((original, rectificativa), period=_Q2)

    assert side.source.findings == ()
    values = _casilla_values(side, period=_Q2)
    assert values[_CASILLA_BASE] == -_BASE
    assert values[_CASILLA_CUOTA] == -_CUOTA


def test_the_same_document_received_in_the_next_period_is_excluded_here_and_declared_there() -> None:
    """One modification reaches exactly one declaración-liquidación, and the other one says so."""
    original = _original()
    rectificativa = _rectificativa(document_received_on=_RECEIVED_IN_Q3)

    second_quarter = _side((original, rectificativa), period=_Q2)
    third_quarter = _side((original, rectificativa), period=_Q3)

    assert second_quarter.source.findings == ()
    assert second_quarter.source.observations == ()
    (disclosure,) = excluded_rectification_diagnostics(
        second_quarter.source.screen.rectificativas,
        resolver_id="ledger-iva",
    )
    assert disclosure.reason == "invoice_rectificativa_declared_in_another_period"
    assert str(_Q3) in disclosure.message

    third_values = _casilla_values(third_quarter, period=_Q3)
    assert third_values[_CASILLA_BASE] == -_BASE
    assert third_values[_CASILLA_CUOTA] == -_CUOTA


def test_an_issued_minoracion_without_its_election_blocks_naming_it() -> None:
    """Art. 89.Cinco hands the issuer two routes, and this application makes neither choice."""
    rectificativa = _rectificativa(kind=InvoiceKind.ISSUED, document_received_on=None)

    side = _side((_invoice(issued_at=_ORIGINAL_ISSUED_AT, kind=InvoiceKind.ISSUED), rectificativa), period=_Q2)

    finding = _finding(side)
    assert finding.reason is InvoiceIvaFindingReason.RECTIFICATIVA_PERIOD_NEEDS_FACT
    assert finding.rectification_period_need is RectificationFact.ISSUER_MINORACION_ELECTION
    assert side.source.observations == ()


def test_a_recipient_aumento_without_its_elected_period_blocks_naming_it() -> None:
    """Art. 114.Dos.1.º's election is the recipient's, and an unrecorded one is not guessed."""
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    rectificativa = _rectificativa(rectification_direction=str(catalogue.aumento_token))

    side = _side((_original(), rectificativa), period=_Q2)

    finding = _finding(side)
    assert finding.reason is InvoiceIvaFindingReason.RECTIFICATIVA_PERIOD_NEEDS_FACT
    assert finding.rectification_period_need is RectificationFact.RECIPIENT_INCREASE_PERIOD
    assert side.source.observations == ()


def test_art_80_tres_without_the_riva_art_24_attestation_blocks() -> None:
    """The application cannot observe the communication or the remittance art. 24 requires."""
    rectificativa = _rectificativa(rectification_cause="art_80_tres")

    side = _side((_original(), rectificativa), period=_Q2)

    finding = _finding(side)
    assert finding.reason is InvoiceIvaFindingReason.RECTIFICATIVA_PERIOD_NEEDS_FACT
    assert finding.rectification_period_need is RectificationFact.ART_80_TRES_OBLIGATIONS_ATTESTED
    assert side.source.observations == ()


def test_a_received_modification_whose_original_the_catalogue_lacks_blocks_rather_than_routes_a_guess() -> None:
    """The deduction family that routes the box is the ORIGINAL's, never the rectificativa's."""
    rectificativa = _rectificativa()

    side = _side((rectificativa,), period=_Q2)

    finding = _finding(side)
    assert finding.reason is InvoiceIvaFindingReason.RECTIFICATIVA_DEDUCTION_ROW_UNDECLARABLE
    assert side.source.observations == ()


def test_an_issued_minoracion_this_period_declares_reaches_casillas_14_and_15_signed() -> None:
    """Art. 89.Cinco places it here, and the instructions declare it "con el signo que corresponda".

    A minoración by difference of a 100.00 base at 21 % is a 100.00 base and a
    21.00 cuota the document reduces, so both are declared negative. The
    observation carries the rectification-modification role, which is what
    keeps the correction out of the ordinary rate boxes [01] and [03] the sale
    itself is declared in, and the semantic carriers of boxes 14 and 15 are the
    ones that read it.
    """
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    rectificativa = _rectificativa(
        kind=InvoiceKind.ISSUED,
        document_received_on=None,
        issuer_minoracion_election=str(catalogue.regularizacion_en_autoliquidacion_token),
        issuer_minoracion_regularisation_period=_Q2,
    )

    side = _side((_invoice(issued_at=_ORIGINAL_ISSUED_AT, kind=InvoiceKind.ISSUED), rectificativa), period=_Q2)

    assert side.source.findings == ()
    (observation,) = side.source.observations
    assert observation.observation_role is IvaLedgerObservationRole.RECTIFICATION_MODIFICATION
    assert observation.deduction_fact_kind is None
    assert _Q2.contains(observation.transaction_date)
    values = _casilla_values(side, period=_Q2)
    assert values[_CASILLA_MODIFICACION_BASE] == -_BASE
    assert values[_CASILLA_MODIFICACION_CUOTA] == -_CUOTA


def test_the_same_minoracion_under_the_art_120_3_route_is_disclosed_and_declared_nowhere_here() -> None:
    """The art. 120.3 LGT procedure is outside these returns, so this period declares nothing."""
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    rectificativa = _rectificativa(
        kind=InvoiceKind.ISSUED,
        document_received_on=None,
        issuer_minoracion_election=str(catalogue.procedimiento_120_3_lgt_token),
    )

    side = _side((_invoice(issued_at=_ORIGINAL_ISSUED_AT, kind=InvoiceKind.ISSUED), rectificativa), period=_Q2)

    assert side.source.observations == ()
    assert side.source.findings == ()
    (disclosure,) = excluded_rectification_diagnostics(side.source.screen.rectificativas, resolver_id="ledger-iva")
    assert disclosure.reason == "invoice_rectificativa_declared_in_another_period"


def test_the_14_and_15_projections_add_the_invoice_half_to_the_operator_contribution() -> None:
    """Each box states one figure the record keeps as two contributions that never merge earlier."""
    revision = published_snapshot("303", filing_year=_Q2.filing_year, period=_Q2.registry_token).revision
    formulas = {str(formula.target_casilla_id): formula for formula in revision.formulas}
    for box, carrier, operator in (
        ("14", _CASILLA_MODIFICACION_BASE, "iva.modificacion-bases-cuotas.operador.base"),
        ("15", _CASILLA_MODIFICACION_CUOTA, "iva.modificacion-bases-cuotas.operador"),
    ):
        expression = formulas[box].expression
        assert str(expression.op) == "add"
        assert [str(arg.casilla_id) for arg in expression.args] == [carrier, operator]


def test_an_issued_minoracion_carrying_recargo_reaches_casilla_26_signed() -> None:
    """The instructions put the recargo half of a modification in casillas 25 and 26.

    LIVA art. 161 pairs one recargo rate with each IVA rate, so a modification
    at one rate carries its recargo on that rung. Box 26 states the cuota; box
    25, the base, stays the operator's exactly as the ordinary recargo bases
    [16], [19] and [22] do, because a base sum cannot select only the rows that
    bore recargo.
    """
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    recargo = Decimal("5.20")
    rectificativa = _rectificativa(
        kind=InvoiceKind.ISSUED,
        document_received_on=None,
        issuer_minoracion_election=str(catalogue.regularizacion_en_autoliquidacion_token),
        issuer_minoracion_regularisation_period=_Q2,
        recargo_amount=recargo,
        grand_total=_BASE + _CUOTA + recargo,
    )

    side = _side((_invoice(issued_at=_ORIGINAL_ISSUED_AT, kind=InvoiceKind.ISSUED), rectificativa), period=_Q2)

    assert side.source.findings == ()
    (observation,) = side.source.observations
    assert observation.recargo_amount == -recargo
    values = _casilla_values(side, period=_Q2)
    assert values[_CASILLA_MODIFICACION_RECARGO] == -recargo
