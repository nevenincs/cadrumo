"""AEAT portal catalogue and metadata.

This subpackage exposes the strict pydantic v2 registry of AEAT and
adjacent portal metadata used by the project. The registry is built at import
time from the per-portal entries under the private ``_entries`` package and is
frozen as a :class:`types.MappingProxyType`. Each entry is a
:class:`PortalMetadata` record keyed by a :class:`PortalCategory` and
identified by a :class:`Portal` code.

Consumers outside :mod:`aeat.domain.portals` MUST import from this module
only; the underscore-prefixed submodules are internal and unstable.
The public surface is the :data:`__all__` tuple below.

The heavy imports (``_metadata``, ``_registry``) load lazily via
``__getattr__`` so importing portal enums does not materialise the full
catalogue. The first access to any registry name loads the full catalogue.

Modelo filing linkage is resolved from validated calculation registry data.
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
