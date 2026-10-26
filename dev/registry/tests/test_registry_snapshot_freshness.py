"""Pin filing snapshot lifetime to the validated authority that serves it."""

from __future__ import annotations

import pytest

from cadrumo.application.filing.runtime import RegistrySchemaAccessor, schema_provider_from_authority
from cadrumo.core.period import Period

from ..compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "130"
_PERIOD = Period(filing_year=2024, code="1T")


def _schema_provider(period: Period) -> RegistrySchemaAccessor:
    """Project the compiled authority through the filing snapshot boundary."""
    return schema_provider_from_authority(
        compiled_bundled_authority(),
        modelos=(_MODELO,),
        filing_year=period.filing_year,
        period=period,
    )


def test_snapshot_resolution_uses_only_the_authority_private_cache() -> None:
    """Repeated filing resolution serves the pinned entry without growing the cache.

    Each call builds its own schema provider, so a second resolution that added
    an entry would mean the cache is keyed on the caller rather than on the
    filing coordinate. The resolved snapshot is the exact pinned object: it is a
    frozen registry model, so handing every caller the same instance is the
    cheap reuse the pinning exists for, not shared mutable state.
    """
    authority = compiled_bundled_authority()

    first = _schema_provider(_PERIOD).get_snapshot(_MODELO)
    cache_size = len(authority._snapshots)
    warm = _schema_provider(_PERIOD).get_snapshot(_MODELO)

    assert warm == first
    assert warm is first
    assert len(authority._snapshots) == cache_size


def test_law_determined_resolution_is_preserved() -> None:
    """Resolution stays driven by ``(modelo, filing_year, period)``.

    Two different filing years for the same period token must not collapse onto
    one another, and the resolved revision must be the one the registry's own
    temporal selection returns for that context.
    """
    authority = compiled_bundled_authority()

    for filing_year in (2023, 2024):
        period = Period(filing_year=filing_year, code="1T")
        resolved = _schema_provider(period).get_snapshot(_MODELO)
        expected = authority.snapshot(_MODELO, filing_year=filing_year, period="1T")
        assert resolved.revision.id == expected.revision.id, (
            f"filing year {filing_year} resolved revision {resolved.revision.id!r}, but the "
            f"registry authority selects {expected.revision.id!r} for that context"
        )
        # Asserted rather than assumed: filing_period is Optional on the
        # snapshot schema, so dereferencing it unguarded would surface a
        # missing period as an AttributeError inside the comparison rather
        # than as the failure it is. A snapshot resolved for a period must
        # carry one.
        assert resolved.filing_period is not None, f"snapshot for filing year {filing_year} carries no filing_period"
        assert resolved.filing_period.filing_year == filing_year
