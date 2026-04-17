"""Portal: Modelo 390 — resumen anual IVA."""

from __future__ import annotations

from aeat.models import ModeloCode
from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M390_RESUMEN_IVA,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/G412.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_390,
    label={
        "es": "Modelo 390 — Resumen anual IVA",
        "en": "Modelo 390 — Annual VAT summary",
        "hu": "390-es űrlap — Éves IVA-összefoglaló",
    },
    purpose_es="Declaración-resumen anual del IVA (complementa a las autoliquidaciones periódicas del Modelo 303).",
)
