"""Portal: Modelo 200 — IS autoliquidación anual."""

from __future__ import annotations

from aeat.models import ModeloCode
from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M200_SOCIEDADES_ANUAL,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GE04.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_200,
    label={
        "es": "Modelo 200 — Impuesto sobre Sociedades (anual)",
        "en": "Modelo 200 — Corporate income tax (annual)",
        "hu": "200-as űrlap — Társasági adó (éves)",
    },
    purpose_es="Autoliquidación anual del Impuesto sobre Sociedades.",
)
