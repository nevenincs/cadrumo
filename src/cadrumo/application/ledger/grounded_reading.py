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
    :func:`~application.ledger.grounding_anchor.evaluate_anchor`
        The per-field check this module applies across a draft.
    :func:`~application.ledger.closure_findings`
        The arithmetic identities appended as discrepancies.
    :func:`~application.ledger.identity_roles.resolve_counterparty_identity`
        Role resolution, run only when the filer's identity is known.
"""

from __future__ import annotations

from decimal import Decimal

from ...core.field_grounding import FieldGroundingOutcome
from ...core.field_origin import FieldOrigin
from .deterministic_findings import deterministic_findings
from .document_direction import (
    DirectionDerivationOutcome,
    InvoiceKindDerivation,
    derive_invoice_kind_from_filer_role,
)
from .document_transcription import DocumentTranscription
from .evidence_draft import DraftDiscrepancyFinding, FieldProvenance, InvoiceDraft
from .grounding_anchor import evaluate_anchor, printed_excerpt_occurs, refused_anchor_of
from .identity_roles import IdentityCandidate, resolve_counterparty_identity
from .party_attribution import stamp_unverified_party_attribution
from .party_colocation import (
    PartyAttributionOutcome,
    party_attribution_findings,
    resolve_party_attribution_by_colocation,
)

__all__ = [
    "GROUNDABLE_ORIGINS",
    "ground_draft_against_transcription",
    "verified_provenance",
]

GROUNDABLE_ORIGINS = frozenset(
    {FieldOrigin.TEXT_LAYER, FieldOrigin.VISION, FieldOrigin.EXACT_STRUCTURED, FieldOrigin.TABULAR_MAPPED},
)
"""Origins whose anchors can be checked against an independent transcription.

