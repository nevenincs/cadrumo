"""The identifier accessor answers exactly what the snapshot boundary would, without the copy.

``snapshot`` returns an isolated deep copy so a caller cannot mutate cached
registry state. That copy is the whole cost of the call: against the bundled
registry the cache hit is unmeasurable and the copy is practically all of it.
A caller that only needs to know which revision the boundary admits was paying
for a full validated projection to read one string out of it, and the coverage
composer did that seventeen hundred times to build one report.

These tests hold the accessor to the only bargain that makes it safe: same
answer, same refusals, and nothing mutable handed out.
"""

from __future__ import annotations

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from ..authority import bundled_authority
from ..errors import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def authority():
    return bundled_authority()


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period"),
    [("111", 2026, "1T"), ("303", 2026, "1T"), ("390", 2025, "0A"), ("151", 2025, "0A")],
)
def test_it_returns_the_revision_the_snapshot_boundary_admits(authority, modelo, filing_year, period) -> None:
    """The identifier equals the one the isolated snapshot carries, across unlike modelos."""
    expected = str(authority.snapshot(modelo, filing_year=filing_year, period=period).revision.id)

    assert authority.admitted_revision_id(modelo, filing_year=filing_year, period=period) == expected


def test_it_refuses_exactly_where_the_snapshot_boundary_refuses(authority) -> None:
    """A grade the revision cannot satisfy is refused identically by both accessors.

    Modelo 200's 2024 revision declares calculation grade, so demanding filing
    grade from it is a refusal the shipped registry really makes rather than a
    contrived one. Refusing identically is the whole safety argument: an accessor
    that skipped the copy but also skipped a refusal would hand back an
    identifier the boundary never admitted.
    """
    with pytest.raises(RegistryValidationError) as snapshot_refusal:
        authority.snapshot("200", filing_year=2024, period="0A", grade=RegistryAuthorityGrade.FILING)
    with pytest.raises(RegistryValidationError) as identifier_refusal:
        authority.admitted_revision_id("200", filing_year=2024, period="0A", grade=RegistryAuthorityGrade.FILING)

    assert str(identifier_refusal.value) == str(snapshot_refusal.value)


def test_it_hands_out_a_plain_string_and_not_registry_state(authority) -> None:
    """What escapes is a string, which is why giving up the isolating copy is safe.

    The copy exists to stop a caller mutating a cached projection. This accessor
    can skip it only for as long as it returns nothing a caller could mutate, so
    that is asserted rather than assumed from the annotation.
    """
    admitted = authority.admitted_revision_id("303", filing_year=2026, period="1T")

    assert type(admitted) is str
