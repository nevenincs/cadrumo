"""Wiring contract for the profile-key reverse grounding index.

Grounded against the bundled validated registry (the authority the
calculation engine itself consumes) — the expectations below quote
grounding the registry TOML declares, never values invented for the test.
"""

from __future__ import annotations

import pytest

from .....core import Modelo
from .....core.resources import resources
from .. import ProfileKeyGrounding, build_profile_grounding_index

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def index() -> dict[str, ProfileKeyGrounding]:
    return dict(build_profile_grounding_index(resources().modelos.authority))


def test_index_inverts_the_censo_status_binding(index: dict[str, ProfileKeyGrounding]) -> None:
    """The M036 censo-status binding's declared grounding survives inversion intact."""
    grounding = index["censo.status"]
    assert Modelo.M036 in grounding.modelos
    assert "rd-1065-2007:art-9" in grounding.legal_refs
    assert "orden-eha-1274-2007:art-1" in grounding.legal_refs
    assert "aeat-modelo-036-procedure" in grounding.source_refs


def test_every_entry_is_sorted_union_shape(index: dict[str, ProfileKeyGrounding]) -> None:
    """Entries are deterministic: sorted keys, sorted tuple unions, no empties."""
    assert list(index) == sorted(index)
    for key, grounding in index.items():
        assert grounding.profile_key == key
        assert grounding.modelos, key
        assert list(grounding.legal_refs) == sorted(set(grounding.legal_refs))
        assert list(grounding.source_refs) == sorted(set(grounding.source_refs))


def test_unconsumed_keys_are_absent_not_empty(index: dict[str, ProfileKeyGrounding]) -> None:
    """A key no profile binding consumes renders no legal zone — absent, never invented."""
    assert "identity.notes" not in index
    assert all(grounding.legal_refs or grounding.source_refs for grounding in index.values())


def test_index_spans_multiple_modelos(index: dict[str, ProfileKeyGrounding]) -> None:
    """Profile bindings exist across several modelos, not only M036."""
    consuming = {modelo for grounding in index.values() for modelo in grounding.modelos}
    assert len(consuming) >= 3
    assert Modelo.M036 in consuming
