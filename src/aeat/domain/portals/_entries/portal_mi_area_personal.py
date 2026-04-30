"""Portal: Mi área personal."""

from __future__ import annotations

from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_MI_AREA_PERSONAL,
    url="https://sede.agenciatributaria.gob.es/Sede/area-personal.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.AUTH,
    auth_methods=(
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label={
        "es": "Mi área personal",
        "en": "My personal area",
        "hu": "Személyes felületem",
    },
    purpose_es="Punto de entrada autenticado al área personal del contribuyente.",
)
