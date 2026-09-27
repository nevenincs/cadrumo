"""The filing year the installed-CLI journeys run for, read from the published support envelope.

A journey refuses any coordinate the published authority only projects from
another year's edition.  The horizon exercise carries its Modelo 390 annual
summary forward from an earlier authored edition, so the newest exercise every
journey can prove end to end is the one immediately below the horizon.
"""

from __future__ import annotations

from pathlib import Path

from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority


def newest_fully_authored_journey_year(authority_root: Path) -> int:
    """Return the exercise below the published support horizon.

    The journey's own admission check still verifies, before any side effect,
    that each exercised coordinate is authored for this year, so a generation
    that stops authoring it fails loudly instead of running a projected year.
    """
    authority = IndexedRegistryAuthority(authority_root.resolve(strict=True) / "authority.current.json")
    try:
        with authority.operation() as operation:
            return operation.supported_filing_years().horizon - 1
    finally:
        authority.close()
