"""Catalogue entry for the Cl@ve whole-of-government identity provider root.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.AUTH`. Hosted on
:attr:`aeat.domain.portals.Subdomain.CLAVE_GOB`; sits adjacent to AEAT but
is in scope because the scraper hands off to it during Cl@ve flows.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CLAVE_IDP_ROOT,
    path="/",
    subdomain=Subdomain.CLAVE_GOB,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.ANONYMOUS,),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_clave_idp_root.label",
    purpose="entries.portal_clave_idp_root.purpose",
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the Cl@ve IdP root page."""