Derived as a named set rather than an inline test so the exclusion is auditable.
``VISION`` is present because the vision lane now transcribes and interprets in
SEPARATE calls: stage one turns pixels into a transcription and reads no fields,
stage two proposes values from that text, and the anchor check runs against
stage one's output. That is the same independence the text lane has -- a
different reader produced the text the anchor is searched in -- so excluding it
would now withhold a verdict a real check had earned. It was excluded while one
call went image-to-fields, because the only thing an anchor could then be
compared against was the reply that asserted it, and a fabricating model is
self-consistent. ``OPERATOR`` is absent
because an operator-supplied value is not a reading of the document at all.
``DERIVED`` is absent for a sharper reason than either: a derived value was never
printed, so there is no anchor to check and the envelope refuses to carry one.
What makes it auditable is its recorded input set, and those inputs are anchored
in their own right by whichever origin read them.
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
        anchor check or passed through unchanged where no check applies, and
        each per-party address envelope additionally stamped with whether
        anything verified the party it was filed under.
    """
    upgraded: list[FieldProvenance] = []
    for envelope in draft.provenance:
        upgraded.append(_verified_envelope(envelope=envelope, draft=draft, transcription=transcription))
    # Applied AFTER the anchor check, on its output rather than beside it,
    # because the two answer different questions and the second must not read as
    # a consequence of the first: an anchor check that passed says the value is
    # on the page, and says nothing whatever about whose it is.
    #
    # Co-location is asked BEFORE the stamp rather than after, so a value the
    # document itself attributes is never stamped in the first place. Stamping
    # and then clearing would leave a window in which the draft asserts an
    # unverified attribution it can in fact verify.
    resolution = resolve_party_attribution_by_colocation(draft=draft, transcription=transcription)
    return stamp_unverified_party_attribution(
        tuple(upgraded),
        attributed_fields=frozenset(
            field for field, outcome in resolution.outcomes.items() if outcome is PartyAttributionOutcome.ATTRIBUTED
        ),
    )


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
            # The other half of the distinction the early return above protects.
            # That branch keeps "the reader reported no printed form" legible;
            # clearing the anchor here without recording the refusal would make
            # a form the reader DID offer arrive looking exactly like one it
            # never offered, and the operator surface would then read the
            # refusal out as an absence.
            "refused_anchor": refused_anchor_of(envelope.anchor, evaluation),
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
    # Through the shared list rather than naming the checks here, so a check
    # added later cannot reach this path and miss the structured reader's.
    findings.extend(deterministic_findings(draft))
    # Named here rather than in that shared list because it is the one check
    # that needs the TRANSCRIPTION as well as the draft: co-location is a fact
    # about where a value is printed, which a draft alone cannot answer. The
    # structured reader does not reach it and does not need to -- its element
    # paths already name the party.
    findings.extend(
        party_attribution_findings(
            resolve_party_attribution_by_colocation(draft=draft, transcription=transcription),
        ),
    )

    if taxpayer_tax_id is not None:
        resolution = resolve_counterparty_identity(
            field="supplier_tax_id",
            candidates=_identity_candidates(draft=draft, envelopes=envelopes, transcription=transcription),
            taxpayer_tax_id=taxpayer_tax_id,
            origin=_reading_origin(envelopes),
        )
        findings.extend(resolution.findings)
        envelopes = _with_replaced_envelope(envelopes, resolution.provenance)

    # Derived LAST, from the draft the reader proposed rather than from the
    # envelopes above, because it asks a question about the document's layout and
    # not about any one value's grounding. It raises no finding here: which side
    # the document places the filer on is a suggestion until the operator states
    # a direction, and the two are compared at the confirm boundary where both
    # are in hand.
    derivation = derive_invoice_kind_from_filer_role(
        draft=draft,
        transcription=transcription,
        taxpayer_tax_id=taxpayer_tax_id,
    )
    envelopes = _with_replaced_envelope(envelopes, _suggested_kind_envelope(derivation))

    return draft.model_copy(
        update={
            "provenance": envelopes,
            "discrepancies": tuple(findings),
            "suggested_kind": derivation.kind,
        },
    )


def _suggested_kind_envelope(derivation: InvoiceKindDerivation) -> FieldProvenance:
    """Return the provenance envelope recording how direction was derived.

    Stamped whatever the outcome, including the ones that settled nothing. An
    envelope only for the settled case would leave the review surface printing an
    empty basis beside an empty suggestion, which reads as "the question was
    never asked" -- and the commonest reason it settles nothing (the document
    states no usable pair of party headings) is a fact about the document the
    operator benefits from seeing.

    ``DERIVED`` origin carries two obligations the envelope contract enforces: it
    may not claim ``ANCHORED``, because no printed form of "issued" exists on the
    page to anchor, and it must name the inputs it was concluded from. Both are
    honoured rather than worked around. The settled case claims ``RECONCILED``
    because the corroborating check -- containment inside a party's own block --
    does not consult the value it corroborates.
    """
    return FieldProvenance(
        field="suggested_kind",
        origin=FieldOrigin.DERIVED,
        grounding=(
            FieldGroundingOutcome.RECONCILED
            if derivation.outcome is DirectionDerivationOutcome.DERIVED
            else FieldGroundingOutcome.UNANCHORED
        ),
        derived_from=("supplier_tax_id", "customer_tax_id"),
        note=derivation.basis,
    )


def _identity_candidates(
    *,
    draft: InvoiceDraft,
    envelopes: tuple[FieldProvenance, ...],
    transcription: DocumentTranscription,
) -> tuple[IdentityCandidate, ...]:
    """Return the tax identifiers the draft carries, with their anchors and role evidence.

    Only identifiers the reader actually proposed. This deliberately does NOT
    re-scan the transcription for every checksum-valid token: that scan is the
    defect this campaign removed, and reintroducing it here under a different
    name would restore first-match selection at the exact seam that was fixed.

    **Role evidence is admitted only after the document is asked.** The reader
    reports, per identity field, the printed heading or label that assigns the
    identifier to a party. That is a claim about the document, exactly like an
    anchor, so it is checked against the transcription with
    :func:`~application.ledger.grounding_anchor.printed_excerpt_occurs` before it is allowed to
    influence anything. An excerpt the document does not print is dropped, and
    the candidate carries no role evidence -- which fails safe, because an
    unevidenced identity does not resolve.

    That check is what separates this from what it replaced. The reading stage
    once synthesised ``f"the reader assigned this identifier to {field}"``,
    which is always truthy and unfalsifiable, so the resolver's
    positive-role-evidence filter accepted every candidate and could never
    exclude one. The measured defect that filter exists to stop -- the true
    supplier's identifier failing its control character, one unrelated but valid
    identifier left standing, and the survivor grounded with full confidence --
    was live through it, under a note that read as positive evidence while
    saying only that the reader had assigned the field.

    The difference is not that the text is longer. It is that this text can be
    WRONG: a model that invents a heading the document does not carry loses its
    role evidence here and its identity stays unresolved, while the synthesised
    string was true by construction for every candidate on every document.
    """
    anchors = {envelope.field: envelope.anchor for envelope in envelopes}
    role_evidence = {envelope.field: envelope.role_evidence for envelope in envelopes}
    candidates: list[IdentityCandidate] = []
    for field in ("supplier_tax_id", "customer_tax_id"):
        value = getattr(draft, field, None)
        if not isinstance(value, str) or not value.strip():
            continue
        claimed = role_evidence.get(field)
        candidates.append(
            IdentityCandidate(
                value=value,
                anchor=anchors.get(field),
                role_evidence=(
                    claimed if claimed and printed_excerpt_occurs(claimed, transcription=transcription) else ""
                ),
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
