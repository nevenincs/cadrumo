"""The filing year the installed-CLI journeys run for, read from the published support envelope.

A journey refuses any coordinate the published authority only projects from
another year's edition, or answers below filing grade.  The annual summary is
the last Modelo 390 edition the published authority authors at filing grade, so
the newest exercise every journey can prove end to end is that edition's.
"""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority


def newest_fully_authored_journey_year(authority_root: Path) -> int:
    """Return the exercise of the newest Modelo 390 edition the published authority authors at filing grade.

    An edition authored below filing grade, such as one whose Orden precedes
    AEAT's record design, cannot answer the journey's filing snapshot, so it is
    not a journey year. The journey's own admission check still verifies, before
    any side effect, that each exercised coordinate is authored for this year, so
    a generation that stops authoring it fails loudly instead of running a
    projected year.
    """
    authority = IndexedRegistryAuthority(authority_root.resolve(strict=True) / "authority.current.json")
    try:
        with authority.operation() as operation:
            return max(
                revision.valid_from.year
                for revision in operation.modelo_directory("390").revisions
                if operation.revision("390", str(revision.id)).effective_authority_grade
                is RegistryAuthorityGrade.FILING
            )
    finally:
        authority.close()
