"""Guard that the filing layer never memoizes registry snapshots above the loader.

``build_draft`` resolves its registry snapshot through
:func:`cadrumo.application.filing._load_registry_snapshot`. Any cache placed on
that function would be keyed on ``(modelo, period)`` alone — carrying neither the
registry-tree fingerprint nor a TTL — and would therefore sit outside the
invalidation protocol the registry authority defines. The consequence is not a
performance nit: a snapshot pinned from before a registry change decides which
revision's norms a filing is computed under, so a stale one computes a filing
against superseded law with no signal to the operator.

The property this module owns is therefore narrow and exact: *a resolved
snapshot's lifetime must be the authority's, not the process's*. Everything below
runs against the real process authority over the real bundled registry. No
collaborator is substituted and nothing here is a test double.

**How the behavioural proof works, and why it is shaped this way.** A memo above
:func:`_load_registry_snapshot` is invisible while the authority's own snapshot
cache is warm, because both layers hand back the same object. It becomes visible
the instant the layer below is invalidated: a memo-free resolution rebuilds the
snapshot, yielding a new object, while a memoized one returns the object it
pinned. So the test resolves once, evicts exactly that entry from the authority's
cache, and resolves again, asserting the second result is a rebuilt object. The
eviction is invalidation of real state, not substitution of a collaborator:
nothing is re-pointed, replaced, or restored, and the two resolutions carry
byte-identical arguments.

**Why not the shapes that were rejected.** This module previously re-pointed the
process resource registry at a second authority over a second copy of the
registry tree, so one ``(modelo, period)`` could resolve two ways. That worked
only through ``monkeypatch``, and the obvious removals are each wrong. A
hand-rolled save/restore on the same private target hides the construct from the
inventory's AST matcher instead of removing it. A scoped ``override_resources``
in ``core.resources`` is the exact shape ``tests.test_override_seam_singularity``
forbids with no allowlist and no baseline; ``override_settings`` is sanctioned
only because it has real production callers scoping a call tree, and a seam
existing for one test is a test-hook setter rather than production dependency
injection. The third shape carries a trap worth keeping on the record: threading
an ``authority`` parameter through would let a naive ``@cache`` key on
``(modelo, period, authority)`` instead of ``(modelo, period)``, so a
two-distinct-authorities setup stops colliding and the behavioural test passes
with the defect present — removing the substitution that way silently guts the
test. The eviction proof is immune to that trap precisely because it varies
nothing a memo could key on.

**What is deliberately not re-asserted here.** That a changed registry tree
re-derives through a freshly loaded authority is the registry layer's own
contract, proven there against a minimal synthetic tree by
``test_authority_uses_fingerprint_backed_process_cache_and_invalidates`` in
:mod:`cadrumo.domain.calculations.registry.tests.test_authority`. Re-proving it
at this layer would mean copying and re-validating the whole bundled tree —
minutes per run — to restate a fact the owning layer already covers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....core import Period
from ....domain.calculations.registry.authority import bundled_authority
from .. import _load_registry_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

if TYPE_CHECKING:
    from ....domain.calculations.registry.authority import ValidatedRegistryAuthority
    from ....domain.calculations.registry.schema import RegistrySnapshot

_MODELO = "130"
_PERIOD = Period(filing_year=2024, code="1T")


def _evict_from_the_authority_cache(
    authority: ValidatedRegistryAuthority,
    snapshot: RegistrySnapshot,
) -> None:
    """Drop exactly the authority cache entry currently holding ``snapshot``.

    Matched on the cached value rather than on a reconstructed key, so the
    eviction stays correct if the authority's cache key ever gains a dimension.
    When no entry matches, nothing is evicted and the caller's next resolution
    returns the same object, which fails the assertion loudly rather than
    reporting a green on an eviction that never happened.
    """
    for key, cached in list(authority._snapshots.items()):
        if cached is snapshot:
            del authority._snapshots[key]


def test_snapshot_resolution_is_not_memoized_above_the_authority() -> None:
    """Invalidating the authority's snapshot cache must reach the filing resolver.

    Fails loudly if a fingerprint-blind cache is reintroduced on
    ``_load_registry_snapshot``: that memo would outlive the authority's own
    cache entry, so the second resolution would return the pinned object instead
    of a rebuilt one.
    """
    authority = bundled_authority()

    first = _load_registry_snapshot(modelo=_MODELO, period=_PERIOD)
    warm = _load_registry_snapshot(modelo=_MODELO, period=_PERIOD)
    assert warm is first, (
        "control: while the authority holds this snapshot, every resolution must hand back "
        "that one object; if it does not, object identity cannot distinguish a rebuild from "
        "a memo and the assertion below would prove nothing"
    )

    _evict_from_the_authority_cache(authority, first)
    rebuilt = _load_registry_snapshot(modelo=_MODELO, period=_PERIOD)

    assert rebuilt is not first, (
        "registry snapshot resolution returned the snapshot it had resolved before the "
        "authority's cache entry was evicted: a cache above the loader is keyed without the "
        "registry-tree fingerprint, so it outlives the authority that owns invalidation and "
        "a filing would be computed under a superseded revision's norms"
    )
    assert rebuilt.revision.id == first.revision.id, (
        f"rebuilding the snapshot changed the resolved revision from {first.revision.id!r} to "
        f"{rebuilt.revision.id!r}; the registry tree did not change, so resolution is not "
        "deterministic for one filing context"
    )


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
    authority = bundled_authority()

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
