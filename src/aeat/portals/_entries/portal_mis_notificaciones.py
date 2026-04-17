"""Portal: Mis notificaciones."""

from __future__ import annotations

from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_MIS_NOTIFICACIONES,
    url="https://sede.agenciatributaria.gob.es/Sede/notificaciones-comunicaciones/buzon-electronico.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.CONSULTATION,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label={
        "es": "Mis notificaciones",
        "en": "My notifications",
        "hu": "Értesítéseim",
    },
    purpose_es="Buzón electrónico de notificaciones y comunicaciones recibidas de la AEAT.",
)
