"""The blocking half of the human review gate: what cannot be confirmed blind.

A draft is a proposal. Turning one into an :class:`~domain.invoices.Invoice` is
the moment a machine reading becomes a filing-grade fact, and this module is the
only thing standing between the two. It answers one question --- *which of this
draft's problems must a human answer before it may be confirmed at all* --- and
refuses the confirm until each named one carries an explicit, per-finding answer.

**There is no bulk resolution and there will not be one.** Not a
``--confirm-all``, not a ``--force``, not an "accept remaining" that resolves the
set in one keystroke. The entire value of the gate is the per-document attention
it forces; a flag that clears every blocker at once re-creates exactly the rubber
stamp the gate exists to remove, and it would be asked for the first time someone
has a hundred documents waiting. Every resolution names ONE blocker by its id.

**Completeness is by construction, not by diligence.**
:data:`BLOCKING_REASON_BY_DISCREPANCY_KIND` maps every member of
:class:`~core.DraftDiscrepancyKind` to a
:class:`~core.ConfirmationBlockReason`, and the module refuses to import if a
member is missing. A new deterministic check therefore cannot land as a finding
that quietly fails to block --- the tree stops instead. That is the opposite of a
hand-listed set, which passes silently while covering half the axis.

The second blocker source is the grounding pass rather than the discrepancy
checks: a counterparty identifier whose reading was
:attr:`~core.FieldGroundingOutcome.AMBIGUOUS` produced competing candidates and
no decision. That is not an arithmetic failure and raises no
:class:`~application.ledger.evidence_draft.DraftDiscrepancyFinding`, but confirming it picks one
real taxpayer's identifier over another's by accident.

See Also:
    :class:`~application.ledger.evidence_draft.InvoiceDraft`
        The proposal this gate guards.
    :func:`~application.ledger.closure_findings`
        Where the arithmetic blockers come from.
    :class:`~application.ledger.confirmation_record.InvoiceConfirmationRecord`
        What the resolutions are persisted into once the confirm succeeds.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Self

from pydantic import BaseModel, Field, model_validator

from ...core import (
    ConfirmationBlockReason,
    DraftDiscrepancyKind,
    FieldGroundingOutcome,
    FindingResolutionAction,
)
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import content_hash_hex
from .evidence_draft import FieldAmbiguityCandidate, InvoiceDraft
from .preconditions import LedgerPreconditionCondition, LedgerPreconditionErrorMixin, ledger_no_recovery_verdict

__all__ = [
    "BLOCKING_REASON_BY_DISCREPANCY_KIND",
    "IDENTITY_FIELDS",
    "ConfirmationBlockedError",
    "ConfirmationBlocker",
    "FindingResolution",
    "confirmation_blockers",
    "resolved_blockers",
]

BLOCKING_REASON_BY_DISCREPANCY_KIND: Mapping[DraftDiscrepancyKind, ConfirmationBlockReason] = {
    DraftDiscrepancyKind.ARITHMETIC_CLOSURE: ConfirmationBlockReason.CLOSURE_DISCREPANCY,
    DraftDiscrepancyKind.RATE_INCONSISTENT: ConfirmationBlockReason.CLOSURE_DISCREPANCY,
    DraftDiscrepancyKind.BREAKDOWN_INCONSISTENT: ConfirmationBlockReason.CLOSURE_DISCREPANCY,
    DraftDiscrepancyKind.IDENTITY_UNVERIFIED: ConfirmationBlockReason.AMBIGUOUS_IDENTITY,
    DraftDiscrepancyKind.ROLE_UNRESOLVED: ConfirmationBlockReason.UNRESOLVED_DIRECTION,
    DraftDiscrepancyKind.REGIME_CONTRADICTED: ConfirmationBlockReason.CONTRADICTED_REGIME,
    DraftDiscrepancyKind.DIRECTION_CONTRADICTED: ConfirmationBlockReason.UNRESOLVED_DIRECTION,
    DraftDiscrepancyKind.POSTAL_CODE_UNREADABLE: ConfirmationBlockReason.UNDETERMINED_ESTABLISHMENT,
    DraftDiscrepancyKind.PARTY_ATTRIBUTION_CONTRADICTED: ConfirmationBlockReason.UNDETERMINED_ESTABLISHMENT,
    DraftDiscrepancyKind.INVOICE_CLASS_UNMODELLED: ConfirmationBlockReason.UNMODELLED_INVOICE_CLASS,
    DraftDiscrepancyKind.INVOICE_CLASS_CONTRADICTED: ConfirmationBlockReason.CONTRADICTED_INVOICE_CLASS,
}
"""Which review-gate reason each deterministic check's failure raises.

