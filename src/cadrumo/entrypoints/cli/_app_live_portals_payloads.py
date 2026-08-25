"""Typed JSON transport schemas for the live portals service."""

from __future__ import annotations

from ...core.json_contract import OutputSchema


class PortalEntryPayload(OutputSchema):
    """One local portal-registry catalogue entry.

    Projects :class:`PortalMetadata` from :data:`PORTAL_REGISTRY`, resolving
    translatable labels before the value enters the CLI envelope. Category,
    auth-method, and URL stability fields carry the domain enum values from
    :class:`PortalCategory`, :class:`AuthMethod`, and :class:`UrlStability`.
    """

    portal: str
    category: str
    subdomain: str
    url: str
    auth_methods: str
    url_stability: str
    label: str
    purpose: str
    active: bool


class PortalsListResult(OutputSchema):
    """Typed local-catalogue result for ``aeat app live portals list``.

    Rows are selected from :data:`PORTAL_REGISTRY` directly or through
    :func:`portals_by_category` / :func:`portals_for_modelo`, then projected as
    :class:`PortalEntryPayload`; the command never opens a browser or contacts
    AEAT.
    """

    count: int
    rows: list[PortalEntryPayload]


class PortalsViewResult(PortalEntryPayload):
    """Typed local-catalogue result for ``aeat app live portals view``.

    The requested portal id resolves through :func:`get_portal` and emits the
    same :class:`PortalEntryPayload` projection as the list surface.
    """


__all__ = [
    "PortalEntryPayload",
    "PortalsListResult",
    "PortalsViewResult",
]
