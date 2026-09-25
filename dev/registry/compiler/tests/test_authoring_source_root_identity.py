"""The development source-root memo answers for one authority, never its address.

``source_root_for`` hands a development tool the mutable evidence root a
compilation was made from, and the memo behind it is keyed by ``id(authority)``.
CPython reuses the address of a collected object, and a development process
compiles many short-lived authorities over temporary trees -- the edition-delta
migration alone builds one per scratch registry -- so an entry made for a
scratch tree can outlive its authority and sit under an address a later,
unrelated authority is allocated at. Answering from that entry would hand one
compilation another's evidence root, and nothing downstream could tell.

These tests own the module's state around each case rather than assuming a clean
process, because the memo is process-wide by design.

An authority here is constructed without compiling a registry: the memo treats
it as an opaque identity and reads none of its fields, so identity is the whole
of what is under test.
"""

from __future__ import annotations

import gc
from collections.abc import Generator
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError

from .. import authority_state
from ..authority_state import register_authoring_authority, source_root_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SCRATCH_ROOT = Path("scratch-migration-tree")
_BUNDLED_ROOT = Path("bundled-tree")


def _authority() -> ValidatedRegistryAuthority:
    """Return an authority instance used only as an identity."""
    return ValidatedRegistryAuthority.__new__(ValidatedRegistryAuthority)


@pytest.fixture(autouse=True)
def isolated_memo() -> Generator[None]:
    """Restore whatever the process already held, so these cases own the memo."""
    with authority_state._state_lock:
        preserved = dict(authority_state._authority_sources)
        authority_state._authority_sources.clear()
    try:
        yield
    finally:
        with authority_state._state_lock:
            authority_state._authority_sources.clear()
            authority_state._authority_sources.update(preserved)


def test_a_registered_authority_resolves_to_the_root_it_was_compiled_from() -> None:
    authority = _authority()
    register_authoring_authority(authority, source_root=_BUNDLED_ROOT)

    assert source_root_for(authority) == _BUNDLED_ROOT


def test_an_unregistered_authority_is_refused() -> None:
    with pytest.raises(RegistrySnapshotError, match="compiler-owned authority"):
        source_root_for(_authority())


def test_a_dead_authoritys_entry_is_not_served_to_whatever_reuses_its_address() -> None:
    """MUTATION: the exact address-reuse the id key cannot rule out.

    A scratch-tree entry is placed under a live authority's address, standing in
    for the allocator handing that address to a new object, and its own
    authority is then collected. Serving the entry would answer the live
    authority with a scratch tree it never compiled.
    """
    live = _authority()
    collected = _authority()
    register_authoring_authority(collected, source_root=_SCRATCH_ROOT)
    with authority_state._state_lock:
        authority_state._authority_sources[id(live)] = authority_state._authority_sources.pop(id(collected))
    del collected
    gc.collect()

    with pytest.raises(RegistrySnapshotError, match="compiler-owned authority"):
        source_root_for(live)


def test_a_live_authority_keeps_answering_beside_a_collected_neighbour() -> None:
    """The refusal above is identity, not a blanket invalidation on collection."""
    live = _authority()
    register_authoring_authority(live, source_root=_BUNDLED_ROOT)
    collected = _authority()
    register_authoring_authority(collected, source_root=_SCRATCH_ROOT)
    del collected
    gc.collect()

    assert source_root_for(live) == _BUNDLED_ROOT


def test_registering_drops_entries_whose_authority_is_gone() -> None:
    """The memo is process-wide, so dead entries must not accumulate forever."""
    for _ in range(5):
        register_authoring_authority(_authority(), source_root=_SCRATCH_ROOT)
    gc.collect()
    survivor = _authority()
    register_authoring_authority(survivor, source_root=_BUNDLED_ROOT)

    with authority_state._state_lock:
        remaining = dict(authority_state._authority_sources)
    assert [root for _reference, root in remaining.values()] == [_BUNDLED_ROOT]
