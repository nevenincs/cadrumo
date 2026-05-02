"""Authoritative AEAT portal catalogue and metadata.

This subpackage exposes the closed, strict, pydantic v2 registry of
every AEAT (and adjacent) portal the project interacts with for
Spanish autónomo and small-SL tax filing. Membership is fixed at 42
entries (8 AUTH + 21 FILING/CENSUS + 2 BORRADOR + 4 CONSULTATION + 5
PAYMENT + 2 CALENDAR_REFERENCE). The registry is built at import time
from the per-portal entries under the private ``_entries`` package and
is frozen as a :class:`types.MappingProxyType`.

Consumers outside :mod:`aeat.domain.portals` MUST import from this module
only; the underscore-prefixed submodules are internal and unstable.
The public surface is the :data:`__all__` tuple below.

The heavy imports (``_metadata``, ``_registry``) load lazily via
``__getattr__`` so that :mod:`aeat.domain.modelos._metadata` can import
:class:`Portal` without triggering the circular dependency chain
``models → portals → models``. The first access to any registry name
materialises the full catalogue.

Modelo cross-reference is tied to :class:`aeat.domain.modelos.ModeloCode` —
every ``ModeloCode`` member has at least one FILING or CENSUS portal
backing it (``ModeloCode.MODELO_037`` is the sole retired carve-out).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
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
    }
)


def __getattr__(name: str) -> Any:
    """Lazily materialise the registry surface on first access.

    Keeping ``_metadata`` / ``_registry`` out of the eager import chain
    lets :mod:`aeat.domain.modelos._metadata` import :class:`Portal` without
    inducing a circular import through :mod:`aeat.domain.portals._metadata`
    (which itself imports from :mod:`aeat.domain.modelos`).
    """
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
    "PortalIntegrityError",
    "PortalMetadata",
    "PortalRegistryError",
    "Subdomain",
    "UnknownPortalError",
    "UrlStability",
    "get_portal",
    "portals_by_category",
    "portals_for_modelo",
)
