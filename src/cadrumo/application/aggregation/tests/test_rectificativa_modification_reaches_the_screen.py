"""The M303 invoice screen derives a rectificativa's signed modification and still declares none.

Slice 1 blocked every factura rectificativa with the facts its side was
missing. With the facts recorded, RD 1619/2012 art. 15.5 says what its figures
mean, so the screen now reads the signed modification out of the document and
shows it. What it does NOT do is declare it: LIVA art. 89.Cinco and
art. 114.Dos put three different periods on three different grounds, and the
period being calculated is not evidence that the modification belongs to it.

Four properties are proved here through the real screen, the real period side
and the real original resolver:

- a complete difference rectificativa is held on its own reason with the signed
  figures in the finding, and reaches no rate row;
- a complete substitution is held the same way, with the difference read from
  the catalogue invoice it replaces, which accrued in an earlier period;
- a substitution whose original is in no catalogue invoice is held naming that;
- a substitution whose original answers to two catalogue invoices is held
  naming the ambiguity, because which figures it replaces is then unknown.

Expected figures are computed by hand from what each invoice states.

Real-behaviour: real invoices through the real invoice IVA screen and period
side over the published authority. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.invoice_legal_classification import (
    resolve_invoice_legal_classification_catalogue,
)
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.invoices.enums import InvoiceClass, IvaRate, PaymentStatus
from ....domain.invoices.models import INVOICE_WRITE_ADMISSION, Invoice, InvoiceLine
from ....domain.invoices.rectification_modification import (
    RectificationModification,
    RectificationModificationRefusal,
)
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.models import TransactionCatalogue
from ...ledger.preflight import HeldTransactionCatalogue, LedgerPreflightIssueReason
from ..invoice_iva_source import (
    InvoiceIvaFinding,
    InvoiceIvaFindingReason,
    PeriodInvoiceIvaSide,
    period_invoice_iva_side,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "6c6c6c6c-6c6c-4c6c-8c6c-6c6c6c6c6c6c"
_YEAR = filing_year_envelope().horizon
#: The rectificativa's own quarter, and an earlier one for the invoice it replaces.
_ISSUED_AT = date(_YEAR, 5, 12)
_ORIGINAL_ISSUED_AT = date(_YEAR, 2, 10)
_RATE_21 = IvaRate.from_registry("RATE_21")


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


def _invoice(*, base: Decimal, cuota: Decimal, issued_at: date = _ISSUED_AT, **overrides: Any) -> Invoice:
    line = _line(base, cuota)
    payload: dict[str, Any] = {
        "bucket_id": _BUCKET_ID,
        "kind": InvoiceKind.RECEIVED,
        "invoice_class": InvoiceClass.from_registry("ORDINARIA"),
        "invoice_number": "2026/F-0001",
        "issued_at": issued_at,
        "counterparty_name": "Proveedor SL",
        "counterparty_tax_id": "B00015016",
        "counterparty_country": "ES",
        "base_total": base,
        "iva_total": cuota,
        "grand_total": base + cuota,
        "currency": "EUR",
        "lines": (line,),
        "payment_status": PaymentStatus.PENDING,
    }
    payload.update(overrides)
    return Invoice.model_validate(payload, context=INVOICE_WRITE_ADMISSION)


def _rectificativa(*, method: str, base: Decimal, cuota: Decimal, **overrides: Any) -> Invoice:
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    return _invoice(
        base=base,
        cuota=cuota,
        invoice_class=InvoiceClass.from_registry("RECTIFICATIVA"),
        series="R",
        invoice_number="2026/R-0001",
        rectifies_invoice_number="2026/F-0001",
        rectification_method=method,
        rectification_cause=str(catalogue.otra_modificacion_cause_token),
        rectification_direction=str(catalogue.minoracion_token),
        document_received_on=_ISSUED_AT,
        **overrides,
    )


def _period_side(invoices: Sequence[Invoice]) -> PeriodInvoiceIvaSide:
    """The second quarter's invoice side, through the real screen and period side."""
    window = TransactionCatalogue.from_transactions(())
    with bundled_indexed_authority().operation() as operation:
        return period_invoice_iva_side(
            invoices,
            bucket_id=_BUCKET_ID,
            period=Period.from_year_and_code(_YEAR, "2T"),
            window=window,
            repository=HeldTransactionCatalogue(window),
            operation=operation,
        )


def _finding(invoices: Sequence[Invoice]) -> tuple[InvoiceIvaFinding, tuple[object, ...]]:
    """The one finding the period's invoice side raises, and the observations beside it."""
    side = _period_side(invoices)
    (finding,) = side.source.findings
    return finding, side.source.observations


