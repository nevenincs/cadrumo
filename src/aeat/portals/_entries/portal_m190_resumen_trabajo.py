"""Portal: Modelo 190 — resumen anual retenciones trabajo."""

from __future__ import annotations

from aeat.models import ModeloCode
from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M190_RESUMEN_TRABAJO,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI10.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_190,
    label={
        "es": "Modelo 190 — Resumen anual retenciones trabajo",
        "en": "Modelo 190 — Annual summary of labour withholdings",
        "hu": "190-es űrlap — Éves munkabér-forrásadó összefoglaló",
    },
    purpose_es=(
        "Resumen anual de retenciones e ingresos a cuenta sobre trabajo y actividades (complementa al Modelo 111)."
    ),
)
