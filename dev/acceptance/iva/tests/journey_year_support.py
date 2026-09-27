"""The filing year the installed-CLI journeys run for, read from the published support envelope.

A journey refuses any coordinate the published authority only projects from
another year's edition.  The annual summary is the last Modelo 390 edition the
published authority authors, so the newest exercise every journey can prove end
to end is that edition's.
"""

from __future__ import annotations

from pathlib import Path

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority


def newest_fully_authored_journey_year(authority_root: Path) -> int:
    """Return the exercise of the newest Modelo 390 edition the published authority authors.

    The journey's own admission check still verifies, before any side effect,
    that each exercised coordinate is authored for this year, so a generation
    that stops authoring it fails loudly instead of running a projected year.
    """
    authority = IndexedRegistryAuthority(authority_root.resolve(strict=True) / "authority.current.json")
    try:
        with authority.operation() as operation:
            return max(revision.valid_from.year for revision in operation.modelo_directory("390").revisions)
    finally:
        authority.close()
