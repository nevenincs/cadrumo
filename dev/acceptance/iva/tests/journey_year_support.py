"""The filing year the installed-CLI journeys run for, read from the published support envelope.

A journey refuses any coordinate the published authority only projects from
another year's edition, or answers below filing grade.  The annual summary is
the last Modelo 390 edition the published authority authors at filing grade, so
the newest exercise every journey can prove end to end is that edition's.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority

from ..filing_year import IvaFilingYearUnsupportedError, require_journey_year


def _year_has_ended(year: int) -> bool:
    """Whether ``year`` has closed today, so its last quarter can be observed and attested.

    The journeys record the fourth quarter's Modelo 390 attestation on 31 December, and the
    application refuses an observation dated after the moment it is recorded.
    """
    return datetime.now(UTC).date() > date(year, 12, 31)


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
                and _year_has_ended(revision.valid_from.year)
            )
    finally:
        authority.close()


def supported_journey_years(authority_root: Path, coordinates: tuple[tuple[str, str], ...]) -> tuple[int, ...]:
    """Return every year of the published support envelope the authority authors for each of ``coordinates``.

    The envelope decides which years exist and the journey's own admission decides which of them it can
    run, so no year list is kept here.
    """
    authority = IndexedRegistryAuthority(authority_root.resolve(strict=True) / "authority.current.json")
    try:
        with authority.operation() as operation:
            envelope_years = tuple(operation.supported_filing_years().years)
    finally:
        authority.close()
    supported: list[int] = []
    for year in envelope_years:
        if not _year_has_ended(year):
            continue
        try:
            require_journey_year(authority_root=authority_root, year=year, coordinates=coordinates)
        except IvaFilingYearUnsupportedError:
            continue
        supported.append(year)
    return tuple(supported)
