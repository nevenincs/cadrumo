"""The anchor check: a value grounds only if the document can be pointed at.

This is the structural half of the anti-fabrication contract. A prompt asking a
model not to invent figures reduces noise and enforces nothing; this module is
what makes an anchor mean something, and it runs as ordinary deterministic code
over the transcription no matter which reader proposed the value.

The check has TWO parts, and both matter:

**The anchor must occur in the transcription AS A WHOLE PRINTED TOKEN.** Not the
value -- the anchor, the verbatim printed form the reader claims to have read.
The transcription deliberately preserves printed forms (``2.420,00`` stays
``2.420,00``), so this search runs against the evidence rather than against a
normalised rewrite of it.

The token boundary is load-bearing rather than tidy. A plain substring search --
which this module originally did -- lets a short figure anchor inside any longer
figure ending the same way: ``0,00`` occurs inside ``100,00``, ``1,00`` inside
``21,00``, bare ``00`` inside almost any amount. An injected zero total needed no
cleverness at all to ground, because most real invoices carry some amount ending
in ``,00``. That made the check certify "these digits appear somewhere", which
for short numeric forms is close to vacuous -- structurally weaker than it read.

**The typed value must equal the deterministic parse of that anchor.** The value
is NOT required to be byte-identical to the anchor -- anchor ``21%`` with value
``Decimal("21")`` is the intended case, not a concession. Requiring identity
would make the whole apparatus useless for every field that needs parsing, which
is every monetary field.

Exactly one trailing UNIT marker is removed before that parse
(:func:`strip_printed_unit`). Without it the percentage form inverted: ``21%``
found in the document, ``coerce_finite_european_decimal`` returning ``None`` on
the percent sign, and the checker reporting CONTRADICTION on a rate the reader
read correctly -- punishing the reader that copied more literally, which is what
the field-form contract asks for. A wrong verdict is worse than an absent one,
because an absent verdict prompts review and a wrong one forecloses it.

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

**What this module does NOT do, stated so it is not trusted for more.** It
decides that a printed form is PRESENT. It does not decide that the form plays
the ROLE claimed for it, and it does not decide the value is correct. An injected
sentence that prints its own plausible figure passes this check honestly -- the
figure really is on the page.

The guarantee is therefore **the conjunction of two legs, never this one alone**:
the anchor check establishes presence, and
:func:`~application.ledger.closure_findings` establishes that the monetary set
closes. An injected total that is anchored still reds the arithmetic identity,
because the other figures on the document do not reach it. A suite that gated
only the anchor property would imply a guarantee the code does not provide, and
that is exactly how a check ends up trusted for more than it does.

Anchoring bounds fabrication to transcription error. On a vision path there is no
independent transcription at all -- see
:func:`ground_self_reported_anchor` -- so the bound is weaker still and the
outcome says so.

See Also:
    :class:`~application.ledger.evidence_draft.FieldProvenance`
        The envelope this module produces, carrying the anchor it verified.
    :func:`~application.ledger.evidence_textlayer.transcribe_text_layer`
        The acquisition stage whose verbatim output this checks against.
    :class:`~core.FieldGroundingOutcome`
        The closed outcome axis; this module never widens it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel

from ...core import DocumentShape
from ...core.field_grounding import FieldGroundingOutcome
from ...core.field_origin import FieldOrigin
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.text_fold import unicode_compose
from ...core.decimal import coerce_finite_european_decimal
from ...domain.iva.establishment import country_code_for_stated_country_code
from .document_transcription import DocumentTranscription
from .evidence_draft import FieldAmbiguityCandidate, FieldProvenance

if TYPE_CHECKING:
    from ...adapters.inbound.einvoice import ParsedEInvoice
    from .evidence_input import EvidenceInput

__all__ = [
    "AnchorEvaluation",
    "evaluate_anchor",
    "ground_ambiguous_candidates",
    "ground_anchored_value",
    "ground_self_reported_anchor",
    "ground_structured_value",
    "normalise_for_anchor_search",
    "printed_excerpt_occurs",
    "printed_excerpt_occurs_in_text",
    "refused_anchor_of",
    "strip_printed_unit",
]

#: Characters a PDF text layer routinely substitutes for an ordinary space.
#: Collapsing them is NOT a normalisation of the number: the printed glyphs are
#: unchanged, only the whitespace between them is regularised, so ``1 234,56``
#: and ``1 234,56`` are recognised as the same printed form while
#: ``1.234,56`` and ``1234,56`` stay distinct -- which they must, because the
#: separator is the evidence the decimal reading rests on.
_WHITESPACE_RUN = re.compile(r"\s+")

#: Characters that continue a printed NUMBER. An anchor whose numeric edge sits
#: against one of these is a fragment of a longer figure, not a figure.
#:
#: This set is the whole boundary rule and it is deliberately tiny. A plain
#: substring search made the anchor check close to vacuous for short numeric
#: forms: ``0,00`` occurs inside ``100,00``, ``1,00`` inside ``21,00``, and bare
#: ``00`` inside almost any amount. An injected zero total therefore grounded
#: against a large share of real invoices, because most carry some amount ending
#: in ``,00`` -- which turned D4's structural anti-fabrication check into an
#: assertion that the digits appear *somewhere*.
_NUMBER_CONTINUATION = frozenset("0123456789.,")


#: Unit markers a document prints AFTER a rate. Stripped from the anchor before
#: the decimal parse, exactly one, mirroring the reader-side rule.
_TRAILING_UNIT_MARKERS = ("%", "percent", "pct")


def strip_printed_unit(anchor: str) -> str:
    """Return *anchor* with exactly one trailing unit marker removed.

    A percent sign is a UNIT, not a digit. A document prints ``IVA (21%)`` and a
    reader obeying "copy exactly as printed" cites ``21%`` as the anchor for the
    value ``21`` -- which is the correct, more literal reading. Passing that
    string straight to the decimal authority returns ``None``, so the anchor was
    found, the parse failed, and the check reported CONTRADICTION on a field the
    reader got right. That verdict is worse than no provenance at all: an absent
    verdict prompts review, a wrong one forecloses it.

    Exactly ONE trailing marker is removed and the remainder must still satisfy
    the decimal authority on its own, so ``21%%`` or ``2%1`` still fail. The
    stripping applies only to the anchor's PARSE; the envelope keeps the
    verbatim printed form, so anchor and value stay explicitly distinct and a
    transcription error cannot be laundered into a computed figure.

    Args:
        anchor: The verbatim printed form.

    Returns:
        The anchor with one trailing unit marker removed, or unchanged.
    """
    text = anchor.strip()
    lowered = text.lower()
    for unit in _TRAILING_UNIT_MARKERS:
        if lowered.endswith(unit):
            return text[: -len(unit)].strip()
    return text


def _is_numeric_edge(character: str) -> bool:
    """Return whether *character* participates in a printed number."""
    return character in _NUMBER_CONTINUATION


def _continues_the_token(edge: str, neighbour: str) -> bool:
    """Return whether *neighbour* makes *edge* a fragment rather than a token.

    Asked per EDGE, and **deliberately asymmetric between the two kinds of
    edge**, because what continues a printed NUMBER is not what continues a
    printed WORD.

    A numeric edge continues only into another number character. A letter beside
    a digit is a UNIT, not more of the figure: documents print ``EUR100,00`` and
    ``100,00EUR``, and treating the currency code as a continuation would refuse
    an anchor the document plainly carries. That is the pre-existing rule and it
    is right.

    A letter edge continues into any alphanumeric, digits included, because a
    word running into a digit is exactly how identifiers are built: ``ES``
    against ``ESB12345674`` is a fragment of an IVA identifier, not an occurrence
    of the country code. The symmetric rule was tried first and refused
    ``EUR100,00``, which is how the asymmetry was found rather than reasoned.

    An edge that is neither -- a currency symbol, a percent sign, a parenthesis,
    a hyphen -- continues into nothing, which keeps ``21%`` matching inside
    ``IVA (21%)``.
    """
    if _is_numeric_edge(edge):
        return _is_numeric_edge(neighbour)
    return edge.isalnum() and neighbour.isalnum()


def _occurs_as_a_whole_printed_token(needle: str, haystack: str) -> bool:
    """Return whether *needle* occurs in *haystack* as a complete printed token.

    Boundary-aware rather than substring: an occurrence counts only when the
    anchor is not a fragment of a longer printed token. The rule is applied per
    EDGE, so an anchor abutting punctuation, a currency symbol or a percent sign
    still matches, and only an edge that runs on into more of the same kind of
    character is refused.

    **Alphanumeric, not merely numeric, and the widening is the point.** The rule
    was numeric-only, on the reasoning that a word-shaped anchor is distinctive
    enough for substring matching to be safe. That holds for an invoice number or
    a party name and fails completely for a SHORT CODE: a two-letter country code
    is a fragment of half the strings on an invoice, and ``ES`` is the worst case
    in this domain because it prefixes every Spanish IVA identifier. A record
    stating no country at all had ``ES`` anchor against ``ESB12345674`` and the
    envelope reported the document as evidence for a value the document never
    states -- which is precisely the fabrication this check exists to refuse, and
    precisely the property its own contract claims to enforce.

    Every occurrence is examined, and one clean occurrence is enough: a document
    may print the same figure as a fragment in one place and as a whole token in
    another, and the second is a genuine anchor.

    What this still cannot do is prove the reader chose the RIGHT occurrence. A
    two-letter code appearing as a genuine standalone token somewhere unrelated
    matches, and that limit is stated on the entry points rather than papered
    over here.

    Args:
        needle: The normalised anchor.
        haystack: The normalised transcription text.

    Returns:
        ``True`` when at least one occurrence has clean boundaries.
    """
    if not needle:
        return False

    leading, trailing = needle[0], needle[-1]

    start = haystack.find(needle)
    while start != -1:
        end = start + len(needle)
        before_ok = start == 0 or not _continues_the_token(leading, haystack[start - 1])
        after_ok = end >= len(haystack) or not _continues_the_token(trailing, haystack[end])
        if before_ok and after_ok:
            return True
        start = haystack.find(needle, start + 1)
    return False


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
    composed = unicode_compose(text)
    return _WHITESPACE_RUN.sub(" ", composed).strip()


def printed_excerpt_occurs(excerpt: str, *, transcription: DocumentTranscription) -> bool:
    """Return whether ``excerpt`` occurs in the document, as a printed token.

    The presence half of :func:`evaluate_anchor`, exposed on its own for a claim
    that has no typed value behind it to re-parse. Role evidence is such a
    claim: it is a printed heading or label the reader copied to justify
    assigning an identifier to a party, so the only question that can be asked
    of it is whether the document actually says it.

    Reusing this module's own search rather than open-coding a containment test
    is what keeps one authority over "does the document print this": the same
    Unicode and whitespace regularisation that survives a real PDF text layer,
    and the same numeric-edge boundary rule, so a role evidence excerpt cannot
    be admitted under weaker matching than an anchor.

    Args:
        excerpt: The printed context the reader claims to have copied.
        transcription: The acquisition-stage text, printed forms intact.

    Returns:
        ``True`` when the excerpt occurs. A blank excerpt is ``False``: it
        evidences nothing, and the caller must treat that as absent evidence
        rather than as a permissive match.
    """
    return printed_excerpt_occurs_in_text(excerpt, text=transcription.text)


def printed_excerpt_occurs_in_text(excerpt: str, *, text: str) -> bool:
    """Return whether ``excerpt`` occurs in ``text``, as a printed token.

    The same search as :func:`printed_excerpt_occurs`, asked of a REGION of a
    document rather than the whole of one. Party attribution by co-location has
    to ask "does this value occur inside this party's block", which is the same
    question about a smaller haystack -- and asking it through this module keeps
    one authority over what counts as printed, so a value cannot be admitted to
    a block under weaker matching than the anchor check applies to the document.

    Takes plain text rather than a transcription deliberately. A region is a
    slice of a transcription's text and not a transcription itself: it has no
    page count, no content address and no transcriber, and manufacturing those
    to satisfy a signature would fabricate provenance for a substring.

    Args:
        excerpt: The printed form to look for.
        text: The text to look in, printed forms intact.

    Returns:
        ``True`` when the excerpt occurs. A blank excerpt is ``False``, on the
        same terms as the whole-document search: it evidences nothing.
    """
    if not excerpt.strip():
        return False
    return _occurs_as_a_whole_printed_token(
        normalise_for_anchor_search(excerpt),
        normalise_for_anchor_search(text),
    )


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


def refused_anchor_of(anchor: str | None, evaluation: AnchorEvaluation) -> str | None:
    """Return the printed form the check looked for and did not find, or ``None``.

    The one place the refusal is derived, so every producer that clears the
    anchor on a miss records the same discrimination rather than each deciding
    for itself. Clearing alone loses the fact that a form was OFFERED, and an
    operator told "the reader offered nothing to point at" when the reader
    offered something the document does not carry is being sent to investigate
    the wrong thing.

    A blank or absent anchor returns ``None`` on purpose: there was nothing to
    refuse, and recording an empty refusal would manufacture exactly the false
    distinction this closes, in the other direction.

    Args:
        anchor: The form the reader offered, if any.
        evaluation: The verdict the check reached on it.

    Returns:
        The offered form, when a check ran and did not locate it.
    """
    if anchor is None or evaluation.anchor_found or not anchor.strip():
        return None
    return anchor


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
    return _evaluate_anchor_against(value=value, anchor=anchor, source_text=transcription.text, source="transcription")


def _evaluate_anchor_against(
    *,
    value: Decimal | str,
    anchor: str,
    source_text: str,
    source: str,
    derive: Callable[[str], str | None] | None = None,
) -> AnchorEvaluation:
    """Run the anchor check against any source text, naming it in the detail.

    The check itself is the same two-part test wherever the text came from: the
    anchor must OCCUR in the source, and the value must equal the deterministic
    parse of the anchor. What differs between reading lanes is only which text is
    authoritative -- a transcription for a rendered page, the record's own bytes
    for a machine-readable document -- so that is the parameter, and the lanes
    share one implementation rather than growing two that can drift.

    Args:
        value: The typed value the reader proposes.
        anchor: The verbatim form claimed as its source.
        source_text: The authoritative text to look for the anchor in.
        source: What that text is, for the operator-facing detail line.
        derive: For a TEXTUAL value that differs from its anchor, the
            deterministic function re-deriving the value from the anchor. The
            textual counterpart of the decimal coercion this function already
            applies, and required for the same reason: without it "the anchor
            occurs" is a fact about the anchor and says nothing about the value.
    """
    if not anchor.strip():
        return AnchorEvaluation(
            outcome=FieldGroundingOutcome.UNANCHORED,
            anchor_found=False,
            detail="the candidate carries no anchor, so nothing in the document can be pointed at",
        )

    haystack = normalise_for_anchor_search(source_text)
    needle = normalise_for_anchor_search(anchor)
    anchor_found = _occurs_as_a_whole_printed_token(needle, haystack)

    if not anchor_found:
        return AnchorEvaluation(
            outcome=FieldGroundingOutcome.UNANCHORED,
            anchor_found=False,
            detail=f"the anchor {anchor!r} does not occur in the document's {source}",
        )

    if isinstance(value, str):
        if derive is not None:
            # The textual counterpart of the decimal re-derivation below, and it
            # exists for exactly the same reason. A value that does not equal its
            # own anchor is a DERIVED value, and "the anchor occurs" then says
            # nothing about it: the anchor could be real and the value arbitrary.
            # Re-deriving from the anchor is what ties the two back together.
            rederived = derive(anchor)
            if rederived != value:
                return AnchorEvaluation(
                    outcome=FieldGroundingOutcome.CONTRADICTED,
                    anchor_found=True,
                    detail=(
                        f"the anchor {anchor!r} derives to {rederived!r}, which is not the proposed value {value!r}"
                    ),
                )
            return AnchorEvaluation(
                outcome=FieldGroundingOutcome.ANCHORED,
                anchor_found=True,
                parse_was_vacuous=normalise_for_anchor_search(value) == needle,
                detail=f"anchored to {anchor!r}, which derives to {value!r}",
            )

        # A value that IS its own anchor grounds on the anchor alone: there is no
        # deterministic parse to re-derive it from, and inventing one here would
        # put this module's idea of normalisation in place of the document's own
        # text. Sound only because anchor-found then implies value-present, which
        # is why a derived value may not take this branch.
        rendered = normalise_for_anchor_search(value)
        return AnchorEvaluation(
            outcome=FieldGroundingOutcome.ANCHORED,
            anchor_found=True,
            parse_was_vacuous=rendered == needle,
            detail=f"anchored to {anchor!r}",
        )

    parsed = coerce_finite_european_decimal(strip_printed_unit(anchor))
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


def ground_structured_value(
    *,
    field: str,
    value: Decimal | str,
    element_path: str,
    source_text: str,
    anchor: str | None = None,
    derive: Callable[[str], str | None] | None = None,
) -> FieldProvenance:
    """Return the envelope for one value read from a document's own record.

    The structured sibling of :func:`ground_anchored_value`, and here for the same
    reason: a path that constructs a :class:`FieldProvenance` itself and hand-sets
    ``ANCHORED`` is asserting the check instead of running it. It is a separate
    entry point rather than a parameter on that one because the transcription this
    module normally checks against does not exist for a machine-readable document
    -- there are no pages, no reading order and no transcriber -- and a
    :class:`~application.ledger.document_transcription.DocumentTranscription` synthesised to satisfy the
    signature would have to state a page count and a reader that never existed.
    Both routes run the same two-part check underneath.

    **The anchor is the record's own verbatim text, never the element path.** The
    anchor field means the form the value was read from, and a downstream consumer
    reads it as evidence about what the document states. A schema path is a
    location: true, useful, and not evidence. It rides in the note instead, where
    an operator can still use it to find the value and nothing can mistake it for
    a printed form.

    **The check is real, not ceremonial.** The parser produced the value; this
    looks for its verbatim form in the record's own text independently, and
    re-derives a numeric value from the anchor. A projection that mangled a figure
    on the way through, or a reader that pointed at an element the document does
    not carry, fails it.

    **That second claim is enforced HERE and no longer only upstream.** It was
    once true only because every structured country reader returns its own
    element's text or ``None`` -- a guard in a different module entirely -- while
    this check would happily locate a two-letter code inside a longer token, so a
    record stating no country at all anchored ``ES`` against ``ESB12345674``. The
    search is boundary-aware for word-shaped anchors as well as numeric ones, so
    the property this paragraph asserts is now a property of this function.

    What it still cannot do is prove the reader chose the RIGHT element -- the
    same limit the transcription lane has, where an anchor found somewhere in the
    page does not prove it was found in the right place. A short code occurring
    as a genuine standalone token somewhere unrelated matches, and only the
    element path in the note distinguishes that.

    Args:
        field: Name of the :class:`~application.ledger.evidence_draft.InvoiceDraft` field.
        value: The typed value the parser produced.
        element_path: Where in the record it came from, for the operator's note.
        source_text: The record's own text, decoded from the source bytes.
        anchor: The record's verbatim form of the value, where that DIFFERS from
            the value itself. Defaults to the value's own rendering, which is
            correct for every field copied straight out of the record and was the
            only case until a value arrived normalised: a party's country is
            stated ``ESP`` by Facturae and carried ``ES``, so grounding the
            carried form would look for a string the document never states.

            This is the same relation :attr:`FieldProvenance.anchor` already
            documents for the printed lanes -- ``"1.234,56 €"`` anchoring the
            value ``1234.56``. **The shape is the same and the guarantee is not
            inherited**: that relation is checked by a parse that resolves
            CONTRADICTED on disagreement, so an explicit anchor here must supply
            its own equivalent through *derive*. Requiring it is not ceremony --
            without it the anchor could be real while the value was arbitrary,
            and the envelope would assert the document evidences a value it
            never mentions.
        derive: How to re-derive *value* from *anchor*, REQUIRED whenever an
            explicit anchor is given for a textual value. Refused rather than
            defaulted, because a silent default would be this module choosing a
            normalisation on the caller's behalf, which is the thing the anchor
            check exists to avoid.

    Returns:
        The envelope, stamped :attr:`~core.FieldOrigin.EXACT_STRUCTURED`.
    """
    if anchor is None:
        anchor = value if isinstance(value, str) else str(value)
    elif isinstance(value, str) and derive is None:
        # A caller contract, not a document condition, so it raises rather than
        # resolving to an outcome: an envelope is about what the document says,
        # and "the caller passed an unverifiable pair" is not one of the things
        # it can say.
        raise ValueError(
            f"{field}: an explicit anchor for a textual value needs a derivation to check it against; "
            f"without one the envelope would assert the record evidences {value!r} on the strength of "
            f"a different string occurring in it",
        )
    evaluation = _evaluate_anchor_against(
        value=value,
        anchor=anchor,
        source_text=source_text,
        source="record",
        derive=derive,
    )
    return FieldProvenance(
        field=field,
        origin=FieldOrigin.EXACT_STRUCTURED,
        grounding=evaluation.outcome,
        anchor=anchor if evaluation.anchor_found else None,
        refused_anchor=refused_anchor_of(anchor, evaluation),
        note=f"read from {element_path}; {evaluation.detail}",
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
        field: Name of the :class:`~application.ledger.evidence_draft.InvoiceDraft` field.
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
        refused_anchor=refused_anchor_of(anchor, evaluation),
        note=evaluation.detail,
    )


def ground_self_reported_anchor(
    *,
    field: str,
    anchor: str,
    origin: FieldOrigin,
    note: str = "",
) -> FieldProvenance:
    """Return the envelope for an anchor the reader asserted about its own output.

    The honest verdict for a lane that produces no transcription. The vision path
    reads image to fields in a single model call, so there is no independently
    produced text for an anchor to be a substring OF -- the model returns the
    printed form alongside the value, and that is a CLAIM about the document
    rather than evidence from it. Substring-matching such a claim against the
    model's own reply would confirm only that the model is self-consistent, which
    a fabricating model also is.

    The anchor is still recorded: an operator comparing ``21%`` against the page
    in front of them is doing exactly the check the machine cannot, and taking
    the anchor away would remove the one thing that makes that quick. What is
    withheld is the VERDICT -- the outcome is ``UNANCHORED``, because no
    independent check ran.

    This is a floor, not a ceiling. When a vision transcription stage lands, that
    path calls :func:`evaluate_anchor` like the text lane and earns ``ANCHORED``
    through the real check, with no change to any logic here.

    Args:
        field: Name of the draft field.
        anchor: The printed form the reader claims to have read.
        origin: How the value was obtained.
        note: Additional operator-facing explanation.

    Returns:
        An ``UNANCHORED`` envelope carrying the anchor and flagged self-reported.
    """
    explanation = (
        "the reader asserted this anchor about its own output and no independent transcription "
        "exists to check it against, so the anchor is recorded but not verified"
    )
    return FieldProvenance(
        field=field,
        origin=origin,
        grounding=FieldGroundingOutcome.UNANCHORED,
        anchor=anchor,
        anchor_self_reported=True,
        note=f"{note}; {explanation}" if note else explanation,
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


# Draft fields copied directly from a structured record. The table lives beside
# the structured anchor constructor so a newly recovered field cannot bypass
# the same provenance boundary as every other structured value.
_STRUCTURED_ENVELOPE_FIELDS: Final = (
    "supplier_tax_id",
    "supplier_name",
    "supplier_postal_code",
    "customer_tax_id",
    "customer_name",
    "customer_postal_code",
    "invoice_number",
    "invoice_series",
    "invoice_date",
    "currency",
    "taxable_base",
    "iva_amount",
    "grand_total",
    "recargo_amount",
    "regime_legend",
)

_STRUCTURED_ELEMENT_PATHS: Final[dict[str, dict[DocumentShape, str]]] = {
    "supplier_postal_code": {
        DocumentShape.XML_FACTURAE: "SellerParty/AddressInSpain/PostCode",
        DocumentShape.XML_UBL: "cac:AccountingSupplierParty/cac:PostalAddress/cbc:PostalZone",
        DocumentShape.XML_CII: "ram:SellerTradeParty/ram:PostalTradeAddress/ram:PostcodeCode",
    },
    "supplier_country_code": {
        DocumentShape.XML_FACTURAE: "SellerParty/AddressInSpain/CountryCode",
        DocumentShape.XML_UBL: ("cac:AccountingSupplierParty/cac:PostalAddress/cac:Country/cbc:IdentificationCode"),
        DocumentShape.XML_CII: "ram:SellerTradeParty/ram:PostalTradeAddress/ram:CountryID",
    },
    "customer_country_code": {
        DocumentShape.XML_FACTURAE: "BuyerParty/AddressInSpain/CountryCode",
        DocumentShape.XML_UBL: ("cac:AccountingCustomerParty/cac:PostalAddress/cac:Country/cbc:IdentificationCode"),
        DocumentShape.XML_CII: "ram:BuyerTradeParty/ram:PostalTradeAddress/ram:CountryID",
    },
    "customer_postal_code": {
        DocumentShape.XML_FACTURAE: "BuyerParty/AddressInSpain/PostCode",
        DocumentShape.XML_UBL: "cac:AccountingCustomerParty/cac:PostalAddress/cbc:PostalZone",
        DocumentShape.XML_CII: "ram:BuyerTradeParty/ram:PostalTradeAddress/ram:PostcodeCode",
    },
}

_STATED_COUNTRY_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("supplier_stated_country_code", "supplier_country_code"),
    ("customer_stated_country_code", "customer_country_code"),
)


def _structured_element_path(field: str, *, shape: DocumentShape) -> str:
    """Return where in the record *field* was read from, for the operator's note."""
    known = _STRUCTURED_ELEMENT_PATHS.get(field, {}).get(shape)
    return known if known is not None else f"the {shape.value} record's {field}"


