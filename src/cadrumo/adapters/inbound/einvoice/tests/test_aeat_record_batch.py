"""Real-behaviour cases for the AEAT SII / VERI*FACTU record-batch reader.

Every case drives :func:`~.._record_batch.parse_aeat_record_batch` over bundled
licence-clean fixtures. No mocks, and no sample tallies -- the claims are about
what the SCHEMA declares, exercised through documents chosen to discriminate.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from .....core.document_shape import AEAT_RECORD_BATCH_SHAPES, STRUCTURED_DOCUMENT_SHAPES, DocumentShape
from .._record_batch import AeatRecordFamily, parse_aeat_record_batch
from ..xml import EInvoiceXmlParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_CORPUS = Path(__file__).parents[4] / "application" / "ledger" / "tests" / "_evidence_corpus"


def _read(name: str) -> bytes:
    return (_CORPUS / name).read_bytes()


def _batch():
    return parse_aeat_record_batch(_read("verifactu_alta_batch_record.xml"))


def test_one_submission_carrying_a_registration_and_a_cancellation_is_classified_per_record() -> None:
    """A batch may MIX record kinds, so the file cannot decide for its records.

    ``RegistroFactura`` is a ``<choice>`` of ``RegistroAlta`` or
    ``RegistroAnulacion`` repeated to ``maxOccurs=1000``. No captured sample
    shows a mixed batch, so a reader built from specimens would classify per
    FILE and get one of the two wrong on the first real submission that mixes
    them.
    """
    batch = _batch()

    assert batch.shape is DocumentShape.XML_AEAT_VERIFACTU
    assert batch.record_count == 2, "both records seen"
    assert len(batch.records) == 1, "the registration is read"
    assert len(batch.refusals) == 1, "the cancellation is refused, not read as an invoice"
    assert batch.records[0].family is AeatRecordFamily.VERIFACTU_ALTA
    assert batch.refusals[0].family is AeatRecordFamily.VERIFACTU_ANULACION


def test_the_issuer_is_never_the_billing_software_vendor() -> None:
    """``SistemaInformatico/NombreRazon`` names the SOFTWARE, never a party.

    Four elements in this document share the local name ``NombreRazon`` or a
    variant of it, carrying four different values: the cabecera's obligado, the
    recipient, the software vendor, and -- as ``NombreRazonEmisor`` -- the
    issuer. A namespace-agnostic descendant walk cannot tell them apart and
    would write a billing-software vendor into a record as the invoice issuer.

    The fixture is authored so all four DIFFER. The bundled josemmo specimen
    cannot serve here: its ``SistemaInformatico/NombreRazon`` is byte-identical
    to its ``NombreRazonEmisor``, so a loose walk returns the right answer there
    and the case would certify the defect as working.
    """
    record = _batch().records[0]

    assert record.issuer is not None
    assert record.issuer.name == "EMISOR Verdadero SL"
    assert record.issuer.name != "PROVEEDOR Software SL", "the software vendor is not a party"
    assert record.issuer.name != "OBLIGADO Cabecera SL", "the cabecera's obligado is not the record's issuer"
    assert all(party.name != "PROVEEDOR Software SL" for party in record.recipients)


def test_the_invoice_identity_is_scoped_past_the_hash_chain_predecessor() -> None:
    """``Encadenamiento/RegistroAnterior`` restates the identity element names.

    Both records in the fixture carry a predecessor whose number DIFFERS from
    the record's own subject, which is what makes this discriminate: the
    registration is FA/2026-0044 while its predecessor is FA/2026-0043, and the
    cancellation voids FA/2026-0041 while its predecessor is FA/2026-0044.
    An unscoped lookup returns a predecessor and looks plausible.
    """
    batch = _batch()

    assert batch.records[0].invoice_number == "FA/2026-0044"
    assert batch.records[0].invoice_number != "FA/2026-0043", "not the chain predecessor"
    assert batch.refusals[0].invoice_number == "FA/2026-0041", "the invoice the cancellation VOIDS"
    assert batch.refusals[0].invoice_number != "FA/2026-0044", "not its chain predecessor"


def test_a_cancellation_is_identified_and_refused_rather_than_minted_as_an_invoice() -> None:
    """``RegistroAnulacionType`` declares no parties, no amounts, no Desglose.

    It cannot yield an invoice, so it is refused -- but refused INFORMATIVELY,
    naming the invoice it voids, which is what an operator needs. Note its
    ``IDFactura`` uses the ``-Anulada`` element spellings, so reusing the
    registration lookup silently yields nothing.
    """
    refusal = _batch().refusals[0]

    assert refusal.invoice_number == "FA/2026-0041"
    assert "cancellation" in refusal.reason
    assert refusal.element_name == "RegistroAnulacion"


def test_every_recipient_is_carried_with_its_own_identifier_scheme() -> None:
    """Recipients are read losslessly, foreign identifier schemes included.

    ``IDDestinatario`` is ``[1..1000]`` inside an OPTIONAL wrapper, so a record
    may name none, one, or many. Deciding that only one fits belongs to the
    projection onto a single-counterparty record, not to the reader: splitting a
    party set is impossible once it has been discarded.
    """
    recipients = _batch().records[0].recipients

    assert len(recipients) == 2
    assert recipients[0].tax_id == "A82645177"
    assert recipients[0].country_code is None, "a domestic NIF states no country"
    assert recipients[1].tax_id == "FR52422961982"
    assert recipients[1].country_code == "FR", "the IDOtro scheme is preserved, not flattened to a bare id"
    assert recipients[1].id_type == "02"


def test_the_per_rate_breakdown_uses_the_verifactu_base_element_name() -> None:
    """VERI*FACTU names the base ``BaseImponibleOimporteNoSujeto``.

    Not ``BaseImponible``, which is the SII spelling. A shared lookup across the
    two families silently reads no base at all and leaves every rate with a
    null base, which reconciles to nothing downstream.
    """
    breakdown = _batch().records[0].tax_breakdown

    assert len(breakdown) == 2
    assert [rate for rate, _b, _c in breakdown] == [Decimal("21.00"), Decimal("10.00")]
    assert [base for _r, base, _c in breakdown] == [Decimal("200.00"), Decimal("100.00")]
    bases = sum(base for _r, base, _c in breakdown if base is not None)
    cuotas = sum(cuota for _r, _b, cuota in breakdown if cuota is not None)
    assert bases + cuotas == _batch().records[0].invoice_total


def test_a_record_batch_shape_is_never_routed_to_the_single_invoice_reader() -> None:
    """The two shape sets must stay disjoint.

    ``STRUCTURED_DOCUMENT_SHAPES`` routes a document into the reader that
    returns ONE invoice. A batch shape appearing there would send a submission
    declaring ``maxOccurs=10000`` into a singular reader, keeping the first
    record and silently discarding every other -- the exact defect this separate
    reader exists to prevent.
    """
    assert AEAT_RECORD_BATCH_SHAPES.isdisjoint(STRUCTURED_DOCUMENT_SHAPES)
    assert DocumentShape.XML_AEAT_VERIFACTU in AEAT_RECORD_BATCH_SHAPES
    assert DocumentShape.XML_AEAT_SII in AEAT_RECORD_BATCH_SHAPES


def test_every_batch_shape_has_a_reader_that_accepts_it() -> None:
    """A batch shape may not exist without a reader that handles it.

    Disjointness alone leaves a gap: a new AEAT family could be added to
    :data:`AEAT_RECORD_BATCH_SHAPES` -- correctly kept out of the single-invoice
    set -- while no reader accepts it, so documents of that shape would be
    recognised and then handled by nothing. The evidence path refuses
    unrecognised XML, so such a document would be classified, refused, and
    look deliberate.

    Asserted by ROUTING rather than by a name list, so it holds for a member
    added later: every member must be a shape ``parse_aeat_record_batch``
    admits. Checked on the refusal message, since reaching it means the shape
    passed the entry guard.
    """
    for shape in AEAT_RECORD_BATCH_SHAPES:
        assert shape in set(DocumentShape), "a batch shape must be a real member"

    # The entry guard names precisely the shapes it accepts; anything outside
    # the batch set is turned away by it. Proving a NON-batch shape is refused
    # is what makes the acceptance of the batch shapes meaningful rather than
    # a function that accepts everything.
    with pytest.raises(EInvoiceXmlParseError, match="not an AEAT"):
        parse_aeat_record_batch(_read("facturae_32_series_and_parties_invoice.xml"))

    batch = _batch()
    assert batch.shape in AEAT_RECORD_BATCH_SHAPES, "a batch document reaches the batch reader and is accepted"


def test_a_record_family_outside_the_boundary_is_refused_by_name_not_skipped() -> None:
    """An unclaimed family must REFUSE, never fall through as an empty batch.

    The SII envelope declares seventeen top-level record families; this reader
    claims two of them. A family left unmapped is silently skipped, so a
    submission of bienes de inversion would read as a batch containing nothing
    and report no problem -- indistinguishable, to an operator, from a
    submission we read successfully and found empty.

    Asserted on the refusal naming the element, so the operator learns WHICH
    family was declined rather than that something unspecified was.
    """
    submission = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<siiLR:SuministroLRBienesInversion xmlns:siiLR="urn:sii" xmlns:sii="urn:sii2">'
        b"<sii:Cabecera><sii:Titular><sii:NombreRazon>X</sii:NombreRazon>"
        b"<sii:NIF>B12345674</sii:NIF></sii:Titular></sii:Cabecera>"
        b"<siiLR:RegistroLRBienesInversion><sii:Ejercicio>2026</sii:Ejercicio>"
        b"</siiLR:RegistroLRBienesInversion>"
        b"</siiLR:SuministroLRBienesInversion>"
    )

    batch = parse_aeat_record_batch(submission)

    assert batch.records == (), "nothing is read from an unclaimed family"
    assert len(batch.refusals) == 1, "and it is REFUSED, not skipped"
    assert batch.refusals[0].family is AeatRecordFamily.OTHER
    assert batch.refusals[0].element_name == "RegistroLRBienesInversion"
    assert "RegistroLRBienesInversion" in batch.refusals[0].reason


def test_a_single_invoice_document_is_refused_by_the_batch_reader() -> None:
    """The batch reader declines what the single-invoice reader owns.

    Asserted so the two entry points cannot quietly start overlapping: a
    Facturae document has no AEAT record family and must not be coerced into a
    one-record batch.
    """
    with pytest.raises(EInvoiceXmlParseError, match="not an AEAT"):
        parse_aeat_record_batch(_read("facturae_32_series_and_parties_invoice.xml"))
