"""Shared support for registry catalogue verification tests."""

from __future__ import annotations

from functools import cache

from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.tests.registry_tree import bundled_registry_tree

__all__ = ["registry_tree"]

_FORMAL_WITHHOLDING_MODELOS = frozenset({"111", "115", "123", "180", "190", "193"})
_M100_WITHHOLDING_IMPORT_SECTIONS = frozenset({"bindings", "relations", "dependency_classifications"})
_FORMAL_WITHHOLDING_ARTICLE_REF = "rd-439-2007:art-108"
_FRACTIONAL_PAYMENT_ARTICLE_REF = "rd-439-2007:art-109"


@cache
def registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    modelos, catalogues = bundled_registry_tree()
    return tuple(modelos), catalogues


def _catalogues() -> RegistryCatalogues:
    _, catalogues = registry_tree()
    return catalogues
