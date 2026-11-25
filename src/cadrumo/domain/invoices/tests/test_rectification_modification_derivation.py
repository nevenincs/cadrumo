"""The signed modification a factura rectificativa makes, derived from its own method.

RD 1619/2012 art. 15.5 permits two readings of a rectificativa's figures and
only two, so identical printed amounts mean two different modifications. These
tests prove the derivation reads each one as the article states it, through the
real :class:`Invoice` boundary under the published authority:

- under the difference method the document's own lines ARE the modification,
  and the recorded direction is the only thing that signs them;
- under the substitution method the lines are the post-rectification figures,
  so the modification is the substitute minus the original, per rate and per
  category, and a rate nothing moved on contributes nothing;
- a substitution whose original is absent or ambiguous derives nothing and
  refuses, naming which;
- the recargo de equivalencia follows the same sign as the base and cuota it
  rides on;
- the record keeps its non-negative magnitudes throughout: every sign in these
  assertions exists only in what the derivation returns.

Expected values are computed by hand from the figures each invoice states, not
read back from the derivation.

Real-behaviour: real invoices through the real model validators over the
published authority, with every rectification token projected through the real
fact 0141 vocabulary. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from ...calculations.registry.authority import bundled_indexed_authority
from ...calculations.registry.invoice_legal_classification import (
    resolve_invoice_legal_classification_catalogue,
)
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ...iva.schema import InvoiceKind
from ..enums import InvoiceClass, IvaRate, PaymentStatus
from ..models import INVOICE_WRITE_ADMISSION, Invoice, InvoiceLine
from ..rectification_modification import (
    RectificationModificationRefusal,
    derive_rectification_modification,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = filing_year_envelope().horizon
_ISSUED_AT = date(_YEAR, 4, 15)
_RATE_21 = IvaRate.from_registry("RATE_21")
_RATE_10 = IvaRate.from_registry("RATE_10")


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    """Derive under the generation-pinned authority production uses."""
    with bundled_indexed_authority().operation():
        yield


def _line(*, base: Decimal, cuota: Decimal, rate: IvaRate = _RATE_21) -> InvoiceLine:
    return InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=rate,
        iva_amount=cuota,
    )


def _invoice(
    *,
    lines: tuple[InvoiceLine, ...] = (),
    recargo_amount: Decimal | None = None,
    **overrides: Any,
) -> Invoice:
    """One received invoice, admitted through the context both production write paths pass."""
    if not lines:
        lines = (_line(base=Decimal("100.00"), cuota=Decimal("21.00")),)
    base = sum((line.subtotal for line in lines), Decimal("0"))
    cuota = sum((line.iva_amount for line in lines), Decimal("0"))
    recargo = recargo_amount
    payload: dict[str, Any] = {
        "kind": InvoiceKind.RECEIVED,
        "invoice_class": InvoiceClass.from_registry("ORDINARIA"),
        "invoice_number": "2026/F-0001",
        "issued_at": _ISSUED_AT,
        "counterparty_name": "Proveedor SL",
        "counterparty_tax_id": "B00015016",
        "counterparty_country": "ES",
        "base_total": base,
        "iva_total": cuota,
        "grand_total": base + cuota + (recargo or Decimal("0")),
        "recargo_amount": recargo,
        "currency": "EUR",
        "lines": lines,
        "payment_status": PaymentStatus.PENDING,
    }
    payload.update(overrides)
    return Invoice.model_validate(payload, context=INVOICE_WRITE_ADMISSION)


def _rectificativa(*, method: str, direction: str, **overrides: Any) -> Invoice:
    """One complete rectificativa: the facts its side needs, stated as the registry declares them."""
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    payload: dict[str, Any] = {
        "invoice_class": InvoiceClass.from_registry("RECTIFICATIVA"),
        "series": "R",
        "invoice_number": "2026/R-0001",
        "rectifies_invoice_number": "2026/F-0001",
        "rectification_method": method,
        "rectification_cause": str(catalogue.art_80_tres_cause_token),
        "rectification_direction": direction,
        "document_received_on": _ISSUED_AT,
    }
    payload.update(overrides)
    return _invoice(**payload)


def _methods() -> tuple[str, str]:
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    return str(catalogue.diferencia_token), str(catalogue.sustitucion_token)


def _directions() -> tuple[str, str]:
    catalogue = resolve_invoice_legal_classification_catalogue(effective_date=_ISSUED_AT)
    return str(catalogue.minoracion_token), str(catalogue.aumento_token)


def test_a_difference_minoracion_is_the_documents_own_lines_made_negative() -> None:
    """Art. 15.5's first reading: the printed figures ARE the modification, signed by the direction."""
    diferencia, _ = _methods()
    minoracion, _ = _directions()

    derived = derive_rectification_modification(_rectificativa(method=diferencia, direction=minoracion))

    assert derived.refusal is None
    modification = derived.modification
    assert modification is not None
    assert modification.base == Decimal("-100.00")
    assert modification.cuota == Decimal("-21.00")
    assert [(row.iva_rate, row.base, row.cuota) for row in modification.rows] == [
        (_RATE_21, Decimal("-100.00"), Decimal("-21.00")),
    ]
    assert modification.original_invoice_id is None


