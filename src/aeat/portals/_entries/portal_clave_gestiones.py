"""Portal: Cl@ve gestiones (password + registration)."""

from __future__ import annotations

from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_CLAVE_GESTIONES,
    url="https://sede.agenciatributaria.gob.es/Sede/clave-pin/gestiones.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(AuthMethod.CLAVE_PERMANENTE,),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label={
        "es": "Gestiones Cl@ve PIN",
        "en": "Cl@ve PIN self-service",
        "hu": "Cl@ve PIN önkiszolgáló",
    },
    purpose_es="Gestiones Cl@ve: registro, recuperación y renovación de contraseñas.",
)
