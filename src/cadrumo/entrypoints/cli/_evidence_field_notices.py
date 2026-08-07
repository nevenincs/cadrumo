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
    transcription. Something was read that is not there.
``no_anchor``
    The reader offered nothing to point at. Different from the above: there is
    no claim to check, rather than a claim that failed.
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

from ...application.ledger import FieldProvenance
from ...core import FieldGroundingOutcome
from ...core.i18n import tr
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
    seen = envelope.anchor or ""
    return Notice(
        severity=NoticeSeverity.INFO,
        code="ledger.evidence.field.anchor_not_found",
        message=tr(
            "cli.app.ledger.evidence.field_anchor_not_found",
            field=envelope.field,
            anchor=seen,
            default=(
                f"{envelope.field}: the reader points at {seen!r}, which does not occur in the "
                "document's transcription. A normalised value can fail this search legitimately, so "
                "check the field rather than assuming it was corroborated."
            ),
        ),
        context={
            "field": envelope.field,
            "outcome": envelope.grounding.value,
            "origin": envelope.origin.value,
            "anchor": seen,
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
        elif envelope.anchor:
            notices.append(_anchor_not_found_notice(envelope))
        else:
            notices.append(_no_anchor_notice(envelope))
    return notices
