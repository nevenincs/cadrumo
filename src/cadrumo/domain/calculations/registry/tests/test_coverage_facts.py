"""The coverage-facts projection carries what a ledger reads, isolated, and nothing else.

A coverage ledger consumes a coordinate and four collections of evidence
references. Obtaining them through ``snapshot`` deep-copies the whole validated
projection - against a mid-sized modelo roughly 126 ms, of which the four
collections are under two - and the audit that builds these ledgers did it 884
times.

Cheapness is not the contract, though, and these tests do not assert it. The
contract is that the projection answers identically, refuses identically, and
isolates what it hands out. If any of those breaks, the speed is worthless.
"""

from __future__ import annotations

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from ..authority import bundled_authority
from ..coverage import build_model_law_coverage_ledger
from ..errors import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority():
    return bundled_authority()


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period"),
    [("303", 2026, "1T"), ("390", 2025, "0A"), ("151", 2025, "0A")],
)
def test_it_carries_the_same_facts_the_snapshot_does(authority, modelo, filing_year, period) -> None:
    """Coordinate and all four evidence collections match the snapshot's, across unlike modelos."""
    snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period)
    facts = authority.coverage_facts(modelo, filing_year=filing_year, period=period)

    assert (facts.modelo, facts.revision) == (snapshot.modelo.id, snapshot.revision.id)
    assert (facts.filing_year, facts.period) == (snapshot.filing_year, snapshot.period)
    assert facts.legal == tuple(snapshot.legal)
    assert dict(facts.sources) == dict(snapshot.sources)
    assert facts.workbook_parity_refs == tuple(snapshot.workbook_parity_refs.values())
    assert facts.live_cross_references == tuple(snapshot.live_cross_references.values())


def test_a_ledger_built_from_either_projection_is_the_same_ledger(authority) -> None:
    """The substitution the coverage audit performs is proven, not assumed.

    This is the invariant that made the change safe to land: the audit swapped
    one projection for the other across 884 coordinates, so a divergence here
    would silently alter published coverage findings rather than fail loudly.
    """
    snapshot = authority.snapshot("303", filing_year=2026, period="1T")
    facts = authority.coverage_facts("303", filing_year=2026, period="1T")

    assert build_model_law_coverage_ledger(snapshot).model_dump_json() == (
        build_model_law_coverage_ledger(facts).model_dump_json()
    )


def test_it_refuses_exactly_where_the_snapshot_boundary_refuses(authority) -> None:
    """A grade the revision cannot satisfy is refused identically by both accessors.

    Skipping the full copy must not also skip a refusal: an accessor that
    answered where the boundary would not would hand out facts for a coordinate
    the registry never admitted.
    """
    with pytest.raises(RegistryValidationError) as snapshot_refusal:
        authority.snapshot("200", filing_year=2025, period="0A", grade=RegistryAuthorityGrade.FILING)
    with pytest.raises(RegistryValidationError) as facts_refusal:
        authority.coverage_facts("200", filing_year=2025, period="0A", grade=RegistryAuthorityGrade.FILING)

    assert str(facts_refusal.value) == str(snapshot_refusal.value)


def test_what_it_hands_out_is_a_copy_and_not_cached_registry_state(authority) -> None:
    """Mutating a returned collection cannot reach the next caller.

    This is the whole safety argument for skipping the snapshot's copy. It is
    asserted by mutating what comes back and re-reading, rather than by trusting
    that a deepcopy call is present, because the second proves the code was
    written and the first proves it works.
    """
    first = authority.coverage_facts("303", filing_year=2026, period="1T")
    assert first.sources, "the fixture coordinate must carry sources for this to prove anything"
    handed_out = first.sources
    assert isinstance(handed_out, dict), "the projection must hand out its own mapping to be mutable"

    victim = next(iter(handed_out))
    del handed_out[victim]

    second = authority.coverage_facts("303", filing_year=2026, period="1T")
    assert victim in second.sources, "a deletion from one caller's facts reached the registry"
    assert second.sources is not handed_out
