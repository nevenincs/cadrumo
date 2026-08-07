"""The anchor check: a value grounds only if the document can be pointed at.

This is the structural half of the anti-fabrication contract. A prompt asking a
model not to invent figures reduces noise and enforces nothing; this module is
what makes an anchor mean something, and it runs as ordinary deterministic code
over the transcription no matter which reader proposed the value.

The check has TWO parts, and both matter:

**The anchor must occur in the transcription.** Not the value -- the anchor, the
verbatim printed form the reader claims to have read. The transcription
deliberately preserves printed forms (``2.420,00`` stays ``2.420,00``), so this
search runs against the evidence rather than against a normalised rewrite of it.

**The typed value must equal the deterministic parse of that anchor.** The value
is NOT required to be byte-identical to the anchor -- anchor ``21%`` with value
``Decimal("21")`` is the intended case, not a concession. Requiring identity
would make the whole apparatus useless for every field that needs parsing, which
is every monetary field.

The parse is :func:`~core.decimal.coerce_finite_european_decimal`, the repository's
one extraction-side decimal contract, reused rather than re-spelled. It drops an
ambiguous thousands reading instead of guessing, which is exactly the behaviour
wanted here: an anchor whose reading cannot be settled does not ground.

**A weaker case, stated rather than hidden.** When the anchor and the rendered
value happen to be identical strings, the second part of the check proves nothing
about parsing -- the value is matching itself. The check still runs and still
requires the anchor to occur in the document, so the fabrication bound holds; but
the parse half is vacuous there, and :attr:`AnchorEvaluation.parse_was_vacuous`
says so rather than letting the outcome read stronger than it is.

What this module does NOT do: decide that a grounded value is CORRECT. Anchoring
bounds fabrication to transcription error. On a vision path the transcription is
itself model-produced, so an anchored value survived two reads that agreed rather
than one unchecked guess -- a real improvement, and not a proof.

See Also:
    :class:`~application.ledger.FieldProvenance`
        The envelope this module produces, carrying the anchor it verified.
    :func:`~application.ledger.transcribe_text_layer`
        The acquisition stage whose verbatim output this checks against.
    :class:`~core.FieldGroundingOutcome`
        The closed outcome axis; this module never widens it.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG, FieldGroundingOutcome, FieldOrigin
from ...core.decimal import coerce_finite_european_decimal
from ._document_transcription import DocumentTranscription
from ._evidence_draft import FieldAmbiguityCandidate, FieldProvenance

__all__ = [
    "AnchorEvaluation",
    "evaluate_anchor",
    "ground_ambiguous_candidates",
    "ground_anchored_value",
    "normalise_for_anchor_search",
]

#: Characters a PDF text layer routinely substitutes for an ordinary space.
#: Collapsing them is NOT a normalisation of the number: the printed glyphs are
#: unchanged, only the whitespace between them is regularised, so ``1 234,56``
#: and ``1 234,56`` are recognised as the same printed form while
#: ``1.234,56`` and ``1234,56`` stay distinct -- which they must, because the
#: separator is the evidence the decimal reading rests on.
_WHITESPACE_RUN = re.compile(r"\s+")


def normalise_for_anchor_search(text: str) -> str:
    """Return *text* with Unicode form and whitespace regularised, nothing else.

    The narrowest normalisation that survives a real PDF text layer. Two
    documents printing the same figure can differ in a non-breaking space, in a
    soft hyphen, or in whether a composed character arrived pre-composed -- none
    of which is a difference in what was printed. Digits, separators and
    punctuation are left exactly as they are, because those ARE the evidence.

    Args:
        text: Raw text from a transcription or a proposed anchor.

    Returns:
        The regularised form, for anchor comparison only. Never stored as the
        anchor itself: the envelope keeps what the document actually printed.
    """
    composed = unicodedata.normalize("NFKC", text)
    return _WHITESPACE_RUN.sub(" ", composed).strip()


class AnchorEvaluation(BaseModel):
    """The verdict on one candidate, before it becomes a provenance envelope.

    Separated from :class:`FieldProvenance` so the decision is inspectable on its
    own: a caller can ask WHY a value failed to ground without reading it back
    out of an outcome enum, and a test can assert on the reason rather than on
    the consequence.

    Attributes:
        outcome: The grounding outcome this evaluation resolves to.
        anchor_found: Whether the anchor occurs in the transcription.
        parsed_anchor: The deterministic parse of the anchor, when the value
            under check is a decimal and the anchor parses at all.
        parse_was_vacuous: ``True`` when the anchor and the rendered value are
            the same string, so the parse half of the check compared a value
            against itself and established nothing. The anchor half still ran.
        detail: Operator-facing explanation.
    """

    model_config = STRICT_FROZEN_CONFIG

    outcome: FieldGroundingOutcome
    anchor_found: bool
    parsed_anchor: Decimal | None = None
    parse_was_vacuous: bool = False
    detail: str = ""


def evaluate_anchor(
    *,
    value: Decimal | str,
    anchor: str,
    transcription: DocumentTranscription,
) -> AnchorEvaluation:
    """Evaluate one candidate's anchor against the transcription it came from.

    Args:
        value: The typed value the reader proposes.
        anchor: The verbatim printed form the reader claims to have read it from.
        transcription: The acquisition-stage text, printed forms intact.

    Returns:
        The evaluation. ``ANCHORED`` requires BOTH that the anchor occurs in the
        transcription AND that the value equals the deterministic parse of the
        anchor. A missing anchor is ``UNANCHORED``; a present anchor that parses
        to a different value is ``CONTRADICTED``, which is a stronger and more
        actionable statement than merely failing to ground.
    """
    if not anchor.strip():
        return AnchorEvaluation(
            outcome=FieldGroundingOutcome.UNANCHORED,
            anchor_found=False,
            detail="the candidate carries no anchor, so nothing in the document can be pointed at",
        )

    haystack = normalise_for_anchor_search(transcription.text)
    needle = normalise_for_anchor_search(anchor)
    anchor_found = needle in haystack

    if not anchor_found:
        return AnchorEvaluation(
            outcome=FieldGroundingOutcome.UNANCHORED,
            anchor_found=False,
            detail=f"the anchor {anchor!r} does not occur in the document's transcription",
        )

    if isinstance(value, str):
        # A textual field grounds on the anchor alone: there is no deterministic
        # parse to re-derive it from, and inventing one here would put this
        # module's idea of normalisation in place of the document's own text.
        rendered = normalise_for_anchor_search(value)
        return AnchorEvaluation(
            outcome=FieldGroundingOutcome.ANCHORED,
            anchor_found=True,
            parse_was_vacuous=rendered == needle,
            detail=f"anchored to {anchor!r}",
        )

    parsed = coerce_finite_european_decimal(anchor)
    if parsed is None:
        return AnchorEvaluation(
            outcome=FieldGroundingOutcome.CONTRADICTED,
            anchor_found=True,
            detail=(
                f"the anchor {anchor!r} occurs in the document but does not parse to a decimal "
                f"under the extraction contract, so it cannot support the value {value}"
            ),
        )

    if parsed != value:
        return AnchorEvaluation(
            outcome=FieldGroundingOutcome.CONTRADICTED,
            anchor_found=True,
            parsed_anchor=parsed,
            detail=(f"the anchor {anchor!r} parses to {parsed}, which is not the proposed value {value}"),
        )

    return AnchorEvaluation(
        outcome=FieldGroundingOutcome.ANCHORED,
        anchor_found=True,
        parsed_anchor=parsed,
        parse_was_vacuous=normalise_for_anchor_search(str(value)) == needle,
        detail=f"anchored to {anchor!r}, which parses to {parsed}",
    )


def ground_anchored_value(
    *,
    field: str,
    value: Decimal | str,
    anchor: str,
    origin: FieldOrigin,
    transcription: DocumentTranscription,
) -> FieldProvenance:
    """Return the provenance envelope for one candidate, anchor-checked.

    The single entry point a reading path uses to turn a proposed value into a
    reviewable one. A reader that bypasses this and constructs a ``FieldProvenance``
    with a hand-set ``ANCHORED`` outcome is asserting the check rather than
    running it, which is the failure this module exists to make unnecessary.

    Args:
        field: Name of the :class:`~application.ledger.InvoiceDraft` field.
        value: The typed value proposed.
        anchor: The verbatim printed form claimed as its source.
        origin: How the value was obtained.
        transcription: The acquisition-stage text to check against.

    Returns:
        The envelope, carrying the verified anchor and the resolved outcome.
    """
    evaluation = evaluate_anchor(value=value, anchor=anchor, transcription=transcription)
    return FieldProvenance(
        field=field,
        origin=origin,
        grounding=evaluation.outcome,
        # The anchor rides along whenever it was actually located, including on a
        # CONTRADICTED outcome: the operator resolving a disagreement needs to see
        # the printed form the reader misread, not merely be told it disagreed.
        anchor=anchor if evaluation.anchor_found else None,
        note=evaluation.detail,
    )


def ground_ambiguous_candidates(
    *,
    field: str,
    origin: FieldOrigin,
    candidates: tuple[FieldAmbiguityCandidate, ...],
    note: str = "",
) -> FieldProvenance:
    """Return an ``AMBIGUOUS`` envelope carrying every competing candidate.

    The sanctioned way to record "several readings competed and none was
    decidable". Deliberately takes the whole candidate set rather than a winner
    plus alternates: there is no winner, and a shape that had one would invite a
    caller to promote the first.

    Args:
        field: Name of the draft field.
        origin: How the competing values were obtained.
        candidates: Every competing reading. Two or more, enforced by the
            envelope itself.
        note: Operator-facing explanation of what made them competitors.

    Returns:
        The ``AMBIGUOUS`` envelope.
    """
    return FieldProvenance(
        field=field,
        origin=origin,
        grounding=FieldGroundingOutcome.AMBIGUOUS,
        candidates=candidates,
        note=note,
    )
