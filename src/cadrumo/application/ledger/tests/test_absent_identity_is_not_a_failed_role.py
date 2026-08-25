"""An ABSENT counterparty identifier is not a failed role; an UNVERIFIABLE one is.

Every :class:`~core.DraftDiscrepancyKind` maps to a
:class:`~core.ConfirmationBlockReason` by construction, so any finding raised
here blocks the confirm. That makes the absent/unverifiable distinction a
product decision rather than a wording one: a document that simply does not
print a counterparty NIF is common and correct -- a factura simplificada may
legitimately omit it, an ordinary domestic ticket identifies no customer at all
-- and a blocker firing across that population is one the operator learns to
clear unread. They then clear it on the checksum-failure case too, which is the
one the resolver was built for.

Both directions are gated. Narrowing only the absent side would be worth
nothing if the unverifiable side stopped blocking with it, and the two collapse
one stage upstream unless the reading stage records its own rejections: it drops
an identifier that fails its control character to ``None``, which reaches the
resolver as an absence indistinguishable from a document that printed nothing.
Only the stage that performs the rejection still holds that fact.
"""

from __future__ import annotations

import json

import pytest

from ....core import DraftDiscrepancyKind, FieldGroundingOutcome, FieldOrigin
from ....llm import ground_extracted_fields, parse_invoice_extraction_response
from ..identity_roles import IdentityCandidate, resolve_counterparty_identity

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: The filer's own identifier, and a real third party's. Both verify.
_FILER_CIF = "B17283946"
_COUNTERPARTY_CIF = "B12345674"
#: Correct shape, wrong control character -- the misread that hides a real
#: supplier from a validating read.
_BAD_CHECKSUM_CIF = "B1234567X"


def _resolve(candidates: tuple[IdentityCandidate, ...], *, filer: str | None = _FILER_CIF):
    return resolve_counterparty_identity(
        field="supplier_tax_id",
        candidates=candidates,
        taxpayer_tax_id=filer,
        origin=FieldOrigin.TEXT_LAYER,
    )


def _kinds(resolution) -> set[DraftDiscrepancyKind]:
    return {finding.kind for finding in resolution.findings}


# ---------------------------------------------------------------------------
# Absence: no role failure
# ---------------------------------------------------------------------------


def test_a_document_stating_no_identifier_at_all_raises_no_role_failure() -> None:
    """A receipt carrying no identifiers states no role to get wrong."""
    resolution = _resolve(())

    assert _kinds(resolution) == set()


def test_a_simplificada_carrying_only_the_filers_own_identifier_raises_no_role_failure() -> None:
    """The measured shape: the document names the filer and nobody else.

    Every candidate is excluded by the identity test, so nothing was rejected
    for being unverifiable -- there was simply no counterparty identifier on the
    page.
    """
    resolution = _resolve((IdentityCandidate(value=_FILER_CIF, role_evidence="Cliente:"),))

    assert _kinds(resolution) == set()


def test_an_absence_is_still_reported_as_unresolved_and_never_as_resolved() -> None:
    """The load-bearing half of the narrowing.

    Withholding the finding must mean "the question was not asked", never "the
    role is fine". A consumer reading a resolved counterparty out of this would
    be reading an absence as a verdict, so the resolution must carry no value
    and an unanchored envelope.
    """
    resolution = _resolve((IdentityCandidate(value=_FILER_CIF),))

    assert resolution.resolved is None
    assert resolution.provenance.grounding is FieldGroundingOutcome.UNANCHORED
    assert resolution.provenance.candidates == ()
    assert "no tax identifier" in resolution.provenance.note


# ---------------------------------------------------------------------------
# Unverifiability: still a role failure
# ---------------------------------------------------------------------------


def test_a_counterparty_identifier_failing_its_checksum_still_blocks() -> None:
    """The genuine catch, which the narrowing must not weaken.

    The true supplier's identifier fails its control character. The document DID
    print a counterparty identity and it could not be verified, which is exactly
    the condition that makes the real supplier invisible to a validating read.
    """
    resolution = _resolve(
        (
            IdentityCandidate(value=_BAD_CHECKSUM_CIF, role_evidence="Proveedor:"),
            IdentityCandidate(value=_FILER_CIF, role_evidence="Cliente:"),
        ),
    )

    assert _kinds(resolution) == {
        DraftDiscrepancyKind.IDENTITY_UNVERIFIED,
        DraftDiscrepancyKind.ROLE_UNRESOLVED,
    }
    assert resolution.resolved is None


