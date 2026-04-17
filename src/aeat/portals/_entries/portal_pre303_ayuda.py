"""Portal: Pre303 — ayuda prefilled IVA."""

from __future__ import annotations

from aeat.models import ModeloCode
from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_PRE303_AYUDA,
    url="https://sede.agenciatributaria.gob.es/Sede/iva/autoliquidacion-iva-modelo-303/pre303.html",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.BORRADOR,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PERMANENTE,
    ),
    url_stability=UrlStability.STABLE_WITHIN_CAMPAIGN,
    related_modelo=ModeloCode.MODELO_303,
    label={
        "es": "Pre303 — Ayuda IVA prefilled",
        "en": "Pre303 — Pre-filled VAT helper",
        "hu": "Pre303 — Előzetes IVA kitöltő segéd",
    },
    purpose_es="Servicio de ayuda Pre303: prefilled de casillas del Modelo 303 a partir de libros registro y SII.",
)
