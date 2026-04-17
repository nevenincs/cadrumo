"""Portal: Domiciliación bancaria."""

from __future__ import annotations

from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_DOMICILIACION_BANCARIA,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GA16.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.PAYMENT,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    label={
        "es": "Domiciliación bancaria",
        "en": "Bank-account direct debit",
        "hu": "Banki csoportos beszedés",
    },
    purpose_es="Alta, consulta y revocación de domiciliaciones bancarias de autoliquidaciones.",
)
