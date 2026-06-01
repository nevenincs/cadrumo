"""Local portal-registry discovery service.

The portals surface is **local-only**: it does not contact AEAT, does
not call :func:`AeatAccessGate.require_live_read`, and emits no bucket
events. Operators consume it to discover catalogued AEAT portals —
their canonical URLs, auth methods, stability tiers, and purpose
strings — without leaving the CLI.

Verbs::

  list [--category C] [--modelo M]   filter the registry by category
                                     and/or modelo binding.
  show PORTAL                        render one portal's full metadata.

Portals expose **no action verbs**: ``open``, ``submit``, ``present``,
``sign``, and ``pay`` are intentionally absent from this service. The
catalogue is metadata-only.
"""

from __future__ import annotations

from ._service import (
    PortalNotFoundError,
    PortalRow,
    PortalsService,
)

__all__ = [
    "PortalNotFoundError",
    "PortalRow",
    "PortalsService",
]
