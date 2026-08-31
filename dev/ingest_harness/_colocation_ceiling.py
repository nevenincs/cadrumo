"""What fraction of real documents CAN clear the co-location bar, at best.

The co-location resolver attributes an address value to the party whose region
of the page contains it, and it fires only when the reader supplied role
evidence for BOTH identities and both excerpts occur in the transcription. On a
document quoting one heading or none, every address value stays unresolved and
falls back to the interim advisory. The failure direction is safe -- unresolved
keeps the warning -- so nothing goes wrong when the bar is not cleared, and
nothing announces it either. **The resolver landing is not the same as the hole
closing, and only a measurement distinguishes them.**

**This measures a CEILING, not an observed rate, and the distinction is the
whole design.** An observed rate would score the model's quoted headings, which
means scoring a reader against a truth derived from that same reader -- not
evidence. So the anchors here come only from AUTHORED sources: the corpus key's
hand-written ``issuer`` and ``counterparty_name`` truth, and a hand-written
label vocabulary. The question asked is therefore "could a PERFECT reader
partition this document at all", and its answer is a property of the DOCUMENT.
A perfect reader is an upper bound on every real one, so a document failing here
cannot be rescued by a better prompt, a larger model or a second pass.

The verdict is never computed here. Every document is put through
:func:`~application.ledger.party_colocation.party_regions`, the production partition itself, so
this module cannot drift into a second implementation of the rule it is scoring.

**The dominant real layout defeats line containment, and that is the finding.**
A two-column invoice header -- issuer on the left, recipient on the right -- is
emitted by a reading-order text extractor as ONE line carrying both parties.
Both candidate anchor kinds collapse together: the labels share a line
(``EMISOR  DESTINATARIO / CLIENTE``) and so do the names printed under them.
Two anchors on one line yield one zero-width span, which ``_regions`` drops by
design, so the partition is empty. The resolver's own docstring anticipated
"two headings printed on one line" as an edge case; on this corpus it is the
norm rather than the exception.

**A count alone would not have shown that.** Every unpartitionable document
therefore carries a stated :class:`CeilingOutcome` reason, so a new failure mode
arrives as a new reason rather than hiding inside a total that was already
large.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
from cadrumo.application.ledger.evidence_draft import FieldProvenance, InvoiceDraft
from cadrumo.application.ledger.grounding_anchor import printed_excerpt_occurs_in_text
from cadrumo.application.ledger.party_colocation import party_regions
from cadrumo.core.field_grounding import FieldGroundingOutcome
from cadrumo.core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from cadrumo.core.field_origin import FieldOrigin

__all__ = [
    "AUTHORED_LABEL_PAIRS",
    "CeilingOutcome",
    "CeilingReport",
    "CeilingRow",
    "colocation_ceiling",
    "documents_with_authored_transcription",
]

_STRICT = ConfigDict(frozen=True, strict=True, extra="forbid")

#: Party-label pairs authored by hand from the printed documents, never taken
#: from a reader's output. Ordered most to least specific so a document printing
#: the compound label is scored on the compound rather than on its prefix.
AUTHORED_LABEL_PAIRS: Final[tuple[tuple[str, str], ...]] = (
    ("EMISOR", "DESTINATARIO / CLIENTE"),
    ("EMISOR", "DESTINATARIO"),
    ("EMISOR", "CLIENTE"),
    ("PROVEEDOR", "CLIENTE"),
    ("FACTURA A", "FACTURAR A"),
)


class CeilingOutcome(StrEnum):
    """Why one document can or cannot be partitioned by ANY authored anchor pair.

    Attributes:
        PARTITIONED: Some authored pair yields two non-empty regions. A perfect
            reader quoting that pair would clear the bar.
        ANCHORS_SHARE_A_LINE: Both anchors were located and landed on the same
            line, so one region is zero-width and is dropped. The two-column
            header case, and the commonest one measured.
        ANCHOR_NOT_PRINTED: At least one side of every authored pair does not
            occur in the transcription at all.
        UNPARTITIONED_FOR_ANOTHER_REASON: Both anchors were located on DIFFERENT
            lines and the partition was still empty. No measured cause explains
            that, so it is reported as its own population rather than folded
            into the shared-line one. Its whole purpose is to stay at zero: a
            member here means the shared-line reading has stopped being the
            explanation and the measurement needs re-deriving.
        NO_AUTHORED_ANCHORS: The key carries no authored identity for one of the
            parties, so there is nothing to test with. Distinct from a failure:
            this document has no denominator rather than a low score.
    """

    PARTITIONED = "partitioned"
    ANCHORS_SHARE_A_LINE = "anchors_share_a_line"
    ANCHOR_NOT_PRINTED = "anchor_not_printed"
    UNPARTITIONED_FOR_ANOTHER_REASON = "unpartitioned_for_another_reason"
    NO_AUTHORED_ANCHORS = "no_authored_anchors"


class CeilingRow(BaseModel):
    """One document's ceiling verdict, with the pair that produced it."""

    model_config = _STRICT

    doc_id: str = Field(min_length=1)
    outcome: CeilingOutcome
    supplier_anchor: str | None = None
    customer_anchor: str | None = None


