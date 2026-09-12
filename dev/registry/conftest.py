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
