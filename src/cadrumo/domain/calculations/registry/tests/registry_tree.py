"""Canonical compiled-registry-tree accessor for registry-aware tests."""

from __future__ import annotations

from functools import cache

from ..authority import bundled_authority
from ..schema import ModeloDefinition, RegistryCatalogues


@cache
def bundled_registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Return the immutable bundled registry published for runtime use.

    Test fixtures that need a mutable source tree must live in the development
    authoring test lane.  This accessor is deliberately limited to the
    published artifact, so shared source tests do not reach ``dev`` or a root
    test-support package just to obtain bundled facts.
    """
    authority = bundled_authority()
    return authority.modelos, authority.catalogues


__all__ = ["bundled_registry_tree"]
