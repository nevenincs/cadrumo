"""Catalogue entry for the AEAT Sede DNI electrónico (DNIe) entry point.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.AUTH`. Reuses the shared
certificate gateway for credential exchange.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_DNIE_SEDE_ENTRY,
    path="/Sede/dnie-electronico.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.DNIE,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_dnie_sede_entry.label",
    purpose="entries.portal_dnie_sede_entry.purpose",
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the DNIe Sede entry page."""
