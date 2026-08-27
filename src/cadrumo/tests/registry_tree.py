"""Canonical compiled-registry-tree accessor for tests in any package."""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

from ..core.resources import bundled_path
from ..domain.calculations.registry.loader import load_registry_tree

if TYPE_CHECKING:
    from ..domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues


@cache
def bundled_registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Return the compiled bundled registry, loaded once per process.

    ``load_registry_tree`` carries no memo of its own. Four consecutive calls in
    one process measured 15.62s, 3.10s, 4.67s and 15.29s -- the spread is the
    fingerprint-keyed disk cache hitting or missing while the tree is edited,
    and the floor is never free. Across the suite 66 call sites in 45 test
    modules made that call, so a module asking twice paid twice for one answer.

    ``@cache`` on a function taking no arguments holds exactly one entry, which
    is the point: there is one bundled tree. A test needing a DIFFERENT root
    calls ``load_registry_tree`` directly and is unaffected -- this accessor
    cannot serve another root, so it cannot answer for one by mistake.

    Sound because the bundled tree does not change while a test session runs.
    A test that edits a registry tree and reloads it must use its own root, and
    will then be calling the uncached function anyway.

    Handing every caller the SAME objects is safe by construction rather than by
    convention: ``ModeloDefinition`` and ``RegistryCatalogues`` are both declared
    ``frozen``, and an attempted attribute write raises. A caller deriving a
    variant does so with ``model_copy(update=...)``, which leaves the shared
    originals untouched. Were they mutable this accessor would be a hazard --
    one test's edit would reach every later test in the worker.

    Returns:
        The compiled modelos and the shared registry catalogues.
    """
    return load_registry_tree(bundled_path("registry", "aeat"))


__all__ = ["bundled_registry_tree"]