def test_a_difference_aumento_is_the_same_lines_made_positive() -> None:
    """The same printed figures, the other direction: nothing but the sign differs."""
    diferencia, _ = _methods()
    _, aumento = _directions()

    derived = derive_rectification_modification(_rectificativa(method=diferencia, direction=aumento))

    modification = derived.modification
    assert modification is not None
    assert modification.base == Decimal("100.00")
    assert modification.cuota == Decimal("21.00")


def test_the_record_keeps_its_non_negative_magnitudes_whatever_the_derivation_signs() -> None:
    """The sign exists only in the derived modification, never on the stored invoice."""
    diferencia, _ = _methods()
    minoracion, _ = _directions()
    invoice = _rectificativa(method=diferencia, direction=minoracion)

    derived = derive_rectification_modification(invoice)

    assert invoice.base_total == Decimal("100.00")
    assert invoice.iva_total == Decimal("21.00")
    assert derived.modification is not None
    assert derived.modification.base < Decimal("0")


def test_a_substitution_is_the_substitute_minus_the_original() -> None:
    """Art. 15.5's second reading: 800.00 replacing 1000.00 modifies by -200.00 and -42.00."""
    _, sustitucion = _methods()
    minoracion, _ = _directions()
    original = _invoice(lines=(_line(base=Decimal("1000.00"), cuota=Decimal("210.00")),))
    substitute = _rectificativa(
        method=sustitucion,
        direction=minoracion,
        lines=(_line(base=Decimal("800.00"), cuota=Decimal("168.00")),),
    )

    derived = derive_rectification_modification(substitute, originals=(original,))

    modification = derived.modification
    assert modification is not None
    assert modification.base == Decimal("-200.00")
    assert modification.cuota == Decimal("-42.00")
    assert modification.original_invoice_id == original.invoice_id


def test_a_substitution_moves_only_the_rate_whose_figures_changed() -> None:
    """Per rate, not in total: an untouched tier contributes no row at all."""
    _, sustitucion = _methods()
    minoracion, _ = _directions()
    unchanged = _line(base=Decimal("500.00"), cuota=Decimal("50.00"), rate=_RATE_10)
    original = _invoice(
        lines=(_line(base=Decimal("1000.00"), cuota=Decimal("210.00")), unchanged),
    )
    substitute = _rectificativa(
        method=sustitucion,
        direction=minoracion,
        lines=(_line(base=Decimal("800.00"), cuota=Decimal("168.00")), unchanged),
    )

    derived = derive_rectification_modification(substitute, originals=(original,))

    modification = derived.modification
    assert modification is not None
    assert [(row.iva_rate, row.base, row.cuota) for row in modification.rows] == [
        (_RATE_21, Decimal("-200.00"), Decimal("-42.00")),
    ]


