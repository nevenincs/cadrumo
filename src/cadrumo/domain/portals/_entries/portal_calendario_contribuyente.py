"""Catalogue entry for the AEAT *Calendario del contribuyente* reference page.

Exposes :data:`ENTRY`, a frozen :class:`PortalMetadata` record identified
by the :class:`Portal` code ``PORTAL_CALENDARIO_CONTRIBUYENTE`` under
the :class:`PortalCategory` member
:attr:`cadrumo.domain.portals.PortalCategory.CALENDAR_REFERENCE`.
"""

from __future__ import annotations

from ..categories import AuthMethod, PortalCategory, PortalHost, UrlStability
from ..codes import Portal
from ..metadata import PortalMetadata
from .common import build_entry, portal_path

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CALENDARIO_CONTRIBUYENTE,
    path=portal_path(Portal.PORTAL_CALENDARIO_CONTRIBUYENTE),
    subdomain=PortalHost.SEDE,
    category=PortalCategory.CALENDAR_REFERENCE,
    auth_methods=(AuthMethod.ANONYMOUS,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_calendario_contribuyente.label",
    purpose="entries.portal_calendario_contribuyente.purpose",
)
"""Frozen :class:`cadrumo.domain.portals.PortalMetadata` for the taxpayer calendar reference page."""