class CeilingReport(BaseModel):
    """The ceiling over a population, with every denominator carried beside it.

    ``testable`` is the honest denominator: documents carrying an authored
    transcription AND an authored anchor for each party. A document with no
    authored identity is excluded rather than counted as a failure, because an
    undefined result is not a zero.
    """

    model_config = _STRICT

    rows: tuple[CeilingRow, ...]

    @property
    def transcribed(self) -> int:
        """Documents carrying an authored reference transcription."""
        return len(self.rows)

    @property
    def testable(self) -> int:
        """Documents with an authored anchor available for BOTH parties."""
        return sum(1 for row in self.rows if row.outcome is not CeilingOutcome.NO_AUTHORED_ANCHORS)

    @property
    def partitioned(self) -> int:
        """Documents a perfect reader could partition."""
        return sum(1 for row in self.rows if row.outcome is CeilingOutcome.PARTITIONED)

    def by_outcome(self, outcome: CeilingOutcome) -> tuple[CeilingRow, ...]:
        """Return every row carrying *outcome*."""
        return tuple(row for row in self.rows if row.outcome is outcome)


def _transcription(text: str) -> DocumentTranscription:
    """Return an authored reference text wearing the production transcription type.

    The transcriber identity names the AUTHORED source rather than a real
    extractor, so a row can never be mistaken for something a reader produced.
    """
    return DocumentTranscription(
        text=text,
        page_count=1,
        source_content_sha256="0" * 64,
        transcriber=TranscriberIdentity(
            origin=FieldOrigin.TEXT_LAYER,
            name="authored-reference-text",
            transport=LOCAL_TRANSPORT_LABEL,
            revision="1",
        ),
    )


def _draft(supplier: str, customer: str) -> InvoiceDraft:
    """Return the minimal draft carrying one role-evidence excerpt per identity."""

    def envelope(field: str, role_evidence: str) -> FieldProvenance:
        return FieldProvenance(
            field=field,
            origin=FieldOrigin.TEXT_LAYER,
            grounding=FieldGroundingOutcome.UNANCHORED,
            anchor=role_evidence,
            role_evidence=role_evidence,
        )

    return InvoiceDraft(
        provenance=(
            envelope("supplier_tax_id", supplier),
            envelope("customer_tax_id", customer),
        ),
    )


def _line_of(excerpt: str, lines: list[str]) -> int | None:
    """Return the first line index printing *excerpt*, through the one authority."""
    for index, line in enumerate(lines):
        if printed_excerpt_occurs_in_text(excerpt, text=line):
            return index
    return None