Total over :class:`~core.DraftDiscrepancyKind` by construction --- the assertion
below fails the import when a member is unmapped, so a newly-landed check cannot
produce a finding that silently does not block. Every member maps to a reason
because every member names a real defect: an unmapped member would be a check
whose failure the product decided not to care about, and that decision belongs in
the check's own existence rather than hidden in this table.

A deterministic condition the product decides NOT to block on is therefore not
represented here at all. It is reported through the non-blocking advisory channel
instead -- :func:`~application.ledger.country_vocabulary_advisory` and
:func:`~application.ledger.party_attribution.party_attribution_advisory` are the two -- which the
review surface projects onto the envelope's typed notices. An exemption row in
this table would be the worse shape: the reader could no longer tell a blocking
axis from an advisory one by looking at the axis.
"""

if set(BLOCKING_REASON_BY_DISCREPANCY_KIND) != set(DraftDiscrepancyKind):
    _unmapped = ", ".join(sorted(set(DraftDiscrepancyKind) - set(BLOCKING_REASON_BY_DISCREPANCY_KIND)))
    raise RuntimeError(
        f"every DraftDiscrepancyKind must declare a ConfirmationBlockReason; unmapped: {_unmapped}",
    )

IDENTITY_FIELDS: frozenset[str] = frozenset({"supplier_tax_id", "customer_tax_id"})
"""Draft fields whose ambiguity is an ambiguous COUNTERPARTY, not a soft field.