def structured_provenance(
    *,
    parsed: ParsedEInvoice,
    evidence: EvidenceInput,
    derived: Mapping[str, tuple[str, str] | None],
) -> tuple[FieldProvenance, ...]:
    """Return one provenance envelope per value the structured record stated."""
    del evidence
    source_text = parsed.record_text
    envelopes: list[FieldProvenance] = []
    for field in _STRUCTURED_ENVELOPE_FIELDS:
        value = getattr(parsed, field, None)
        if value is None:
            continue
        envelopes.append(
            ground_structured_value(
                field=field,
                value=value,
                element_path=_structured_element_path(field, shape=parsed.shape),
                source_text=source_text,
            ),
        )
    for stated_field, resolved_field in _STATED_COUNTRY_FIELDS:
        stated = getattr(parsed, resolved_field, None)
        if stated is None or not stated.strip():
            continue
        envelopes.append(
            ground_structured_value(
                field=stated_field,
                value=stated,
                element_path=_structured_element_path(resolved_field, shape=parsed.shape),
                source_text=source_text,
            ),
        )
    for field, pair in derived.items():
        if pair is None:
            continue
        value, stated = pair
        envelopes.append(
            ground_structured_value(
                field=field,
                value=value,
                anchor=stated,
                derive=country_code_for_stated_country_code,
                element_path=_structured_element_path(field, shape=parsed.shape),
                source_text=source_text,
            ),
        )
    return tuple(envelopes)


def resolved_country_code(stated: str | None) -> tuple[str, str] | None:
    """Return a record country as ``(resolved alpha-2, stated form)``."""
    resolved = country_code_for_stated_country_code(stated)
    if resolved is None or stated is None:
        return None
    return resolved, stated


def country_code_value(pair: tuple[str, str] | None) -> str | None:
    """Return the resolved half of a country-code pair, or nothing."""
    return None if pair is None else pair[0]


def stated_country_code(stated: str | None) -> str | None:
    """Return the record's non-blank country token verbatim."""
    return None if stated is None or not stated.strip() else stated
