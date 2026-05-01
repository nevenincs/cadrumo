"""Portal: Modelo 180 — resumen anual retenciones arrendamientos."""

from __future__ import annotations

from ...modelos import ModeloCode
from .._categories import AuthMethod, PortalCategory, Subdomain, UrlStability
from .._codes import Portal
from .._metadata import PortalMetadata
from ._common import build_entry

ENTRY: PortalMetadata = build_entry(
    portal=Portal.PORTAL_M180_RESUMEN_ARRENDAMIENTOS,
    url="https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI00.shtml",
    subdomain=Subdomain.SEDE,
    category=PortalCategory.FILING,
    auth_methods=(
        AuthMethod.CERTIFICATE,
        AuthMethod.CLAVE_PIN,
        AuthMethod.CLAVE_PERMANENTE,
        AuthMethod.DNIE,
    ),
    url_stability=UrlStability.STABLE_PROTOCOL_GRADE,
    related_modelo=ModeloCode.MODELO_180,
    label={
        "es": "Modelo 180 — Resumen anual retenciones arrendamientos",
        "en": "Modelo 180 — Annual summary of rental withholdings",
        "hu": "180-as űrlap — Éves bérleti forrásadó összefoglaló",
    },
    purpose_es=(
        "Resumen anual de retenciones e ingresos a cuenta sobre "
        "arrendamientos de inmuebles urbanos (complementa al Modelo 115)."
    ),
)
