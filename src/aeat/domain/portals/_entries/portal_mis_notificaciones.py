"""Portal: Mis notificaciones."""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

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
