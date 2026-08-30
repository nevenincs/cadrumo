"""Which identifier on the page is the counterparty's -- decided, never guessed.

This module exists because of a measured defect, not a hypothetical one. Scanning
a document for the first checksum-valid tax identifier produces a **confident
wrong answer** whenever the real supplier's identifier fails its own check
character: validation correctly rejects the true one, the scan walks on, and the
next valid identifier on the page -- a bank's, a gestoría's, the taxpayer's own --
is returned as the supplier. Nothing fails. The record names a real, valid,
entirely unrelated entity, and no downstream check can tell.

**First-match is the defect.** The fix is not a better scan order: any total order
over the candidates is still a guess wearing a ranking. When role evidence does
not pick exactly one candidate, the resolution is
:attr:`~core.FieldGroundingOutcome.AMBIGUOUS` with every candidate surfaced, and
the operator -- who has the document -- decides.

Two exclusions are applied before candidacy, and both are load-bearing:

**The taxpayer's own identifier is never a counterparty candidate.** It appears on
every invoice in the corpus, on both directions, so leaving it in the pool means
the most frequently occurring identifier on the page competes for the role it can
never hold. Comparison is on the normalised form, so a printed ``B-1234567-4``
does not evade exclusion against a stored ``B12345674``.

That exclusion asks an IDENTITY question, never a validity one, and routes
through :func:`~core.identity.same_tax_identifier` -- the same predicate
:func:`~application.invoices.counterparty_is_the_filer` uses, so a document
cannot evade one while being caught by the other. Routing it through
:func:`canonical_identity_token` instead makes it a validity question, and then
a filer whose stored identifier is foreign, or Spanish with a bad control
character, excludes nothing at all. The strict form remains correct for
verifying a *candidate*; the two are not interchangeable.

**A checksum failure is recorded, not silently dropped.** An identifier that fails
its control character is a real fact about the document -- it is what makes the
true supplier invisible to a validating scan -- so it surfaces as an
:attr:`~core.DraftDiscrepancyKind.IDENTITY_UNVERIFIED` finding rather than
vanishing. That is the difference between "we could not verify the supplier" and
"we found a supplier", and the operator needs the first when the first is true.

**An ABSENT counterparty identifier is not a failed role.** A document that
prints no counterparty identifier at all, or prints only the filer's own, states
no role for this resolver to get wrong: a factura simplificada may legitimately
omit the recipient's NIF, and an ordinary domestic ticket identifies no customer.
Those raise no :attr:`~core.DraftDiscrepancyKind.ROLE_UNRESOLVED`. An
UNVERIFIABLE one still does, because that is the measured defect above. The
distinction is not cosmetic: every discrepancy kind blocks confirmation by
construction, so a blocker firing across the legitimate population is one an
operator learns to clear unread -- and then clears on the checksum case too.

Withholding the finding never asserts that the role is fine. The resolution
carries ``resolved=None`` under an
:attr:`~core.FieldGroundingOutcome.UNANCHORED` envelope whose note says the
document stated nothing, so the absence reads as "not asked" at every consumer.

**EU identifiers count.** A Spanish-only check silently discards every intra-EU
counterparty, which is precisely the Modelo 349 population -- the filing that
exists to report them. Validation therefore routes through the repository's
established EU IVA authority (:mod:`core.identity`) rather than a local
Spain-shaped test.

See Also:
    :class:`~application.ledger.evidence_draft.FieldProvenance`
        The envelope a resolution produces.
    :func:`~application.ledger.grounding_anchor.ground_ambiguous_candidates`
        The sanctioned constructor for the ambiguous outcome.
    :class:`~application.ledger.evidence_draft.DraftDiscrepancyFinding`
        Carrier for the unverified-identity and unresolved-role findings.
"""

from __future__ import annotations

from pydantic import BaseModel

from ...core import DraftDiscrepancyKind, FieldGroundingOutcome, FieldOrigin
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.identity import (
    IdentityError,
    nif_iva_format_for_country,
    normalise_nif_iva,
    same_tax_identifier,
    validate_spanish_tax_id,
)
from ...domain.iva.establishment import country_code_for_printed_tax_identifier
from .evidence_draft import DraftDiscrepancyFinding, FieldAmbiguityCandidate, FieldProvenance
from .grounding_anchor import ground_ambiguous_candidates

