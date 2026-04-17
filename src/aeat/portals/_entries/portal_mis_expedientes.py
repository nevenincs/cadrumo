"""Portal: Mis expedientes."""

from __future__ import annotations

from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_MIS_EXPEDIENTES,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/ZZ09.shtml",
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
        "es": "Mis expedientes",
        "en": "My case files",
        "hu": "Aktáim",
    },
    purpose_es="Consulta del estado de los expedientes administrativos del contribuyente.",
)
