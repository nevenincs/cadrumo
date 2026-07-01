"""Public facade for the local AEAT portal metadata catalogue.

This package owns declarative AEAT portal identifiers and metadata used by
registry, schema, and live-read planning surfaces. The facade exposes
:class:`Portal` identifiers, taxonomy enums :class:`PortalCategory`,
:class:`AuthMethod`, :class:`PortalHost`, and :class:`UrlStability`, plus lazy
exports for strict frozen :class:`PortalMetadata` records and the frozen
:data:`PORTAL_REGISTRY` mapping from :class:`Portal` keys to metadata.

Registry assembly validates host names through the central external-constants
catalogue, filing/censo path shape, anonymous-auth exclusivity, retired-portal
replacement links, and complete coverage of every :class:`Portal` member. Use
:func:`get_portal` for one entry, :func:`portals_by_category` for taxonomy
views, and :func:`portals_for_modelo` for filing and borrador portals declared
by validated :mod:`aeat.domain.calculations.registry` application links for a
:class:`~aeat.domain.modelos.ModeloCode`.

Consumers outside :mod:`aeat.domain.portals` import from this package root; the
underscore-prefixed modules are internal. This package describes portal,
filing, borrador, censo, auth, payment, and consultation metadata only. It does
not open portals, submit returns, sign, pay, mark notifications read, or perform
live AEAT access; those operations belong to application and adapter layers.

See Also:
    :mod:`aeat.application.portals`
        Local operator discovery service that projects this catalogue without
        contacting AEAT or emitting bucket events.
    :mod:`aeat.application.live`
        Read-only remote observation workflows that may consult portal metadata
        before entering an access-gated live path.
    :mod:`aeat.domain.calculations.registry`
        Validated application links that declare modelo-to-portal references
        consumed by :func:`portals_for_modelo`.
    :class:`aeat.core.access_gate.AeatAccessGate`
        Live-read/live-write gate; this metadata package never invokes it.
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
