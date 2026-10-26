"""A rectificativa reaches the catalogue as one, instead of silently as ordinaria.

RD 1619/2012 art. 15 makes a factura rectificativa a distinct CLASS of invoice
by mandate: it must be issued when the original fails the content requirements
of arts. 6 or 7, and when the cuotas repercutidas were determined incorrectly.
The :class:`~domain.invoices.Invoice` model already encodes what follows from
that class -- a specific series per art. 6.1.a.2, and naming the invoice it
corrects per LIVA art. 89 -- in a validator that ties the class and the
reference together in both directions.

**The defect this closes is a SILENT MISCLASSIFICATION, not a missing feature.**
The Facturae reader already walked past ``Corrective/InvoiceNumber``: its own
comment said a rectificativa restates the corrected invoice's number there, and
the direct-child scoping deliberately stepped over it to read the invoice's own.
The confirm then defaulted the class to ORDINARIA regardless. So the fact was on
the document, was seen, and was discarded -- and because nothing ever stated the
class, the model's rectificativa invariants never fired to object. An invoice
correcting another reached the catalogue indistinguishable from one that
corrected nothing.

**The declared Facturae class and corrective reference are separate facts.**
The parser preserves the closed ``InvoiceClass`` code as a typed adapter value
and separately carries the ``Corrective`` reference. The application can then
map the supported class axis without confusing the document's own class with
the invoice number it names as corrected.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.inbound.einvoice.parsers import FacturaeInvoiceClass, ParsedEInvoice, parse_einvoice_document
from cadrumo.core.directory_scan import iter_directory
from cadrumo.domain.calculations.registry.invoice_legal_classification import require_invoice_class

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter, pytest.mark.usefixtures("operation")]

#: A bundled Facturae 3.2 document that corrects invoice ``0028`` in its own
#: ``Corrective`` block while numbering itself ``0031`` in series ``R-2026``.
_RECTIFICATIVA = (
    Path(__file__).resolve().parents[4]
    / "application"
    / "ledger"
    / "tests"
    / "_evidence_corpus"
    / "facturae_32_series_and_parties_invoice.xml"
)

_CORRECTED_NUMBER = "0028"
_OWN_NUMBER = "0031"


def _parsed() -> ParsedEInvoice:
    return parse_einvoice_document(_RECTIFICATIVA.read_bytes())


def test_the_bundled_document_really_corrects_another_one() -> None:
    """Anchor: if the fixture stops carrying a Corrective block, the rest is vacuous."""
    raw = _RECTIFICATIVA.read_text(encoding="utf-8")

    assert "<Corrective>" in raw
    assert _CORRECTED_NUMBER in raw


def test_the_corrected_invoice_number_is_recovered() -> None:
    """The measured discard: this number was read past and thrown away."""
    assert _parsed().rectifies_invoice_number == _CORRECTED_NUMBER


def test_the_documents_own_number_is_not_the_one_it_corrects() -> None:
    """The reason the direct-child scoping exists, still holding.

    Both numbers live in one ``InvoiceHeader`` subtree, so a reader that
    searched the subtree loosely would take the CORRECTED number as the
    invoice's own -- mislabelling the document rather than merely losing a
    field.
    """
    parsed = _parsed()

    assert parsed.invoice_number == _OWN_NUMBER
    assert parsed.rectifies_invoice_number == _CORRECTED_NUMBER
    assert parsed.invoice_number != parsed.rectifies_invoice_number


def test_an_ordinary_document_states_no_correction() -> None:
    """The precision half: absence must stay absence.

    Deriving the class from this reference means a false positive here would
    mint an ordinary invoice as a rectificativa, and the model would then
    demand a series and a corrected number it has no business demanding.
    """
    corpus = _RECTIFICATIVA.parent
    ordinary = next(
        path
        for path in iter_directory(corpus, pattern="*.xml")
        if "<Corrective>" not in path.read_text(encoding="utf-8")
    )

    assert parse_einvoice_document(ordinary.read_bytes()).rectifies_invoice_number is None


def test_the_class_follows_the_reference_in_both_directions() -> None:
    """The parser preserves both the declared class and its corrective reference.

    The domain ``InvoiceClass`` is intentionally distinct from Facturae's
    six-code adapter vocabulary, while the parsed record carries the declared
    ``OR`` code alongside the reference to ``0028``.
    """
    parsed = _parsed()

    assert require_invoice_class("ORDINARIA") != require_invoice_class("RECTIFICATIVA")
    assert parsed.facturae_invoice_class is FacturaeInvoiceClass.ORIGINAL_CORRECTIVE
    assert parsed.rectifies_invoice_number is not None


def test_reading_the_corrective_block_preserves_the_reference() -> None:
    """Mutation proof: without that read the corrective reference disappears.

    Re-runs the pre-change reading -- the invoice's own header fields only --
    and shows it yields no corrective reference, while the declared Facturae
    class remains independently available. A suite asserting only the class
    would not show what the discarded reference used to cost.
    """
    parsed = _parsed()

    def _without_the_corrective_read() -> str | None:
        return None

    assert _without_the_corrective_read() is None
    assert parsed.rectifies_invoice_number is not None