def test_the_role_failure_now_names_the_verification_failure_rather_than_the_exclusion() -> None:
    """The surviving detail must say what actually went wrong.

    It previously read "no verified identifier remained after excluding the
    filer's own identity", which described the filer exclusion on a document
    whose real problem is a rejected counterparty identifier.
    """
    resolution = _resolve((IdentityCandidate(value=_BAD_CHECKSUM_CIF, role_evidence="Proveedor:"),))

    role = next(f for f in resolution.findings if f.kind is DraftDiscrepancyKind.ROLE_UNRESOLVED)
    assert "failed verification" in role.detail


def test_a_verified_but_unevidenced_lone_survivor_still_blocks() -> None:
    """The narrowing is scoped to ABSENCE and must not reach the survivor case.

    One identifier verified and nothing on the page ties it to the counterparty.
    That is a present-but-unroled identity, not an absent one, and accepting it
    would name whichever unrelated entity happens to appear on the page.
    """
    resolution = _resolve((IdentityCandidate(value=_COUNTERPARTY_CIF),))

    assert DraftDiscrepancyKind.ROLE_UNRESOLVED in _kinds(resolution)


def test_role_evidence_still_resolves_an_evidenced_counterparty() -> None:
    """Positive control: the resolver still promotes on real role evidence.

    Without this, every assertion above would also pass against a resolver that
    had simply stopped resolving anything.
    """
    resolution = _resolve(
        (
            IdentityCandidate(value=_COUNTERPARTY_CIF, role_evidence="Proveedor:"),
            IdentityCandidate(value=_FILER_CIF, role_evidence="Cliente:"),
        ),
    )

    assert resolution.resolved == _COUNTERPARTY_CIF
    assert resolution.provenance.grounding is FieldGroundingOutcome.ANCHORED


# ---------------------------------------------------------------------------
# The distinction has to survive the stage that performs the rejection
# ---------------------------------------------------------------------------


def _grounded(payload: dict[str, str]):
    return ground_extracted_fields(
        parse_invoice_extraction_response(json.dumps(payload)),
        raw_text_length=256,
        origin=FieldOrigin.TEXT_LAYER,
    )


def test_the_reading_stage_records_an_identifier_it_rejected() -> None:
    """Dropping the VALUE is right; dropping the FACT is not.

    The grounder drops a checksum-failing identifier to ``None`` and builds no
    envelope for it, so by the time the resolver reads the draft the document
    looks like it printed nothing. This is the only stage that still knows
    otherwise.
    """
    draft = _grounded(
        {
            "supplier_tax_id": _BAD_CHECKSUM_CIF,
            "supplier_tax_id_anchor": _BAD_CHECKSUM_CIF,
            "supplier_tax_id_role_evidence": "Proveedor:",
        },
    )

    assert draft.supplier_tax_id is None, "the unverifiable value must still be dropped"
    assert [f.kind for f in draft.discrepancies] == [DraftDiscrepancyKind.IDENTITY_UNVERIFIED]
    assert _BAD_CHECKSUM_CIF in draft.discrepancies[0].detail, (
        "the operator must be told which printed identifier failed, not merely that one did"
    )


def test_the_reading_stage_records_nothing_when_the_document_printed_nothing() -> None:
    """The bound on the case above: silence must not become a rejection.

    Without this, "record a rejection" could be implemented as "record one
    whenever the slot is empty", which re-creates the blocker across the
    legitimate population from the other side.
    """
    draft = _grounded({"invoice_number": "2026-0142", "invoice_number_anchor": "2026-0142"})

    assert draft.discrepancies == ()


def test_the_reading_stage_records_nothing_for_an_identifier_that_verifies() -> None:
    """A good identifier is not a rejection, on either party's slot."""
    draft = _grounded(
        {
            "supplier_tax_id": _COUNTERPARTY_CIF,
            "supplier_tax_id_anchor": _COUNTERPARTY_CIF,
            "customer_tax_id": _FILER_CIF,
            "customer_tax_id_anchor": _FILER_CIF,
        },
    )

    assert draft.supplier_tax_id == _COUNTERPARTY_CIF
    assert draft.discrepancies == ()
