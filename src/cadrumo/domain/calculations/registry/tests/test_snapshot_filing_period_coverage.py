"""Declared coverage of the snapshot filing-period cross-check.

A revision can be addressed by a token that names no period a taxpayer files
in: the administrative censo/comunicacion tokens (Modelo 036, Modelo 145) and
the symbolic event selector (Modelo 210) are registry coordinates, not filing
periods. :attr:`RegistrySnapshot.filing_period` is therefore ``None`` for those
snapshots, and the snapshot's filing-period consistency validator returns early
rather than cross-checking anything.

That is correct - there is no filing period to check against - but it means the
cross-check covers a smaller set than its name suggests, and a validator whose
real coverage is narrower than it appears is the shape that gets misread later.
These tests state the reduced coverage as an asserted fact so it is declared
somewhere durable rather than inferred by the next reader: the administrative
snapshots are pinned as carrying no filing period, and a filing-period snapshot
is pinned as carrying one that agrees with its coordinates.
"""

from __future__ import annotations

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from ..authority import ValidatedRegistryAuthority

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

#: Revision coordinates addressed by a token that names no filing period.
_ADMINISTRATIVE_COORDINATES: tuple[tuple[str, int, str], ...] = (
    ("036", 2025, "alta"),
    ("036", 2025, "modificacion"),
    ("036", 2025, "baja"),
    ("145", 2025, "comunicacion"),
    ("145", 2025, "variacion"),
)

#: Coordinates addressed by a real filing period, as the positive control.
_FILING_COORDINATES: tuple[tuple[str, int, str], ...] = (
    ("303", 2025, "1T"),
    ("100", 2024, "0A"),
)


@pytest.mark.parametrize(("modelo", "filing_year", "period"), _ADMINISTRATIVE_COORDINATES)
def test_an_administrative_coordinate_carries_no_filing_period(
    registry_authority: ValidatedRegistryAuthority,
    modelo: str,
    filing_year: int,
    period: str,
) -> None:
    """An administrative token builds a snapshot with no filing period."""
    snapshot = registry_authority.snapshot(
        modelo, filing_year=filing_year, period=period, grade=RegistryAuthorityGrade.APPLICABILITY
    )

    assert snapshot.filing_period is None, (
        f"M{modelo} {period!r} produced a filing period; an administrative token addresses a "
        "revision rather than naming a period a taxpayer files in"
    )
    assert snapshot.period == period


@pytest.mark.parametrize(("modelo", "filing_year", "period"), _FILING_COORDINATES)
def test_a_filing_coordinate_carries_a_consistent_filing_period(
    registry_authority: ValidatedRegistryAuthority,
    modelo: str,
    filing_year: int,
    period: str,
) -> None:
    """A real filing period is present and agrees with its own coordinates."""
    snapshot = registry_authority.snapshot(
        modelo, filing_year=filing_year, period=period, grade=RegistryAuthorityGrade.APPLICABILITY
    )

    assert snapshot.filing_period is not None, (
        f"M{modelo} {period!r} lost its filing period; the cross-check silently stops applying "
        "when this is None, so an absent period here would disable it unnoticed"
    )
    assert snapshot.filing_period.filing_year == filing_year
    assert snapshot.filing_period.registry_token == period


def test_the_two_classes_are_both_represented(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """Both branches are exercised, so neither list can quietly empty out."""
    absent = [
        (modelo, period)
        for modelo, filing_year, period in _ADMINISTRATIVE_COORDINATES
        if registry_authority.snapshot(
            modelo, filing_year=filing_year, period=period, grade=RegistryAuthorityGrade.APPLICABILITY
        ).filing_period
        is None
    ]
    present = [
        (modelo, period)
        for modelo, filing_year, period in _FILING_COORDINATES
        if registry_authority.snapshot(
            modelo, filing_year=filing_year, period=period, grade=RegistryAuthorityGrade.APPLICABILITY
        ).filing_period
        is not None
    ]

    assert len(absent) == len(_ADMINISTRATIVE_COORDINATES), "an administrative coordinate gained a filing period"
    assert len(present) == len(_FILING_COORDINATES), "a filing coordinate lost its filing period"