Named rather than inlined so the exclusion is auditable. An ambiguous supplier
name is a nuisance the operator retypes; an ambiguous tax identifier selects
which real taxpayer the record names, feeds Modelo 347 per counterparty, and
drives deductibility --- so it blocks and the name does not.
"""


class ConfirmationBlockedError(LedgerPreconditionErrorMixin, CadrumoError):
    """Raised when a confirm is attempted with an unresolved blocking finding."""


class ConfirmationBlocker(BaseModel):
    """One problem a human must answer before this draft may be confirmed.

    Attributes:
        blocker_id: Clock-free, deterministic address for this blocker, derived
            from what the blocker IS. Re-reading the same document raises the
            same id, so an operator can resolve a blocker they saw in an earlier
            listing without the ids having shifted under them --- and a
            resolution can never be pointed at a blocker by position.
        reason: Which class of refusal this is.
        field: The draft field the blocker is about, or ``None`` when it is
            about a relationship between several.
        detail: Operator-facing explanation naming the figures or readings
            involved.
        candidates: The competing readings, when the blocker is an ambiguity
            the operator resolves by choosing one. Empty otherwise.
    """

    model_config = STRICT_FROZEN_CONFIG

    blocker_id: str = Field(min_length=16, max_length=16)
    reason: ConfirmationBlockReason
    field: str | None = None
    detail: str = ""
    candidates: tuple[FieldAmbiguityCandidate, ...] = ()

    @property
    def candidate_values(self) -> tuple[str, ...]:
        """Return the candidate values, for checking a choose-candidate resolution."""
        return tuple(candidate.value for candidate in self.candidates)

    @property
    def candidate_digests(self) -> tuple[str, ...]:
        """Return each candidate's value as the review surface renders it.

        The operator-facing surfaces emit every payload through the redaction
        funnel, so an ambiguous IDENTITY reaches the operator as a digest. That
        is correct and stays: the value that could not be established is exactly
        the value that must not cross an output boundary.

        It also means the value is not a token the operator can type back. This
        is the form they actually saw, so it is the form they can name.
        """
        # Imported at call time rather than module scope: this module is reached
        # by the CLI error path, and ``core.redaction`` reaches ``core.errors``
        # in turn -- the same cycle the sibling arms in this package defer.
        from ...core.redaction import redact_for_cli_output

        return tuple(redact_for_cli_output(candidate.value) for candidate in self.candidates)

    def names_a_candidate(self, token: str) -> bool:
        """Return whether *token* identifies one of this blocker's readings.

        Accepts the value or the digest the surface rendered it as. **Both are
        choices rather than assertions**, which is the property the refusal below
        exists to enforce: a digest matches only a reading the document actually
        offered, and it cannot be constructed for a value that was never a
        candidate without already holding that value.

        Accepting the digest does not weaken the check -- it makes it reachable.
        A resolution can only ever have been expressed by an operator who had the
        value in hand, which excluded every operator adjudicating from the review
        surface, where the value is redacted by design.
        """
        return token in self.candidate_values or token in self.candidate_digests


class FindingResolution(BaseModel):
    """The operator's explicit answer to exactly one named blocker.

    One resolution, one blocker, always. The id is required and is matched
    against the blockers the draft actually raises, so a resolution naming
    nothing is a refusal rather than a silent no-op --- the failure mode where an
    operator believes they answered a finding and the confirm proceeded on a
    different one entirely.

    Attributes:
        blocker_id: The blocker being answered.
        action: How it was settled.
        value: The chosen or supplied value, as printed. Required for
            ``CHOOSE_CANDIDATE`` and ``SUPPLY_VALUE``, refused for ``ATTEST``,
            which changes no figure.
        note: The operator's reason, required for ``ATTEST`` --- an attestation
            with no stated basis is a waiver wearing a resolution's shape.
    """

    model_config = STRICT_FROZEN_CONFIG

    blocker_id: str = Field(min_length=16, max_length=16)
    action: FindingResolutionAction
    value: str | None = None
    note: str = ""

    @model_validator(mode="after")
    def _the_action_determines_what_must_accompany_it(self) -> Self:
        """Refuse a resolution whose payload does not match its action.

        The three actions carry different evidentiary weight and each is
        incomplete without its own payload. Accepting an ``ATTEST`` with no note
        would record "a human waved this through" under a field name that reads
        as though they explained themselves.
        """
        if self.action is FindingResolutionAction.ATTEST:
            if self.value is not None:
                raise ValueError("an attestation states no value: it accepts the document as printed")
            if not self.note.strip():
                raise ValueError("an attestation must state why the finding is accepted")
            return self
        if self.value is None or not self.value.strip():
            raise ValueError(f"a {self.action.value} resolution must carry the value it settles the finding with")
        return self


def blocker_id(*, reason: ConfirmationBlockReason, field: str | None, detail: str) -> str:
    """Return the clock-free derived address for one blocker.

    Folds only what the blocker IS. A timestamp would make a re-read of the same
    unchanged document raise different ids, so a resolution captured from one
    listing would refuse against the next --- and the operator would learn to
    re-run and re-copy rather than to answer.
    """
    return content_hash_hex({"detail": detail, "field": field or "", "reason": reason.value})[:16]


def confirmation_blockers(draft: InvoiceDraft) -> tuple[ConfirmationBlocker, ...]:
    """Return every problem that must be answered before *draft* may be confirmed.

    Deterministic and total: the same draft always yields the same blockers with
    the same ids. An empty result means nothing blocks --- never that the
    document is correct, because a check whose terms the document did not state
    is not run at all.

    Args:
        draft: The reviewed draft, carrying the discrepancies its deterministic
            checks raised and the provenance envelopes its grounding pass wrote.

    Returns:
        Blockers in a stable order: the discrepancy findings in the order the
        checks produced them, then the ambiguous identity fields in draft-field
        declaration order.
    """
    blockers: list[ConfirmationBlocker] = []
    seen: set[str] = set()

    def _append(blocker: ConfirmationBlocker) -> None:
        if blocker.blocker_id in seen:
            return
        seen.add(blocker.blocker_id)
        blockers.append(blocker)

    for finding in draft.discrepancies:
        reason = BLOCKING_REASON_BY_DISCREPANCY_KIND[finding.kind]
        _append(
            ConfirmationBlocker(
                blocker_id=blocker_id(reason=reason, field=finding.field, detail=finding.detail),
                reason=reason,
                field=finding.field,
                detail=finding.detail,
            ),
        )

    for envelope in draft.provenance:
        if envelope.grounding is not FieldGroundingOutcome.AMBIGUOUS:
            continue
        if envelope.field not in IDENTITY_FIELDS:
            continue
        detail = envelope.note or (
            f"several readings of {envelope.field} competed and none was decidable; "
            f"confirming would select one real taxpayer's identifier over another's"
        )
        reason = ConfirmationBlockReason.AMBIGUOUS_IDENTITY
        _append(
            ConfirmationBlocker(
                blocker_id=blocker_id(reason=reason, field=envelope.field, detail=detail),
                reason=reason,
                field=envelope.field,
                detail=detail,
                candidates=envelope.candidates,
            ),
        )

    return tuple(blockers)


def resolved_blockers(
    *,
    draft: InvoiceDraft,
    resolutions: Sequence[FindingResolution] = (),
) -> tuple[ConfirmationBlocker, ...]:
    """Return *draft*'s blockers, having refused unless every one is answered.

    The single gate every confirm path passes through. It returns the blockers
    rather than a bare ``None`` so the caller persists exactly the set that was
    answered, and cannot record a different one.

    Args:
        draft: The draft being confirmed.
        resolutions: One explicit answer per blocker. Order is irrelevant;
            coverage is not.

    Returns:
        The blockers the draft raised, all of them resolved.

    Raises:
        ConfirmationBlockedError: When a blocker carries no resolution, when a
            resolution names no blocker this draft raises, when two resolutions
            answer one blocker, or when a ``CHOOSE_CANDIDATE`` names neither a
            recorded candidate's value nor the digest the surface rendered it
            as.

    A choose-candidate resolution may name its reading EITHER way, and the
    second form is what makes the ambiguity surface usable at all. An ambiguous
    identity reaches the operator through the redaction funnel, so both
    competing readings render as digests; requiring the value asked them to type
    a string the surface had deliberately withheld, and the review command's
    whole purpose for identity fields is that the operator -- who holds the
    document -- decides between the readings. They could see which was right and
    had no way to say so.

    The value is never consumed beyond this check: it attests WHICH reading was
    chosen and never becomes the record's data, so nothing downstream needed it
    to have crossed the boundary.
    """
    blockers = confirmation_blockers(draft)
    by_id = {blocker.blocker_id: blocker for blocker in blockers}

    answered: dict[str, FindingResolution] = {}
    for resolution in resolutions:
        if resolution.blocker_id not in by_id:
            known = ", ".join(sorted(by_id)) or "none"
            raise ConfirmationBlockedError(
                translated_message="errors.refused.refused_ledger_confirmation_blocked",
                context={"blocker_id": resolution.blocker_id, "known_blocker_ids": known},
                precondition_verdict=ledger_no_recovery_verdict(
                    LedgerPreconditionCondition.CONFIRMATION_BLOCKERS_RESOLVED,
                    facts={"resolution_addresses_known_blocker": False},
                ),
            )
        if resolution.blocker_id in answered:
            raise ConfirmationBlockedError(
                translated_message="errors.refused.refused_ledger_confirmation_blocked",
                context={"blocker_id": resolution.blocker_id, "resolution_count": 2},
                precondition_verdict=ledger_no_recovery_verdict(
                    LedgerPreconditionCondition.CONFIRMATION_BLOCKERS_RESOLVED,
                    facts={"one_resolution_per_blocker": False},
                ),
            )
        answered[resolution.blocker_id] = resolution

    for blocker_id, resolution in answered.items():
        if resolution.action is not FindingResolutionAction.CHOOSE_CANDIDATE:
            continue
        blocker = by_id[blocker_id]
        if resolution.value is None or not blocker.names_a_candidate(resolution.value):
            # The refusal enumerates the DIGESTS, not the values. They are what
            # the review surface showed, so they are what the operator can check
            # their answer against -- and naming the raw values here would put
            # the identity this blocker exists to protect into a refusal message.
            offered = ", ".join(blocker.candidate_digests) or "none"
            raise ConfirmationBlockedError(
                translated_message="errors.refused.refused_ledger_confirmation_blocked",
                context={"blocker_id": blocker_id, "offered_candidate_digests": offered},
                precondition_verdict=ledger_no_recovery_verdict(
                    LedgerPreconditionCondition.CONFIRMATION_BLOCKERS_RESOLVED,
                    facts={"chosen_candidate_offered_by_document": False},
                ),
            )

    unresolved = tuple(blocker for blocker in blockers if blocker.blocker_id not in answered)
    if unresolved:
        named = "; ".join(f"{blocker.blocker_id} ({blocker.reason.value}): {blocker.detail}" for blocker in unresolved)
        raise ConfirmationBlockedError(
            translated_message="errors.refused.refused_ledger_confirmation_blocked",
            context={
                "unresolved_blocker_ids": ",".join(blocker.blocker_id for blocker in unresolved),
                "unresolved_blockers": named,
            },
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.CONFIRMATION_BLOCKERS_RESOLVED,
                facts={"all_blockers_resolved": False},
            ),
        )

    return blockers
