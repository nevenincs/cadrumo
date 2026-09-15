"""Pytest controls for the development registry compiler.

The mutable registry compiler has process-local loader and fingerprint caches.
Their session boundary belongs to this development-only tree: shipped Cadrumo
tests consume the published authority and must not import the authoring
compiler merely to clear its caches.
"""

from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolate_registry_caches() -> Iterator[None]:
    """Clear development compiler caches at each pytest session boundary."""
    from .compiler.loader import load_registry_tree_cached
    from .compiler.loader_fingerprints import clear_fingerprint_cache

    def _reset() -> None:
        load_registry_tree_cached.cache_clear()
        clear_fingerprint_cache()

    _reset()
    yield
    _reset()


@pytest.fixture(scope="module")
def governed_fact_scope() -> Iterator[None]:
    """Resolve registry tokens in a requesting module against the compiled authored facts.

    Governed-fact resolvers refuse to run without an explicit authority scope.
    Modules whose test bodies construct registry-validated values request this
    fixture instead of relying on an ambient scope.
    """
    from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts

    from .compiler.authority import compiled_bundled_authority

    with validating_governed_facts(compiled_bundled_authority()):
        yield
