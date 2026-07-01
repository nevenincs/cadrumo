"""Public facade for the local AEAT portal metadata catalogue.

The facade exposes :class:`Portal` identifiers, taxonomy enums
:class:`PortalCategory`, :class:`AuthMethod`, :class:`PortalHost`, and
:class:`UrlStability`, strict frozen :class:`PortalMetadata` records, and the
frozen :data:`PORTAL_REGISTRY` mapping from :class:`Portal` keys to metadata.

Use :func:`get_portal` for one portal, :func:`portals_by_category` to filter on
the :class:`PortalCategory` axis carried by metadata, and
:func:`portals_for_modelo` for modelo-linked filing and borrador portals
derived from :mod:`aeat.domain.calculations.registry` application links.

Consumers outside :mod:`aeat.domain.portals` import from this package root; the
underscore-prefixed modules are internal. This package describes portal, filing,
borrador, censo, and modelo metadata only; it does not open portals, submit
returns, sign, pay, or perform live AEAT access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ._codes import Portal
from ._errors import (
    PortalIntegrityError,
    PortalRegistryError,
    UnknownPortalError,
)

if TYPE_CHECKING:
    from ._metadata import PortalMetadata
    from ._registry import (
        PORTAL_REGISTRY,
        get_portal,
        portals_by_category,
        portals_for_modelo,
    )

_LAZY_NAMES: frozenset[str] = frozenset(
    {
        "PORTAL_REGISTRY",
        "PortalMetadata",
        "get_portal",
        "portals_by_category",
        "portals_for_modelo",
    },
)


def __getattr__(name: str) -> object:
    """Lazily materialise the registry surface on first access."""
    if name not in _LAZY_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from . import _metadata, _registry

    resolved = {
        "PORTAL_REGISTRY": _registry.PORTAL_REGISTRY,
        "PortalMetadata": _metadata.PortalMetadata,
        "get_portal": _registry.get_portal,
        "portals_by_category": _registry.portals_by_category,
        "portals_for_modelo": _registry.portals_for_modelo,
    }
    value = resolved[name]
    globals()[name] = value
    return value


__all__ = (
    "PORTAL_REGISTRY",
    "AuthMethod",
    "Portal",
    "PortalCategory",
    "PortalHost",
    "PortalIntegrityError",
    "PortalMetadata",
    "PortalRegistryError",
    "UnknownPortalError",
    "UrlStability",
    "get_portal",
    "portals_by_category",
    "portals_for_modelo",
)
