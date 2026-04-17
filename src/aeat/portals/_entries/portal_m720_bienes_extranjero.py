"""Portal: Modelo 720 — bienes y derechos en el extranjero."""

from __future__ import annotations

from aeat.models import ModeloCode
from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M720_BIENES_EXTRANJERO,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI34.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_720,
    label={
        "es": "Modelo 720 — Bienes y derechos en el extranjero",
        "en": "Modelo 720 — Foreign assets and rights",
        "hu": "720-as űrlap — Külföldi vagyontárgyak és jogok",
    },
    purpose_es="Declaración informativa sobre bienes y derechos situados en el extranjero.",
)
