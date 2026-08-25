"""Identity role resolution: never a first match, never the filer's own NIF.

The central case is the MEASURED defect, reproduced exactly: a document whose
true supplier CIF fails its own control character, carrying a second, valid tax
identifier belonging to an unrelated entity on the same page. A validating scan
rejects the true one and returns the unrelated one, and nothing downstream can
tell. Every assertion about that shape below is written as an outcome -- what
resolved -- rather than as a call count, because the defect is a wrong answer,
not a wrong code path.

The identifiers used here are checksum-real: `B17283946` and `A82645177` pass the
AEAT control-character algorithm and `B17283945` fails it. That is verified by a
control test rather than asserted in a comment, so a change to the validator
cannot leave these cases silently testing nothing.
"""

from __future__ import annotations

import pytest

from ....core import DraftDiscrepancyKind, FieldGroundingOutcome, FieldOrigin
from ....core.identity import IdentityError, validate_spanish_tax_id
from ..identity_roles import (
    IdentityCandidate,
    canonical_identity_token,
    resolve_counterparty_identity,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The filer's own identifier. Appears on every invoice, both directions.
_OWN_NIF = "12345678Z"

#: A valid CIF belonging to an entity that is NOT the supplier -- a bank, a
#: gestoría, a logo in the footer. This is the identifier the defect returns.
_UNRELATED_VALID_CIF = "B17283946"

#: A second valid identifier, for the genuine multi-candidate case.
_OTHER_VALID_CIF = "A82645177"

#: A third, for proving every competitor is surfaced rather than the first two.
_THIRD_VALID_CIF = "B10000016"

#: The true supplier's CIF, whose control character does not check out. This is
#: why a validating scan walks past it and reaches the unrelated one.
_SUPPLIER_CIF_FAILING_CHECKSUM = "B17283945"

#: A filer whose own identifier is a French IVA number. Nothing about a Spanish
#: filing obligation requires the filer's stored identifier to be Spanish, and
#: no checksum-asserting exclusion can see this one at all.
_FOREIGN_OWN_IVA = "FR52422961982"


def _resolve(candidates: tuple[IdentityCandidate, ...], *, own: str | None = _OWN_NIF):
    return resolve_counterparty_identity(
        field="supplier_tax_id",
        candidates=candidates,
        taxpayer_tax_id=own,
        origin=FieldOrigin.TEXT_LAYER,
    )


def test_the_fixture_identifiers_still_carry_the_properties_they_are_named_for() -> None:
    """Anchor test: a validator change must not make these cases vacuous.

    Without this, a loosened checksum would turn the defect fixture into three
    valid identifiers and every case below would still pass while testing
    something else entirely.
    """
    assert validate_spanish_tax_id(_UNRELATED_VALID_CIF) == _UNRELATED_VALID_CIF
    assert validate_spanish_tax_id(_OTHER_VALID_CIF) == _OTHER_VALID_CIF
    assert validate_spanish_tax_id(_THIRD_VALID_CIF) == _THIRD_VALID_CIF
    assert validate_spanish_tax_id(_OWN_NIF) == _OWN_NIF
    with pytest.raises(IdentityError):
        validate_spanish_tax_id(_SUPPLIER_CIF_FAILING_CHECKSUM)
    with pytest.raises(IdentityError):
        validate_spanish_tax_id(_FOREIGN_OWN_IVA)


def test_the_measured_defect_shape_never_yields_a_first_match_identifier() -> None:
    """THE case this test exists for.

    A page carrying the true supplier's checksum-failing CIF, an unrelated valid
    CIF, and the filer's own NIF must not resolve to any identifier at all. The
    old behaviour returned the unrelated CIF with full confidence.
    """
    resolution = _resolve(
        (
            IdentityCandidate(value=_SUPPLIER_CIF_FAILING_CHECKSUM),
            IdentityCandidate(value=_UNRELATED_VALID_CIF),
            IdentityCandidate(value=_OWN_NIF),
        ),
    )

    assert resolution.resolved is None, "an unrelated entity was returned as the counterparty"
    assert resolution.resolved != _UNRELATED_VALID_CIF
    assert resolution.provenance.grounding is not FieldGroundingOutcome.ANCHORED


def test_the_defect_shape_reports_both_the_bad_checksum_and_the_unresolved_role() -> None:
    """Neither fact may be swallowed: they are different things the operator needs."""
    resolution = _resolve(
        (
            IdentityCandidate(value=_SUPPLIER_CIF_FAILING_CHECKSUM),
            IdentityCandidate(value=_UNRELATED_VALID_CIF),
            IdentityCandidate(value=_OWN_NIF),
        ),
    )

    kinds = {finding.kind for finding in resolution.findings}
    assert DraftDiscrepancyKind.IDENTITY_UNVERIFIED in kinds
    assert DraftDiscrepancyKind.ROLE_UNRESOLVED in kinds
    unverified = next(f for f in resolution.findings if f.kind is DraftDiscrepancyKind.IDENTITY_UNVERIFIED)
    assert _SUPPLIER_CIF_FAILING_CHECKSUM in unverified.detail


def test_a_lone_surviving_identifier_without_role_evidence_does_not_resolve() -> None:
    """Sole survivorship is first-match with the competitors removed beforehand.

    This is the subtle half of the defect. Eliminating the bad checksum and the
    filer's own identity can leave exactly one candidate standing -- and grounding
    it because it is the only one left names whichever unrelated entity happened
    to be printed on the page.
    """
    resolution = _resolve((IdentityCandidate(value=_UNRELATED_VALID_CIF),))

    assert resolution.resolved is None
    assert resolution.provenance.grounding is FieldGroundingOutcome.UNANCHORED
    assert any(f.kind is DraftDiscrepancyKind.ROLE_UNRESOLVED for f in resolution.findings)


def test_role_evidence_picking_exactly_one_candidate_resolves_it() -> None:
    """Positive control: the resolver is not a blanket refusal.

    Without this, every assertion above would be satisfied by a function that
    returns ``None`` unconditionally.
    """
    resolution = _resolve(
        (
            IdentityCandidate(value=_UNRELATED_VALID_CIF, role_evidence="printed under 'Proveedor'"),
            IdentityCandidate(value=_OTHER_VALID_CIF),
        ),
    )

    assert resolution.resolved == _UNRELATED_VALID_CIF
    assert resolution.provenance.grounding is FieldGroundingOutcome.ANCHORED
    assert resolution.findings == ()


def test_two_candidates_carrying_role_evidence_stay_ambiguous_with_both_surfaced() -> None:
    """Competing evidence is ambiguity, not a ranking to be broken by order."""
    resolution = _resolve(
        (
            IdentityCandidate(value=_UNRELATED_VALID_CIF, role_evidence="under 'Proveedor'"),
            IdentityCandidate(value=_OTHER_VALID_CIF, role_evidence="under 'Emisor'"),
        ),
    )

    assert resolution.resolved is None
    assert resolution.provenance.grounding is FieldGroundingOutcome.AMBIGUOUS
    surfaced = {candidate.value for candidate in resolution.provenance.candidates}
    assert surfaced == {_UNRELATED_VALID_CIF, _OTHER_VALID_CIF}


def test_every_competing_candidate_is_surfaced_not_just_the_winner_and_one_alternate() -> None:
    """All of them. A truncated candidate list is a partial answer wearing a full one."""
    resolution = _resolve(
        (
            IdentityCandidate(value=_UNRELATED_VALID_CIF),
            IdentityCandidate(value=_OTHER_VALID_CIF),
            IdentityCandidate(value=_THIRD_VALID_CIF),
        ),
    )

    assert resolution.provenance.grounding is FieldGroundingOutcome.AMBIGUOUS
    assert len(resolution.provenance.candidates) == 3


def test_reversing_document_order_does_not_change_the_outcome() -> None:
    """Order-independence is the structural proof that no first-match remains.

    A resolver that ranked by position would return a different identifier here.
    """
    forward = _resolve(
        (
            IdentityCandidate(value=_UNRELATED_VALID_CIF),
            IdentityCandidate(value=_OTHER_VALID_CIF),
        ),
    )
    reverse = _resolve(
        (
            IdentityCandidate(value=_OTHER_VALID_CIF),
            IdentityCandidate(value=_UNRELATED_VALID_CIF),
        ),
    )

    assert forward.resolved == reverse.resolved is None
    assert forward.provenance.grounding is reverse.provenance.grounding
    assert {c.value for c in forward.provenance.candidates} == {c.value for c in reverse.provenance.candidates}


def test_the_filers_own_identifier_is_never_a_counterparty_candidate() -> None:
    """It is on every invoice in both directions; leaving it in makes it compete."""
    resolution = _resolve(
        (
            IdentityCandidate(value=_OWN_NIF),
            IdentityCandidate(value=_UNRELATED_VALID_CIF, role_evidence="under 'Proveedor'"),
        ),
    )

    assert resolution.resolved == _UNRELATED_VALID_CIF
    assert _OWN_NIF not in {c.value for c in resolution.provenance.candidates}


def test_the_own_identifier_exclusion_survives_printed_separators() -> None:
    """A printed ``12.345.678-Z`` must not evade exclusion against a stored form."""
    resolution = _resolve(
        (
            IdentityCandidate(value="12.345.678-Z"),
            IdentityCandidate(value=_UNRELATED_VALID_CIF, role_evidence="under 'Proveedor'"),
        ),
    )

    assert resolution.resolved == _UNRELATED_VALID_CIF
    assert not any(c.value == _OWN_NIF for c in resolution.provenance.candidates)


def test_a_foreign_filer_identifier_still_excludes_the_filer_from_candidacy() -> None:
    """Exclusion is identity, not validity.

    A profile whose own identifier is a French IVA number cannot pass the AEAT
    control-character algorithm, so an exclusion routed through the checksum
    validator produces an EMPTY exclusion set -- and the identifier printed on
    every invoice this filer holds competes for the counterparty role. Here the
    filer's own id is the only one carrying role evidence, so if it is not
    excluded it RESOLVES, naming the filer as their own supplier.
    """
    resolution = _resolve(
        (
            IdentityCandidate(
                value=_FOREIGN_OWN_IVA,
                country_code="FR",
                role_evidence="printed under 'Fournisseur'",
            ),
            IdentityCandidate(value=_UNRELATED_VALID_CIF),
        ),
        own=_FOREIGN_OWN_IVA,
    )

    assert resolution.resolved != _FOREIGN_OWN_IVA, "the filer was named as their own counterparty"
    assert resolution.resolved is None
    assert _FOREIGN_OWN_IVA not in {c.value for c in resolution.provenance.candidates}


def test_a_checksum_invalid_filer_identifier_still_excludes_the_filer() -> None:
    """The stored own id need not verify for the exclusion to run.

    A Spanish identifier stored with a wrong control character is unverifiable,
    not unknown -- and a strict-validator exclusion silently drops it, leaving
    the filer in the pool.
    """
    resolution = _resolve(
        (
            IdentityCandidate(
                value=_SUPPLIER_CIF_FAILING_CHECKSUM,
                role_evidence="printed under 'Proveedor'",
            ),
            IdentityCandidate(value=_UNRELATED_VALID_CIF),
        ),
        own=_SUPPLIER_CIF_FAILING_CHECKSUM,
    )

    assert resolution.resolved is None
    assert not any(f.kind is DraftDiscrepancyKind.IDENTITY_UNVERIFIED for f in resolution.findings), (
        "the filer's own identifier was reported as an unverifiable counterparty"
    )


def test_the_exclusion_note_reports_the_actual_exclusion_not_the_arguments_presence() -> None:
    """A note claiming an exclusion that did not run is worse than no note.

    The provenance clause is the only operator-facing signal that the filer was
    removed from candidacy. Keyed on ``taxpayer_tax_id is not None`` it read
    "after excluding the filer's own identifier" for every unusable stored id.
    """
    unusable = _resolve(
        (IdentityCandidate(value=_UNRELATED_VALID_CIF, role_evidence="under 'Proveedor'"),),
        own="   ",
    )

    assert "could not be excluded" in unusable.provenance.note
    assert "after excluding the filer's own identifier" not in unusable.provenance.note

    usable = _resolve(
        (IdentityCandidate(value=_UNRELATED_VALID_CIF, role_evidence="under 'Proveedor'"),),
        own=_OWN_NIF,
    )
    assert "after excluding the filer's own identifier" in usable.provenance.note


def test_an_unknown_own_identifier_is_reported_rather_than_passed_over() -> None:
    """A weaker resolution must say it is weaker."""
    resolution = _resolve(
        (IdentityCandidate(value=_UNRELATED_VALID_CIF, role_evidence="under 'Proveedor'"),),
        own=None,
    )

    assert "could not be excluded" in resolution.provenance.note


def test_a_document_stating_no_identifier_resolves_to_nothing_without_blaming_the_role() -> None:
    """An ABSENT identifier states no role, so there is no failed role to report.

    This case previously asserted a ``ROLE_UNRESOLVED`` finding. Every
    discrepancy kind blocks the confirm by construction, so that fired a blocker
    on every document printing no counterparty identifier -- which a factura
    simplificada and an ordinary domestic ticket both legitimately do.

    What must NOT weaken with it is the outcome: the resolution still carries no
    value and an unanchored envelope, so withholding the finding says the
    question was not asked rather than that the role is fine. The unverifiable
    case, which is the one this resolver was built for, still raises -- see
    ``test_absent_identity_is_not_a_failed_role.py``.
    """
    resolution = _resolve(())

    assert resolution.resolved is None
    assert resolution.provenance.grounding is FieldGroundingOutcome.UNANCHORED
    assert not any(f.kind is DraftDiscrepancyKind.ROLE_UNRESOLVED for f in resolution.findings)


def test_an_intra_eu_counterparty_verifies_rather_than_being_discarded() -> None:
    """A Spanish-only check silently drops exactly the Modelo 349 population."""
    resolution = _resolve(
        (
            IdentityCandidate(
                value="FR52422961982",
                country_code="FR",
                role_evidence="printed under 'Fournisseur'",
            ),
        ),
    )

    assert resolution.resolved == "FR52422961982"
    assert resolution.provenance.grounding is FieldGroundingOutcome.ANCHORED


def test_a_malformed_eu_identifier_does_not_verify() -> None:
    """Positive control for the EU path: it validates rather than waving through."""
    assert canonical_identity_token("FR00", country_code="FR") is None
    assert canonical_identity_token("XX123456789", country_code="XX") is None


def test_the_spanish_path_still_rejects_a_bad_control_character() -> None:
    """Positive control for the Spanish path."""
    assert canonical_identity_token(_SUPPLIER_CIF_FAILING_CHECKSUM) is None
    assert canonical_identity_token(_UNRELATED_VALID_CIF) == _UNRELATED_VALID_CIF


def test_an_absent_country_does_not_verify_a_foreign_identifier_as_spanish() -> None:
    """The country parameter is nullable here, so absence must not become Spain.

    The ledger transaction's counterparty country is itself optional, so this
    helper genuinely receives ``None``. The documented fallback to the Spanish
    path is safe only because the Spanish algorithm then REFUSES an identifier
    that is not Spanish: a bare foreign number with no prefix to speak for it
    comes back unverified rather than canonicalised into a Spanish identity.

    Without this, the fallback could be loosened to accept what it cannot
    verify and nothing would notice, because the two identifiers that do carry
    their own evidence -- a valid Spanish CIF, and a foreign number wearing its
    country prefix -- resolve identically whether or not a country is stated.
    """
    bare_foreign_number = "811907980"

    assert canonical_identity_token(bare_foreign_number, country_code=None) is None
    assert canonical_identity_token(bare_foreign_number) is None

    # Positive controls: an absent country must not break the two cases that
    # can answer for themselves, or the assertion above would hold for a helper
    # that simply verifies nothing.
    assert canonical_identity_token("A58818501", country_code=None) == "A58818501"
    assert canonical_identity_token("DE811907980", country_code=None) == "DE811907980"
