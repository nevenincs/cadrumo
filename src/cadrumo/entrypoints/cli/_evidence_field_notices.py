"""Per-field degradation advisories for an extracted invoice draft.

The reading path does not raise when it reads a document badly. It returns a
draft with fewer fields, which on its own is indistinguishable from a document
that genuinely carries fewer fields — so "read this layout poorly" and "read this
layout fine" arrive at the operator looking identical. These notices are that
distinction: one per field whose value did not survive its check, naming **what
was seen** and **why it was not accepted**.

Each shape is a different operator action, so each carries its own code rather
than one flattened "field not verified":

``contradicted``
    An independent check disagreed with the value. The document says something
    else, and the disagreeing figure is itself evidence.
``ambiguous``
    Several readings competed and none was decidable. The operator picks.
``anchor_not_found``
    The reader pointed at a printed form that does not occur in the document's
    transcription. Something was read that is not there. Selected on the
    envelope's REFUSED anchor alone: the grounding stage clears an anchor it
    could not locate, so the refused form is the only surviving trace that
    anything was offered at all.
``anchor_uncorroborated``
    The reader pointed at a printed form the check did NOT report missing, and
    the field still did not come through. Whatever is unsettled here is not the
    printed form — the commonest case is an identifier that verified while
    nothing on the page assigns it to a party. Reported apart from the above
    because telling this operator the form "does not occur in the document"
    sends them to re-read a page that says exactly what the reader claimed.
``no_anchor``
    The reader offered nothing to point at. Different from the above: there is
    no claim to check, rather than a claim that failed — a reader limitation
    against a possible misread or the wrong document, which are different
    operator actions.
``anchor_self_reported``
    The anchor was asserted by the same reader that produced the value. **Not a
    failed check — an absent one.** The vision lane reads image to fields in one
    call, so matching its anchor against its own reply would confirm only that
    the model is self-consistent, which a fabricating model also is.

That last distinction is the one that must not be flattened. A text-lane
``UNANCHORED`` is a check that RAN against an independently produced
transcription and did not pass; a self-reported anchor is a check that could not
run at all. Collapsing them would tell an operator the same thing about two
different strengths of evidence.

Severity follows what the check established, not how much is missing. A
disagreement and an undecided ambiguity are warnings, because something is
positively wrong or unresolved. A missing verbatim match is informational: a
normalised value — a date rewritten to ISO form, a tax id stripped of its
separators — legitimately fails a verbatim search, and warning on every one of
those would train an operator to ignore the channel.

See Also:
    :class:`~core.FieldGroundingOutcome`
        The closed set of verification outcomes these notices report.
    :class:`~core.json_contract.Notice`
        The only sanctioned channel for an operator-facing diagnostic.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...application.ledger.invoice_draft_records import FieldProvenance
from ...core.field_grounding import FieldGroundingOutcome
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity

__all__ = ["DEGRADED_GROUNDING_OUTCOMES", "field_degradation_notices"]

#: The outcomes that mean a field did not come through its check intact.
#: Derived by excluding the two that did, so a new member added to the
#: vocabulary is reported by default rather than silently ignored.
DEGRADED_GROUNDING_OUTCOMES: frozenset[FieldGroundingOutcome] = frozenset(FieldGroundingOutcome) - {
    FieldGroundingOutcome.RECONCILED,
    FieldGroundingOutcome.ANCHORED,
}


def _contradicted_notice(envelope: FieldProvenance) -> Notice:
    seen = envelope.anchor or ""
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="ledger.evidence.field.contradicted",
        message=tr(
            "cli.app.ledger.evidence.field_contradicted",
            field=envelope.field,
            anchor=seen,
            detail=envelope.note,
            default=(
                f"{envelope.field}: the document reads {seen!r}, which does not agree with the value "
                f"recorded for this field. {envelope.note}"
            ),
        ),
        context={
            "field": envelope.field,
            "outcome": envelope.grounding.value,
            "origin": envelope.origin.value,
            "anchor": seen,
            "detail": envelope.note,
        },
    )


def _ambiguous_notice(envelope: FieldProvenance) -> Notice:
    competing = ", ".join(repr(candidate.value) for candidate in envelope.candidates)
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="ledger.evidence.field.ambiguous",
        message=tr(
            "cli.app.ledger.evidence.field_ambiguous",
            field=envelope.field,
            candidates=competing,
            default=(
                f"{envelope.field}: several readings competed and none could be decided between "
                f"({competing}). Choose one rather than accepting the draft as read."
            ),
        ),
        context={
            "field": envelope.field,
            "outcome": envelope.grounding.value,
            "origin": envelope.origin.value,
            "candidates": competing,
            "candidate_count": str(len(envelope.candidates)),
        },
    )


def _self_reported_notice(envelope: FieldProvenance) -> Notice:
    seen = envelope.anchor or ""
    return Notice(
        severity=NoticeSeverity.INFO,
        code="ledger.evidence.field.anchor_self_reported",
        message=tr(
            "cli.app.ledger.evidence.field_anchor_self_reported",
            field=envelope.field,
            anchor=seen,
            default=(
                f"{envelope.field}: the reader reports having read this from {seen!r}, but that claim "
                "came from the same reader that produced the value, so nothing independent has "
                "confirmed it."
            ),
        ),
        context={
            "field": envelope.field,
            "outcome": envelope.grounding.value,
            "origin": envelope.origin.value,
            "anchor": seen,
            "anchor_self_reported": "true",
        },
    )


def _anchor_not_found_notice(envelope: FieldProvenance) -> Notice:
    # The refused form, and only it. The selection below reaches this notice
    # solely on a recorded refusal, so reading the carried anchor as a fallback
    # would be a dead branch that quietly re-admits the confusion: a carried
    # anchor means the check did NOT report the form missing.
    seen = envelope.refused_anchor or ""
    return Notice(
        severity=NoticeSeverity.INFO,
        code="ledger.evidence.field.anchor_not_found",
        message=tr(
            "cli.app.ledger.evidence.field_anchor_not_found",
            field=envelope.field,
            anchor=seen,
            detail=envelope.note,
            default=(
                f"{envelope.field}: the reader points at {seen!r}, which does not occur in the "
                "document's transcription. A normalised value can fail this search legitimately, so "
                f"check the field rather than assuming it was corroborated. {envelope.note}"
            ),
        ),
        context={
            "field": envelope.field,
            "outcome": envelope.grounding.value,
            "origin": envelope.origin.value,
            "anchor": seen,
            # Carried rather than dropped: the check already computed WHY it
            # refused, and an operator deciding between a misread and the wrong
            # document is deciding on exactly that sentence.
            "detail": envelope.note,
            "anchor_self_reported": "false",
        },
    )


def _uncorroborated_anchor_notice(envelope: FieldProvenance) -> Notice:
    seen = envelope.anchor or ""
    return Notice(
        severity=NoticeSeverity.INFO,
        code="ledger.evidence.field.anchor_uncorroborated",
        message=tr(
            "cli.app.ledger.evidence.field_anchor_uncorroborated",
            field=envelope.field,
            anchor=seen,
            detail=envelope.note,
            default=(
                f"{envelope.field}: the reader points at {seen!r}, and nothing found that form missing "
                "from the document. The value is still not corroborated, so what is unsettled is "
                f"something other than the printed form. {envelope.note}"
            ),
        ),
        context={
            "field": envelope.field,
            "outcome": envelope.grounding.value,
            "origin": envelope.origin.value,
            "anchor": seen,
            # The only place the specific reason exists. This shape is reached by
            # producers that failed on DIFFERENT questions -- a role nothing on
            # the page assigns, a check that has not run -- and the message can
            # only say truthfully that the printed form is not the problem.
            "detail": envelope.note,
            "anchor_self_reported": "false",
        },
    )


def _no_anchor_notice(envelope: FieldProvenance) -> Notice:
    return Notice(
        severity=NoticeSeverity.INFO,
        code="ledger.evidence.field.no_anchor",
        message=tr(
            "cli.app.ledger.evidence.field_no_anchor",
            field=envelope.field,
            default=(
                f"{envelope.field}: the reader offered nothing in the document to point at, so there "
                "is no printed form to check this value against."
            ),
        ),
        context={
            "field": envelope.field,
            "outcome": envelope.grounding.value,
            "origin": envelope.origin.value,
            "anchor_self_reported": "false",
        },
    )


def field_degradation_notices(provenance: Sequence[FieldProvenance]) -> list[Notice]:
    """Return one notice per field that did not come through its check intact.

    A field whose value was reconciled or anchored produces nothing: the channel
    reports degradation, not inventory. Ordering follows the provenance sequence,
    so the notices read in the order the draft's fields were assembled.

    Args:
        provenance: The draft's per-field provenance envelopes.

    Returns:
        The notices, in provenance order. Empty when every field came through
        its check.
    """
    notices: list[Notice] = []
    for envelope in provenance:
        if envelope.grounding not in DEGRADED_GROUNDING_OUTCOMES:
            continue
        if envelope.grounding is FieldGroundingOutcome.CONTRADICTED:
            notices.append(_contradicted_notice(envelope))
        elif envelope.grounding is FieldGroundingOutcome.AMBIGUOUS:
            notices.append(_ambiguous_notice(envelope))
        elif envelope.anchor_self_reported:
            # Checked LAST among the unanchored shapes on purpose: the flag says
            # the check could not run, which is only meaningful once the outcomes
            # that mean a check ran and failed are already handled.
            notices.append(_self_reported_notice(envelope))
        elif envelope.refused_anchor:
            # A recorded refusal, and nothing else, reaches the not-found shape.
            # The grounding stage clears the anchor it could not locate, so the
            # refusal is the only surviving trace that a form was offered; without
            # this test a refused claim falls through to the no-anchor branch and
            # the operator is told the reader offered nothing, which is
            # affirmatively false about a reader that offered a printed form.
            notices.append(_anchor_not_found_notice(envelope))
        elif envelope.anchor:
            # A CARRIED anchor under a degraded outcome is the third state, and
            # routing it to the not-found shape told the operator the form does
            # not occur in the document when the check had located it. Whatever
            # left this field unsettled, it was not the printed form.
            notices.append(_uncorroborated_anchor_notice(envelope))
        else:
            notices.append(_no_anchor_notice(envelope))
    return notices
