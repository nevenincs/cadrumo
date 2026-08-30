"""Catalogue entry for the Cl@ve whole-of-government identity provider root.

Exposes :data:`ENTRY`, a :class:`PortalMetadata` record for
:class:`Portal` ``PORTAL_CLAVE_IDP_ROOT`` under :class:`PortalCategory`
``AUTH``. Hosted on the central Cl@ve identity-provider origin; in
scope because the scraper hands off to it during Cl@ve flows.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CLAVE_IDP_ROOT,
    path=portal_path(Portal.PORTAL_CLAVE_IDP_ROOT),
    subdomain=PortalHost.CLAVE_GOB,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.ANONYMOUS,),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    label="entries.portal_clave_idp_root.label",
    purpose="entries.portal_clave_idp_root.purpose",
)
"""Frozen :class:`cadrumo.domain.portals.PortalMetadata` for the Cl@ve IdP root page."""
