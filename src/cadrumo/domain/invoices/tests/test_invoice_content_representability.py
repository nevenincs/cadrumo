"""RD 1619/2012 art. 6.1.e (domicilio) and .j/.l/.m/.n/.o/.p (menciones) representability.

Before this module :class:`~cadrumo.domain.invoices.Invoice` had no field for
either party's domicilio or for the fixed legal notices (menciones) the
reglamento requires under an exemption, inversión del sujeto pasivo, a
special regime (REBU, agencias de viajes, criterio de caja), or
autofacturación. This is representability only: the fields exist so a
document's real content can be recorded, independent of whether any gate
later requires them present for a given category.

Every field here is evidence of what the issuer PRINTED. None is derived
from :attr:`~cadrumo.domain.invoices.Invoice.iva_category` -- deriving a
mención or an address from our own classification would manufacture evidence
of compliance nobody observed on the document, so no test here asserts a
coupling between the two; a separate gating decision is a different scope.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ....core.resources import bundled_path
from ....domain.iva import InvoiceKind
from ..enums import InvoiceLegalMention, IvaRate, PaymentStatus, invoice_legal_mention_text
from ..models import Invoice, InvoiceLine

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")

_ART_6_CORPUS_PATH = "corpus/normatives/html/rd-1619-2012-art-6.html"


def _line() -> InvoiceLine:
    return InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=IvaRate.RATE_21,
        iva_amount=_CUOTA,
    )


def _invoice(**overrides: Any) -> Invoice:
    payload: dict[str, Any] = {
        "kind": InvoiceKind.ISSUED,
        "invoice_number": "2026/CT-1",
        "issued_at": date(2026, 4, 15),
        "counterparty_name": "Cliente SL",
        "counterparty_tax_id": "B12345674",
        "counterparty_country": "ES",
        "base_total": _BASE,
        "iva_total": _CUOTA,
        "grand_total": _BASE + _CUOTA,
        "currency": "EUR",
        "lines": (_line(),),
        "payment_status": PaymentStatus.PAID,
    }
    payload.update(overrides)
    return Invoice(**payload)  # type: ignore[arg-type]


def test_an_invoice_can_state_both_parties_domicilio() -> None:
    """art. 6.1.e: the document names the domicilio of issuer and destinatario."""
    invoice = _invoice(
        issuer_address="Calle Mayor 1, 28001 Madrid",
        recipient_address="Avenida Diagonal 200, 08018 Barcelona",
    )

    assert invoice.issuer_address == "Calle Mayor 1, 28001 Madrid"
    assert invoice.recipient_address == "Avenida Diagonal 200, 08018 Barcelona"


def test_an_ordinary_invoice_declares_no_domicilio() -> None:
    """Most existing invoices carry no domicilio; the field is additive, not mandatory here."""
    invoice = _invoice()

    assert invoice.issuer_address is None
    assert invoice.recipient_address is None


def test_a_blank_domicilio_normalises_to_absent() -> None:
    """Mirrors the ``series`` convention: whitespace-only means "not stated"."""
    invoice = _invoice(issuer_address="   ")

    assert invoice.issuer_address is None


def test_an_invoice_can_state_the_exemption_reference() -> None:
    """art. 6.1.j: a reference the issuer composed, not a fixed phrase, so it is free text."""
    invoice = _invoice(exemption_reference="Exenta por el artículo 20.Uno.9º LIVA")

    assert invoice.exemption_reference == "Exenta por el artículo 20.Uno.9º LIVA"


def test_an_invoice_can_state_its_fixed_legal_mentions() -> None:
    """art. 6.1.m/.p: an invoice under inversión del sujeto pasivo and criterio de caja."""
    invoice = _invoice(
        legal_mentions=[InvoiceLegalMention.REVERSE_CHARGE, InvoiceLegalMention.CASH_ACCOUNTING_REGIME],
    )

    assert invoice.legal_mentions == (
        InvoiceLegalMention.REVERSE_CHARGE,
        InvoiceLegalMention.CASH_ACCOUNTING_REGIME,
    )


def test_legal_mentions_coerces_plain_string_values() -> None:
    """A JSON-decoded payload carries plain strings, not enum instances."""
    invoice = _invoice(legal_mentions=["REVERSE_CHARGE"])

    assert invoice.legal_mentions == (InvoiceLegalMention.REVERSE_CHARGE,)


def test_an_unknown_legal_mention_is_refused() -> None:
    with pytest.raises(ValidationError):
        _invoice(legal_mentions=["NOT_A_REAL_MENTION"])


def test_an_ordinary_invoice_declares_no_legal_mentions_or_exemption_reference() -> None:
    invoice = _invoice()

    assert invoice.legal_mentions == ()
    assert invoice.exemption_reference is None


@pytest.mark.parametrize(
    "mention",
    list(InvoiceLegalMention),
)
def test_every_legal_mention_text_occurs_verbatim_in_the_bundled_corpus(mention: InvoiceLegalMention) -> None:
    """Each phrase is extracted from RD 1619/2012 art. 6, never retyped.

    A retyped quotation is unfalsifiable: any string passes a check against
    itself. Reading it back against the bundled corpus file is what proves
    the enum's wording actually matches what the reglamento prints, the same
    corpus-containment discipline used to ground the IVA catalogue.
    """
    corpus_root = bundled_path("registry", "aeat").parents[1]
    text = Path(corpus_root / _ART_6_CORPUS_PATH).read_text(encoding="utf-8")

    assert invoice_legal_mention_text(mention) in text, (
        f"{mention.value} phrase {invoice_legal_mention_text(mention)!r} not found verbatim in {_ART_6_CORPUS_PATH}"
    )


def test_domicilio_clause_occurs_verbatim_in_the_bundled_corpus() -> None:
    """Grounds the field pair's own legal basis against the bundled art. 6 text."""
    corpus_root = bundled_path("registry", "aeat").parents[1]
    text = Path(corpus_root / _ART_6_CORPUS_PATH).read_text(encoding="utf-8")

    assert "Domicilio, tanto del obligado a expedir factura como del destinatario de las operaciones" in text


def test_exemption_reference_clause_occurs_verbatim_in_the_bundled_corpus() -> None:
    corpus_root = bundled_path("registry", "aeat").parents[1]
    text = Path(corpus_root / _ART_6_CORPUS_PATH).read_text(encoding="utf-8")

    assert "una referencia a las disposiciones correspondientes de la Directiva 2006/112/CE" in text


def test_legal_mentions_are_never_derived_from_iva_category() -> None:
    """An EXEMPT-rated invoice with no stated mención stays unresolved, not inferred.

    This is the negative case the module docstring promises: nothing on the
    model reads ``iva_category`` to populate ``legal_mentions`` or
    ``exemption_reference``, so a caller that never states them gets exactly
    that -- an honest gap, not a fabricated one.
    """
    from ....domain.iva import IvaCategory

    invoice = _invoice(
        iva_category=IvaCategory.DOMESTIC_EXEMPT,
        lines=(
            InvoiceLine(
                description="Servicio exento",
                quantity=Decimal("1"),
                unit_price=_BASE,
                subtotal=_BASE,
                iva_rate=IvaRate.EXEMPT,
                iva_amount=Decimal("0"),
            ),
        ),
        iva_total=Decimal("0"),
        grand_total=_BASE,
    )

    assert invoice.legal_mentions == ()
    assert invoice.exemption_reference is None