def test_a_substitution_with_no_original_in_the_catalogue_refuses() -> None:
    """There is nothing to subtract from, so no modification is derived and none is guessed."""
    _, sustitucion = _methods()
    minoracion, _ = _directions()

    derived = derive_rectification_modification(_rectificativa(method=sustitucion, direction=minoracion))

    assert derived.modification is None
    assert derived.refusal is RectificationModificationRefusal.ORIGINAL_NOT_FOUND


def test_a_substitution_whose_original_is_ambiguous_refuses_and_counts_the_candidates() -> None:
    """Two catalogue invoices answer to the named number, so which figures it replaces is unresolved."""
    _, sustitucion = _methods()
    minoracion, _ = _directions()
    first = _invoice(lines=(_line(base=Decimal("1000.00"), cuota=Decimal("210.00")),))
    second = _invoice(series="B", lines=(_line(base=Decimal("900.00"), cuota=Decimal("189.00")),))
    substitute = _rectificativa(
        method=sustitucion,
        direction=minoracion,
        lines=(_line(base=Decimal("800.00"), cuota=Decimal("168.00")),),
    )

    derived = derive_rectification_modification(substitute, originals=(first, second))

    assert derived.modification is None
    assert derived.refusal is RectificationModificationRefusal.ORIGINAL_AMBIGUOUS
    assert derived.original_candidates == 2


def test_a_substitution_whose_difference_runs_against_the_recorded_direction_refuses() -> None:
    """Both describe the same document, so a contradiction is reported rather than resolved."""
    _, sustitucion = _methods()
    minoracion, _ = _directions()
    original = _invoice(lines=(_line(base=Decimal("800.00"), cuota=Decimal("168.00")),))
    substitute = _rectificativa(
        method=sustitucion,
        direction=minoracion,
        lines=(_line(base=Decimal("1000.00"), cuota=Decimal("210.00")),),
    )

    derived = derive_rectification_modification(substitute, originals=(original,))

    assert derived.modification is None
    assert derived.refusal is RectificationModificationRefusal.DIRECTION_CONTRADICTS_DIFFERENCE


def test_a_recargo_de_equivalencia_takes_the_same_sign_as_the_cuota_it_rides_on() -> None:
    """LIVA art. 161 has the recargo repercutido beside the cuota, so it moves with it."""
    diferencia, _ = _methods()
    minoracion, _ = _directions()
    rectificativa = _rectificativa(
        kind=InvoiceKind.ISSUED,
        method=diferencia,
        direction=minoracion,
        document_received_on=None,
        recargo_amount=Decimal("5.20"),
    )

    derived = derive_rectification_modification(rectificativa)

    modification = derived.modification
    assert modification is not None
    assert modification.recargo == Decimal("-5.20")
    assert modification.cuota == Decimal("-21.00")


def test_a_rectificativa_missing_a_fact_its_side_needs_derives_nothing() -> None:
    """The method is what says what the figures mean, so an absent fact is a refusal, not a default."""
    diferencia, _ = _methods()
    minoracion, _ = _directions()
    without_cause = _rectificativa(method=diferencia, direction=minoracion, rectification_cause=None)

    derived = derive_rectification_modification(without_cause)

    assert derived.modification is None
    assert derived.refusal is RectificationModificationRefusal.FACTS_NOT_STATED


def test_an_invoice_of_any_other_class_makes_no_modification() -> None:
    """Only a rectificativa modifies a prior base and cuota; no other class states one."""
    derived = derive_rectification_modification(_invoice())

    assert derived.modification is None
    assert derived.refusal is RectificationModificationRefusal.NOT_A_RECTIFICATIVA