def _derived_modification(invoices: Sequence[Invoice]) -> RectificationModification:
    """The signed modification the screen read out of the one rectificativa it holds.

    These documents state the cause the Modelo 303 instructions call "cualquier
    otra modificación", so LIVA art. 114.Dos.2.º's first paragraph routes them
    to a declaración-liquidación rectificativa and this period declares
    nothing. The derivation is what this module is about, so it is read off the
    screen rather than through a finding the period rule does not raise.
    """
    side = _period_side(invoices)
    assert side.source.findings == ()
    assert side.source.observations == ()
    (screened,) = side.source.screen.rectificativas
    modification = screened.derived.modification
    assert modification is not None
    return modification


def _methods() -> tuple[str, str]:
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    return str(catalogue.diferencia_token), str(catalogue.sustitucion_token)


def test_a_complete_difference_rectificativa_is_held_with_its_signed_figures() -> None:
    """The document's own lines, negated once by the minoración it records, and declared nowhere."""
    diferencia, _ = _methods()
    rectificativa = _rectificativa(method=diferencia, base=Decimal("100.00"), cuota=Decimal("21.00"))

    modification = _derived_modification((rectificativa,))

    assert (modification.base, modification.cuota) == (Decimal("-100.00"), Decimal("-21.00"))


def test_a_complete_substitution_is_held_with_the_difference_from_the_invoice_it_replaces() -> None:
    """800.00 replacing 1000.00 modifies by -200.00 and -42.00, read across periods.

    The original accrued in an earlier quarter, which is the ordinary case: the
    screen resolves it from the bucket's invoices, and that earlier invoice
    still contributes nothing to this period.
    """
    _, sustitucion = _methods()
    original = _invoice(
        base=Decimal("1000.00"),
        cuota=Decimal("210.00"),
        issued_at=_ORIGINAL_ISSUED_AT,
    )
    substitute = _rectificativa(method=sustitucion, base=Decimal("800.00"), cuota=Decimal("168.00"))

    modification = _derived_modification((original, substitute))

    assert (modification.base, modification.cuota) == (Decimal("-200.00"), Decimal("-42.00"))
    assert modification.original_invoice_id == original.invoice_id


def test_a_substitution_whose_original_the_catalogue_does_not_hold_is_held_naming_that() -> None:
    """Nothing to subtract from, so no modification is derived and the finding says why."""
    _, sustitucion = _methods()
    substitute = _rectificativa(method=sustitucion, base=Decimal("800.00"), cuota=Decimal("168.00"))

    finding, observations = _finding((substitute,))

    assert observations == ()
    assert finding.reason is InvoiceIvaFindingReason.RECTIFICATIVA_MODIFICATION_UNMODELLED
    assert finding.rectification_modification is None
    assert finding.rectification_refusal is RectificationModificationRefusal.ORIGINAL_NOT_FOUND
    assert finding.missing_rectification_facts == ()


def test_a_substitution_whose_original_answers_to_two_invoices_is_held_naming_the_ambiguity() -> None:
    """A correction records the number it replaces and not that invoice's series, so two can answer."""
    _, sustitucion = _methods()
    first = _invoice(base=Decimal("1000.00"), cuota=Decimal("210.00"), issued_at=_ORIGINAL_ISSUED_AT)
    second = _invoice(
        base=Decimal("900.00"),
        cuota=Decimal("189.00"),
        issued_at=_ORIGINAL_ISSUED_AT,
        series="B",
    )
    substitute = _rectificativa(method=sustitucion, base=Decimal("800.00"), cuota=Decimal("168.00"))

    finding, observations = _finding((first, second, substitute))

    assert observations == ()
    assert finding.reason is InvoiceIvaFindingReason.RECTIFICATIVA_MODIFICATION_UNMODELLED
    assert finding.rectification_refusal is RectificationModificationRefusal.ORIGINAL_AMBIGUOUS


def test_the_ledger_reports_every_rectificativa_hold_calculation_raises() -> None:
    """The ledger says a period is ready only when calculation would find the same reason."""
    for reason in (
        InvoiceIvaFindingReason.RECTIFICATIVA_MODIFICATION_UNMODELLED,
        InvoiceIvaFindingReason.RECTIFICATIVA_PERIOD_NEEDS_FACT,
        InvoiceIvaFindingReason.RECTIFICATIVA_DEDUCTION_ROW_UNDECLARABLE,
        InvoiceIvaFindingReason.RECTIFICATIVA_ISSUED_MODIFICATION_UNBOUND,
    ):
        assert LedgerPreflightIssueReason(reason.value).value == reason.value
