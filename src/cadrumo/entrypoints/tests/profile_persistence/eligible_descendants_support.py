"""Descendant fixtures shared by the Renta descendant-minimum tests."""

from __future__ import annotations

from datetime import date

from cadrumo.domain.contribuyente.descendant import DescendantInfo

from ....domain.calculations.registry.tests.authored_editions import newest_authored_edition

_YEAR = newest_authored_edition("100")


def eligible_descendants() -> tuple[DescendantInfo, ...]:
    """Two descendants born well before the filing year, both living with the taxpayer.

    An unambiguously Art. 58.1-eligible pair that produces a non-zero estatal
    aggregate the sentinel has to visibly displace. Callers build it inside a
    pinned authority scope because the default relationship is a registry
    projection.
    """
    return (
        DescendantInfo(birth_date=date(_YEAR - 15, 3, 4)),
        DescendantInfo(birth_date=date(_YEAR - 11, 9, 18)),
    )
