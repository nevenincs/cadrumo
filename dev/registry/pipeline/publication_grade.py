"""The authority grade a static generated export tree must reach to be published.

The publisher validates each candidate tree at this grade, and the disposition
ledger reads the same value to decide whether a revision's declared grade puts
republication out of reach. Declared once so the two cannot disagree about where
the floor sits.
"""

from __future__ import annotations

from cadrumo.core.authority_grade import RegistryAuthorityGrade

__all__ = ["reaches_static_publication_grade", "static_publication_authority_grade"]


def static_publication_authority_grade() -> RegistryAuthorityGrade:
    """Return the grade every static generated export candidate is validated at."""
    return RegistryAuthorityGrade.CALCULATION


def reaches_static_publication_grade(grade: RegistryAuthorityGrade) -> bool:
    """Return whether ``grade`` sits at or above the static-publication floor on the grade ladder."""
    ladder = tuple(RegistryAuthorityGrade)
    return ladder.index(grade) >= ladder.index(static_publication_authority_grade())
