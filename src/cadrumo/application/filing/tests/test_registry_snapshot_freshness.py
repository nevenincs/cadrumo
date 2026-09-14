"""Pin filing snapshot lifetime to the published validated authority."""

from __future__ import annotations

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority

from ....core.period import Period
from ..draft_construction import _load_registry_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO = "130"
_PERIOD = Period(filing_year=2024, code="1T")


def test_snapshot_resolution_uses_only_the_authority_private_cache() -> None:
    """Repeated filing resolution reuses the authority entry while isolating callers."""
    authority = compiled_bundled_authority()

    first = _load_registry_snapshot(modelo=_MODELO, period=_PERIOD)
    cache_size = len(authority._snapshots)
    warm = _load_registry_snapshot(modelo=_MODELO, period=_PERIOD)

    assert warm == first
    assert warm is not first
    assert len(authority._snapshots) == cache_size


def test_snapshot_resolution_exposes_no_cache_handle() -> None:
    """``_load_registry_snapshot`` must carry no memoization wrapper.

    Structural companion to the behavioural test above: ``functools`` caches
    expose ``cache_clear``/``cache_info``, so their absence pins the intent even
    if a future change makes the staleness window harder to trigger.
    """
    for attribute in ("cache_clear", "cache_info", "__wrapped__"):
        assert not hasattr(_load_registry_snapshot, attribute), (
            f"_load_registry_snapshot exposes {attribute!r}, so it is memoized above the registry "
            "loader; such a cache is keyed without the registry-tree fingerprint and can serve a "
            "snapshot from before a registry change"
        )


def test_law_determined_resolution_is_preserved() -> None:
    """Resolution stays driven by ``(modelo, filing_year, period)``.

    Two different filing years for the same period token must not collapse onto
    one another, and the resolved revision must be the one the registry's own
    temporal selection returns for that context.
    """
    authority = compiled_bundled_authority()

    for filing_year in (2023, 2024):
        period = Period(filing_year=filing_year, code="1T")
        resolved = _load_registry_snapshot(modelo=_MODELO, period=period)
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
