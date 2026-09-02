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
by validated :mod:`domain.calculations.registry` application links for a
:class:`~ModeloCode`.

Consumers import from the owning module -- :mod:`categories`, :mod:`codes`,
:mod:`drift`, :mod:`hosts`, :mod:`metadata`, :mod:`registry`, :mod:`errors` --
rather than from this package root, which is inert. This package describes portal,
filing, borrador, censo, auth, payment, and consultation metadata only. It does
not open portals, submit returns, sign, pay, mark notifications read, or perform
live AEAT access; those operations belong to application and adapter layers.

See Also:
    :mod:`application.live`
        Read-only remote observation workflows that may consult portal metadata
        before entering an access-gated live path.
    :mod:`domain.calculations.registry`
        Validated application links that declare modelo-to-portal references
        consumed by :func:`portals_for_modelo`.
    :class:`core.access_gate.AeatAccessGate`
        Live-read/live-write gate; this metadata package never invokes it.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
"""Inert namespace: every contract is reached at the module that defines it."""
