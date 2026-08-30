"""Catalogue entry for the AEAT *Cl@ve PIN gestiones* self-service page.

Exposes :data:`ENTRY`, a frozen :class:`PortalMetadata` record identified
by the :class:`Portal` code ``PORTAL_CLAVE_GESTIONES`` under the
:class:`PortalCategory` member
:attr:`cadrumo.domain.portals.PortalCategory.AUTH`, covering password
registration, recovery, and renewal via Cl@ve permanente.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CLAVE_GESTIONES,
    path=portal_path(Portal.PORTAL_CLAVE_GESTIONES),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.CLAVE_PERMANENTE,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_clave_gestiones.label",
    purpose="entries.portal_clave_gestiones.purpose",
)
"""Frozen :class:`cadrumo.domain.portals.PortalMetadata` for the Cl@ve self-service page."""