__all__ = [
    "IdentityCandidate",
    "IdentityRoleResolution",
    "canonical_identity_token",
    "resolve_counterparty_identity",
]


class IdentityCandidate(BaseModel):
    """One tax identifier observed on the document, with where it was read.

    Attributes:
        value: The identifier exactly as printed, separators and all.
        anchor: The verbatim printed form, when it differs from the value (a
            label-prefixed occurrence, say). Defaults to the value itself.
        country_code: ISO country the identifier is stated under, when the
            document says. ``None`` means unstated, which is read as Spain only
            because that is what an unqualified identifier on a Spanish invoice
            means -- never inferred from the identifier's own shape.
        role_evidence: What on the page suggests this identifier belongs to the
            counterparty, if anything. Empty means no role evidence at all.
    """

    model_config = STRICT_FROZEN_CONFIG

    value: str
    anchor: str | None = None
    country_code: str | None = None
    role_evidence: str = ""

    @property
    def printed_anchor(self) -> str:
        """Return the anchor to record, defaulting to the value as printed."""
        return self.anchor if self.anchor is not None else self.value


class IdentityRoleResolution(BaseModel):
    """The outcome of resolving which candidate holds the counterparty role.

    Attributes:
        provenance: The envelope for the counterparty identifier field.
        resolved: The canonical identifier when exactly one candidate survived,
            ``None`` otherwise. ``None`` on an ambiguous resolution is the point:
            there is no value to carry forward, and a caller that wants one must
            take it from the operator.
        findings: Deterministic findings raised while resolving -- unverified
            identifiers, and an unresolved role.
    """

    model_config = STRICT_FROZEN_CONFIG

    provenance: FieldProvenance
    resolved: str | None = None
    findings: tuple[DraftDiscrepancyFinding, ...] = ()


def canonical_identity_token(value: str, *, country_code: str | None = None) -> str | None:
    """Return the canonical form of *value*, or ``None`` when it does not verify.

    Routes Spanish identifiers through the AEAT control-character algorithm and
    non-Spanish ones through the EU IVA format authority. Returning ``None``
    rather than raising keeps this usable as a filter: a document carrying a
    malformed identifier is an ordinary case the caller reports, not an
    exception it must catch per candidate.

    **An absent country asks the identifier's own prefix before assuming Spain.**
    An intra-community IVA number leads with its Member State's prefix, so a
    document printing ``SE556677889901`` states its country in the number
    itself -- and that is exactly the document whose address block often states
    none. Defaulting the absence to Spain measured such a number against the
    AEAT control-character rule, which it cannot satisfy, so a perfectly
    well-formed foreign identifier yielded no verdict at all. The country the
    default assumed is the very thing the establishment ladder exists to
    determine, and the ladder's own first rung already reads this prefix.

    The prefix is read through
    :func:`~domain.iva.country_code_for_printed_tax_identifier`, the single
    authority on which country a printed number names, rather than by matching
    two leading letters here: the prefix alone is not evidence, and that
    authority requires the body to match the structure its own prefix claims.

    A SUPPLIED country still decides, unchanged. A caller that names one is
    asserting it, and a supplied country disagreeing with the printed prefix is
    a disagreement to surface rather than to resolve silently in the prefix's
    favour -- so only the absence position moves.

    Args:
        value: The identifier as printed.
        country_code: ISO country it is stated under. When ``None``, the
            identifier's own prefix answers; an identifier carrying no
            recognisable prefix takes the Spanish path, which is right because
            a bare ``B``-CIF is what an unqualified Spanish invoice prints.

    Returns:
        The canonical identifier, or ``None`` when it fails verification.
    """
    stripped = value.strip()
    if not stripped:
        return None

    country = (country_code or country_code_for_printed_tax_identifier(stripped) or "ES").strip().upper()
    if country == "ES":
        try:
            return validate_spanish_tax_id(stripped)
        except IdentityError:
            return None

    spec = nif_iva_format_for_country(country)
    if spec is None:
        return None
    normalised = normalise_nif_iva(stripped)
    # The spec's anchored pattern is matched against the full normalised number,
    # prefix included; `normalise_nif_iva` is what puts it in that form. A bare
    # national number with the prefix stripped would fail here, which is correct
    # -- an intra-EU identifier without its country prefix is not one.
    return normalised if spec.pattern.match(normalised) else None


