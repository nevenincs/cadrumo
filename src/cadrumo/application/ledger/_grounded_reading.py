"""Upgrade a read draft's unverified claims into checked provenance.

The seam between the reading stage and the grounding stage, and the module that
makes the anchor check reachable at all.

A reader returns a draft whose every :class:`FieldProvenance` envelope is
``UNANCHORED`` while carrying the anchor the model reported. That is a deliberate
under-claim on the reader's part rather than a placeholder: the model REPORTING a
printed form is a claim about the document, and the check that would turn it into
a fact needs the transcription the reading stage does not hold. A check that did
not run did not pass.

This module holds the transcription, so it runs the check. Every envelope is
re-evaluated against the document text, and the outcome the reader could not
justify becomes one it can: ``ANCHORED`` where the printed form is really there
and parses to the value, ``CONTRADICTED`` where it is there and parses to
something else, ``UNANCHORED`` where it is not there at all. **That upgrade is
what the wiring buys** -- before it, the envelopes were honest and empty.

The vision lane is deliberately NOT upgraded here. It produces no independent
transcription, so its anchor is self-reported by the same model that produced the
value and there is nothing to check it against; those envelopes keep the
``anchor_self_reported`` flag and their unverified outcome. Passing a
model-produced text off as a transcription would make the check verify a model
against itself, which is the failure this whole apparatus is arranged against.

Two further stages run here because they need the whole draft rather than one
field: the arithmetic identities
(:func:`~application.ledger.closure_findings`) and, when the caller supplies the
filer's own identifier, counterparty role resolution.

See Also:
    :func:`~application.ledger.evaluate_anchor`
        The per-field check this module applies across a draft.
    :func:`~application.ledger.closure_findings`
        The arithmetic identities appended as discrepancies.
    :func:`~application.ledger.resolve_counterparty_identity`
        Role resolution, run only when the filer's identity is known.
"""

from __future__ import annotations

from decimal import Decimal

from ...core import FieldGroundingOutcome, FieldOrigin
from ._closure_findings import closure_findings
from ._document_transcription import DocumentTranscription
from ._evidence_draft import DraftDiscrepancyFinding, FieldProvenance, InvoiceDraft
from ._grounding_anchor import evaluate_anchor
from ._identity_roles import IdentityCandidate, resolve_counterparty_identity

__all__ = [
    "GROUNDABLE_ORIGINS",
    "ground_draft_against_transcription",
    "verified_provenance",
]

GROUNDABLE_ORIGINS = frozenset({FieldOrigin.TEXT_LAYER, FieldOrigin.EXACT_STRUCTURED, FieldOrigin.TABULAR_MAPPED})
"""Origins whose anchors can be checked against an independent transcription.

Derived as a named set rather than an inline test so the exclusion is auditable.
``VISION`` is absent because that path produces no transcription -- its anchor is
the model's own claim about its own output, and checking it against the model's
reply would confirm self-consistency rather than evidence. ``OPERATOR`` is absent
because an operator-supplied value is not a reading of the document at all.
"""


def verified_provenance(
    *,
    draft: InvoiceDraft,
    transcription: DocumentTranscription,
) -> tuple[FieldProvenance, ...]:
    """Return *draft*'s envelopes with every groundable anchor actually checked.

    Args:
        draft: The read draft, whose envelopes carry reader-reported anchors.
        transcription: The independently produced document text.

    Returns:
        The envelopes, in their original order, each either upgraded by the
        anchor check or passed through unchanged where no check applies.
    """
    upgraded: list[FieldProvenance] = []
    for envelope in draft.provenance:
        upgraded.append(_verified_envelope(envelope=envelope, draft=draft, transcription=transcription))
    return tuple(upgraded)


def _verified_envelope(
    *,
    envelope: FieldProvenance,
    draft: InvoiceDraft,
    transcription: DocumentTranscription,
) -> FieldProvenance:
    """Return one envelope with its anchor checked, or unchanged where it cannot be."""
    if envelope.anchor_self_reported or envelope.origin not in GROUNDABLE_ORIGINS:
        # Nothing independent to check against. The envelope already says so.
        return envelope
    if envelope.anchor is None:
        # No claim to verify. Left exactly as the reader left it rather than
        # restamped, so "the reader reported no printed form" stays legible.
        return envelope
    if envelope.grounding is FieldGroundingOutcome.AMBIGUOUS:
        # An ambiguity is a decision about competing readings, not a claim about
        # one printed form; re-running a single-anchor check would discard the
        # candidates that justify it.
        return envelope

    value = getattr(draft, envelope.field, None)
    if not isinstance(value, (Decimal, str)):
        # A field the anchor check has no comparable value for -- a tuple field,
        # or one the reader dropped between recording the envelope and building
        # the draft. Passed through rather than guessed at.
        return envelope

    evaluation = evaluate_anchor(value=value, anchor=envelope.anchor, transcription=transcription)
    return envelope.model_copy(
        update={
            "grounding": evaluation.outcome,
            "anchor": envelope.anchor if evaluation.anchor_found else None,
            "note": evaluation.detail,
        },
    )


