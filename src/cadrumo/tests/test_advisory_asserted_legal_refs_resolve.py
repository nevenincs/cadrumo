"""A calculation advisory's ``asserted_legal_refs`` must resolve to the legal catalogue.

``CalculationSourceDiagnostic.asserted_legal_refs`` lets an advisory declare a
provision it asserts about ITSELF -- an eligibility rule governing one of a
casilla's inputs, distinct from the casilla-derived ``legal_refs`` path a
grounded advisory about the casilla's own computation already carries. A
declared id is a claim with no structural guarantee behind it unless
something resolves it against the catalogue: this is the check a prose-only
message could never carry, because nothing validates a string.

Two proofs, and closure rests on the second rather than the first. The
refusal firing on a fabricated id proves the mechanism catches a defect; on
its own that proves nothing about whether it over-reaches on real advisory
claims. The CONTROL is the ids drawn from the governing decision's own measurement -- real
articles a legal-catalogue entry was independently confirmed to carry at the
exact granularity an advisory would assert -- all still resolving against the
live bundled catalogue.
"""

from __future__ import annotations

import pytest

from ..application.aggregation import CalculationSourceDiagnostic
from ..domain.calculations.registry.authority import bundled_authority
from ..domain.calculations.registry.errors import RegistryValidationError
from ..domain.calculations.registry.legal import assert_legal_ref_ids_resolve

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Provision ids drawn from the grounding reference's Population B measurement
#: (``advisory-grounding`` reference, "Three populations, and the largest is a
#: precision gap"): real articles independently confirmed present in the legal
#: catalogue at the exact apartado/norma granularity an advisory's message
#: already asserted in prose. Chosen because they are EVIDENCED, not because
#: they are convenient -- a control built from ids invented for this test would
#: prove nothing about the real population an advisory would declare.
_EVIDENCED_LEGITIMATE_ASSERTED_REFS: tuple[str, ...] = (
    "ley-35-2006:art-58-1",
    "ley-35-2006:art-61-norma-2",
    "ley-35-2006:art-81-2",
    "ley-35-2006:art-81-3",
    "ley-37-1992:art-103",
    "ley-37-1992:art-104",
    "ley-37-1992:art-105",
    "ley-37-1992:art-106",
)


def _asserted_diagnostic(ref_id: str) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="source_issue",
        source_kind="eligibility_rule_advisory",
        message=f"advisory asserting the provision {ref_id!r} governs one of this casilla's inputs",
        asserted_legal_refs=(ref_id,),
    )


def test_the_evidenced_legitimate_population_still_resolves() -> None:
    """The CONTROL that decides closure, not the refusal below.

    Every id an advisory would legitimately declare today -- drawn from the
    governing decision's own hand-checked measurement rather than fabricated for this test --
    must still resolve against the live bundled legal catalogue now that the
    refusal exists. A legitimate id failing here would mean the catalogue is
    incomplete for that provision, which is a stop-and-report finding, never a
    reason to relax the check.
    """
    catalogue = bundled_authority().catalogues.legal
    diagnostics = tuple(_asserted_diagnostic(ref_id) for ref_id in _EVIDENCED_LEGITIMATE_ASSERTED_REFS)

    for diagnostic in diagnostics:
        assert_legal_ref_ids_resolve(
            diagnostic.asserted_legal_refs,
            legal=catalogue,
            subject=diagnostic.source_kind,
        )


def test_a_fabricated_provision_id_refuses() -> None:
    """The refusal fires on an id no catalogue entry carries.

    Necessary but not sufficient on its own -- see the control above, which is
    what proves the mechanism does not over-reach on real advisory claims.
    """
    catalogue = bundled_authority().catalogues.legal
    diagnostic = _asserted_diagnostic("ley-99-9999:art-0")

    with pytest.raises(RegistryValidationError, match="ley-99-9999:art-0"):
        assert_legal_ref_ids_resolve(
            diagnostic.asserted_legal_refs,
            legal=catalogue,
            subject=diagnostic.source_kind,
        )