def _own_identity_is_excludable(taxpayer_tax_id: str | None) -> bool:
    """Return whether the filer's identifier is usable for exclusion at all.

    Blank is not a value: a profile carrying whitespace has nothing to exclude,
    and the note must say so rather than claim an exclusion that never ran.
    """
    return taxpayer_tax_id is not None and bool(normalise_nif_iva(taxpayer_tax_id))


def resolve_counterparty_identity(
    *,
    field: str,
    candidates: tuple[IdentityCandidate, ...],
    taxpayer_tax_id: str | None,
    origin: FieldOrigin,
) -> IdentityRoleResolution:
    """Resolve which observed identifier holds the counterparty role.

    Never returns a first match. Exactly one surviving candidate resolves; two or
    more resolve to ``AMBIGUOUS`` carrying every one of them; none resolves to
    ``UNANCHORED`` with an unresolved-role finding.

    Args:
        field: Name of the draft field being resolved.
        candidates: Every tax identifier observed on the document, in document
            order. Order is preserved for display only and is never used to
            break a tie -- breaking a tie by position is first-match under
            another name.
        taxpayer_tax_id: This profile's own identifier, excluded from candidacy.
            Never required to be checksum-valid or Spanish -- exclusion is an
            identity comparison. ``None`` or blank means unknown, which weakens
            the resolution and is reported in the note rather than passed over.
        origin: How the candidates were obtained.

    Returns:
        The resolution, carrying the envelope, any resolved value, and every
        deterministic finding raised on the way.
    """
    findings: list[DraftDiscrepancyFinding] = []
    own_excludable = _own_identity_is_excludable(taxpayer_tax_id)

    verified: list[tuple[IdentityCandidate, str]] = []
    for candidate in candidates:
        # Exclusion runs BEFORE verification, and on the checksum-free identity
        # predicate, because "is this the filer's own identifier" is an identity
        # question rather than a validity one. Routing it through
        # `canonical_identity_token` made it a validity question, and a filer
        # whose stored identifier is foreign -- or Spanish with a bad control
        # character -- then excluded nothing at all, leaving the identifier that
        # appears on every invoice in the corpus competing for the one role it
        # can never hold. Excluding first also keeps the filer's own identifier
        # from being reported as an unverifiable *counterparty*, which it is not.
        if same_tax_identifier(candidate.value, taxpayer_tax_id):
            continue
        token = canonical_identity_token(candidate.value, country_code=candidate.country_code)
        if token is None:
            # Recorded, never dropped: an identifier failing its control
            # character is exactly what hides the true supplier from a scan that
            # only keeps valid ones.
            findings.append(
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.IDENTITY_UNVERIFIED,
                    field=field,
                    detail=(
                        f"the identifier {candidate.value!r} is printed on the document but fails its "
                        f"control-character check, so it cannot be accepted as a verified identity"
                    ),
                ),
            )
            continue
        verified.append((candidate, token))

    if not verified:
        # ABSENT is not UNVERIFIABLE, and the two are separated on whether any
        # candidate was PRINTED AND REJECTED -- which is exactly what `findings`
        # already records. Nothing rejected means the document simply carries no
        # counterparty identifier: a factura simplificada may legitimately omit
        # it, an ordinary domestic ticket names no customer at all, and raising
        # an unresolved ROLE over a role nobody could have stated fires a blocker
        # across a large correct population. An operator taught to clear it
        # unread clears it on the one document where it is genuinely right.
        #
        # The envelope stays UNANCHORED either way, and that is the load-bearing
        # half: withholding the finding says the question was NOT ASKED, never
        # that the role is fine. A caller reading "no ROLE_UNRESOLVED" as a
        # resolved counterparty would be reading an absence as a verdict; the
        # resolution reports `resolved=None` and an unanchored envelope so no
        # such reading is available.
        if not findings:
            return IdentityRoleResolution(
                provenance=FieldProvenance(
                    field=field,
                    origin=origin,
                    grounding=FieldGroundingOutcome.UNANCHORED,
                    note=(
                        "the document states no tax identifier for the counterparty; nothing was "
                        "resolved because there was nothing to resolve"
                        if candidates
                        else "the document states no tax identifier"
                    ),
                ),
            )
        return IdentityRoleResolution(
            provenance=FieldProvenance(
                field=field,
                origin=origin,
                grounding=FieldGroundingOutcome.UNANCHORED,
                note="no identifier on the document verified as a counterparty identity",
            ),
            findings=(
                *findings,
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.ROLE_UNRESOLVED,
                    field=field,
                    detail=(
                        "every identifier the document prints for the counterparty failed verification, "
                        "so the true counterparty is invisible to a validating read"
                        + (
                            ", and the filer's own identifier was not available to exclude"
                            if not own_excludable
                            else ""
                        )
                    ),
                ),
            ),
        )

    # An identity resolves on POSITIVE role evidence, never on survival. This is
    # the distinction the measured defect turns on: when the true supplier's
    # identifier fails its control character, a single unrelated but valid
    # identifier is left standing, and "exactly one candidate remained" would
    # ground it with full confidence. Sole survivorship is first-match with the
    # competitors removed beforehand -- the same guess, harder to see.
    evidenced = [(candidate, token) for candidate, token in verified if candidate.role_evidence]

    if len(evidenced) == 1:
        candidate, token = evidenced[0]
        return IdentityRoleResolution(
            provenance=FieldProvenance(
                field=field,
                origin=origin,
                grounding=FieldGroundingOutcome.ANCHORED,
                anchor=candidate.printed_anchor,
                note=(
                    f"role evidence picks exactly one identifier: {candidate.role_evidence}"
                    f"{_own_exclusion_note(own_excludable)}"
                ),
            ),
            resolved=token,
            findings=tuple(findings),
        )

    # Nothing picks one. Every verified identifier is surfaced; none is promoted.
    # When several carry role evidence they compete on it; when none does, they
    # compete on nothing, and both cases are ambiguity rather than a ranking.
    competing = evidenced if len(evidenced) > 1 else verified

    if len(competing) == 1:
        candidate, _token = competing[0]
        return IdentityRoleResolution(
            provenance=FieldProvenance(
                field=field,
                origin=origin,
                grounding=FieldGroundingOutcome.UNANCHORED,
                anchor=candidate.printed_anchor,
                note=(
                    "one identifier verified but nothing on the document establishes it as the "
                    "counterparty's; a lone survivor is not evidence of a role"
                ),
            ),
            findings=(
                *findings,
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.ROLE_UNRESOLVED,
                    field=field,
                    detail=(
                        f"the identifier {candidate.printed_anchor!r} verified, but no role evidence "
                        f"ties it to the counterparty; accepting it because it is the only one left "
                        f"would name whichever unrelated entity happens to appear on the page"
                    ),
                ),
            ),
        )

    ambiguity = tuple(
        FieldAmbiguityCandidate(
            value=token,
            anchor=candidate.printed_anchor,
            note=candidate.role_evidence or "no role evidence distinguishes this identifier",
        )
        for candidate, token in competing
    )
    return IdentityRoleResolution(
        provenance=ground_ambiguous_candidates(
            field=field,
            origin=origin,
            candidates=ambiguity,
            note=(
                f"{len(competing)} verified identifiers remained and no role evidence picks exactly one"
                f"{_own_exclusion_note(own_excludable)}"
            ),
        ),
        findings=(
            *findings,
            DraftDiscrepancyFinding(
                kind=DraftDiscrepancyKind.ROLE_UNRESOLVED,
                field=field,
                detail=(
                    f"{len(competing)} identifiers could each be the counterparty; "
                    f"selecting one by position would be a guess"
                ),
            ),
        ),
    )


def _own_exclusion_note(own_excludable: bool) -> str:
    """Return the clause stating whether the filer's own identity was excluded.

    Keyed on whether the exclusion actually ran, never on whether an argument
    was passed. The two diverged once: an identifier that failed a Spanish
    checksum produced an empty exclusion set while this note still read "after
    excluding the filer's own identifier", so the operator was told a
    load-bearing exclusion had been applied to a candidate pool that still
    contained the filer.
    """
    if not own_excludable:
        return " (the filer's own identifier was not available, so it could not be excluded)"
    return " after excluding the filer's own identifier"
