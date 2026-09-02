"""The multi-recipient guard the batch reader named and could not enforce itself.

Read against the bundled VERI*FACTU submission through the shipped reader rather
than against hand-built records: the requirement is inherited from that reader's
schema reading (``IDDestinatario`` is ``[0..1000]``), and the bundled fixture
already carries a record naming two recipients under two DIFFERENT identifier
schemes -- a national ``NIF`` and a foreign ``IDOtro``. A hand-built record would
be asserting the guard against a shape nothing produces, and a single-scheme
fixture would let a refusal that renders only digits pass.

The zero- and one-recipient variants are derived from that same document by
removing recipient blocks, so all three cases traverse the identical parse path.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ....adapters.inbound.einvoice.record_batch import ParsedAeatRecord, parse_aeat_record_batch
from ..aeat_record_projection import (
    AeatRecordProjectionError,
    describe_aeat_party_identifier,
    project_aeat_record_counterparty,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CORPUS = Path(__file__).parent / "_evidence_corpus"
_SUBMISSION = _CORPUS / "verifactu_alta_batch_record.xml"

_RECIPIENT_BLOCK_RE = re.compile(
    r"[ \t]*<sum1:IDDestinatario>.*?</sum1:IDDestinatario>\n",
    re.DOTALL,
)
_RECIPIENTS_ELEMENT_RE = re.compile(
    r"[ \t]*<sum1:Destinatarios>.*?</sum1:Destinatarios>\n",
    re.DOTALL,
)


def _read_record(document: bytes) -> ParsedAeatRecord:
    """Parse *document* through the shipped reader and return its sole record."""
    batch = parse_aeat_record_batch(document)
    # The bundled submission deliberately mixes a registration with a
    # cancellation; the cancellation is refused by design and is not an
    # invoice, so exactly one READ record is the correct expectation here.
    assert len(batch.records) == 1, f"expected exactly one read record, got {len(batch.records)}"
    return batch.records[0]


def _bundled_text() -> str:
    return _SUBMISSION.read_text(encoding="utf-8")


def test_the_bundled_submission_still_names_two_recipients_under_two_schemes() -> None:
    """Fixture anchor: the corpus document must still carry the case under test.

    Without this, an edit to the fixture that dropped a recipient would leave
    every assertion below passing vacuously against a single-recipient record.
    """
    record = _read_record(_SUBMISSION.read_bytes())

    assert len(record.recipients) == 2
    schemes = {party.id_type is not None or party.country_code is not None for party in record.recipients}
    assert schemes == {True, False}, "the fixture no longer mixes a NIF party with an IDOtro party"


def test_a_record_naming_no_recipient_projects_to_none() -> None:
    """A factura simplificada legitimately names nobody; that is not a failure.

    Guarding ``!= 1`` instead of ``> 1`` would reject this whole document class,
    so the distinction is gated rather than left to reading the code.
    """
    stripped = _RECIPIENTS_ELEMENT_RE.sub("", _bundled_text(), count=1)
    record = _read_record(stripped.encode("utf-8"))

    assert record.recipients == ()
    assert project_aeat_record_counterparty(record) is None


def test_a_single_recipient_projects_through() -> None:
    """The ordinary case still passes; the guard is not a blanket refusal."""
    text = _bundled_text()
    blocks = _RECIPIENT_BLOCK_RE.findall(text)
    assert len(blocks) >= 2, "fixture must carry more than one recipient to drop one"
    single = text.replace(blocks[1], "", 1)

    record = _read_record(single.encode("utf-8"))

    assert len(record.recipients) == 1
    projected = project_aeat_record_counterparty(record)
    assert projected is not None
    assert projected is record.recipients[0]


def test_several_recipients_refuse_and_name_every_party_with_its_scheme() -> None:
    """The refusal enumerates parties WITH schemes; a count would not be actionable.

    The scheme is the load-bearing half: the same digits stated under ``NIF`` and
    under ``IDOtro`` are two different parties, so an operator resolving the
    split cannot act on identifiers stripped of the scheme they were stated
    under.
    """
    record = _read_record(_SUBMISSION.read_bytes())

    with pytest.raises(AeatRecordProjectionError) as raised:
        project_aeat_record_counterparty(record)

    message = str(raised.value)
    for party in record.recipients:
        assert party.tax_id is not None
        assert party.tax_id in message, f"recipient {party.tax_id} is absent from the refusal"
        assert party.name is not None
        assert party.name in message
    assert "NIF" in message
    assert "IDOtro" in message
    assert "country=FR" in message


def test_the_first_recipient_is_never_returned_silently() -> None:
    """The exact defect the guard exists for, asserted as an outcome.

    A projection that took ``recipients[0]`` would satisfy every type in the
    system and produce a well-formed record naming a real counterparty -- just
    not all of them. Nothing downstream could detect that, which is why the
    refusal has to happen here.
    """
    record = _read_record(_SUBMISSION.read_bytes())
    first = record.recipients[0]

    with pytest.raises(AeatRecordProjectionError):
        result = project_aeat_record_counterparty(record)
        pytest.fail(f"projection silently returned {result} instead of refusing; first was {first}")


def test_a_party_with_no_identifier_is_described_as_absent_not_blank() -> None:
    """An identifier the record never stated must say so, not render as empty."""
    record = _read_record(_SUBMISSION.read_bytes())
    described = [describe_aeat_party_identifier(party) for party in record.recipients]

    assert any(text.startswith("DESTINATARIO Nacional SA [NIF ") for text in described)
    assert any("[IDOtro country=FR" in text for text in described)
