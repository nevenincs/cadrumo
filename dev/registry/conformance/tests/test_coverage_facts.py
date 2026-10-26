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

from collections.abc import MutableMapping
from typing import Any, cast

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import NoRevisionForPeriodError, RegistryValidationError

from ...compiler.authority import compiled_bundled_authority
from ..coverage import build_model_law_coverage_ledger, coverage_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority():
    return compiled_bundled_authority()


def _a_coordinate_below_filing_grade(authority: ValidatedRegistryAuthority) -> tuple[str, int, str, str]:
    """Return the first published coordinate whose revision cannot reach filing grade.

    Discovered rather than pinned: which revisions publish below filing grade
    changes as the registry is authored, and a pinned coordinate that has since
    been raised leaves the refusal unexercised while still passing.
    """
    support = authority.supported_filing_years()
    for modelo in (definition.id for definition in authority.modelos):
        for filing_year in range(support.floor, support.horizon + 1):
            for period in ("0A", "1T"):
                try:
                    authority.snapshot(
                        modelo, filing_year=filing_year, period=period, grade=RegistryAuthorityGrade.FILING
                    )
                except NoRevisionForPeriodError:
                    continue  # the coordinate is unauthored, which is not a grade refusal
                except RegistryValidationError as refusal:
                    return modelo, filing_year, period, str(refusal)
    pytest.fail("every published coordinate reaches filing grade, so the refusal parity is unexercised")


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period"),
    [("303", 2026, "1T"), ("390", 2025, "0A"), ("151", 2025, "0A")],
)
def test_it_carries_the_same_facts_the_snapshot_does(authority, modelo, filing_year, period) -> None:
    """Coordinate and all four evidence collections match the snapshot's, across unlike modelos."""
    snapshot = authority.snapshot(modelo, filing_year=filing_year, period=period)
    facts = coverage_facts(authority, modelo, filing_year=filing_year, period=period)

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
    facts = coverage_facts(authority, "303", filing_year=2026, period="1T")

    assert build_model_law_coverage_ledger(snapshot).model_dump_json() == (
        build_model_law_coverage_ledger(facts).model_dump_json()
    )


def test_it_refuses_exactly_where_the_snapshot_boundary_refuses(authority) -> None:
    """A grade the revision cannot satisfy is refused identically by both accessors.

    Skipping the full copy must not also skip a refusal: an accessor that
    answered where the boundary would not would hand out facts for a coordinate
    the registry never admitted.
    """
    modelo, filing_year, period, snapshot_refusal = _a_coordinate_below_filing_grade(authority)

    with pytest.raises(RegistryValidationError) as facts_refusal:
        coverage_facts(authority, modelo, filing_year=filing_year, period=period, grade=RegistryAuthorityGrade.FILING)

    assert str(facts_refusal.value) == snapshot_refusal


def test_what_it_hands_out_is_a_copy_and_not_cached_registry_state(authority) -> None:
    """Mutating a returned collection cannot reach the next caller.

    This is the whole safety argument for skipping the snapshot's copy. It is
    asserted by mutating what comes back and re-reading, rather than by trusting
    that a deepcopy call is present, because the second proves the code was
    written and the first proves it works.
    """
    first = coverage_facts(authority, "303", filing_year=2026, period="1T")
    assert first.sources, "the fixture coordinate must carry sources for this to prove anything"
    handed_out = first.sources
    victim = next(iter(handed_out))

    if isinstance(handed_out, MutableMapping):
        del handed_out[victim]
    else:
        # A mapping that refuses mutation isolates by construction, which is the
        # same guarantee by a stronger means; the refusal itself is asserted so
        # a mapping that silently accepted the write could not pass here.
        with pytest.raises(TypeError):
            # Deliberately exercising an operation the static Mapping type does
            # not support, to prove it fails closed at runtime.
            del cast(Any, handed_out)[victim]

    second = coverage_facts(authority, "303", filing_year=2026, period="1T")
    assert victim in second.sources, "a deletion from one caller's facts reached the registry"
    if isinstance(handed_out, MutableMapping):
        # Only a mutable mapping has to be a distinct object; an immutable one
        # may be shared precisely because no caller can alter it.
        assert second.sources is not handed_out
