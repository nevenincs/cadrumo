"""What LIVA art. 105 lets a taxpayer declare, and what it requires as evidence.

Three refusals, each a legal rule rather than an input-shape preference:

The art. 105.Cinco interrupted-activity percentage is COMPUTED from the
register's own stored volumes over the last three active years. Accepting it as
a declaration would let an operator assert a figure the law derives, and the
asserted one would stand in place of the computation for that ejercicio.

An AEAT-authorised percentage (art. 105.Dos) and an inicio-de-actividades
percentage (art. 105.Tres via art. 111.Dos) each stand on a document. Recorded
without their reference, the register holds a percentage whose authority cannot
be produced when it is asked for.

And a reference against a provenance that carries no document records evidence
for an authority that does not exist.
"""

from __future__ import annotations

import pytest

from ....core.prorrata_register import ProrrataProvisionalProvenance
from ..election import (
    ELECTABLE_PROVENANCES,
    REFERENCED_PROVENANCES,
    ProrrataElectionError,
    ProrrataElectionRefusal,
    validate_prorrata_election,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_carried_prior_definitive_needs_no_reference() -> None:
    """The art. 105.Uno normal case: carried from the prior settlement."""
    provenance, reference = validate_prorrata_election(
        provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        reference=None,
    )

    assert provenance is ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA
    assert reference is None


@pytest.mark.parametrize(
    "provenance",
    [ProrrataProvisionalProvenance.AEAT_AUTORIZADA, ProrrataProvisionalProvenance.INICIO_ACTIVIDAD],
)
def test_a_document_backed_provenance_records_its_reference(
    provenance: ProrrataProvisionalProvenance,
) -> None:
    """Both document-backed provenances are checked, not just one."""
    resolved, reference = validate_prorrata_election(provenance=provenance, reference="AUT-2026-1")

    assert resolved is provenance
    assert reference == "AUT-2026-1"


def test_the_computed_interrupted_percentage_cannot_be_declared() -> None:
    """Art. 105.Cinco is derived; asserting it would displace the computation."""
    with pytest.raises(ProrrataElectionError) as excinfo:
        validate_prorrata_election(
            provenance=ProrrataProvisionalProvenance.INTERRUMPIDA_TRES_ULTIMOS,
            reference=None,
        )

    assert excinfo.value.refusal is ProrrataElectionRefusal.PROVENANCE_NOT_ELECTABLE


@pytest.mark.parametrize(
    "provenance",
    [ProrrataProvisionalProvenance.AEAT_AUTORIZADA, ProrrataProvisionalProvenance.INICIO_ACTIVIDAD],
)
def test_a_document_backed_provenance_without_its_reference_is_refused(
    provenance: ProrrataProvisionalProvenance,
) -> None:
    """A percentage whose authority cannot be produced is not recordable."""
    with pytest.raises(ProrrataElectionError) as excinfo:
        validate_prorrata_election(provenance=provenance, reference=None)

    assert excinfo.value.refusal is ProrrataElectionRefusal.REFERENCE_REQUIRED


def test_a_blank_reference_does_not_satisfy_the_document_requirement() -> None:
    """Whitespace is not an authorisation.

    Accepting it would store a reference field that looks populated to every
    later reader while naming no document at all.
    """
    with pytest.raises(ProrrataElectionError) as excinfo:
        validate_prorrata_election(
            provenance=ProrrataProvisionalProvenance.AEAT_AUTORIZADA,
            reference="   ",
        )

    assert excinfo.value.refusal is ProrrataElectionRefusal.REFERENCE_REQUIRED


def test_a_reference_against_an_undocumented_provenance_is_refused() -> None:
    """Evidence for an authority the provenance does not have."""
    with pytest.raises(ProrrataElectionError) as excinfo:
        validate_prorrata_election(
            provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
            reference="AUT-2026-1",
        )

    assert excinfo.value.refusal is ProrrataElectionRefusal.REFERENCE_NOT_PERMITTED


def test_every_electable_provenance_is_a_real_art_105_provenance() -> None:
    """The declarable set is a subset of the regulated one, never an extension."""
    assert set(ELECTABLE_PROVENANCES) <= set(ProrrataProvisionalProvenance)


def test_every_referenced_provenance_is_itself_electable() -> None:
    """A provenance requiring evidence but not declarable would be unreachable.

    The two sets are maintained separately, so nothing but this stops one
    drifting into naming a provenance the other refuses.
    """
    assert set(ELECTABLE_PROVENANCES) >= REFERENCED_PROVENANCES


def test_exactly_one_electable_provenance_carries_no_document() -> None:
    """The carried prior definitive is the only one standing on the register.

    Pinned as a count so adding a fourth declarable provenance has to state
    which side of the evidence rule it falls on rather than defaulting.
    """
    undocumented = set(ELECTABLE_PROVENANCES) - REFERENCED_PROVENANCES

    assert undocumented == {ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA}
