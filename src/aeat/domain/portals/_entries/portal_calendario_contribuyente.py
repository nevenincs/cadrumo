"""Catalogue entry for the AEAT *Calendario del contribuyente* reference page.

Exposes :data:`ENTRY`, a frozen :class:`aeat.domain.portals.PortalMetadata`
under :attr:`aeat.domain.portals.PortalCategory.CALENDAR_REFERENCE`.
"""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CALENDARIO_CONTRIBUYENTE,
    path="/Sede/ayuda/manuales-videos-folletos/calendario-contribuyente.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.CALENDAR_REFERENCE,
    auth_methods=(AuthMethod.ANONYMOUS,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label="entries.portal_calendario_contribuyente.label",
    purpose="entries.portal_calendario_contribuyente.purpose",
)
"""Frozen :class:`aeat.domain.portals.PortalMetadata` for the taxpayer calendar reference page."""
