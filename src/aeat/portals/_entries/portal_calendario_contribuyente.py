"""Portal: Calendario del contribuyente."""

from __future__ import annotations

from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CALENDARIO_CONTRIBUYENTE,
    url="https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/calendario-contribuyente.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.CALENDAR_REFERENCE,
    auth_methods=(AuthMethod.ANONYMOUS,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label={
        "es": "Calendario del contribuyente",
        "en": "Taxpayer calendar",
        "hu": "Adózói naptár",
    },
    purpose_es="Calendario oficial del contribuyente con los plazos de presentación por modelo.",
)
