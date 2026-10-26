"""Adversarial parsing tests against the real evidence corpus.

Drives the actual on-host structured-invoice parser and image validation over a
corpus of real, licence-clean invoice files (Wikimedia Commons public-domain
images, an Apache-2.0 EN16931 reference invoice PDF) plus generated adversarial
variants. The structured readers must extract real content and fail *loudly*
(raise, never crash) on hostile input -- nothing is written outside memory.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from cadrumo.adapters.inbound.einvoice.parsers import parse_einvoice_document
from cadrumo.adapters.inbound.einvoice.xml import EInvoiceXmlParseError
from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.document_shape import DocumentShape
from cadrumo.core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from cadrumo.tests.fixtures.provenance import (
    FIXTURE_PROVENANCE_REAL,
    RECOGNISED_FIXTURE_PROVENANCES,
    SYNTHETIC_FIXTURE_PRODUCER,
    producer_field,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter, pytest.mark.usefixtures("operation")]

_CORPUS = Path(__file__).resolve().parents[4] / "application" / "ledger" / "tests" / "_evidence_corpus"


def _read(name: str) -> bytes:
    return (_CORPUS / name).read_bytes()


def test_real_image_invoice_is_a_valid_image() -> None:
    """The real public-domain invoice images load (the image-evidence base64 path)."""
    for name in ("commons_invoice_1.jpg", "commons_invoice_2.jpg"):
        image = Image.open(BytesIO(_read(name)))
        assert image.format in {"JPEG", "PNG"}
        assert image.size[0] > 0 and image.size[1] > 0


def _corpus_fixtures() -> list[Path]:
    return [p for p in scan_directory(_CORPUS) if not p.name.endswith(".provenance.json")]


def _sidecar_of(fixture: Path) -> dict[str, object]:
    sidecar = fixture.with_suffix(fixture.suffix + ".provenance.json")
    assert sidecar.exists(), f"missing provenance sidecar for {fixture.name}"
    return STR_KEYED_MAPPING_ADAPTER.validate_json(sidecar.read_text(encoding="utf-8"))


def _readable_producer(fixture: Path) -> str | None:
    """Return the fixture's ``/Producer``, or ``None`` when it has no readable DocInfo.

    Measured rather than assumed. Several fixtures here are adversarial by
    design -- a zero-byte ``.pdf``, a PDF header followed by garbage -- and
    images and XML carry no PDF DocInfo at all, so "unreadable" is a property of
    the bytes and never a list of exempt filenames.
    """
    try:
        return producer_field(fixture)
    except Exception:
        return None


def test_every_corpus_fixture_declares_provenance() -> None:
    """Every corpus fixture carries a provenance sidecar (fixture-provenance rule)."""
    fixtures = _corpus_fixtures()
    assert fixtures, "corpus must not be empty"
    for fixture in fixtures:
        meta = _sidecar_of(fixture)
        assert meta["provenance"] in RECOGNISED_FIXTURE_PROVENANCES
        # Real-corpus fixtures must name a licence and a source; adversarial ones
        # are honestly declared synthetic.
        if meta["provenance"] == FIXTURE_PROVENANCE_REAL:
            assert meta.get("licence")
            assert meta.get("source")


def test_every_sidecar_content_address_matches_the_committed_bytes() -> None:
    """The declared content address and size must equal the file actually committed.

    The sidecar is a claim about bytes, so the bytes are what settles it. This is
    the cross-check that survives for every fixture kind: a swapped, truncated or
    re-rendered file diverges here even when its DocInfo does not, and a fixture
    copied in from an external corpus is only as trustworthy as the byte identity
    of that copy.
    """
    for fixture in _corpus_fixtures():
        meta = _sidecar_of(fixture)
        data = fixture.read_bytes()
        assert meta["sha256"] == hashlib.sha256(data).hexdigest(), (
            f"{fixture.name}: declared sha256 does not match the committed bytes"
        )
        assert meta["bytes"] == len(data), f"{fixture.name}: declared size does not match the committed bytes"


def test_no_fixture_claims_real_origin_while_carrying_the_generator_signature() -> None:
    """A synthetic fixture may never pass itself off as externally-authored evidence.

    The direction that matters for honesty. The mirror rule -- that every
    ``synthetic_generated`` fixture carries the in-tree generator signature --
    holds only for fixtures an in-tree generator wrote, and this corpus also
    bundles documents rendered by external tooling under a generic producer. So
    the claim each of those makes is bound by its own declared ``producer``
    instead, asserted below; forcing the signature rule onto them would push an
    author toward stamping ``real_corpus`` on synthetic bytes, which is the exact
    lie this gate exists to prevent.
    """
    for fixture in _corpus_fixtures():
        meta = _sidecar_of(fixture)
        if meta["provenance"] != FIXTURE_PROVENANCE_REAL:
            continue
        producer = _readable_producer(fixture)
        assert SYNTHETIC_FIXTURE_PRODUCER not in (producer or "").lower(), (
            f"{fixture.name}: declares {FIXTURE_PROVENANCE_REAL} but /Producer={producer!r} "
            f"carries the {SYNTHETIC_FIXTURE_PRODUCER!r} signature"
        )


def test_every_declared_producer_matches_the_documents_own_docinfo() -> None:
    """A sidecar naming a ``/Producer`` is checked against the document's DocInfo.

    Binds the declaration to the physical bytes for fixtures whose provenance
    rests on an external attestation rather than on the in-tree signature. The
    readability assertion is what stops this from degrading into a silent skip:
    a fixture that declares a producer and then cannot be opened fails here
    rather than passing vacuously.
    """
    declared = [(f, _sidecar_of(f)) for f in _corpus_fixtures()]
    checked = [(f, m) for f, m in declared if m.get("producer")]
    assert checked, "no fixture declares a producer; this gate would be vacuous"
    for fixture, meta in checked:
        producer = _readable_producer(fixture)
        assert producer is not None, (
            f"{fixture.name}: sidecar declares producer {meta['producer']!r} but the file has no readable DocInfo"
        )
        assert producer == meta["producer"], (
            f"{fixture.name}: declared producer {meta['producer']!r} but the document reports {producer!r}"
        )


def test_zugferd_structured_record_parses_to_its_exact_printed_values() -> None:
    """The ZUGFeRD fixture is asserted FIELD BY FIELD against its own record.

    Supersedes the neighbouring text-layer check as the fixture's real gate.
    That one asserts only that a German word appears in the extracted text,
    which passes for any German-language PDF -- and passes just as happily for
    a parser returning a wrong tax identifier or swapped parties. This is the
    difference between "the fixture is readable" and "the fixture is read
    correctly", and only the second is a gate.

    The tax identifier is pinned deliberately. ZUGFeRD is a Franco-German
    format whose supplier block carries a Steuernummer alongside the IVA id,
    and selecting the wrong one accounted for 22 of the 34 wrong fields
    measured corpus-wide with ZERO missing fields -- the parser was finding
    every field and choosing the wrong one, which is a selection bug this
    assertion catches and a coverage gap it would not.
    """
    parsed = parse_einvoice_document(_read("zugferd_en16931_invoice.pdf"))

    assert parsed.shape is DocumentShape.XML_CII
    assert parsed.invoice_number == "471102"
    assert parsed.supplier_tax_id == "DE123456789", "the IVA number, never the Steuernummer"
    assert parsed.currency == "EUR"
    assert parsed.taxable_base == Decimal("473.00")
    assert parsed.iva_amount == Decimal("56.87")
    assert parsed.grand_total == Decimal("529.87")


def test_zugferd_two_rate_document_does_not_collapse_to_one_pair() -> None:
    """Both declared rates survive the read, each with its own base and cuota.

    The multi-rate silent collapse is the defect this reading path exists to
    close: a draft carrying only a flat base/rate/cuota triple sums two bases
    into one figure and loses a rate, producing an invoice whose printed total
    no longer reconciles with its declared cuota. A parser returning a single
    pair here would pass every other assertion in this module.
    """
    parsed = parse_einvoice_document(_read("zugferd_en16931_invoice.pdf"))

    rates = sorted(rate for rate, _base, _cuota in parsed.iva_breakdown if rate is not None)
    assert rates == [Decimal("7.00"), Decimal("19.00")], "both declared rates must survive"
    assert len(parsed.lines) == 2

    bases = sum((base for _rate, base, _cuota in parsed.iva_breakdown if base is not None), Decimal(0))
    cuotas = sum((cuota for _rate, _base, cuota in parsed.iva_breakdown if cuota is not None), Decimal(0))
    # Invoice-level identity is EXACT, not tolerance-bounded: per-line rounding
    # may not accumulate into the invoice-level total.
    assert bases == parsed.taxable_base
    assert cuotas == parsed.iva_amount
    # Both operands are optional; without these the sum raises on None instead of
    # the assertion naming which component the parse failed to produce.
    assert parsed.taxable_base is not None
    assert parsed.iva_amount is not None
    assert parsed.taxable_base + parsed.iva_amount == parsed.grand_total


def test_zugferd_states_each_partys_country_and_the_reader_recovers_it() -> None:
    """The country the bundled CII already printed is read rather than passed over.

    Not a new capability's fixture but its oldest evidence: this document has
    carried ``ram:CountryID`` for both parties since it was bundled, one element
    away from the ``PostcodeCode`` the reader was already taking out of the same
    address block. The value was present, parsed past, and established nothing.

    Pinned here as well as against the purpose-authored specimen because a
    fixture written alongside a reader can be written to suit it; this one
    predates the read entirely, so agreeing with it is a fact about the format
    rather than about the author.
    """
    parsed = parse_einvoice_document(_read("zugferd_en16931_invoice.pdf"))

    assert parsed.supplier_country_code == "DE"
    assert parsed.customer_country_code == "DE"


def test_a_standalone_cii_document_is_classified_without_a_pdf_around_it() -> None:
    """A bare ``.xml`` CII reaches the CII reader, not the unrecognised-XML refusal.

    The shape probe had two routes to :attr:`DocumentShape.XML_CII` and only one
    was ever travelled. Every CII byte in this corpus arrived embedded in the
    ZUGFeRD PDF, so the probe classified CII through the PDF-attachment branch;
    the standalone branch -- the same one that carries every UBL and Facturae
    specimen -- had no CII document to classify and would have refused one as
    unrecognised XML without anything noticing.
    """
    parsed = parse_einvoice_document(_read("en16931_cii_export_third_country_invoice.xml"))

    assert parsed.shape is DocumentShape.XML_CII


def test_the_cii_specimen_reads_to_its_own_printed_values() -> None:
    """Field by field against the document's own figures, both parties kept apart.

    The parties are asserted individually rather than as a pair. A CII party
    subtree carries a ``SpecifiedTaxRegistration`` whose id opens with the two
    letters of a country, so a reader searching the subtree for a short code
    finds the IVA prefix and returns something that looks right -- and here
    ``CHE116281277`` and ``CH`` agree, which is exactly why the postal code is
    pinned beside the country: an IVA-prefix read recovers no postal code.
    """
    parsed = parse_einvoice_document(_read("en16931_cii_export_third_country_invoice.xml"))

    assert parsed.invoice_number == "CII-2024-0042"
    assert parsed.currency == "EUR"
    assert parsed.taxable_base == Decimal("7400.00")
    assert parsed.iva_amount == Decimal("0.00")
    assert parsed.grand_total == Decimal("7400.00")

    assert parsed.supplier_name == "Maquinaria Levantina SL"
    assert parsed.supplier_tax_id == "ESB12345674"
    assert parsed.supplier_country_code == "ES"
    assert parsed.supplier_postal_code == "46015"

    assert parsed.customer_name == "Alpine Packaging AG"
    assert parsed.customer_tax_id == "CHE116281277"
    assert parsed.customer_country_code == "CH"
    assert parsed.customer_postal_code == "8004"

    # The UNTDID 5305 code, and only the code, distinguishes an export from an
    # exempt or a reverse-charge supply: all three print a base and no cuota.
    assert parsed.iva_category == "export_third_country_zero_rated"
    assert parsed.regime_legend == "Exportacion exenta - art. 21 LIVA"


def test_malformed_structured_document_refuses_rather_than_partially_reading() -> None:
    """A truncated record raises and yields NO record, not a partial one.

    This is the property the structured path is chosen for. A model handed the
    same bytes returns a confident, plausible, wrong invoice; the parser
    refuses outright. A reader returning half a record would be worse than the
    model, because it would look exact while being wrong.
    """
    with pytest.raises(EInvoiceXmlParseError):
        parse_einvoice_document(b"<rsm:CrossIndustryInvoice><rsm:ExchangedDocument>")


def test_the_ubl_fixture_parses_both_rates_and_selects_the_iva_identifier() -> None:
    """EN16931 UBL, the half of the standard a CII-only reader returns nothing for.

    Nothing in the bundled corpus exercised UBL before this fixture, so the UBL
    parser shipped unread against any real document. Two rates on purpose: a
    single-rate document cannot detect the multi-rate collapse, which is the
    defect the per-rate breakdown exists to prevent.
    """
    parsed = parse_einvoice_document(_read("en16931_ubl_two_rate_invoice.xml"))

    assert parsed.shape is DocumentShape.XML_UBL
    assert parsed.invoice_number == "UBL-2024-0042", "the document's own ID, not a guideline identifier"
    assert parsed.supplier_tax_id == "ESB12345674", "the schemeID=VA id, not the 0088 party identifier"
    assert parsed.currency == "EUR"

    rates = sorted(rate for rate, _b, _c in parsed.iva_breakdown if rate is not None)
    assert rates == [Decimal("10.00"), Decimal("21.00")]
    assert len(parsed.lines) == 2

    bases = sum((b for _r, b, _c in parsed.iva_breakdown if b is not None), Decimal(0))
    cuotas = sum((c for _r, _b, c in parsed.iva_breakdown if c is not None), Decimal(0))
    assert bases == parsed.taxable_base
    assert cuotas == parsed.iva_amount
    # Asserted rather than assumed: all three are optional on the parsed record,
    # so without this a document that parsed none of them would reach the sum
    # below and fail there on a TypeError instead of here on the real claim.
    assert parsed.taxable_base is not None
    assert parsed.iva_amount is not None
    assert parsed.grand_total is not None
    assert parsed.taxable_base + parsed.iva_amount == parsed.grand_total


def test_the_facturae_fixture_reads_recargo_and_does_not_double_count_its_taxes() -> None:
    """Facturae 3.2.x, plus the double-count this fixture caught on arrival.

    Facturae states taxes TWICE -- once at invoice level and again per line --
    so a descendant walk collects both and reports every band twice. A
    single-rate invoice then looks like a two-rate one and the invoice-level
    identity fails on a perfectly well-formed document. The parser now scopes to
    the invoice-level block; this asserts the count, which is the only thing
    that distinguishes the fix from the bug.

    The recargo assertion matters for its own reason: the draft grew a recargo
    slot because a peer-landed discrepancy check had begun firing with nowhere
    for the operator to resolve it. A slot with no document that states one
    would have shipped untested against real structure.
    """
    parsed = parse_einvoice_document(_read("facturae_32_recargo_invoice.xml"))

    assert parsed.shape is DocumentShape.XML_FACTURAE
    assert parsed.invoice_number == "FAC-2024-0007"
    assert parsed.supplier_tax_id == "ESB12345674"
    assert parsed.recargo_amount == Decimal("5.20")

    assert len(parsed.iva_breakdown) == 1, "invoice-level taxes only; the per-line block must not double-count"
    rate, base, cuota = parsed.iva_breakdown[0]
    assert (rate, base, cuota) == (Decimal("21.00"), Decimal("100.00"), Decimal("21.00"))
    assert base == parsed.taxable_base
    # The band-sum identity every sibling corpus test above asserts, and which
    # this one alone lacked. Its absence is exactly how the scalar came to carry
    # cuota PLUS recargo (26,20) while the breakdown correctly stated the cuota:
    # nothing compared the two, so the surcharge rode into a term that means the
    # cuota and the printed total then failed to close by precisely the recargo.
    assert cuota == parsed.iva_amount
    assert parsed.taxable_base is not None
    assert parsed.iva_amount is not None
    assert parsed.recargo_amount is not None, "the recargo term is what this closure turns on"
    assert parsed.taxable_base + parsed.iva_amount + parsed.recargo_amount == parsed.grand_total


def test_the_facturae_reader_keeps_the_invoice_series_beside_the_number() -> None:
    """Facturae states the invoice's identity in TWO header elements, not one.

    ``InvoiceSeriesCode`` is the other half of the reference a Facturae document
    carries, so a reader taking ``InvoiceNumber`` alone reports an identity the
    document does not state -- which then keys deduplication and the
    counterparty reconciliation a Modelo 347 declaration is checked on. The
    series assertion is what fails if that element stops being read.

    The fixture's header also restates both elements inside a ``Corrective``
    block, for the invoice being rectified. That block is NOT what these
    assertions discriminate: Facturae fixes element order, so the header's own
    values always precede the corrective ones and a descendant walk reaches the
    right value on any schema-valid document. The reader scopes to the header's
    own children anyway, as defence against an input whose order is not
    guaranteed, but the scoping is deliberately not claimed as a gate here --
    a mutation reverting it changes nothing observable, so asserting it would
    pass vacuously.
    """
    parsed = parse_einvoice_document(_read("facturae_32_series_and_parties_invoice.xml"))

    assert parsed.shape is DocumentShape.XML_FACTURAE
    assert parsed.invoice_number == "0031"
    assert parsed.invoice_series == "R-2026", "the series half of the identity, dropped entirely before this"


def test_the_facturae_reader_names_both_parties_and_not_their_administrative_contact() -> None:
    """A party's stated name is read for both sides, from either naming block.

    Facturae names a party in one of two mutually exclusive blocks:
    ``LegalEntity/CorporateName`` for a company, or ``Individual`` split across
    a given name and two surnames for a natural person. Reading neither forced
    the operator to retype a name the document states, because the domain
    invoice requires a counterparty name and the reader supplied none.

    The seller here also carries an ``AdministrativeCentres`` contact whose
    ``Name`` and ``FirstSurname`` elements share their local names with the
    party's own. A reader that walks descendants for ``Name`` reports that
    contact -- a real Facturae document in the wild is shaped exactly this way --
    so the assertion is that the administrative contact is NOT what comes back.
    """
    parsed = parse_einvoice_document(_read("facturae_32_series_and_parties_invoice.xml"))

    assert parsed.supplier_name == "Marta Iglesias Ferrer", "the Individual block, joined across both surnames"
    assert parsed.supplier_name is not None
    assert "Ruth" not in parsed.supplier_name, "the AdministrativeCentre contact is not the party"
    assert "Decoy" not in parsed.supplier_name
    assert parsed.customer_name == "Talleres Berrocal, S.A.", "the LegalEntity CorporateName block"


def test_the_facturae_reader_carries_both_parties_tax_ids_not_only_the_supplier() -> None:
    """Both sides of the invoice are read, so a caller can pick the counterparty.

    Which party is the counterparty depends on the direction of the invoice: on
    an invoice the taxpayer issued it is the customer, on one they received it
    is the supplier. A reader that carries only the supplier side leaves a
    caller on the issued direction with the taxpayer's OWN identifier where the
    counterparty belongs, and that value reaches the counterparty totals AEAT
    reconciles against the other party's own filing.
    """
    parsed = parse_einvoice_document(_read("facturae_32_series_and_parties_invoice.xml"))

    assert parsed.supplier_tax_id == "45821337R"
    assert parsed.customer_tax_id == "A82645177"
    assert parsed.supplier_tax_id != parsed.customer_tax_id
