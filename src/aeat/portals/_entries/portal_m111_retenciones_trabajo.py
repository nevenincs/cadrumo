"""Portal: Modelo 111 — retenciones trabajo y actividades."""

from __future__ import annotations

from aeat.models import ModeloCode
from aeat.portals._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from aeat.portals._codes import Portal
from aeat.portals._entries._common import build_entry
from aeat.portals._metadata import PortalMetadata

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M111_RETENCIONES_TRABAJO,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GH01.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.CLAVE_MOVIL,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_111,
    label={
        "es": "Modelo 111 — Retenciones trabajo y actividades",
        "en": "Modelo 111 — Withholdings on labour and activities",
        "hu": "111-es űrlap — Munkabérek és tevékenységek forrásadója",
    },
    purpose_es=(
        "Autoliquidación periódica de retenciones e ingresos a cuenta "
        "sobre rendimientos del trabajo y actividades económicas."
    ),
)
