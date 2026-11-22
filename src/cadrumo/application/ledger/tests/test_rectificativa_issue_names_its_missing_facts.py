"""The Modelo 303 block on a rectificativa names exactly the facts its side is missing.

A blanket "this is a rectificativa and no rate row declares it" told the person
that the period was stuck and nothing about what to do. The facts the record
needs differ by side -- LIVA art. 114.Dos keys the recipient's period on the
reception date, which an issued document never states -- so the finding carries
them per side and the served sentence lists them.

Two properties matter and are both proved here:

- the issued side is asked for three facts and the received side for four, with
  the reception date the only difference;
- the block holds even when every fact IS stated, on its own reason and with
  the derived figures in hand, because the period a modification belongs to is
  still undecided. A sentence that stopped complaining once the facts were in
  would say the modification was declared when it is not.

Real-behaviour: real invoices through the real invoice-side screen and the real
preflight projection over the published authority. No mocks, stubs, skips or
xfail.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.invoice_legal_classification import (
    resolve_invoice_legal_classification_catalogue,
)
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.invoices.enums import InvoiceClass, IvaRate, PaymentStatus, RectificationFact
from ....domain.invoices.models import INVOICE_WRITE_ADMISSION, Invoice, InvoiceLine
from ....domain.invoices.rectification_modification import RectificationModificationRefusal
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.models import TransactionCatalogue
from ...aggregation.invoice_iva_source import period_invoice_iva_side
from ..preflight import (
    HeldTransactionCatalogue,
    LedgerPreflightIssue,
    LedgerPreflightIssueReason,
    invoice_side_preflight_issues,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "5b5b5b5b-5b5b-4b5b-8b5b-5b5b5b5b5b5b"
_YEAR = filing_year_envelope().horizon
_ISSUED_AT = date(_YEAR, 5, 12)
_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Screen invoices under the generation-pinned authority production uses."""
    with bundled_indexed_authority().operation():
        yield


def _period() -> Period:
    return Period.from_year_and_code(_YEAR, "2T")


def _rectificativa(*, kind: InvoiceKind, **facts: object) -> Invoice:
    payload: dict[str, object] = {
        "kind": kind,
        "invoice_class": InvoiceClass.from_registry("RECTIFICATIVA"),
        "series": "R",
        "rectifies_invoice_number": "2026/F-0001",
        "invoice_number": "2026/R-0001",
        "issued_at": _ISSUED_AT,
        "counterparty_name": "Contraparte SL",
        "counterparty_tax_id": "B00015016",
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA,
        "currency": "EUR",
        "lines": (
            InvoiceLine(
                description="Abono",
                quantity=Decimal("1"),
                unit_price=_BASE,
                subtotal=_BASE,
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=_CUOTA,
            ),
        ),
        "payment_status": PaymentStatus.PENDING,
    }
    payload.update(facts)
    return Invoice.model_validate(payload, context=INVOICE_WRITE_ADMISSION)


def _issue(invoice: Invoice) -> LedgerPreflightIssue:
    """The one preflight issue the period's invoice side raises, through the real projection."""
    window = TransactionCatalogue.from_transactions(())
    with bundled_indexed_authority().operation() as operation:
        side = period_invoice_iva_side(
            (invoice,),
            bucket_id=_BUCKET_ID,
            period=_period(),
            window=window,
            repository=HeldTransactionCatalogue(window),
            operation=operation,
        )
    issues = invoice_side_preflight_issues(side, cash_accounting_enrolled=False)
    (issue,) = issues
    return issue


def test_a_received_rectificativa_is_asked_for_four_facts() -> None:
    """The recipient's period needs the reception date LIVA art. 114.Dos keys it on."""
    issue = _issue(_rectificativa(kind=InvoiceKind.RECEIVED))

    assert issue.reason is LedgerPreflightIssueReason.INVOICE_RECTIFICATIVA_MODIFICATION_UNMODELLED
    assert issue.missing_facts == (
        RectificationFact.RECTIFICATION_METHOD.value,
        RectificationFact.RECTIFICATION_CAUSE.value,
        RectificationFact.RECTIFICATION_DIRECTION.value,
        RectificationFact.DOCUMENT_RECEIVED_ON.value,
    )
    for fact in issue.missing_facts:
        assert fact in issue.detail


def test_an_issued_rectificativa_is_asked_for_three_and_never_the_reception_date() -> None:
    """The issuer states no reception, so asking for one would be asking for a fact it lacks."""
    issue = _issue(_rectificativa(kind=InvoiceKind.ISSUED))

    assert issue.missing_facts == (
        RectificationFact.RECTIFICATION_METHOD.value,
        RectificationFact.RECTIFICATION_CAUSE.value,
        RectificationFact.RECTIFICATION_DIRECTION.value,
    )
    assert RectificationFact.DOCUMENT_RECEIVED_ON.value not in issue.detail


def test_a_fact_the_record_already_states_is_not_asked_for_again() -> None:
    """Only the gaps are named, so supplying one fact removes it from the list."""
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    invoice = _rectificativa(
        kind=InvoiceKind.ISSUED,
        rectification_method=str(catalogue.diferencia_token),
    )

    issue = _issue(invoice)

    assert issue.missing_facts == (
        RectificationFact.RECTIFICATION_CAUSE.value,
        RectificationFact.RECTIFICATION_DIRECTION.value,
    )


def test_a_complete_rectificativa_still_blocks_and_shows_the_derived_figures() -> None:
    """Slice boundary: the modification is derived, and the period it belongs to is not decided.

    This is the assertion that keeps the slice honest. A complete record moves
    to its own reason carrying the signed figures the document's method reads,
    with no fact named, rather than appearing to be declared.
    """
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    invoice = _rectificativa(
        kind=InvoiceKind.RECEIVED,
        rectification_method=str(catalogue.diferencia_token),
        rectification_cause=str(catalogue.art_80_tres_cause_token),
        rectification_direction=str(catalogue.minoracion_token),
        document_received_on=_ISSUED_AT + timedelta(days=5),
    )

    issue = _issue(invoice)

    assert issue.reason is LedgerPreflightIssueReason.INVOICE_RECTIFICATIVA_PERIOD_UNDECIDED
    assert issue.missing_facts == ()
    assert "does not state" not in issue.detail
    # A minoración of the whole invoice: the magnitudes the record holds,
    # negated once by the direction it records.
    assert issue.derived_modification_base == -_BASE
    assert issue.derived_modification_cuota == -_CUOTA
    assert issue.derived_modification_recargo is None
    assert f"-{_BASE:f}" in issue.detail
    assert f"-{_CUOTA:f}" in issue.detail


def test_a_substitution_with_no_original_says_so_in_its_own_sentence() -> None:
    """The refusal reaches the diagnostic, so the hold names the problem rather than the family."""
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    invoice = _rectificativa(
        kind=InvoiceKind.ISSUED,
        rectification_method=str(catalogue.sustitucion_token),
        rectification_cause=str(catalogue.otra_modificacion_cause_token),
        rectification_direction=str(catalogue.minoracion_token),
    )

    issue = _issue(invoice)

    assert issue.reason is LedgerPreflightIssueReason.INVOICE_RECTIFICATIVA_MODIFICATION_UNMODELLED
    assert issue.missing_facts == ()
    assert RectificationModificationRefusal.ORIGINAL_NOT_FOUND.value in issue.detail
    assert issue.derived_modification_base is None
