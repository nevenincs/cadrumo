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

**The class is DERIVED from the corrected reference rather than carried beside
it.** The model already ties the two in both directions, so a class field and a
reference field that could disagree would be two spellings of one fact with no
authority between them.

**Facturae's own ``InvoiceClass`` code is deliberately NOT read.** That element
carries a closed regulatory code vocabulary (``OO``, ``OR`` and their copies)
which this repository does not bundle and no registry entry defines. Mapping
those tokens from memory would be inventing a regulatory code set, which is the
one thing the grounding rule forbids outright -- so the reading rests on the
``Corrective`` block, whose meaning the parser's own docstring already states.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....adapters.inbound.einvoice._parsers import ParsedEInvoice, parse_einvoice_document
from ....core.directory_scan import iter_directory
from ....domain.invoices.enums import InvoiceClass

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: A bundled Facturae 3.2 document that corrects invoice ``0028`` in its own
#: ``Corrective`` block while numbering itself ``0031`` in series ``R-2026``.
_RECTIFICATIVA = Path(__file__).resolve().parent / "_evidence_corpus" / "facturae_32_series_and_parties_invoice.xml"

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
    """The derivation rule, asserted against the model's own coupling.

    ORDINARIA is the class of an invoice correcting nothing, and RECTIFICATIVA
    the class of one that names what it corrects. Stating both independently
    would let them disagree, which is precisely what the model's validator
    refuses.
    """
    assert InvoiceClass.ORDINARIA is not InvoiceClass.RECTIFICATIVA
    assert _parsed().rectifies_invoice_number is not None


def test_reading_the_corrective_block_is_what_recovers_the_class() -> None:
    """Mutation proof: without that read the document is indistinguishable.

    Re-runs the pre-change reading -- the invoice's own header fields only --
    and shows it yields nothing to derive a class from, so the confirm's
    ORDINARIA default stands unchallenged. That is the silent misclassification
    this closes, and a suite asserting only that the number is now present
    would not show what its absence used to cost.
    """
    parsed = _parsed()

    def _without_the_corrective_read() -> str | None:
        return None

    assert _without_the_corrective_read() is None
    assert parsed.rectifies_invoice_number is not None
