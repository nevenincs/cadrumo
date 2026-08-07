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

**A checksum failure is recorded, not silently dropped.** An identifier that fails
its control character is a real fact about the document -- it is what makes the
true supplier invisible to a validating scan -- so it surfaces as an
:attr:`~core.DraftDiscrepancyKind.IDENTITY_UNVERIFIED` finding rather than
vanishing. That is the difference between "we could not verify the supplier" and
"we found a supplier", and the operator needs the first when the first is true.

**EU identifiers count.** A Spanish-only check silently discards every intra-EU
counterparty, which is precisely the Modelo 349 population -- the filing that
exists to report them. Validation therefore routes through the repository's
established EU VAT authority (:mod:`core.identity`) rather than a local
Spain-shaped test.

See Also:
    :class:`~application.ledger.FieldProvenance`
        The envelope a resolution produces.
    :func:`~application.ledger.ground_ambiguous_candidates`
        The sanctioned constructor for the ambiguous outcome.
    :class:`~application.ledger.DraftDiscrepancyFinding`
        Carrier for the unverified-identity and unresolved-role findings.
"""

from __future__ import annotations

from pydantic import BaseModel

from ...core import (
    STRICT_FROZEN_CONFIG,
    DraftDiscrepancyKind,
    FieldGroundingOutcome,
    FieldOrigin,
)
from ...core.identity import (
    IdentityError,
    nif_iva_format_for_country,
    normalise_nif_iva,
    validate_spanish_tax_id,
)
from ._evidence_draft import DraftDiscrepancyFinding, FieldAmbiguityCandidate, FieldProvenance
from ._grounding_anchor import ground_ambiguous_candidates

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
    non-Spanish ones through the EU VAT format authority. Returning ``None``
    rather than raising keeps this usable as a filter: a document carrying a
    malformed identifier is an ordinary case the caller reports, not an
    exception it must catch per candidate.

    Args:
        value: The identifier as printed.
        country_code: ISO country it is stated under. ``None`` or ``ES`` takes
            the Spanish path.

    Returns:
        The canonical identifier, or ``None`` when it fails verification.
    """
    stripped = value.strip()
    if not stripped:
        return None

    country = (country_code or "ES").strip().upper()
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


def _excluded_as_own(token: str, taxpayer_tokens: frozenset[str]) -> bool:
    return token in taxpayer_tokens


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
            ``None`` when unknown, which weakens the resolution and is reported
            in the note rather than passed over.
        origin: How the candidates were obtained.

    Returns:
        The resolution, carrying the envelope, any resolved value, and every
        deterministic finding raised on the way.
    """
    findings: list[DraftDiscrepancyFinding] = []

    taxpayer_tokens: frozenset[str] = frozenset()
    if taxpayer_tax_id is not None:
        own = canonical_identity_token(taxpayer_tax_id)
        if own is not None:
            taxpayer_tokens = frozenset({own})

    verified: list[tuple[IdentityCandidate, str]] = []
    for candidate in candidates:
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
        if _excluded_as_own(token, taxpayer_tokens):
            continue
        verified.append((candidate, token))

    if not verified:
        return IdentityRoleResolution(
            provenance=FieldProvenance(
                field=field,
                origin=origin,
                grounding=FieldGroundingOutcome.UNANCHORED,
                note=(
                    "no identifier on the document verified as a counterparty identity"
                    if candidates
                    else "the document states no tax identifier"
                ),
            ),
            findings=(
                *findings,
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.ROLE_UNRESOLVED,
                    field=field,
                    detail="no verified identifier remained after excluding the filer's own identity",
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
                    f"{_own_exclusion_note(taxpayer_tax_id)}"
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
                f"{_own_exclusion_note(taxpayer_tax_id)}"
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


def _own_exclusion_note(taxpayer_tax_id: str | None) -> str:
    """Return the clause stating whether the filer's own identity was excludable."""
    if taxpayer_tax_id is None:
        return " (the filer's own identifier was not supplied, so it could not be excluded)"
    return " after excluding the filer's own identifier"
