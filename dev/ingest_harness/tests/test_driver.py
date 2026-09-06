"""The driver drives the product, and the instrument still refuses what it must.

The harness was an instrument with no caller: ``HarnessReport`` was constructed
only in its own tests, so nothing could point it at a document. This suite gates
the half that closes that -- the plumbing between the shipped reader, the
corpus-to-draft projection and the scorer.

**The structured lane is measured because it needs no model.** A Facturae, UBL
or CII record is read deterministically, so these cases are reproducible on a
machine with no inference runtime and their numbers do not move between runs.
The text and vision lanes reach a model by design and are not measurable here,
which is a property of those lanes rather than a gap in this one.

**No accuracy figure is asserted, deliberately.** A number pinned here would
become a target and would go stale against a corpus that grows; what is asserted
is that real documents produce quotable rows, that the reader is the product's
own, and that every refusal the runner exists for still fires through this path.
"""

from __future__ import annotations

import pytest

from .._driver import DriverError, measure_structured_document, read_structured_draft
from .._key import CorpusKey
from .._result import EngineRoute, HarnessRefusalError, ModelTier, PipelineStage
from .._runner import HarnessReport

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def _structured_documents(key: CorpusKey) -> list:
    return [document for document in key.documents if document.path.lower().endswith(".xml")]


def _first_readable(key: CorpusKey):
    for document in _structured_documents(key):
        try:
            read_structured_draft(document)
        except DriverError:
            continue
        return document
    pytest.fail("no structured document in the pinned corpus could be read at all")


def test_the_corpus_carries_structured_documents_to_drive(key: CorpusKey) -> None:
    """Anchor: without these the rest of the suite is vacuous rather than passing."""
    assert _structured_documents(key), "the pinned key names no XML document"


def test_a_real_document_reads_through_the_products_own_parser(key: CorpusKey) -> None:
    """The whole point of a driver: it reimplements nothing.

    A 409-line shadow parser was deleted from an earlier harness because a
    harness that reimplements the reader measures itself.
    """
    draft = read_structured_draft(_first_readable(key))

    assert draft, "the parser returned nothing at all"
    assert "invoice_number" in draft


def test_driving_a_real_document_produces_a_quotable_row(key: CorpusKey) -> None:
    """A row the report accepts, which is the measurement this unblocks."""
    document = _first_readable(key)

    row = measure_structured_document(document, key_sha256=key.sha256)

    assert row.doc_id == document.doc_id
    assert row.key_sha256 == key.sha256
    # Scorable is the oracle's expected field set - live 15, decomposing as 11
    # matched plus 4 missed against a draft of 26 keys. `> 0` accepted an
    # oracle narrowed to a single field, which would make the row quotable
    # while measuring almost nothing. The floor sits below the smallest
    # plausible real field set rather than just under 15, because the test
    # takes the FIRST READABLE document and a different one may legitimately
    # carry fewer fields; it therefore does not catch a narrowing to the 11
    # matched alone, which a per-document expectation would be needed for.
    # This is a corpus-size floor, not the acceptance floor the route test
    # below rightly refuses to draw from a parser.
    assert row.outcome.scorable_field_count > 8, (
        f"the oracle scored only {row.outcome.scorable_field_count} fields for "
        f"{document.doc_id}, so this row quotes a measurement over almost nothing"
    )


def test_the_row_names_the_route_and_tier_it_actually_ran_under(key: CorpusKey) -> None:
    """No model runs here, and the row must not imply one did.

    The route is DETERMINISTIC rather than a local inference route, and the tier
    sets no acceptance floor: a floor drawn from a parser would flatter every
    model-read lane compared against it.
    """
    row = measure_structured_document(_first_readable(key), key_sha256=key.sha256)

    assert row.engine_route is EngineRoute.DETERMINISTIC
    assert row.model_tier is ModelTier.UPPER_REFERENCE
    assert not row.is_baseline_eligible
    assert row.stage is PipelineStage.END_TO_END


def test_the_report_accepts_what_the_driver_produces(key: CorpusKey) -> None:
    """End to end: the instrument and its caller agree on the row shape."""
    report = HarnessReport(key)

    report.add(measure_structured_document(_first_readable(key), key_sha256=key.sha256))

    assert len(report.rows) == 1


def test_a_row_scored_against_another_key_is_still_refused(key: CorpusKey) -> None:
    """The driver must not become a way around the instrument's own refusals."""
    report = HarnessReport(key)
    foreign = measure_structured_document(_first_readable(key), key_sha256="b" * 64)

    with pytest.raises(HarnessRefusalError, match=r"(?i)key"):
        report.add(foreign)


def test_a_document_the_reader_refuses_is_reported_as_such(key: CorpusKey) -> None:
    """An AEAT SII or VeriFactu payload is not an invoice record, and says so.

    Those are reporting submissions rather than structured invoices, so the
    product's reader refuses them correctly. The driver surfaces that as its own
    error instead of scoring a document it never read -- which would book a
    reader's correct refusal as a measurement failure.
    """
    refusals = 0
    for document in _structured_documents(key):
        try:
            read_structured_draft(document)
        except DriverError as error:
            refusals += 1
            assert document.doc_id in str(error)

    assert refusals, "no document exercised the refusal path, so this proves nothing"


def test_a_document_absent_from_disk_refuses_rather_than_scoring_zero(key: CorpusKey) -> None:
    """A missing file is a broken measurement, not a reader that found nothing.

    Scoring it would report a denominator over documents that are not there.
    """
    document = _first_readable(key).model_copy(update={"path": "does/not/exist.xml"})

    with pytest.raises(DriverError, match=r"(?i)no such file"):
        read_structured_draft(document)
