"""Shared support for registry catalogue verification tests."""

from __future__ import annotations

from functools import cache

from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.tests.registry_tree import bundled_registry_tree

__all__ = ["authored_catalogues", "registry_tree"]

_FORMAL_WITHHOLDING_MODELOS = frozenset({"111", "115", "123", "180", "190", "193"})
_FORMAL_WITHHOLDING_ARTICLE_REF = "rd-439-2007:art-108"
_FRACTIONAL_PAYMENT_ARTICLE_REF = "rd-439-2007:art-109"


@cache
def registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    modelos, catalogues = bundled_registry_tree()
    return tuple(modelos), catalogues


def _catalogues() -> RegistryCatalogues:
    _, catalogues = registry_tree()
    return catalogues


def authored_catalogues() -> RegistryCatalogues:
    """Return the catalogues of the COMMITTED authoring tree, not the published view.

    ``registry_tree`` above is the published view, and it carries only the
    legal and source references published modelos cite. Historical law, and
    law cited from declarations outside that set, is absent there by design -
    so a check about the committed catalogue's own integrity has to read the
    authored tree or it raises ``KeyError`` on the very references it exists to
    verify.
    """
    from ..conformance.registry_schema_support import committed_registry_tree

    _modelos, catalogues = committed_registry_tree()
    return catalogues
