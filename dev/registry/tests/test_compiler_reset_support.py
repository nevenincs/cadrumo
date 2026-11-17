"""A test that resets the compiler leaves the authorities other tests hold usable."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError

from ..compiler.authority import compiled_bundled_authority
from ..compiler.authority_state import source_root_for
from ..maintenance_support import reset_registry_caches
from .compiler_reset_support import held_authorities_kept_registered

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def test_a_reset_forgets_the_source_root_of_an_authority_built_before_it() -> None:
    held = compiled_bundled_authority()
    expected = source_root_for(held)

    with held_authorities_kept_registered():
        reset_registry_caches()
        with pytest.raises(RegistrySnapshotError, match="compiler-owned authority"):
            source_root_for(held)

    assert source_root_for(held) == expected
