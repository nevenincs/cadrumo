"""Local portal-registry discovery service.

The portals surface is **local-only**: it does not contact AEAT, does
not call :meth:`core.access_gate.AeatAccessGate.require_live_read`,
and emits no bucket events. CLI-facing callers consume it to discover
catalogued AEAT portals — their canonical URLs, auth methods, stability
tiers, and purpose strings — without leaving the local catalogue boundary.

Verbs::

  list [--category C] [--modelo M]   filter the registry by category
                                     and/or modelo binding.
  view/show PORTAL                   render one portal's metadata row.

Portals expose **no action verbs**: ``open``, ``submit``, ``present``,
``sign``, and ``pay`` are intentionally absent from this service. The
catalogue is metadata-only.

The service projects domain :class:`domain.portals.PortalMetadata`
records into :class:`PortalRow` values keyed by
:class:`domain.portals.Portal` and grouped by
:class:`domain.portals.PortalCategory`.

See Also:
    :class:`PortalsService`
        Local projection service over the immutable portal catalogue.
    :class:`PortalRow`
        Operator-facing row shape produced by ``list`` and ``show``.
    :data:`domain.portals.PORTAL_REGISTRY`
        Authoritative local registry of portal metadata.
    :func:`domain.portals.portals_for_modelo`
        Domain helper for modelo-to-portal cross-references.
    :class:`domain.portals.PortalMetadata`
        Canonical domain metadata record projected by this facade.
    :class:`~ModeloCode`
        Modelo identifier used by the optional portal filter.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
