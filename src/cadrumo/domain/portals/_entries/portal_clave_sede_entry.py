"""Catalogue entry for the AEAT Sede *Cl@ve* gateway page.

Exposes :data:`ENTRY`, a :class:`PortalMetadata` record for
:class:`Portal` ``PORTAL_CLAVE_SEDE_ENTRY`` under
:class:`PortalCategory` ``AUTH``. Anonymous landing page that
redirects authenticated users to the central Cl@ve identity-provider origin.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CLAVE_SEDE_ENTRY,
    path=portal_path(Portal.PORTAL_CLAVE_SEDE_ENTRY),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.ANONYMOUS,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_clave_sede_entry.label",
    purpose="entries.portal_clave_sede_entry.purpose",
)
"""Frozen :class:`cadrumo.domain.portals.PortalMetadata` for the Sede Cl@ve gateway page."""