def _authored_pairs(ground_truth: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    """Return every authored anchor pair worth trying for one document.

    The key's own ``issuer`` and ``counterparty_name`` first -- those are the
    strongest authored identities available -- then the hand-written labels.
    Trying several is what makes the result a CEILING: a document is only
    reported unpartitionable when NO authored pair partitions it.
    """
    pairs: list[tuple[str, str]] = []
    issuer, counterparty = ground_truth.get("issuer"), ground_truth.get("counterparty_name")
    if isinstance(issuer, str) and issuer.strip() and isinstance(counterparty, str) and counterparty.strip():
        pairs.append((issuer, counterparty))
    pairs.extend(AUTHORED_LABEL_PAIRS)
    return tuple(pairs)


def _row_for(doc_id: str, text: str, ground_truth: Mapping[str, object]) -> CeilingRow:
    """Return one document's ceiling verdict, reason included."""
    lines = text.split("\n")
    pairs = _authored_pairs(ground_truth)
    shared: tuple[str, str] | None = None
    unexplained: tuple[str, str] | None = None
    for supplier, customer in pairs:
        if party_regions(draft=_draft(supplier, customer), transcription=_transcription(text)):
            return CeilingRow(
                doc_id=doc_id,
                outcome=CeilingOutcome.PARTITIONED,
                supplier_anchor=supplier,
                customer_anchor=customer,
            )
        # The reason is MEASURED, never inferred from the partition being empty.
        # Reading "both located, so they must share a line" off a failed
        # partition would relabel every future cause as this one, and a
        # homogeneous finding set produced that way is a fact about the
        # instrument rather than about the corpus.
        supplier_line, customer_line = _line_of(supplier, lines), _line_of(customer, lines)
        if supplier_line is None or customer_line is None:
            continue
        if supplier_line == customer_line:
            shared = shared or (supplier, customer)
        else:
            unexplained = unexplained or (supplier, customer)

    if unexplained is not None:
        # Both anchors were found on DIFFERENT lines and the partition still
        # came back empty. Nothing in the measured causes explains that, so it
        # gets its own outcome rather than being folded into the shared-line
        # population it would otherwise inflate.
        return CeilingRow(
            doc_id=doc_id,
            outcome=CeilingOutcome.UNPARTITIONED_FOR_ANOTHER_REASON,
            supplier_anchor=unexplained[0],
            customer_anchor=unexplained[1],
        )
    if shared is not None:
        return CeilingRow(
            doc_id=doc_id,
            outcome=CeilingOutcome.ANCHORS_SHARE_A_LINE,
            supplier_anchor=shared[0],
            customer_anchor=shared[1],
        )
    if len(pairs) == len(AUTHORED_LABEL_PAIRS):
        return CeilingRow(doc_id=doc_id, outcome=CeilingOutcome.NO_AUTHORED_ANCHORS)
    return CeilingRow(doc_id=doc_id, outcome=CeilingOutcome.ANCHOR_NOT_PRINTED)


def documents_with_authored_transcription(
    key_documents: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    """Return the key entries carrying a non-empty authored reference text.

    The measurable population. A document with no authored transcription cannot
    be scored against an authored truth at all, and inventing one from a
    reader's output is precisely the derivation this measurement exists to
    avoid.
    """
    return [
        entry
        for entry in key_documents
        if isinstance(entry.get("stage1_reference_text"), str) and str(entry["stage1_reference_text"]).strip()
    ]


def colocation_ceiling(key_documents: Sequence[Mapping[str, object]]) -> CeilingReport:
    """Return the co-location ceiling over every authored-transcription document.

    Args:
        key_documents: Raw key entries, as loaded from the pinned corpus key.
            Taken raw rather than as :class:`~._key.CorpusDocument` because the
            authored transcription is not on that narrow projection.

    Returns:
        One row per document carrying an authored transcription.
    """
    rows: list[CeilingRow] = []
    for entry in documents_with_authored_transcription(key_documents):
        ground_truth = entry.get("ground_truth")
        rows.append(
            _row_for(
                str(entry["doc_id"]),
                str(entry["stage1_reference_text"]),
                ground_truth if isinstance(ground_truth, Mapping) else {},
            ),
        )
    return CeilingReport(rows=tuple(rows))
