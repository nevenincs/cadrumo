"""Catalogue entry for the AEAT Sede *Cl@ve* gateway page.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.AUTH`. Anonymous landing
page that redirects authenticated users to ``clave.gob.es``.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CLAVE_SEDE_ENTRY,
    path="/Sede/clave.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.ANONYMOUS,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_clave_sede_entry.label",
    purpose="entries.portal_clave_sede_entry.purpose",
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the Sede Cl@ve gateway page."""