def ground_draft_against_transcription(
    *,
    draft: InvoiceDraft,
    transcription: DocumentTranscription,
    taxpayer_tax_id: str | None = None,
) -> InvoiceDraft:
    """Return *draft* with its provenance verified and its findings attached.

    The single entry point the router uses after a reader returns. Deterministic
    and side-effect free: it reads the draft and the transcription and returns a
    new draft.

    Args:
        draft: The draft a reader produced.
        transcription: The independently produced document text the anchors are
            checked against.
        taxpayer_tax_id: The filer's own identifier, when known. Supplied only
            so it can be EXCLUDED from counterparty candidacy; role resolution
            is skipped entirely when it is unknown, because resolving without it
            would let the filer's own identifier win the counterparty role.

    Returns:
        A new draft carrying verified envelopes and every deterministic finding.
    """
    envelopes = verified_provenance(draft=draft, transcription=transcription)
    findings: list[DraftDiscrepancyFinding] = list(draft.discrepancies)
    findings.extend(closure_findings(draft))

    if taxpayer_tax_id is not None:
        resolution = resolve_counterparty_identity(
            field="supplier_tax_id",
            candidates=_identity_candidates(draft=draft, envelopes=envelopes),
            taxpayer_tax_id=taxpayer_tax_id,
            origin=_reading_origin(envelopes),
        )
        findings.extend(resolution.findings)
        envelopes = _with_replaced_envelope(envelopes, resolution.provenance)

    return draft.model_copy(
        update={
            "provenance": envelopes,
            "discrepancies": tuple(findings),
        },
    )


def _identity_candidates(
    *,
    draft: InvoiceDraft,
    envelopes: tuple[FieldProvenance, ...],
) -> tuple[IdentityCandidate, ...]:
    """Return the tax identifiers the draft carries, with their anchors.

    Only identifiers the reader actually proposed. This deliberately does NOT
    re-scan the transcription for every checksum-valid token: that scan is the
    defect this campaign removed, and reintroducing it here under a different
    name would restore first-match selection at the exact seam that was fixed.

    **No role evidence is supplied here, and that is the point.** The candidates
    carry none, because nothing on this path has any: the reader reports a value
    under a field name, and the field name is a restatement of the reader's own
    assignment rather than anything the document says about the party.

    This previously passed ``f"the reader assigned this identifier to {field}"``,
    which is always truthy, so the resolver's positive-role-evidence filter
    accepted every candidate and could never exclude one. The measured defect
    that filter exists to stop -- the true supplier's identifier failing its
    control character, one unrelated but valid identifier left standing, and the
    survivor grounded with full confidence -- was live again through it, and the
    note it emitted read as positive evidence while saying only that the reader
    had assigned the field. A guard that cannot refuse is worse than no guard,
    because its output is trusted.

    With nothing supplied, an identity that cannot be evidenced stays
    unresolved, which is the direction that fails safe: an absent counterparty
    refuses as a missing field naming the override that supplies it, while a
    wrong one reaches the counterparty totals AEAT reconciles against the other
    party's own filing. Real evidence -- the transcription context that assigns
    a value to a party role -- is a payload field the reading stage does not yet
    carry; when it does, it arrives here and the filter has something true to
    test.
    """
    anchors = {envelope.field: envelope.anchor for envelope in envelopes}
    candidates: list[IdentityCandidate] = []
    for field in ("supplier_tax_id", "customer_tax_id"):
        value = getattr(draft, field, None)
        if not isinstance(value, str) or not value.strip():
            continue
        candidates.append(
            IdentityCandidate(
                value=value,
                anchor=anchors.get(field),
            ),
        )
    return tuple(candidates)


def _reading_origin(envelopes: tuple[FieldProvenance, ...]) -> FieldOrigin:
    """Return the origin the reading path stamped, defaulting conservatively."""
    for envelope in envelopes:
        return envelope.origin
    return FieldOrigin.TEXT_LAYER


def _with_replaced_envelope(
    envelopes: tuple[FieldProvenance, ...],
    replacement: FieldProvenance,
) -> tuple[FieldProvenance, ...]:
    """Return *envelopes* with the one naming ``replacement.field`` swapped in.

    Appended when absent, so a role resolution is never silently dropped for a
    field the reader recorded no envelope against.
    """
    replaced = tuple(replacement if e.field == replacement.field else e for e in envelopes)
    if any(e.field == replacement.field for e in envelopes):
        return replaced
    return (*envelopes, replacement)
